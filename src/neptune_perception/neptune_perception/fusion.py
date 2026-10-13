"""Exact-source pipe association. No orientation or control estimation."""

from collections import OrderedDict
from copy import deepcopy
import math

from .core import MODEL_ID, A1_MODEL_ID

MODELS = {'inspection': MODEL_ID, 'orientation_a': A1_MODEL_ID}


def source_key(status):
    header = status['source_header']
    stamp = header['stamp']
    if (type(stamp['sec']) is not int or type(stamp['nanosec']) is not int
            or stamp['sec'] < 0 or not 0 <= stamp['nanosec'] < 1000000000
            or not isinstance(header['frame_id'], str) or not header['frame_id']):
        raise ValueError('Invalid source header')
    return stamp['sec'], stamp['nanosec']


def iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(
        0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1])-intersection
    return intersection/union if union > 0 else 0.0


def associate(inspection, orientation, threshold=0.30):
    """Descending-IoU greedy one-to-one matching, stable indices for equal edges."""
    edges = sorted(((-iou(a['xyxy'], b['xyxy']), i, j)
                    for i, a in enumerate(inspection) for j, b in enumerate(orientation)
                    if iou(a['xyxy'], b['xyxy']) >= threshold))
    used_i, used_a, records = set(), set(), []
    for negative, i, j in edges:
        if i not in used_i and j not in used_a:
            used_i.add(i)
            used_a.add(j)
            records.append(record(inspection[i], orientation[j], -negative))
    records.extend(record(a, None) for i, a in enumerate(inspection) if i not in used_i)
    records.extend(record(None, b) for j, b in enumerate(orientation) if j not in used_a)
    return records


def record(inspection, orientation, overlap=None):
    return dict(state='CONSENSUS' if overlap is not None else
                'INSPECTION_ONLY' if inspection is not None else 'ORIENTATION_A_ONLY',
                inspection=deepcopy(inspection), orientation_a=deepcopy(orientation),
                inspection_confidence=None if inspection is None else inspection['confidence'],
                orientation_a_confidence=None if orientation is None else orientation['confidence'],
                inspection_bbox=None if inspection is None else inspection['xyxy'],
                orientation_a_bbox=None if orientation is None else orientation['xyxy'],
                iou=overlap, model_provenance=[MODELS[k] for k, value in
                    [('inspection', inspection), ('orientation_a', orientation)] if value is not None],
                orientation_valid=False)


def fuse(inspection, orientation, threshold=0.30):
    if inspection is not None and orientation is not None:
        if (source_key(inspection) != source_key(orientation)
                or inspection['source_header'] != orientation['source_header']
                or (inspection['image_width'], inspection['image_height']) !=
                   (orientation['image_width'], orientation['image_height'])):
            raise ValueError('Different source frames')
    source = inspection if inspection is not None else orientation
    pipes_i = [] if inspection is None else [o for o in inspection['observations'] if o['class_name'] == 'pipe']
    pipes_a = [] if orientation is None else orientation['observations']
    records = associate(pipes_i, pipes_a, threshold)
    matched = [r for r in records if r['state'] == 'CONSENSUS']
    selected = None
    state = 'NO_PIPE'
    if matched:
        best = matched[0]
        # No arbitrary target choice when distinct pairs tie for best overlap.
        if len(matched) > 1 and math.isclose(best['iou'], matched[1]['iou'], abs_tol=1e-9):
            state = 'AMBIGUOUS'
        else:
            selected, state = best, 'CONSENSUS'
    elif len(records) == 1:
        selected, state = records[0], records[0]['state']
    elif records:
        state = 'AMBIGUOUS'
    target = None
    if selected:
        geometry_source = 'inspection' if selected['inspection'] is not None else 'orientation_a'
        observation = selected[geometry_source]
        x1, y1, x2, y2 = observation['xyxy']
        u, v = (x1+x2)/2, (y1+y2)/2
        target = dict(**deepcopy(selected), bbox_source=geometry_source,
                      selected_source=MODELS[geometry_source], bbox=observation['xyxy'],
                      center=[u, v], horizontal_error=(u-source['image_width']/2)/(source['image_width']/2),
                      vertical_error=(v-source['image_height']/2)/(source['image_height']/2),
                      valid=True)
    passthrough = [] if inspection is None else [dict(deepcopy(o), model_id=MODEL_ID)
        for o in inspection['observations'] if o['class_name'] in ('valve', 'flange')]
    return dict(source_header=deepcopy(source['source_header']), image_width=source['image_width'],
                image_height=source['image_height'], state=state, valid=target is not None,
                orientation_valid=False, orientation_rad=None, selected_target=target,
                pipes=records, semantic_detections=passthrough,
                source_matched=inspection is not None and orientation is not None)


class MatchingCache:
    """Bounded pending sources; finalized watermark prevents late retroactive output."""

    def __init__(self, threshold=0.30, window=0.20, freshness=0.5, capacity=8):
        if not math.isfinite(threshold) or not 0 < threshold <= 1:
            raise ValueError('IoU threshold must be in (0, 1]')
        if not 0 < window < freshness or not math.isfinite(freshness) or capacity < 1:
            raise ValueError('Invalid cache bounds')
        self.threshold, self.window, self.freshness, self.capacity = threshold, window, freshness, capacity
        self.pending = OrderedDict()
        self.closed = (-1, -1)
        self.last_model_key = {k: (-1, -1) for k in MODELS}
        self.model_states = {k: 'MODEL_UNAVAILABLE' for k in MODELS}
        self.model_receipts = {k: None for k in MODELS}
        self.rejected = self.evicted = self.mismatched = 0

    def fresh(self, status, now, ros_now):
        stamp = source_key(status)
        age = ros_now-(stamp[0]+stamp[1]/1e9)
        return (status.get('observation_valid') is True
                and status.get('state') in ('READY', 'NO_DETECTION')
                and 0 <= age <= self.freshness
                and 0 <= status['processing_latency_s'] <= self.freshness
                and 0 <= status['result_receipt_age_s']+now-status['_received'] <= self.freshness
                and 0 <= now-status['_received'] <= self.freshness)

    def add(self, model, status, now, ros_now):
        if status.get('model_id') != MODELS[model]:
            raise ValueError('Unexpected model provenance')
        self.model_states[model] = status.get('state', 'MODEL_UNAVAILABLE')
        self.model_receipts[model] = now
        if status.get('source_header') is None:
            return []
        key = source_key(status)
        if key <= self.closed or key <= self.last_model_key[model]:
            return []
        status = deepcopy(status)
        status['_received'] = now
        if not self.fresh(status, now, ros_now):
            self.rejected += 1
            return []
        self.validate(model, status)
        self.last_model_key[model] = key
        outputs = self.flush(now, ros_now)
        if key <= self.closed:
            return outputs
        if key not in self.pending:
            if len(self.pending) >= self.capacity:
                oldest = min(self.pending)
                outputs.append(self.finish(oldest, now, ros_now))
                self.evicted += 1
            self.pending[key] = dict(first=now, results={})
        entry = self.pending[key]
        others = list(entry['results'].values())
        if others and (others[0]['source_header'] != status['source_header'] or
                      (others[0]['image_width'], others[0]['image_height']) !=
                      (status['image_width'], status['image_height'])):
            self.mismatched += 1
            return outputs
        entry['results'][model] = status
        if len(entry['results']) == 2:
            outputs.append(self.finish(key, now, ros_now))
        return outputs

    def validate(self, model, status):
        width, height = status['image_width'], status['image_height']
        if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
            raise ValueError('Invalid dimensions')
        observations = status['observations']
        if not isinstance(observations, list) or len(observations) > 300:
            raise ValueError('Invalid observations')
        for o in observations:
            box = o['xyxy']
            if (o['class_name'] not in ({'pipe', 'valve', 'flange'} if model == 'inspection' else {'pipe'})
                    or len(box) != 4 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in box)
                    or not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height
                    or not math.isfinite(o['confidence']) or not 0 <= o['confidence'] <= 1
                    or o.get('orientation_valid') is not False):
                raise ValueError('Invalid observation')

    def finish(self, key, now, ros_now):
        entry = self.pending.pop(key)
        self.closed = max(self.closed, key)
        for older in list(self.pending):
            if older <= self.closed:
                del self.pending[older]
                self.rejected += 1
        results = {k: v for k, v in entry['results'].items() if self.fresh(v, now, ros_now)}
        if not results:
            source = next(iter(entry['results'].values()))
            output = fuse(dict(source, observations=[]), None, self.threshold)
            output.update(state='STALE', valid=False)
        else:
            output = fuse(results.get('inspection'), results.get('orientation_a'), self.threshold)
        output['observation_age_s'] = ros_now-(key[0]+key[1]/1e9)
        output['receipt_age_s'] = max(now-v['_received']+v['result_receipt_age_s'] for v in entry['results'].values())
        output['model_states'] = dict(self.model_states)
        return output

    def flush(self, now, ros_now):
        return [self.finish(key, now, ros_now) for key in sorted(self.pending)
                if now-self.pending[key]['first'] >= self.window or key <= self.closed]
