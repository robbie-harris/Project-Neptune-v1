#!/usr/bin/env python3
"""Check managed deployment accuracy and measured runtime gates; never activate."""
import argparse
import json
import re
import statistics
from pathlib import Path


def check(validation, test, live, baseline):
    failures = []
    model = test.get('model_id')
    if not model or validation.get('model_id') != model or live.get('detector', {}).get('model_id') != model:
        failures.append('Model identity differs between validation, test and live run')
    if (validation.get('split') != 'val' or validation.get('confidence_selection_split') != 'val'
            or test.get('split') != 'test' or validation.get('images') != 900 or test.get('images') != 900
            or validation.get('diagnostic_only') or test.get('diagnostic_only')):
        failures.append('Full validation and untouched test reports are required')
    manifest = validation.get('dataset_validation', {}).get('manifest_sha256')
    if not manifest or manifest != test.get('dataset_validation', {}).get('manifest_sha256'):
        failures.append('Frozen dataset identity differs')
    confidence = test.get('confidence')
    if confidence != validation.get('confidence') or confidence != live.get('detector', {}).get('confidence_threshold'):
        failures.append('Confidence differs from validation selection')
    if not test.get('passed') or test.get('recall_iou_0_5', 0) < .95 or test.get('negative_frame_fpr', 1) > .05:
        failures.append('Overall accuracy targets failed')
    if any(test.get('slices', {}).get(f'angle_bin:{i}', {}).get('recall', 0) < .9 for i in range(6)):
        failures.append('Orientation bin recall failed')
    if not live.get('passed') or live.get('detector', {}).get('state') != 'ready':
        failures.append('Live ROS checks failed')
    for name, actual, reference, ratio, higher in [
        ('Annotated FPS', live.get('wall_rates_hz', {}).get('annotated', 0), baseline.get('wall_rates_hz', {}).get('annotated', 0), .9, True),
        ('GUI FPS', live.get('gui_fresh_fps_median') or 0, baseline.get('gui_fresh_fps_median') or 0, .9, True),
        ('p95 inference latency', live.get('sampled_inference_latency_ms', {}).get('p95'), baseline.get('sampled_inference_latency_ms', {}).get('p95'), 1.1, False),
    ]:
        if not reference or actual is None or (actual < reference * ratio if higher else actual > reference * ratio):
            failures.append(f'{name} failed: measured {actual}, limit {reference * ratio if reference else None}')
    if not live.get('gui_fresh_fps_samples'):
        failures.append('Fresh GUI measurements missing')
    return failures


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['validation', 'test', 'live', 'baseline', 'gui_log', 'output']:
        p.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    p.add_argument('--gui-start-line', type=int, required=True)
    args = p.parse_args()
    load = lambda path: json.loads(path.read_text())
    live = load(args.live)
    lines = args.gui_log.read_text().splitlines()[args.gui_start_line - 1:]
    samples = [float(x) for x in re.findall(r'GUI feed FPS: ([0-9.]+)', '\n'.join(lines))]
    live.update(gui_fresh_fps_samples=samples, gui_fresh_fps_median=statistics.median(samples) if samples else None,
                gui_diagnostics_log=str(args.gui_log), gui_log_start_line=args.gui_start_line)
    args.live.write_text(json.dumps(live, indent=2))
    failures = check(load(args.validation), load(args.test), live, load(args.baseline))
    result = dict(passed=not failures, failures=failures, activation_complete=False,
                  model_id=live.get('detector', {}).get('model_id'), live=str(args.live))
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()
