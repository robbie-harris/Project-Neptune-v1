"""Pure synthetic tests: no ROS graph, simulator, mission or command publisher."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'diagnose_demo_freeze', Path(__file__).with_name('diagnose_demo_freeze.py'))
diag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diag)


def snapshots(now, receipts=None):
    receipts = receipts or {}
    return {key: dict(count=1, receipt_monotonic=receipts.get(key, 0.0),
                      age_s=now-receipts.get(key, 0.0), source_stamp=100.0,
                      source_stamp_delta=-0.42, data=None)
            for key in diag.TOPICS}


class GapTests(unittest.TestCase):
    def test_transient_gap_and_recovery(self):
        detector = diag.GapDetector()
        receipts = {key: .6 for key in diag.TOPICS if key != 'pressure'}
        events = detector.update(.6, snapshots(.6, receipts))
        self.assertFalse(any(e['type'] == 'GLOBAL_GAP' for e in events))
        receipts['pressure'] = .8
        events = detector.update(.8, snapshots(.8, receipts))
        transient = [e for e in events if e['type'] == 'TRANSIENT_GAP']
        self.assertEqual(len(transient), 1)
        self.assertEqual(transient[0]['scope'], 'pressure')
        self.assertAlmostEqual(transient[0]['gap_duration_s'], .8)
        self.assertTrue(any(e['type'] == 'RECOVERY' for e in events))

    def test_global_gap_requires_all_four_raw_streams(self):
        detector = diag.GapDetector()
        events = detector.update(.6, snapshots(.6, {'sim_odometry': .6}))
        self.assertFalse(any(e['type'] == 'GLOBAL_GAP' for e in events))
        events = detector.update(1.1, snapshots(1.1, {'sim_odometry': .6}), {'state': 'TRANSIT'})
        gaps = [e for e in events if e['type'] == 'GLOBAL_GAP']
        self.assertEqual(len(gaps), 1)
        self.assertAlmostEqual(gaps[0]['duration_s'], .5)
        self.assertEqual(detector.global_gaps[0]['mission']['state'], 'TRANSIT')

    def test_global_recovery_and_multiple_episodes(self):
        detector = diag.GapDetector()
        detector.update(.5, snapshots(.5))
        receipts = {key: 1.2 for key in diag.TOPICS}
        events = detector.update(1.3, snapshots(1.3, receipts))
        recovery = [e for e in events if e['type'] == 'RECOVERY' and e['scope'] == 'global']
        self.assertEqual(len(recovery), 1)
        self.assertAlmostEqual(recovery[0]['gap_duration_s'], 1.2)
        self.assertTrue(detector.global_gaps[0]['recovered'])
        self.assertEqual(detector.status(1.3), 'HEALTHY')
        detector.update(1.8, snapshots(1.8, receipts))
        self.assertEqual(len(detector.global_gaps), 2)

    def test_sustained_freeze_emitted_once_and_observation_continues(self):
        detector = diag.GapDetector()
        detector.update(.5, snapshots(.5))
        self.assertFalse(any(e['type'] == 'SUSTAINED_FREEZE'
                             for e in detector.update(4.99, snapshots(4.99))))
        events = detector.update(5.0, snapshots(5.0))
        self.assertEqual(sum(e['type'] == 'SUSTAINED_FREEZE' for e in events), 1)
        self.assertFalse(any(e['type'] == 'SUSTAINED_FREEZE'
                             for e in detector.update(12, snapshots(12))))
        detector.update(13, snapshots(13, {key: 13 for key in diag.TOPICS}))
        self.assertTrue(detector.global_gaps[0]['recovered'])
        self.assertAlmostEqual(detector.global_gaps[0]['duration_s'], 13)

    def test_never_received_streams_are_waiting_not_freeze(self):
        detector = diag.GapDetector()
        data = snapshots(100)
        for item in data.values():
            item.update(count=0, receipt_monotonic=None, age_s=None)
        self.assertEqual(detector.update(100, data), [])
        self.assertEqual(detector.global_gaps, [])

    def test_camera_only_and_source_regression_does_not_trigger_gap(self):
        detector = diag.GapDetector()
        fresh = {key: .6 for key in diag.TOPICS}
        self.assertEqual(detector.update(.6, snapshots(.6, fresh)), [])
        fresh['camera'] = 0
        events = detector.update(.6, snapshots(.6, fresh))
        self.assertTrue(any(e['type'] == 'CAMERA_ONLY_GAP' for e in events))
        self.assertFalse(any(e['type'] == 'GLOBAL_GAP' for e in events))
        fresh['camera'] = .8
        self.assertTrue(any(e['type'] == 'RECOVERY'
                            for e in detector.update(.8, snapshots(.8, fresh))))

    def test_gap_that_recovers_between_dashboard_ticks(self):
        # The callback runs detection before and after reception, even if no
        # dashboard tick observes the stale state.
        detector = diag.GapDetector()
        detector.update(.6, snapshots(.6))
        events = detector.update(.6, snapshots(.6, {key: .6 for key in diag.TOPICS}))
        self.assertTrue(any(e['type'] == 'TRANSIENT_GAP' for e in events))
        self.assertTrue(detector.global_gaps[0]['recovered'])

    def test_metadata_is_bounded_and_source_delta_preserved(self):
        stream = diag.Stream()
        stream.receive(0, 10)
        stream.receive(.2, 9.58)
        snap = stream.snapshot(.3)
        self.assertAlmostEqual(snap['age_s'], .1)
        self.assertAlmostEqual(snap['source_stamp_delta'], -.42)
        self.assertEqual(snap['source_regressions'], 1)
        self.assertAlmostEqual(snap['last_source_regression']['delta'], -.42)
        for index in range(10000):
            stream.receive(index+.3, index)
        self.assertLessEqual(len(stream.recent), 4096)
        self.assertEqual(stream.count, 10002)

    def test_no_process_waits_without_error(self):
        with tempfile.TemporaryDirectory() as root:
            result = diag.ProcMonitor(92, root).sample(1)
            self.assertIsNone(result['pid'])
            self.assertIsNone(result['alive'])

    def test_proc_exit_and_unreadable_fields_are_best_effort(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = diag.ProcMonitor(92, root)
            monitor.pid, monitor.birth = 1, 1
            self.assertFalse(monitor.sample(1)['alive'])
            Path(root, '1').mkdir()
            self.assertIsNone(monitor.sample(2)['alive'])


    def test_gap_resource_summary_and_camera_order(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            sample = dict(monotonic=1.0, stonefish=dict(cpu_percent=80.0, rss_bytes=1024,
                          thread_count=2, fd_count=3, state='S', wchan='futex_wait'),
                          gpu=dict(available=True, query_age_s=.1, devices=[dict(index='0',
                          utilization_percent=20, memory_used_mib=100, memory_total_mib=1000)]))
            (output/'samples.jsonl').write_text(json.dumps(sample)+'\n')
            result = diag.gap_resources(output, dict(start_monotonic=.5, recovered_monotonic=2))
            self.assertEqual(result['metrics']['cpu_percent']['mean'], 80)
            self.assertEqual(result['metrics']['gpu_0_memory_used_mib']['max'], 100)
            self.assertEqual(result['wchan_counts'], {'futex_wait': 1})
        topics = snapshots(1, {'camera': 1})
        self.assertIn('fresh', diag.camera_order(topics, .5))

    def test_empty_summary_outputs(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            diag.write_summary(output, diag.GapDetector(), [], 'Ctrl-C', .5)
            self.assertEqual(json.loads((output/'events.json').read_text()), [])
            self.assertIn('F) insufficient evidence', (output/'summary.txt').read_text())


if __name__ == '__main__':
    unittest.main()
