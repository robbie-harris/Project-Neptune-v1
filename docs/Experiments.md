---
tags: [neptune, experiments]
---
# Experiments

## 2026-10-08 — initial runtime

- Host: Apple Silicon ARM64; Docker Linux ARM64; software Mesa rendering.
- Pinned ROS 2 Jazzy / Stonefish 1.6.0 image: build passed.
- Pure Python checks: 3 tests passed (safety commands, scene sensor/boundary contract, camera/label geometry).
- Scene parser: passed, including compound torpedo body and all instruments.
- Initial 10-second observation: IMU ≈100 Hz, pressure ≈20 Hz, DVL ≈10 Hz; camera ≈0.87 Hz and sonar ≈0.80 Hz in wall time.
- Model status: unavailable, correctly reporting missing trained pipe weights.
- Initial stereo check: failed (upstream round-robin vision rendering). Fix implemented; retest pending.
- Captured spawn preview: pipe visible in the forward camera; decorative particles then disabled for the clean-water scene.

## Dataset and model experiment

Planned: 1,000 frames, 100 viewpoint groups, group split 70/15/15, two negative variants per group, seed 42. Model: YOLO11n, pretrained initialization, one pipe class, 100 epochs, image size 640, batch 16, MPS when supported, no image-corruption augmentation.

Generated reports: `data/pipe/generation.json`, `manifest.jsonl`, `models/pipe/training.json`, `outputs/evaluation.json`, `outputs/runtime.json`. Do not report acceptance as passed until recall and negative-frame FPR are measured on held-out data.

See [[Progress]], [[Implementation Plan]], and [[Decision Log]].

## 2026-10-09 — corrected runtime and labels

Container tests: 6 passed. Host tests: 4 passed; 2 ROS launch modules skipped outside ROS. Command timeout and disconnect stops passed even with the simulation clock paused. Corrected full-rig runtime: 16 matching stereo timestamps in a 10-second window; approximately 1.62 Hz camera/sonar wall-time delivery, 100 Hz IMU, 20 Hz pressure, and 10 Hz DVL.

Host: Mac17,2, Apple M5 (10 CPU cores), 16 GB memory, ARM64, macOS 26.6.2. PyTorch 2.8.0 MPS is available outside the restricted execution sandbox.

Capture smoke: 10 genuine images, including 2 negative views. Geometry labels visually align with the visible pipe. Sample below is a ground-truth label review, not model output.

![[attachments/label-review.jpg]]

### Close-view label correction

The complete contact sheet exposed an issue with clipped views: computing a rectangle before clipping the projected silhouette included off-screen y extremes. Corrected with OpenCV convexHull/intersectConvexConvex, and added a regression test. 222 affected views were preserved under `outputs/label-repair-backup` and recaptured with the corrected geometry. The initial training run was intentionally stopped before completion; its metrics are not final validation results.

Final dataset validation: 1,000 images, 100 groups, 700/150/150 split; 800 pipe-positive and 200 pipe-absent frames. Capture uses true rendered camera pixels and settled simulator poses; labels come from known cylinder geometry, optical transforms, and the simulator CameraInfo matrix. Viewpoints span x −3.8…2.5 m, y ±1.6 m, and depths 0.7…2.3 m with deterministic within-group jitter and orientation variation. Seed 42. Capture time/skew tolerance: ≤0.05 simulation seconds to the nearest ground-truth sample. Negative views face away from the pipe.

### Self-contained runtime, before weights

`outputs/runtime-unavailable.json`: pass; 23 matching stereo captures, all rig transforms found. Camera/sonar wall delivery ≈2.27 Hz, IMU ≈100.9 Hz, pressure ≈20.3 Hz, DVL ≈10.1 Hz.

`outputs/controls.json`: pass. Four-second commands at 0.5 magnitude yielded +0.0128 m surge, +0.0656 rad yaw, and −0.0225 m NED z (upward heave). Disconnect stop: 0.0987 s. Commands stop thrust; inertia remains.

`outputs/gui-unavailable.log`: native Tk 8.6 decoded/rendered a 640×480 raw preview, displayed current sensor indicators, and displayed missing-model status.

### Requested GUI FPS improvement

No camera resolution, lighting, sensor rates, noise, or stereo timing changed. Bridge preview ceiling increased from 5 to 10 FPS; identical frames are no longer repeatedly encoded/transmitted. GUI event polling: 33 ms, command keepalive: 100 ms. Fast PNG encoding, no unnecessary resize, and a live feed-FPS indicator were added.

Measured while MPS training continued: 4 Mesa workers / 800×600 viewer ≈2.27 fresh camera FPS; 8 workers / 800×600 ≈3.35 FPS; 8 workers / 640×480 ≈3.46 FPS (about 52% above the baseline). Native GUI logs showed ≈2.4–3.1 FPS while training and ROS tests shared the Mac. All sensor cameras remain 640×480. Final model-on throughput will be reported separately.

ROS preview test: a 10 Hz test source forwards at least 8 FPS with no repeated stale frames. The 7 pytest groups pass, including that launch-test case and paused-clock stopping. Reports: `outputs/runtime-fps-threads8.json`, `outputs/runtime-fps-viewer640.json`, `outputs/gui-fps.log`, `outputs/tests-fps.log`.

Training optimizer selected by the pinned Ultralytics `auto` setting: AdamW, initial learning rate 0.002, momentum 0.9, weight decay 0.0005. The complete resolved training arguments are retained with the run.

## 2026-10-09 — full orientation baseline and clock recovery

All 6,000 rendered captures passed local validation: 600 groups, 4,200/900/900 splits, exactly 25% pipe-absent views per split, no duplicate images and no viewpoint leakage. All six projected-angle bins are populated. Frozen manifest SHA256: `1ca3375ab2314315e2a9f3dac08d1cbce30502a2f41d3c29d5decc41d89f74f9`. Quarantined clock/render-mismatched originals are excluded; verified replacements are included with user approval.

Unchanged old detector, confidence 0.25, complete 900-image test: 48/675 visible targets detected at IoU ≥0.5 (**7.111% recall**); one false-positive frame out of 225 negatives (**0.444% FPR**). Warm offline Mac MPS latency: mean 15.345 ms, p95 22.272 ms. Accuracy acceptance failed. Report: `outputs/orientation-baseline-full.json`. This does not measure live Docker inference latency.

After a clean full-rig restart, `outputs/runtime-baseline-clock.json` passed: real-time factor 1.0038, 54 shared stereo timestamps, approximately 3.03 annotated frames/s. Exact old weights SHA256: `21ef861ead9e4b8813613cc0b17798b2dae62da6cd53847ea761d3724aee6c96`. Live Docker CPU inference: mean 312.85 ms, p95 426.22 ms. Native GUI fresh FPS median: 3.3 over 123 logged samples, `outputs/gui-baseline-clock.log`. No screenshot was recorded in this measurement.

`outputs/controls-clock-fix.json` passed: four-second 0.5 commands produced +0.05074 m surge, +0.08260 rad yaw, and −0.03098 m NED z for upward heave. Disconnect zeroed commanded thrust in 0.0516 seconds; emergency zero commands were observed after each axis. Zero thrust does not remove inertia.

Host full suite: 21 passed, 2 ROS-only modules skipped on Mac. After adding fresh-GUI-FPS promotion checks, six targeted promotion/annotation tests passed. The three-repeat summary helper added two passing tests covering variability, reused checkpoints and changed test distributions. These checks do not establish new-model accuracy.

Local simulator-plus-COU dataset: 6,400 images, 4,600/900/900 splits, no duplicate images; all COU records are training-only. No COU image is uploaded and no COU-assisted cloud training has begun.

All 6,000 simulator images are uploaded to Roboflow. Final cloud annotation correction and full export verification remain pending; no new training job or candidate weights exist. Versions 1 and 2 are diagnostic only. Three managed YOLO11n repeats will request 100 epochs, with unavailable seed/batch/online-augmentation settings explicitly recorded. Use `src/tools/summarize_repeats.py --test RUN1_TEST RUN2_TEST RUN3_TEST --validation RUN1_VAL RUN2_VAL RUN3_VAL --output outputs/roboflow/repeat-summary.json` to report mean, sample standard deviation and range on the identical untouched test set.

### Rebuilt-image baseline

The final-source container build initially failed hash verification on an interrupted package download. Retrying with verification intact succeeded (image manifest `sha256:a060a2e7fc33ca0f5bd713010d61d66cd7a9df15e86a6963779c1e172f7aeaef`). Latest full-rig old-model baseline: 68 shared stereo stamps, real-time factor 1.0054, 3.811 annotated frames/s, CPU mean 237.527 ms / p95 260.306 ms. Native GUI median 3.59 fresh FPS over 97 samples. Use `outputs/runtime-baseline-final-image.json` for candidate comparisons under this rebuilt stack, rather than mixing the earlier image measurements. Resolved dependencies: `outputs/requirements-container-final.lock.txt`. Host full suite now passes 26 tests; two ROS-only modules remain skipped outside ROS.


## Completed cloud training — 2026-10-10

The full version 3 export passed all 6,000 image/split/box checks. All 6,000 JPEGs exactly reproduce source pixels under the exported JPEG encoder settings; maximum native PNG/JPEG MAE was 3.025717/255 and maximum box-coordinate difference 0.499771 pixels. Report: `outputs/roboflow/final-v3-export-validation.json`.

| Run | Training ID | Model | Duration | Cloud mAP50 / mAP50–95 |
|---|---|---|---|---|
| A1 | `028b0b7b7ae5ba04c874` | `projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1` | 55.23 min | 100% / 98.07% |
| A2 | `a60cdfb1e9e27f582a05` | `projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t2` | 57.72 min | 100% / 98.07% |
| A3 | `d6ad871de3e1ccbf613b` | `projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t3` | 56.30 min | 100% / 98.07% |

All three report 100% cloud recall and precision. These are provider metrics, not local acceptance results. Identical metrics do not establish independent seeded variability. Each requested 100 epochs with provider default initialization; actual seed, batch, completed epoch count and online augmentations remain unreported. No new training jobs are needed.

Offline evaluation is blocked by Roboflow weight access: the official SDK returned HTTP 403, `Not authorized to download this model in pt format.` No weights were downloaded. User authorization covered temporary keys for downloads; both the first attempt and its retry keys were revoked immediately, and both secret files were deleted. See `outputs/roboflow/training-completed.json` and `weights-download.json`. No automatic-review rejection occurred for these download attempts.

Next: obtain the three authorized `.pt` files (or have provider export access enabled), verify hashes/class mapping, select thresholds on 900 validation frames only, evaluate the untouched 900-image test and 35 COU positive diagnostic, then compare live full-rig latency and fresh GUI FPS. Active weights remain unchanged. COU-assisted cloud training remains deferred; no paper-derived variant implemented.

Latest live old-model baseline: `outputs/runtime-baseline-final-image.json`, 68 stereo matches, real-time factor 1.00543, 3.810752 annotated Hz, CPU mean 237.527 ms / p95 260.306 ms, native GUI median 3.59 fresh FPS over 97 samples. Use this baseline for candidate comparison, not the earlier clock-recovery run. Host checks: 28 passed, two ROS-only modules skipped on host; packaged ROS launch tests exited successfully.


## 2026-10-10 — first local managed-model validation

A1 full 900-image validation through local Inference: recall 100%, false-positive frames 1/225 (0.444%), threshold 0.05 selected on validation only. All angle bins met validation targets. Final two-core affinity configuration: mean local request latency 260.175 ms, p95 354.390 ms. The simulator was stopped for this offline run. No held-out or live acceptance claim yet. Report `outputs/roboflow/A1-val.json`. Earlier pre-affinity validation was preserved separately.


## 2026-10-10 — live managed deployment

See [[Orientation Deployment Results]] for completed three-run held-out results, live CPU experiments, manual-control verification, unmet performance gates, and the COU transfer diagnostic. Accuracy passed; runtime gates failed, so the original default remains active.

## Switchable errors and tank return — 2026-10-10

Ideal return reached 3.340 cm / 2.272° true spawn/heading errors. Noisy return after transport fixes reached 4.073 cm / 2.199°, with 97.088% normalized pose agreement. This is a single maneuver rather than a general navigation benchmark. Failed intermediate noisy attempts and moderate profile assumptions remain documented in [[Sensor Errors and Return to Spawn]]. Existing detector validation figures do not measure this new noisy image distribution.
