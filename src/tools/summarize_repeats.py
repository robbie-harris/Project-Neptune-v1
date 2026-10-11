#!/usr/bin/env python3
"""Compare three repeat evaluations on one frozen test set."""
import argparse
import json
from pathlib import Path
import numpy as np


def summarize(tests, validations):
    if len(tests) != 3 or len(validations) != 3:
        raise ValueError('Exactly three test/validation report pairs are required')
    manifests = set()
    identities = set()
    backends = set()
    training_ids = set()
    for test, validation in zip(tests, validations):
        if test.get('split') != 'test' or test.get('diagnostic_only') or test.get('images') != 900:
            raise ValueError('Each repeat requires the complete 900-image test evaluation')
        if validation.get('split') != 'val' or validation.get('confidence_selection_split') != 'val' or validation.get('diagnostic_only') or validation.get('images') != 900:
            raise ValueError('Each threshold must be selected on full validation only')
        backend=test.get('backend','ultralytics'); backends.add(backend)
        identity_field='model_id' if backend=='roboflow' else 'weights_sha256'
        digest = test.get(identity_field)
        if backend != validation.get('backend','ultralytics') or not digest or digest != validation.get(identity_field) or test.get('confidence') != validation.get('confidence'):
            raise ValueError('Test weights/threshold do not match validation selection')
        identities.add(digest)
        training_id = test.get('training_id')
        if not training_id or training_id != validation.get('training_id'):
            raise ValueError('Each report pair must identify its actual cloud training job')
        training_ids.add(training_id)
        test_manifest = test.get('dataset_validation', {}).get('manifest_sha256')
        if not test_manifest or test_manifest != validation.get('dataset_validation', {}).get('manifest_sha256'):
            raise ValueError('Test and validation must use the same frozen manifest')
        manifests.add(test_manifest)
    if len(manifests) != 1:
        raise ValueError('Repeat runs must share the same untouched test distribution')
    if len(backends) != 1:
        raise ValueError('Repeat runs must use the same inference backend')
    if len(training_ids) != 3:
        raise ValueError('Three distinct cloud training jobs are required')
    def stats(values):
        values = np.asarray(values, dtype=float)
        return {'mean': float(values.mean()), 'sample_std': float(values.std(ddof=1)), 'min': float(values.min()), 'max': float(values.max())}
    metrics = {key: stats([r[key] for r in tests]) for key in ('recall_iou_0_5', 'negative_frame_fpr', 'latency_ms_mean', 'latency_ms_p95')}
    angles = {}
    for index in range(6):
        name = f'angle_bin:{index}'
        slices = [r.get('slices', {}).get(name) for r in tests]
        if any(s is None or not s.get('targets') for s in slices):
            raise ValueError('All six angle bins must be populated in every repeat')
        if len({s['targets'] for s in slices}) != 1:
            raise ValueError('Repeat angle-bin target counts differ')
        angles[name] = {'targets': slices[0]['targets'], **stats([s['recall'] for s in slices])}
    return {'repeat_count': 3, 'backend':next(iter(backends)), 'distinct_weight_hashes': len(identities) if backends=={'ultralytics'} else None, 'distinct_model_ids':len(identities) if backends=={'roboflow'} else None, 'manifest_sha256': next(iter(manifests)), 'metrics': metrics, 'angle_bins': angles,
            'all_accuracy_targets_passed': all(r.get('passed') for r in tests),
            'runs': [{'training_id': r['training_id'], 'weights_sha256': r.get('weights_sha256'), 'model_id':r.get('model_id'), 'confidence': r['confidence'], 'passed': r['passed']} for r in tests],
            'interpretation': 'Managed repeats; exact seeds are unavailable. Offline latency excludes the live simulator and GUI. For Roboflow, model IDs identify runs; underlying weight hashes and independence remain unverified.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', type=Path, nargs=3, required=True)
    parser.add_argument('--validation', type=Path, nargs=3, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize([json.loads(p.read_text()) for p in args.test], [json.loads(p.read_text()) for p in args.validation])
    result['test_reports'] = list(map(str, args.test)); result['validation_reports'] = list(map(str, args.validation))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
