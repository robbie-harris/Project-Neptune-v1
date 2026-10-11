#!/usr/bin/env python3
"""Prepare pending MCP requests from confirmed corrected-label outcomes."""
import argparse
import json
from pathlib import Path


def pending(requests, outcomes):
    ids = [r['image_id'] for r in requests]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate image IDs in annotation request file')
    names = {r['image_id']: r['annotation_name'] for r in requests}
    done = set()
    failures = set()
    for row in outcomes:
        image_id = row['image_id']
        if image_id not in names or row['annotation_name'] != names[image_id]:
            raise ValueError('Checkpoint does not match this verified annotation request set')
        if row.get('success') is True:
            done.add(image_id)
        else:
            failures.add(image_id)
    todo = [r for r in requests if r['image_id'] not in done]
    return todo, {'total': len(requests), 'confirmed_successes': len(done), 'remaining': len(todo), 'unresolved_failures': len(failures-done)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--requests', type=Path, required=True)
    parser.add_argument('--checkpoints', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    requests = [json.loads(line) for line in args.requests.read_text().splitlines() if line.strip()]
    outcomes = [row for path in sorted(args.checkpoints.glob('*.json')) for row in json.loads(path.read_text())]
    todo, report = pending(requests, outcomes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(r)+'\n' for r in todo))
    args.output.with_suffix('.report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
