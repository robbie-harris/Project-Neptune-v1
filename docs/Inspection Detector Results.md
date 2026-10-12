---
tags: [neptune, perception, experiments]
date: 2026-10-11
---
# Inspection detector results

See [[Inspection Objects and Optics]], [[Progress]], [[Architecture]], and [[MarinaPipe and Real Deployment]].

## Model and data

One managed YOLO11n job finished: `cf8d962d68e32878e60b`, model `projects-zwfft/neptune-inspection-objects-2-yolo11n-t1`, dataset version 2. Requested epochs: 100; inspected input template: 640. Actual completed epochs, seed, batch and online augmentation remain unreported. Cloud metrics: mAP@50 80.69%, mAP@50:95 67.91%, precision 94.7%, recall 74.1%. These provider metrics are distinct from the local eligible-target acceptance results.

The sealed simulator-only dataset contains 6,530 frames in 653 whole viewpoint groups, split 4,570 training / 980 validation / 980 test. Original pipe regression images remain separate and untouched. All Roboflow-exported labels, splits and image re-encoding were verified before training. Data remain public CC BY 4.0; no real underwater data were uploaded or used in this run.

## Measured validation and test

Confidence **0.05** was selected on validation alone, maximizing minimum class recall while requiring false-positive frame rate ≤5%. It was frozen before test evaluation. Matching uses class-correct IoU ≥0.5, without tracking, and the primary recall gate applies to eligible targets in clear/moderate water.

| Split | Pipe recall | Valve recall | Flange recall | Target-absent false-positive frames |
|---|---:|---:|---:|---:|
| Validation, 980 frames | 504/518 = 97.30% | 488/502 = 97.21% | 472/477 = 98.95% | 3/190 = 1.58% |
| Test, 980 frames | 536/540 = 99.26% | 490/512 = 95.70% | 469/469 = 100% | 5/180 = 2.78% |

**Primary test accuracy gate passed.** Turbid test diagnostics fail to provide reliable detection: pipe 48/260 = 18.46%, valve 43/240 = 17.92%, flange 29/222 = 13.06%. This result does not establish real-world readiness. Completely unlit diagnostics are excluded from ordinary negative training examples; see the optics verification note.

Local warm HTTP inference with the simulator stopped: test mean throughput 6.51 frames/s, p95 latency 181.83 ms. This includes PNG encoding, local transport and CPU inference, and excludes disk reading and initial model loading. Apple M5 Mac, 16 GB RAM; pinned ARM64 Roboflow server, CPU ONNX execution. These numbers are not live GUI FPS or the full-simulator runtime gate.

Reports: `outputs/inspection-evaluation/validation.json`, `test.json`, and their saved predictions contain class confusion, water, lighting, particles, roll and small-target breakdowns. Original pipe regression, full-simulator latency/FPS and promotion status are pending at this checkpoint. The existing startup detector remains available.

## Original pipe regression

At the frozen confidence 0.05, the new model achieved **633/675 = 93.78% recall** on the untouched 900-image original orientation test, with **0/225 false-positive frames**. The prior orientation model achieved 675/675 = 100% on this same set. This is a **6.22 percentage-point recall regression** and fails the original ≥95% orientation acceptance check. Do not promote this candidate to normal startup even though its new-scene multiclass accuracy passed. Report: `outputs/inspection-evaluation/pipe-regression.json`. Future mixed old/new training must preserve the original held-out split and cannot tune thresholds against these test outcomes.

## Live rig comparison and experimental integration

Both detectors ran in the same inspection scene on the Apple M5 / 16 GB Mac, ARM64 Docker, software Mesa renderer, eight simulator CPU quota and four inference-server CPUs. Natural lighting and AUV lamps on, clear water, particles off, sensor errors off. Each complete ROS observation lasted 45 seconds with the native GUI open. Fresh GUI FPS uses the last eight steady diagnostic samples, each based on a rolling window of 30 newly received frames; it is not a repaint rate.

| Model | Unique latency samples | Warm live mean ms | Warm live p95 ms | Fresh GUI FPS median |
|---|---:|---:|---:|---:|
| Previous pipe model A1 | 110 | 207.99 | 266.07 | 2.62 |
| Three-class candidate | 108 | 187.69 | 231.08 | 2.43 |

Candidate p95/reference = **0.8685**, passing the ≤1.10 latency limit. Fresh GUI FPS/reference = **0.9275**. Both completed ideal-mode ROS checks passed: required sensor topics, simulation time, stereo capture timestamps, 12 cm baseline/transforms, and preserved detection/image input headers. Candidate status contained all three detected classes, and GUI logs confirmed forward annotated feed, overview and current sensor indicators.

An earlier incomplete baseline window was discarded. The first candidate window unexpectedly had the error toggle on; its injected camera timestamp offsets failed the ideal-stereo assertion. A lightweight diagnostic confirmed exact ideal-camera stereo timestamps; the matched candidate measurement was repeated with errors off. The prior toggle state was restored after testing. The noisy run is retained separately as `live-candidate-errors-enabled.json`, and is not the runtime comparison.

**Experimental integration complete; normal promotion blocked by pipe regression.** Reports: `outputs/inspection-evaluation/live-baseline.json`, `live-candidate.json`, `stereo-delivery.json`, and `acceptance.json`. The existing pipe-only startup and rollback are unchanged. No additional training was launched.

For a fresh start, use three terminals from the repository root:

```bash
bash src/tools/inference-server.sh
bash src/tools/run-inspection.sh --candidate
bash src/tools/gui.sh --diagnostics
```

If `neptune-inference` or `neptune-perception` is already running, reuse it instead of starting a duplicate. The explicit candidate uses confidence 0.05 and supports native lighting/water/particle and sensor-error toggles. Removing `--candidate` selects the prior pipe detector. The simulator and native GUI were left running with the experimental model after evaluation.
