#!/usr/bin/env python3
"""Check a frozen COCO export against the simulator's original manifest."""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import cv2
import numpy as np
from PIL import Image, JpegImagePlugin


def verify(data, archive):
    data, archive = Path(data), Path(archive)
    manifest = data / 'manifest.jsonl'
    records = {r['id']: r for r in map(json.loads, manifest.read_text().splitlines())}
    inspection=bool(records) and next(iter(records.values())).get('schema')=='inspection-v1'
    expected_classes={'pipe','valve','flange'} if inspection else {'pipe'}
    seen = set(); counts = Counter(); negatives = Counter()
    exact_bytes = 0; reencoded = 0; maximum_pixel_mae = 0.0; maximum_box_error = 0.0; reproduced_jpeg = 0
    with zipfile.ZipFile(archive) as z:
        files = [n for n in z.namelist() if n.endswith('_annotations.coco.json')]
        if len(files) != 3:
            raise ValueError('Expected exactly three COCO split files')
        for name in files:
            folder = Path(name).parent
            split = 'val' if folder.name == 'valid' else folder.name
            if split not in {'train', 'val', 'test'}:
                raise ValueError('Unexpected export split: ' + str(folder))
            coco = json.loads(z.read(name))
            categories={c['id']:c['name'].lower() for c in coco['categories'] if c['name'].lower() in expected_classes}
            if set(categories.values())!=expected_classes:
                raise ValueError('Export does not contain the required class schema')
            annotations = defaultdict(list)
            for a in coco['annotations']:
                if a['category_id'] not in categories:
                    raise ValueError('Unexpected annotated class')
                annotations[a['image_id']].append(a)
            for image in coco['images']:
                match = re.match(r'([oi]\d+_v\d+)', Path(image['file_name']).name)
                if not match or match[1] not in records or match[1] in seen:
                    raise ValueError('Unknown or repeated exported image: ' + image['file_name'])
                key = match[1]; r = records[key]; seen.add(key); counts[split] += 1
                if split != r['split'] or (image['width'], image['height']) != (r['width'], r['height']):
                    raise ValueError('Split or dimensions differ: ' + key)
                boxes = annotations.pop(image['id'], [])
                expected=r['boxes'] if inspection else ([{'class':'pipe','bbox':r['bbox']}] if r['bbox'] is not None else [])
                if len(boxes)!=len(expected): raise ValueError('Annotation count differs: '+key)
                available=list(expected)
                for box in boxes:
                    candidates=[b for b in available if b['class']==categories[box['category_id']]]
                    if not candidates: raise ValueError('Class differs: '+key)
                    x,y,w,h=box['bbox']; xyxy=(x,y,x+w,y+h)
                    match=min(candidates,key=lambda b:max(abs(a-c) for a,c in zip(xyxy,b['bbox'])))
                    error=max(abs(a-c) for a,c in zip(xyxy,match['bbox']))
                    maximum_box_error=max(maximum_box_error,error)
                    if error>1.01: raise ValueError('Box differs by more than one pixel: '+key)
                    available.remove(match)
                if not boxes: negatives[split]+=1
                raw = z.read(str(folder / image['file_name']))
                source = (data / r['image']).read_bytes()
                if hashlib.sha256(source).hexdigest() != r['sha256']:
                    raise ValueError('Original source hash changed: ' + key)
                if hashlib.sha256(raw).hexdigest() == r['sha256']:
                    exact_bytes += 1
                else:
                    exported = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                    original = cv2.imdecode(np.frombuffer(source, np.uint8), cv2.IMREAD_COLOR)
                    if exported is None or original is None or exported.shape != original.shape:
                        raise ValueError('Export pixels missing or resized: ' + key)
                    mae = float(np.abs(exported.astype(np.float32)-original).mean())
                    maximum_pixel_mae = max(maximum_pixel_mae, mae)
                    # Reproduce JPEG with the export's own quantization/subsampling.
                    # Exact decoded equality proves compression alone explains any
                    # difference, including textured frames with larger MAE.
                    jpeg_exact = False
                    encoded = Image.open(io.BytesIO(raw))
                    if encoded.format == 'JPEG':
                        buffer = io.BytesIO()
                        Image.fromarray(cv2.cvtColor(original, cv2.COLOR_BGR2RGB)).save(
                            buffer, format='JPEG', qtables=encoded.quantization,
                            subsampling=JpegImagePlugin.get_sampling(encoded))
                        reproduced = cv2.imdecode(np.frombuffer(buffer.getvalue(), np.uint8), cv2.IMREAD_COLOR)
                        jpeg_exact = np.array_equal(reproduced, exported)
                        reproduced_jpeg += int(jpeg_exact)
                    if not jpeg_exact and not np.array_equal(exported, original):
                        raise ValueError('Export pixels cannot be explained by exact lossless/JPEG reencoding: ' + key)
                    reencoded += 1
            if annotations:
                raise ValueError('Annotations reference absent images')
    if seen != set(records):
        raise ValueError(f'Incomplete export: {len(seen)}/{len(records)} images')
    return {'passed': True, 'images': len(seen), 'split_counts': dict(counts),
            'negative_counts': dict(negatives), 'exact_source_hash_matches': exact_bytes,
            'reencoded_images': reencoded, 'maximum_reencoding_pixel_mae': maximum_pixel_mae,
            'exactly_reproduced_jpeg_images': reproduced_jpeg,
            'encoding_verification': 'Exact decoded original pixels, or exact reproduced JPEG using exported quantization/subsampling.',
            'box_coordinate_tolerance_pixels': 1.01,
            'maximum_box_coordinate_error_pixels': maximum_box_error,
            'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'export_sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--data', type=Path, required=True)
    p.add_argument('--archive', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); report = verify(args.data, args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
