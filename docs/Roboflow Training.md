---
tags: [neptune, training, roboflow]
date: 2026-10-09
---
# Roboflow training

Related: [[Orientation Detection]], [[Setup]], [[Decision Log]], [[Orientation Resume Checkpoint]].

Use Roboflow MCP for training, as requested. Project: [Neptune Pipe Orientation A](https://app.roboflow.com/projects-zwfft/neptune-pipe-orientation-a), architecture ID `yolov11n`.

## Authorization and actual limitations

The connected workspace rejected private project creation. The user authorized public simulator images under CC BY 4.0, while retaining COU locally pending compatible handling. Never upload the COU-assisted mixed dataset to this project. COU's CC BY-SA 4.0 terms are not equivalent to the project's CC BY 4.0 choice.

The inspected YOLO11 recipe exposes epochs and 640 input resolution, but no batch-size or seed fields. Advanced recipe access is not entitled in this workspace, so explicit online augmentation/preprocessing configuration through that path is unavailable. All three managed runs finished on 2026-10-10. The user approved managed defaults for three repeat runs on 2026-10-09. Three managed repeat runs cannot be described as seeds 42, 43 and 44.

## Data transfer and frozen versions

1. Validate the complete simulator dataset locally. Preserve the source manifest and hash.
2. Run `src/tools/roboflow_transfer.py pack` to create an image-only ZIP organized into train/valid/test. Only `stonefish` source records are accepted. Each upload must be under 2 GB and 10,000 images.
3. Request upload through MCP, store the signed PUT credentials temporarily in ignored outputs, and use the helper's `put` command. Credentials are deleted after the PUT attempt. Do not print signed URLs or commit credentials.
4. Match returned image IDs to filenames, save normalized YOLO TXT annotations for positives (label map `0: pipe`) and explicit empty VOC annotations for negatives through MCP, and add images to the dataset. Save explicit empty annotations for negative frames. Verify counts and actual split memberships; don't assume a successful image upload imported labels.
5. Generate a frozen version with no baked augmentation/preprocessing, then verify its exported records against local splits and hashes. Version 1 is a partial pilot snapshot and must not be trained.
6. Start each authorized training run exactly once; retain version, training ID, actual settings, status, model ID and report. Poll existing jobs rather than starting replacements.
7. Download compatible offline weights and verify class mapping `{0: pipe}` with the pinned Ultralytics stack. The MCP tool inventory currently has no dedicated weights-download tool; inspect completed model metadata first. An SDK download may require a locally configured API key. Do not place API keys in chat or Git.
8. Evaluate and integrate locally using [[Orientation Detection]] acceptance. Keep the previous active weights until checks pass.

The 220-image pilot upload is complete and all 220 images are annotated in the dataset. This tests the transfer path only. The full 6,000-image capture, upload, annotation import and version 3 export verification are complete.

Local staging metadata: `outputs/roboflow/experiment.json`, `outputs/roboflow/recipe-pilot.json`. Provider documentation: [weights download](https://docs.roboflow.com/models/model-weights/download-roboflow-model-weights).


## Replacement-capture authorization

The user explicitly approved adding verified post-fix replacement captures for groups 228–359 to the cloud training dataset after automatic review blocked filenames overlapping quarantine. The original quarantined records remain excluded. Source manifest validation confirms 6,000 images, 600 groups, 4,200/900/900 splits, exactly 25% negatives per split and no duplicate images. Frozen manifest SHA256: `1ca3375ab2314315e2a9f3dac08d1cbce30502a2f41d3c29d5decc41d89f74f9`. All three version 3 training jobs finished; local weight access is pending.


## Label-coordinate verification

The immutable pilot export showed a systematic roughly one-pixel VOC-origin shift, reaching 1.495 pixels after server rounding. A normalized YOLO TXT import of `o004_v03` exported within 0.166 pixels of its geometry box. All 6,000 current source annotations were refreshed using normalized YOLO positives and empty VOC negatives; overwrite is limited to this project's own verified images. Both diagnostic versions 1 and 2 are incomplete and must not train. Cloud exports encode images as JPEG; final verification records source hashes separately from exported hashes and measures decoded pixel differences.

The official SDK 1.7.1 is installed in an isolated environment. Existing API-key lookup returns metadata without the secret; the initial restricted-key request returned Forbidden (scope/role or Advanced API Keys entitlement restriction). On 2026-10-10 the user explicitly authorized a temporary key inheriting the connector's workspace permissions for bulk label import, with immediate revocation after transfer. `src/tools/roboflow_bulk.py` prepares and transfers the verified dataset through the official SDK; training still uses MCP. Exact SDK pins are in `config/roboflow-client-requirements.txt`. Do not retain the temporary key through training.

The prepared archive contains exactly the authorized 6,000 simulator images, normalized YOLO positive labels and explicit empty VOC negatives. SHA256: `9e99a375d4ef937ea1cddb3043d341a9f7ffe09eea5136dfd11b30adeceadddd`; size 840,291,634 bytes. The SDK import requests `annotation_overwrite=True` on existing images and preserves folder-based train/valid/test splits. Upload/server processing is not acceptance: reconcile actual membership and verify the complete exported version before launching training. No COU data is in the archive.


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
