---
tags: [neptune, perception, progress]
date: 2026-10-10
---
# Orientation resume checkpoint

Branch: `Perception`. See [[Orientation Detection]], [[Roboflow Training]], [[Known Issues and Fixes]], and [[Experiments]].

## Current deployment work

User selected local Roboflow Inference and supplied a deployment key. Integration is implemented and contract-tested. The official ARM64 server is running. All three 900-image held-out tests passed accuracy. Live sensor/control/GUI checks completed; FPS and p95 latency gates failed, so A1 is available only as an explicit candidate. See [[Orientation Deployment Results]]. Raw export denial remains relevant only to direct-weight migration. See [[Local Roboflow Inference]].

## Completed cloud training — 2026-10-10

The full version 3 export passed all 6,000 image/split/box checks. All 6,000 JPEGs exactly reproduce source pixels under the exported JPEG encoder settings; maximum native PNG/JPEG MAE was 3.025717/255 and maximum box-coordinate difference 0.499771 pixels. Report: `outputs/roboflow/final-v3-export-validation.json`.

| Run | Training ID | Model | Duration | Cloud mAP50 / mAP50–95 |
|---|---|---|---|---|
| A1 | `028b0b7b7ae5ba04c874` | `projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1` | 55.23 min | 100% / 98.07% |
| A2 | `a60cdfb1e9e27f582a05` | `projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t2` | 57.72 min | 100% / 98.07% |
| A3 | `d6ad871de3e1ccbf613b` | `projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t3` | 56.30 min | 100% / 98.07% |

All three report 100% cloud recall and precision. These are provider metrics, not local acceptance results. Identical metrics do not establish independent seeded variability. Each requested 100 epochs with provider default initialization; actual seed, batch, completed epoch count and online augmentations remain unreported. No new training jobs are needed.

Historical raw-weight download limitation (managed local-server evaluation is now complete): the official SDK returned HTTP 403, `Not authorized to download this model in pt format.` No weights were downloaded. User authorization covered temporary keys for downloads; both the first attempt and its retry keys were revoked immediately, and both secret files were deleted. See `outputs/roboflow/training-completed.json` and `weights-download.json`. No automatic-review rejection occurred for these download attempts.

Next: obtain the three authorized `.pt` files (or have provider export access enabled), verify hashes/class mapping, select thresholds on 900 validation frames only, evaluate the untouched 900-image test and 35 COU positive diagnostic, then compare live full-rig latency and fresh GUI FPS. Active weights remain unchanged. COU-assisted cloud training remains deferred; no paper-derived variant implemented.

Latest live old-model baseline: `outputs/runtime-baseline-final-image.json`, 68 stereo matches, real-time factor 1.00543, 3.810752 annotated Hz, CPU mean 237.527 ms / p95 260.306 ms, native GUI median 3.59 fresh FPS over 97 samples. Use this baseline for candidate comparison, not the earlier clock-recovery run. Host checks: 28 passed, two ROS-only modules skipped on host; packaged ROS launch tests exited successfully.

## Resume without repeating work

Do not recapture, reupload, regenerate version 3, or start more training jobs. The frozen manifest is `1ca3375ab2314315e2a9f3dac08d1cbce30502a2f41d3c29d5decc41d89f74f9`. Earlier per-image checkpoints and diagnostic versions 1/2 are historical. Temporary download secrets are gone; obtain approved export access or user-provided files before dependent evaluation.

## Capture incident and recovery

A clock/render mismatch began at `o228_v02`. Preserved 1,311 suspect captures under `data/quarantine/clock-render-20261009` and `data/quarantine/clock-onset-20261009`. Recaptured all groups from 228 onward using steady-clock pacing, bounded 100 ms catch-up, pose matching and duplicate-pixel rejection. Final validation and visual audits passed. Quarantined originals must never enter training.

A completed capture can re-enable peripheral sensors with mismatched stereo phases. Restart the full simulator after capture before acceptance measurements; this restored exact stereo timestamp matches.

## Cloud access constraints

Public simulator uploads are authorized under CC BY 4.0. COU is CC BY-SA 4.0 and remains local pending compatible handling. The optional official Roboflow 1.7.1 SDK is installed in isolated `.venv-roboflow`, with resolved pins in `config/roboflow-client-requirements.txt`. The connected MCP exposes existing API-key metadata without its secret. The user subsequently approved a temporary key for SDK bulk label import, with immediate revocation after transfer. Current upload report/log: `outputs/roboflow/bulk-label-import.json` / `.log`. Key ID and revocation state (no secret): `outputs/roboflow/temporary-key-metadata.json`. Training continues through MCP. Individual-label workers are stopped during bulk import.



The approved bulk import completed and its complete version 3 export passed verification. All cloud training is finished; the current blocker is model weight export, as described above.
