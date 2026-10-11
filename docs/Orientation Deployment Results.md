---
tags: [neptune, perception, experiments]
date: 2026-10-10
---
# Orientation deployment results

See [[Home]], [[Local Roboflow Inference]], [[Experiments]], [[Known Issues and Fixes]], and [[Progress]].

## Completed accuracy evaluation

All three managed YOLO11n runs completed validation and untouched 900-image simulator testing (675 visible pipe targets, 225 pipe-absent frames). Each achieved 675/675 hits at IoU ≥0.5: **100% recall**, **1/225 false-positive frames (0.444%)**, and **100% recall in every populated projected-angle bin**. Confidence 0.05 was selected separately using validation only. A1 won the predefined validation tie break before test evaluation. The previous frontal model achieved 48/675 hits (7.11%) on the same orientation test set.

Three-run sample standard deviation is zero for recall and FPR; seeds, batch size, online augmentation and actual completed epoch count remain unreported by managed training. Requested epochs: 100; image size: 640. Distinct managed model artifacts have cache checksums in `outputs/roboflow/deployment-artifacts.json`; these are managed ONNX identities, not exported PyTorch weights or proof of independent seeded training. Reports: `outputs/roboflow/repeats.json`, `candidate-selection.json`, and A1/A2/A3 validation/test reports.

## Completed live tests and unmet performance gates

Hardware: Apple M5 Mac, 16 GB host RAM; Docker ARM64 VM with ten CPUs and 8.719 GiB RAM. Same 640×480 camera pixels, tank, ideal sensor rig, simulation-clock pacing and pixel-only detection. ROS simulator CPU quota stays eight, Mesa LP_NUM_THREADS=8. Official local Inference 1.7.4 CPU/FP32 ONNX server; no MPS inference. Warm live prediction latency includes lossless PNG encoding, local HTTP transport, model execution and response decoding, before annotation drawing.

| Configuration | Annotated Hz | GUI fresh FPS median | Live p95 ms | Result |
|---|---:|---:|---:|---|
| Previous model baseline | 3.811 | 3.590 | 260.306 | Reference |
| A1, server two cores, shared simulation cores | 2.983 | Not bound to this window | 455.877 | Speed gates fail |
| A1, server four cores (0–3), simulator shared cores | 2.985 | 2.970 | 294.646 | Speed gates fail |
| A1, server three cores (0–2), simulator cores 3–9 | 2.928 | 2.900 | 321.488 | Speed gates fail |

Required: annotated Hz ≥3.430, GUI FPS ≥3.231, p95 latency ≤286.337 ms. **A1 is available as an explicit candidate; it is not promoted to the default.** `src/tools/check_managed_deployment.py` checks identity, full split size, frozen dataset, validation-selected confidence, orientation accuracy, ROS health and measured runtime gates. All CPU experiments passed live ROS checks: stereo timestamps, 12 cm baseline, camera sizes, sensor topics, transforms, simulation time and preserved image/detection headers. Four-core run: 111 unique latency samples, mean 223.474 ms, real-time factor near one. No inference FPS claim is derived from camera repaint counts.

Manual surge, yaw and heave passed on the live candidate. Emergency stop produced zero thrust; disconnect stopped commands within 0.051 s. The AUV can still coast. Report: `outputs/controls-roboflow-A1.json`. Detector recovered after local-server restarts; GUI showed error then ready. Automated missing-model and model-load-retry ROS contract tests passed. Host suite: 33 passed, three ROS-only modules skipped on macOS (ROS tests run in Docker separately).

## Real underwater diagnostic and deferred work

The selected simulator-only A1 model detected **1/35 COU pipe targets at IoU ≥0.5 (2.86% recall)**. This is a local, positive-only diagnostic from one G18 sequence, not an independent generalization benchmark; no negative-frame FPR can be measured. COU pixels were sent only to the local server with active learning and model monitoring disabled. No COU uploads or model B training occurred. This poor transfer result means the model is currently suitable for this simulator distribution, and does not establish real underwater readiness. COU-assisted training remains deferred under the user's licensing constraint.

No paper-derived architecture was implemented: corrected simulator coverage already passes all orientation accuracy targets. Runtime optimization and real-domain training are the next priorities. Internet-free startup from cache has not been verified; do not assume self-hosting guarantees offline availability.

## Run the candidate

If `neptune-perception` or `neptune-inference` is already running, use that session rather than starting a duplicate. For a fresh start, run each in its own terminal from the repository root:

```bash
bash src/tools/inference-server.sh
bash src/tools/run-roboflow.sh
bash src/tools/gui.sh --diagnostics
```

The candidate launcher explicitly chooses A1 at confidence 0.05. Server default is four CPU cores (0–3); overrides are NEPTUNE_INFERENCE_CPUS and NEPTUNE_INFERENCE_CPUSET. The normal `src/tools/run.sh` still uses the existing Ultralytics checkpoint. No active `.pt` file was replaced. Keep the deployment key only in ignored `.secrets/roboflow_api_key` (0600). Rotate the key exposed in chat; replace the file and restart the detector. Raw `.pt` migration still requires permitted downloads and backend revalidation; see [[Local Roboflow Inference]].
