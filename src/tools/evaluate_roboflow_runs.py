#!/usr/bin/env python3
"""Three authorized local evaluations; choose candidate on validation only."""
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
RUNS=[('A1','028b0b7b7ae5ba04c874'),('A2','a60cdfb1e9e27f582a05'),('A3','d6ad871de3e1ccbf613b')]


def evaluate(name, job, split, confidence=None):
    output=ROOT/'outputs/roboflow'/f'{name}-{split}.json'
    if output.exists():
        output.replace(output.with_suffix('.previous.json'))
    args=[sys.executable,str(ROOT/'src/tools/evaluate.py'),'--backend','roboflow',
          '--model-id',f'projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t{name[-1]}',
          '--training-id',job,'--split',split,'--output',str(output)]
    args+=['--select-confidence'] if split=='val' else ['--confidence',str(confidence)]
    print(f'Starting {name} {split}',flush=True)
    with output.with_suffix('.log').open('w') as log:
        result=subprocess.run(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode not in (0,1) or not output.exists():
        raise RuntimeError(f'{name} {split} failed; inspect its sanitized local log')
    report=json.loads(output.read_text())
    if report.get('training_id')!=job or report.get('images')!=900:
        raise RuntimeError('Evaluation does not identify the required job/full split')
    print(f"Finished {name} {split}: recall={report['recall_iou_0_5']:.4f}, FPR={report['negative_frame_fpr']:.4f}, p95={report['latency_ms_p95']:.1f}ms",flush=True)
    return report


if __name__=='__main__':
    deadline=time.monotonic()+120
    while True:
        try:
            with urlopen('http://127.0.0.1:9001/openapi.json',timeout=2): break
        except OSError:
            if time.monotonic()>deadline: raise RuntimeError('Local server startup timed out') from None
            time.sleep(1)
    validations=[evaluate(name,job,'val') for name,job in RUNS]
    selected=max(range(3),key=lambda i:(validations[i]['recall_iou_0_5'],-validations[i]['negative_frame_fpr'],-i))
    name,job=RUNS[selected]
    (ROOT/'outputs/roboflow/candidate-selection.json').write_text(json.dumps({
        'run':name,'training_id':job,'model_id':validations[selected]['model_id'],
        'confidence':validations[selected]['confidence'],
        'selection_split':'val','criterion':'Highest validation recall, then lowest validation FPR, then earliest run; no test metrics used.',
        'promotion_complete':False},indent=2))
    for (name,job),validation in zip(RUNS,validations): evaluate(name,job,'test',validation['confidence'])
    command=[sys.executable,str(ROOT/'src/tools/summarize_repeats.py'),'--validation']
    command += [str(ROOT/'outputs/roboflow'/f'{name}-val.json') for name,_ in RUNS]
    command += ['--test']+[str(ROOT/'outputs/roboflow'/f'{name}-test.json') for name,_ in RUNS]
    command += ['--output',str(ROOT/'outputs/roboflow/repeats.json')]
    subprocess.run(command,cwd=ROOT,check=True)
