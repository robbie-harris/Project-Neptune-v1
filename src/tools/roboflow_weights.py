#!/usr/bin/env python3
"""Download only the three authorized Neptune models through the official SDK.

Supply a temporary credential file; its secret is deleted on every outcome.
The caller must revoke the remote key immediately after this process exits.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import re
from pathlib import Path

RUNS = {'A1': '028b0b7b7ae5ba04c874', 'A2': 'a60cdfb1e9e27f582a05', 'A3': 'd6ad871de3e1ccbf613b'}


def download(credentials, output, report):
    key = json.loads(credentials.read_text())['api_key']
    records = []
    try:
        # SDK exceptions and logging can include credential-bearing URLs.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from roboflow.core.training import TrainedModel
            for i, (name, training_id) in enumerate(RUNS.items(), 1):
                model_id = f'projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t{i}'
                destination = output/name
                model = TrainedModel(key, 'projects-zwfft', 'neptune-pipe-orientation-a', model_id, model_type='yolo11n')
                weights = Path(model.download(format='pt', location=str(destination)))
                records.append({'run': name, 'training_id': training_id, 'model_id': model_id,
                                'weights': str(weights), 'bytes': weights.stat().st_size,
                                'sha256': hashlib.sha256(weights.read_bytes()).hexdigest()})
        return records
    except Exception as exc:
        message = str(exc).replace(key, '[REDACTED]')
        message = re.sub(r'https?://[^\s"<>]+', '[URL REDACTED]', message)
        report_error = {'type': type(exc).__name__, 'message': message[:1500]}
        records.append({'error': report_error})
        raise RuntimeError(f'Weights download failed: {report_error}; credentials deleted') from None
    finally:
        credentials.unlink(missing_ok=True)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({'downloads': records, 'complete': len(records) == 3 and all('weights' in r for r in records)}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--credentials', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(download(a.credentials, a.output, a.report), indent=2))
