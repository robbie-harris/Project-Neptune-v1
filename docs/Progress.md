---
tags: [neptune, progress]
---
# Progress

## 2026-10-08 — implementation in progress

Implemented: standalone repository structure, ROS packages, complete tank/rig scenario, YOLO node, adapted GUI/bridge, capture/label/train/evaluate tools, runtime verification, and this vault.

Verified so far: pinned ARM64 image builds; scenario parser accepts the tank, vehicle, sensors, lights, and propeller assets; pure geometry/safety/scenario tests pass. Initial runtime verified scalar sensor rates and explicit missing-model status.

Initial runtime also exposed a bridge attribute conflict and upstream round-robin stereo rendering. Corrections are implemented; revalidation is pending. Dataset generation, training, held-out metrics, and trained live detection remain pending until their runs complete.

See [[Experiments]] and [[Known Issues and Fixes]]. This note will be updated with actual outcomes, not inferred completion.

## 2026-10-09 — resumed validation

Verified: all 6 container tests pass, including ROS launch testing; ideal rig publishes all required sensor streams; reliable transport yields identical stereo capture timestamps. A 10-image smoke capture completed and its bounding boxes were visually checked.

Pause-safe timeout and disconnect behavior have also been verified by ROS launch tests.

The full dataset is being generated. Training and final held-out evaluation remain pending.

## 2026-10-09 — full dataset complete

Captured 1,000 actual Stonefish camera frames. Split: 700 training, 150 validation, 150 test images, with no viewpoint-group leakage. Negative frames: 140/30/30. Corrected close-view silhouette clipping, recaptured 222 affected views, and normalized floating-point viewport-edge roundoff. Dataset validation and visual contact-sheet review passed. Final manifest SHA-256: `1ac69e2b6da83bc215ac0854efe87effd2f1cb782c5a53c5c7575a48f93a1062`.

The final 100-epoch MPS training run is in progress (`outputs/training/pipe2`). Acceptance metrics remain pending.

### Packaged-image and control verification

The image started with only data/models/outputs mounted; source and sibling reference folders were not mounted. All required topics and body-to-sensor TFs passed runtime verification. Stereo: 23 shared timestamps over 10 seconds. IMU/physics approximately 100 Hz, pressure 20 Hz, DVL 10 Hz; vision/sonar approximately 2.27 Hz during this run.

Actual motion checks passed for surge, yaw, and upward heave. Emergency-stop zero commands were observed after every axis. Disconnect zeroed thrust in 0.099 s. The native Tk GUI diagnostics confirmed a rendered 640×480 raw preview, all sensor indicators current, and explicit unavailable status with no fabricated detections.

### GUI FPS improvement

Implemented the requested feed improvement and actual FPS indicator. Full-rig camera delivery improved from ≈2.27 to ≈3.46 FPS under concurrent training. Eight Mesa workers and a 640×480 simulator viewer are now defaults; sensor camera resolution remains unchanged. Camera-stream integration test passed at ≥8 FPS for a 10 Hz source, without repeating old frames. World-to-body TF configuration is also fixed and verified. The software renderer still does not sustain the nominal 10 Hz camera/sonar rate.


## Orientation milestone — 2026-10-09

On `Perception`, expanded orientation capture and Roboflow MCP annotation uploads are running. The simulator timing correction passed runtime checks; representative recaptures align with labels. Quarantined suspect captures remain excluded. The new detector is not trained, evaluated, or promoted yet. [[Orientation Resume Checkpoint]] records durable upload and capture checkpoints; [[Roboflow Training]] records managed-default training differences and the local-only COU constraint.

## 2026-10-10 — verified bulk label transfer

The user authorized a temporary Roboflow key inheriting the connector permissions because the workspace rejected restricted keys. The official SDK 1.7.1 transferred the 840,291,634-byte verified archive with annotation overwrite requested. Archive SHA256: `9e99a375d4ef937ea1cddb3043d341a9f7ffe09eea5136dfd11b30adeceadddd`. Verified entries: 6,000 PNGs, 4,500 normalized YOLO positive labels, 1,500 explicit empty VOC negatives, plus class/config files; splits 4,200/900/900. No COU data included.

SDK transfer exited successfully and returned task `5JYUHw1e9xoCu1pmpTce`. The temporary key was revoked immediately afterward and its local secret file deleted. Initial MCP status: `created`, progress unavailable. Server processing, Dataset membership and a complete label export still require verification; transfer success is not model or dataset acceptance. No training started.

MCP subsequently confirmed bulk processing completed: 6,000 duplicates matched existing images, 6,000 annotations processed, no upload failures or failed chunks. Project Dataset: 6,000 images / 4,500 pipe boxes; splits 4,200/900/900. Edge-touching positive boxes generated trimming warnings (error list capped at 100); full export box verification remains required. Frozen version 3 is ready, with no baked preprocessing/augmentation. The COCO export is downloading.

A second temporary diagnostic key was created, but automatic approval review rejected the SDK status command as outside the bulk-key authorization. That command did not run; the key was revoked and its local secret deleted. MCP status inspection resolved the server state without this SDK diagnostic. No further diagnostic credential is needed.


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


## Local Inference integration — 2026-10-10

User selected a local deployment path and supplied a key. Two configurable backends are implemented; credentials are ignored and mounted read-only. Official SDK/CLI 1.7.4 are isolated from ROS NumPy; ROS calls the official REST API with lossless pixels and original timestamps. New unit checks and ROS contract integration passed. Official ARM64 server image download is pending; candidate accuracy/runtime remain unmeasured. See [[Local Roboflow Inference]].


## 2026-10-10 — manual mobility fix

[[Manual Control and Mobility]] records the hold-to-drive GUI, confirmed command bars, counter-rotating horizontal propellers, increased rotor authority and passive hull stability. All six physical directions, sustained straight travel, emergency stop, disconnect and native Tk repeat/release checks passed. These are simulator parameters, not measured Neptune hardware.


## Switchable sensor errors and return

[[Sensor Errors and Return to Spawn]] documents the moderate error profile, ideal bypass, sensor-only pose comparison score, GUI controls and staged tank return. Actual outcomes are recorded separately from pending verification.

Final feature checks: 41 host tests passed (4 ROS-only skips); container adapter/bridge contracts and native Tk controls passed. Noisy sensor-only return completed with 4.073 cm true spawn error and 2.199° final heading error. Earlier safety-stop failures are retained, with worker/QoS fixes explained in [[Sensor Errors and Return to Spawn]].

The final packaged return guard also requires passive roll/pitch to settle. Repeated noisy physical return passed: 4.008 cm true arrival error, 2.149° final heading error. Simulator and GUI left running in ideal mode; checkbox enables the moderate errors. Report: outputs/operator-features-complete.json.


[[Tank Overview]] adds a fixed live tank camera below the forward GUI feed, 13 pt telemetry text and screen-aware scrolling. Actual camera/GUI checks are recorded in that note.

## 2026-10-10 — Inspection objects implementation

See [[Inspection Objects and Optics]] for planned gates versus actual implementation and native-render verification. Public Roboflow project created; multiclass training has not started.

## 2026-10-11 — Reduced multiclass dataset and cloud training

Approved reduction completed and sealed: **6,530 images / 653 viewpoint groups**, split **4,570 / 980 / 980**. All uploads and annotations confirmed; complete Roboflow COCO export passed pixel-encoding, split, class and box verification. One **YOLO11n / 100 requested epochs** MCP job is **running** on version 2, training ID `cf8d962d68e32878e60b`. See [[Inspection Objects and Optics]] for hashes and measured checks. Cloud training continues independently of the laptop. Model accuracy, runtime evaluation and normal-startup promotion remain pending.

The job subsequently finished. [[Inspection Detector Results]] records completed local validation/test, original pipe regression and matched full-rig runtime measurements. Clear/moderate test recall: **99.26% pipe / 95.70% valve / 100% flange**; absent-frame FPR **2.78%**. Live ideal-mode ROS checks and latency gate passed. The original pipe test regressed to **93.78%**, blocking normal promotion. Explicit `run-inspection.sh --candidate` enables the integrated experiment; existing startup remains unchanged. Turbid recall **13–18%** and real-world generalization remain limitations.

## GUI automated inspection mission

[[Automated Inspection Mission]] adds GUI start/stop, nearest mapped pipe-end approach, correct-class component confirmations, intermediate lateral scan stops and sensor-only return. A complete Stonefish trial passed all nine visits and returned in 472.04 s with **2.26 cm** true spawn error and **2.60°** heading error. Actual GUI disconnect cancelled and zeroed thrust. Final guard tests and native GUI checks passed; **59 host tests passed, four ROS-only skipped**. Mission navigation uses the configured scene map and IMU/DVL/pressure; ground truth remains evaluation-only. Full noisy/turbid mission performance remains unverified.

Perception interruptions now cause a bounded zero-thrust recovery hold instead of immediate permanent cancellation. Raw camera and completed inference freshness are measured independently; the same waypoint resumes only with fresh streams, and persistent failure cancels after 25 s. Actual inference-server pause/unpause tests passed all five recovery checks. **63 host tests passed, four ROS-only skipped**. See [[Automated Inspection Mission]] for the measured fault-injection outcome and limitations.

### 2026-10-11 — Fast mission and independent view priority

Implemented wider/faster bounded inspection and independent AUV/overview display toggles with native render priority. Five-stop three-thruster run completed in 293.10 s, returning within 2.76 cm. This did not satisfy the later one-minute requirement.

User approved two lateral thrusters for an experimental rig. After documented failed controller trials, four-target inspection plus return passed in 37.28 s and 36.92 s with both feeds, and 35.93 s with AUV display hidden. True spawn error approximately 5.2–5.4 cm. 78 host tests passed (four ROS-only skipped); Tk controls, live operator stop, manual override, heartbeat and disconnect checks passed, with native five-motor zero confirmed. Final packaged orientation gate verification and stopped-state confirmation follow. See [[One Minute Mission Experiment]] and [[Faster Mission and View Priority]].

Final packaged fast rig passed **35.63 s**, **5.18 cm** return error with orientation gate. Verified image tagged for startup; rollback images preserved. Simulator and inference stopped after controlled validation. No push or model retraining performed in this iteration.

### 2026-10-11 — Autonomous power slider

Added live 20–100% translation power setting for inspection and return, with controller confirmation and unchanged stabilization/deadline. 87 host tests passed (four ROS-only skipped), native GUI checks passed. Actual 100→60→100 mission completed in 36.91 s, 4.83 cm return error. Reset simulator to spawn and reopened GUI; inference remains running. See [[Autonomous Power Control]].

### 2026-10-11 — 1.7 m standoff

Fast rig scan standoff changed to 1.7 m body-origin-to-pipe-axis (camera 1.08 m). 30 targeted tests passed. Full clear/ideal/100% mission passed in 43.50 s, 3.46 cm return error. Reset to spawn and restore user-selected 70% power, realistic errors and optical/display settings.

### 2026-10-12 — Perception handoff v1 and repository delivery

Created [[Perception_handoff_v1]] with extraction manifest for detector/GUI/bridge, thruster configurations, fixture geometry, native optics/view patches, sensors/telemetry and optional mission. Documented existing-vehicle mapping, authorized model access, excluded secrets/data/weights, Windows WSL2/AMD64 build/start instructions and acceptance/rollback requirements. Registry inspection verified the committed inference digest is ARM64 and identified the companion AMD64 digest. Windows execution is explicitly untested. Host verification passed 87 tests (four ROS-only skipped). Simulator/inference remain stopped. All source/assets/configuration/documentation are being delivered together to Perception; generated artifacts remain ignored.
