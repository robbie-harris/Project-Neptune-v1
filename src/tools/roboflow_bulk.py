#!/usr/bin/env python3
"""Official SDK labeled-ZIP transfer; training remains through Roboflow MCP.

Preparation is offline. Upload requires an explicitly supplied credential and
approval for its use; no key is created by this script.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile
from roboflow_annotations import voc
from geometry import yolo_label
from validate_dataset import validate

PROJECT = 'neptune-pipe-orientation-a'
WORKSPACE = 'projects-zwfft'
MANIFEST = '1ca3375ab2314315e2a9f3dac08d1cbce30502a2f41d3c29d5decc41d89f74f9'


def prepare(data, archive):
    report = validate(data, expected=6000)
    if report['manifest_sha256'] != MANIFEST or report['duplicate_images']:
        raise ValueError('Only the verified, frozen simulator dataset may be transferred')
    records = [json.loads(line) for line in (data/'manifest.jsonl').read_text().splitlines()]
    if any(r.get('source') != 'stonefish' for r in records):
        raise ValueError('COU/public uploads are not authorized')
    archive.parent.mkdir(parents=True, exist_ok=True)
    staged = archive.with_suffix('.partial')
    with zipfile.ZipFile(staged, 'w', compression=zipfile.ZIP_STORED) as output:
        output.writestr('_classes.txt', 'pipe\n')
        output.writestr('data.yaml', 'train: train\nval: valid\ntest: test\nnc: 1\nnames: [pipe]\n')
        for r in records:
            image = data/r['image']; split = 'valid' if r['split'] == 'val' else r['split']
            output.write(image, f'{split}/{image.name}')
            positive = r['bbox'] is not None
            name = image.with_suffix('.txt' if positive else '.xml').name
            content = yolo_label(r['bbox'], r['width'], r['height']) if positive else voc(r)
            output.writestr(f'{split}/{name}', content)
    staged.replace(archive)
    report.update(archive=str(archive), archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  bytes=archive.stat().st_size, project=f'{WORKSPACE}/{PROJECT}',
                  annotation_format='Normalized YOLO positives, explicit empty VOC negatives',
                  overwrite_existing_annotations=True)
    archive.with_suffix('.report.json').write_text(json.dumps(report, indent=2))
    return report


def upload(archive, credentials, result_path):
    report = json.loads(archive.with_suffix('.report.json').read_text())
    if report.get('manifest_sha256') != MANIFEST or report.get('images') != 6000 or report.get('project') != f'{WORKSPACE}/{PROJECT}':
        raise ValueError('Transfer report does not identify the authorized dataset/project')
    if hashlib.sha256(archive.read_bytes()).hexdigest() != report['archive_sha256']:
        raise ValueError('Transfer archive changed after preparation')
    key = json.loads(credentials.read_text())['api_key'] if credentials else os.environ.get('ROBOFLOW_API_KEY')
    if not key:
        raise ValueError('Configure a local API key; do not paste it into chat or Git')
    # SDK logs/errors may include request URLs. Never emit raw SDK output.
    captured = io.StringIO()
    try:
        with redirect_stdout(captured), redirect_stderr(captured):
            from roboflow import Roboflow
            workspace = Roboflow(api_key=key).workspace(WORKSPACE)
            project = workspace.project(PROJECT)
            if project.id != f'{WORKSPACE}/{PROJECT}':
                raise ValueError('Resolved SDK project differs from the authorized project')
            result = workspace.upload_dataset(str(archive), PROJECT, batch_name='verified-orientation-label-refresh',
                                              annotation_overwrite=True, wait=False,
                                              project_license='CC BY 4.0', project_type='object-detection')
        sanitized = json.loads(json.dumps(result).replace(key, '[REDACTED]'))
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps({'manifest_sha256': MANIFEST, 'archive_sha256': report['archive_sha256'],
                                           'project': report['project'], 'sdk_result': sanitized}, indent=2))
        return {'result_file': str(result_path), 'task_id': sanitized.get('task_id'),
                'next_step': 'Monitor via MCP, reconcile Dataset membership, then verify a full COCO export before training.'}
    except Exception as exc:
        raise RuntimeError(str(exc).replace(key, '[REDACTED]')) from None
    finally:
        if credentials: credentials.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    preparation = sub.add_parser('prepare'); preparation.add_argument('--data', type=Path, required=True); preparation.add_argument('--archive', type=Path, required=True)
    transfer = sub.add_parser('upload'); transfer.add_argument('--archive', type=Path, required=True); transfer.add_argument('--credentials', type=Path); transfer.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.data, args.archive) if args.command == 'prepare' else upload(args.archive, args.credentials, args.result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
