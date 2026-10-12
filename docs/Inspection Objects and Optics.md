# Inspection Objects and Optics

[[Home]] · [[Architecture]] · [[Progress]] · [[Methods and Libraries]] · [[Known Issues and Fixes]]

## Scope and class definitions

One detector: `0 pipe`, `1 valve`, `2 flange`. Valve body, stem and handwheel form one instance. Paired flange plates and eight bolts form one instance. Attached pipeline is a separate pipe instance. Intact fixtures are about 1.7 m apart at the far end of the original tank. Valve actuation, damage diagnosis and repair are future milestones.

Procedural fixtures use Trimesh **4.6.8**, NumPy **1.26.4** and metre units. Reproduce with `.venv-host/bin/python src/tools/generate_inspection_scene.py`; install `config/requirements-mesh.txt` in that isolated environment first.

## Native optics

Natural light and AUV lamps are independent. Natural off scales sunlight **and sky illumination** in the shared atmosphere shader API. Lamp illumination and native underwater scattering remain enabled. Requests are queued and applied inside the graphics render thread, not the ROS thread. Existing 800-lux, 90-degree forward lamps retain their mounting positions.

Clear/moderate/turbid map to Jerlov **0.02 / 0.25 / 0.65**. Suspended particles use the native Stonefish renderer. These values are not NTU measurements. Image-space red attenuation, contrast loss and additive backscatter have been removed from the sensor-error adapter; noise, exposure variation, blur, calibration errors and dropouts remain.

Defaults: natural on, lamps on, clear, particles off, sensor errors off. Overview follows the same physical illumination and can become dark. GUI shows applied, pending, failed or stale native status. Changes do not respawn the AUV.

ROS `/neptune/optics/request`: Float64MultiArray `[request_id, natural, lamps, jerlov, particles]`. `/neptune/optics/applied`: same array plus success flag; no success is claimed until a renderer acknowledgement. Both light-native SetBool services are exposed under `/neptune/optics/LightLeft/set_enabled` and `LightRight/set_enabled` in the inspection scene.

## Capture and planned training

Capture-only `CaptureInstances` camera shares the left RGB camera transform, dimensions and intrinsics. Native uint16 masks and RGB must have exactly matching simulation timestamps. Retained `/neptune/capture/instance_map` maps actual graphics instance IDs to named fixtures; it is validated rather than assumed from parser order. It starts disabled and is enabled only during capture. Targets require both box dimensions ≥4 pixels and visible mask area ≥100 pixels for primary metrics. Small targets are retained separately in metric reporting. Ambiguous/unlit captures are diagnostics and cannot become empty training labels.

Planned pilot: 60 actual rendered frames, audit local labels and Roboflow export. Planned full capture: 9,000 frames / 900 viewpoint groups, 70/15/15 split, 25% absent, ≥2,250 eligible instances per class. No images are uploaded until hash, pairing, label and group checks pass. Existing pipe data remains untouched.

Roboflow project created: [Neptune Inspection Objects](https://app.roboflow.com/projects-zwfft/neptune-inspection-objects), public simulator-only **CC BY 4.0** under the user's authorization. COU remains local. Planned one MCP run: YOLO11n, input 640, requested 100 epochs; managed provider defaults, unknown seed/batch recorded honestly. **Training has not started.** A full verified export is a prerequisite.

## Detector contract

All-class `/neptune/perception/object_detections` is Detection2DArray. Legacy `/neptune/perception/pipe_detections` contains pipes only. Annotated image and both detection arrays preserve the input camera header. Pixel-only inference has no geometry or masks. Pipe-only weights remain supported for rollback, as do correctly named three-class downloaded weights. The existing local Roboflow server remains the deployment path; candidate promotion waits for test and runtime gates.

## Initial verification history

- Fixture meshes and inspection scenario generated.
- Multiclass decoder, class colors, detection topics and GUI listing implemented.
- The first native build exposed atmosphere shader-link conflicts. It was rejected and later fixed using a dedicated uniform buffer; see the successful outcomes below.
- Host suite: 44 passed, 4 ROS-only skipped before additional mask tests. Four inspection-specific tests now pass.
- At this initial checkpoint, pilot capture and cloud verification had not started. Their completed results are recorded below; training and runtime acceptance remain pending.

## Acceptance gates

≥95% recall per class at IoU ≥0.5 on eligible clear/moderate test targets; ≤5% false-positive frames on genuinely all-target-absent views. Report orientation, lighting, confusion, turbid and completely unlit diagnostics separately. Threshold selection uses validation only. Run untouched original pipe regression. Compare fresh GUI FPS and p95 inference latency under identical scene settings; candidate may become normal startup only at ≤10% p95 increase and passed accuracy gates.

## Sources

- [Stonefish environment and native optics](https://stonefish.readthedocs.io/en/latest/environment.html)
- [Subsea valve repair](https://www.oceaneering.com/webinars/creating-bespoke-solutions-for-subsea-valve-repair/)
- [Pipeline and flange repair](https://www.oceaneering.com/pipeline-repair/)
- [Trimesh primitive creation](https://trimesh.org/trimesh.creation.html)

The pinned simulator revisions remain in [[Methods and Libraries]] and `Simulation/docker/Dockerfile`; optical patch v1 is `src/tools/patch_optics.py`. Hardware for subsequent evaluation: Apple M5, 16 GB, ARM64 Docker with Mesa. Measured results will be recorded separately from the planned gates.

## Updated implementation outcomes

Native optics passed the 24-condition matrix. Exact matching RGB/mask stamps and actual instance IDs (`14 Pipeline`, `16 InspectionValve`, `18 InspectionFlange` in this scene) were verified. IDs are runtime metadata, not hardcoded label assumptions. All six fully unlit conditions had mean and 95th-percentile pixel value **0**. Lamp-only scenes were visibly illuminated across all three water presets.

The initial generated OBJ files lacked explicit vertex normals: Stonefish rendered black fixture silhouettes. The generator now exports normals explicitly; the correction is covered by a scene test and visually verified. Initial failed images remain in ignored diagnostic outputs and never enter training. Final verification is `outputs/optics-final/report.json`.

Host tests: **48 passed, 4 ROS-only skipped** (latest complete host suite). Native Tk control test passed, including optical acknowledgement and valve listing. ROS multiclass/local-server contract passed: all three classes, pipe-only compatibility, input headers and startup recovery. Both command/controller watchdog tests passed. Synthetic bridge preview under simultaneous rendering delivered **27 frames / 4 seconds**, below its 32-frame requirement; isolated preview verification subsequently passed; live performance comparison remains pending. This is an unmet check, not a measured multiclass-model runtime result.

Repeated dependency downloads were interrupted and rejected by pip hashes. No checksum checks were bypassed. An optional `DEPENDENCY_IMAGE=neptune-perception:latest` build argument reuses the existing pinned Python runtime and checks requirements without network; fresh builds retain normal installation. Native pinned sources and ROS are still rebuilt and patched normally.

The completed 60-image pilot is retained in `data/inspection`. Pilot images are the first viewpoint groups of the eventual 900-group manifest, preserving the final split assignments. They can remain in the full dataset without split leakage or a second upload identity. Later scene-size/material variants stay within a group. No training job exists yet.

Pilot complete: **60 images / 6 groups**, 30 training / 10 validation / 20 test images; 40 eligible pipe instances, 32 valve, 32 flange, 20 target-absent views. Manifest SHA-256 `8aa2bbb6e374293cd38f5897cbf03984ecf410f642662fef3ba9de459ecbffa0`. Pilot proportions are intentionally not the full 900-group quotas. Native masks and local annotations were audited and a contact sheet visually reviewed.

Roboflow SDK import task `KAnYcOf2CDHnbesJbCvZ` uploaded/annotated all 60. The import reported three edge-trimming warnings. All 60 Dataset memberships were then explicitly confirmed through MCP annotation saves, and the cloud export coordinate check passed with zero error, as detailed below. The existing ignored credential was reused; no temporary key was created.

Isolated bridge verification passed **all three active tests plus clean exit**. The renderer-loaded preview failure remains recorded as a load-dependent limitation.

Pilot cloud audit **passed**: version 1, 60 images, zero box coordinate error, all original split assignments preserved, and every exported JPEG exactly reproduced using its quantization/subsampling. Export SHA-256 `bcb14f05f45c326c9e2a417351f746f6de3e2c32cc45c4357064b94efcd07872`. The three edge-trimming warnings did not change boxes. `outputs/inspection-pilot-export-audit.json` contains the full check. Source valve/flange mesh hashes were additionally verified against the actual pilot container and recorded in generation metadata without changing frozen image/label records.

## Full capture and subsequent commands

`bash src/tools/capture-inspection-full.sh` runs the four fixture variants and resumes the pilot's 900-group manifest. It refuses to start without the exact successful 60-image cloud audit. Each viewpoint group remains in one split and one scene; pilot groups retain their original base-scene images. The result is a newly audited 9,000-image archive. Capture is offline: do not drive the vehicle during collection.

Full training/import follows capture, not in parallel with incomplete data:

1. Prepare is performed automatically at full capture completion with `--expected 9000 --full`.
2. Import `outputs/inspection-full.zip` with `src/tools/roboflow_inspection.py upload` in the isolated Roboflow SDK environment.
3. Explicitly confirm Dataset membership with `roboflow_inspection.py confirm --data data/inspection --key-file .secrets/roboflow_api_key --result outputs/inspection-full-membership.json`. This uses the pinned official SDK 1.7.1, verifies all filenames/splits, supports sanitized checkpoints and parallel independent saves. Training still uses MCP.
4. Generate/export the complete version through MCP; run `verify_roboflow_export.py` against every exported image and annotation before requesting the single YOLO11n/100-epoch run.
5. Freeze a validation-only confidence using `evaluate_inspection.py --split val --select-confidence`; supply that confidence for `--split test`. Training/model IDs are mandatory report inputs. Run `evaluate.py` on the original pipe test set; its predictions are explicitly filtered to pipe for regression.
6. Run the candidate locally with `run-inspection.sh model_id:=<confirmed-model-id> confidence:=<validation-threshold>`. Preserve old startup weights until class recall, false-positive, original-pipe regression and live runtime gates are evaluated.

`config/inspection-training.json` contains requested settings and gates, not achieved results. A Roboflow version for pilot verification is **not a trained model**. The full capture has started; multiclass training and candidate promotion remain pending.

## Import concurrency

Image upload and annotation confirmation can overlap across completed batches, but a save must reference an already-uploaded image ID. The optimized run overlaps capture with uploads of audited, complete ten-image groups. Each snapshot verifies source hashes, masks, labels and frozen splits before public transfer. Verified annotation saves use eight concurrent official SDK workers and an atomic image/hash checkpoint. Dataset version generation and training wait for complete membership and exported label verification.

## Capture optimization — 2026-10-11

Observed Docker renderer: Mesa 25.2.8 llvmpipe, LLVM 20.1.2; hardware acceleration false, approximately 700% CPU. Parallel simulators on this Mac would compete for these cores.

A matched 30-image benchmark covered the same requested viewpoints and optical settings: baseline capture/profile time 78.67 s versus overview-disabled 41.40 s, approximately **1.90× faster**. This is a small timing sample, not an end-to-end completion forecast. Native mask/RGB timestamps matched in both. Valid visible-instance counts differed with dynamics and replacement attempts (pipe 20/20, valve 19/11, flange 19/11); images are not claimed to be pixel-equivalent. Full 9,000-image class quotas and acceptance gates remain unchanged and mandatory. Benchmark renders stay outside the training dataset. Detailed report: `outputs/capture-optimization-benchmark.json`.

Guarded pose reuse was tested, but none of these 30 frames qualified. It is **not enabled** in production capture and receives no claimed speed benefit. It remains an explicit experimental flag; a failed capture-time pose guard falls back to the original respawn capture. The baseline's existing post-settle dynamics remain intact. New records also store actual capture-time position/quaternion and profile/attempt timing.

`/neptune/sensors/TankOverview/set_enabled` now exposes the native overview enable control. The full capture script disables it during offline capture and restores it afterward. Operator startup still enables the overview; lighting, image dimensions, camera rates and physics rates remain unchanged.

`stream_inspection_upload.py` stages immutable audited snapshots of complete groups while collection continues. It uses the isolated Roboflow SDK 1.7.1 and existing ignored credential, uploads public simulator data under CC BY 4.0, confirms filenames/splits, then saves verified multiclass annotations using eight workers. The pinned SDK search returns pages as lists, unlike MCP's result wrapper; both shapes are now handled. An upload completion marker avoids redundant transfers after index/annotation retries. Diagnostics omit keys, SDK response URLs and raw exception text.

Start/resume the transfer independently:

```bash
.venv-roboflow/bin/python src/tools/stream_inspection_upload.py \
  --data data/inspection --output outputs/inspection-stream \
  --key-file .secrets/roboflow_api_key
```

Final local audit, all 9,000 cloud memberships, complete exported dataset verification and MCP training remain sequential prerequisites. No model is trained on a partial snapshot. At optimization restart: 840 captured images, 726 image/annotation pairs confirmed in Roboflow. Host tests: **50 passed, 4 ROS-only skipped**. The deliberate collection interruption preserved the complete manifest checkpoint; its shutdown-context error did not enter training records.

## Approved reduced dataset — 2026-10-11

The user approved ending the broad capture early and adding representative missing fourth-variant views. The original run stopped on a whole-group boundary at **6,230 images**. Thirty new fourth-variant groups (300 images) were selected from the existing seeded 900-group generation space. They fill all twelve 30-degree roll bins and preserve the existing split assignments. No uploaded or held-out image was reassigned.

Final planned dataset: **6,530 images / 653 complete groups**, **4,570 train / 980 validation / 980 test**, and **1,630 genuinely target-absent frames** (~24.96%). Fourth-variant additions use 22 train / 3 validation / 5 test groups and six negative groups. Final counts, hashes and coverage are not claimed achieved until the sealed audit passes.

`src/tools/seal_inspection.py` freezes the exact manifest hash and counts into ignored `data/inspection/sealed_dataset.json`. The full audit requires complete ten-image groups, all four fixture variants, all eighteen optical profiles, all twelve roll bins, unchanged source hashes/labels and at least 2,250 eligible instances per class. Export, upload confirmation and evaluation read this approved frozen contract instead of assuming 9,000 images. A sealed dataset rejects further collection. The existing untouched original pipe regression dataset is preserved.

The requested **one YOLO11n run / 100 epochs / 640 input** and all accuracy/runtime gates remain unchanged. Managed recipe entitlement is still unavailable, so seed, batch and online settings remain provider defaults unless reported by the actual training. Public uploads continue to include simulator images only under CC BY 4.0; no MarinaPipe/COU images enter this run.

Host suite after reduced-contract and viewpoint-generation checks: **52 passed, 4 ROS-only skipped**. The earlier 9,000-image sections describe the original plan; this approved reduction supersedes their count requirements. Training remains pending complete cloud export verification.

### Reduced capture actual outcome

The sealed local audit passed: **6530 images / 653 groups**, split **4,570 / 980 / 980**, eligible pipe/valve/flange instances **4,880 / 4,586 / 4,393**, and **1,630 target-absent frames**. All four scene variants, all eighteen optical profiles, all twelve roll bins, complete groups, source hashes, label pairing and exact RGB/mask timestamps passed. Manifest SHA-256 `f672dcd51aacdf0aa1c153b2c8f8b7295baeac241624f9332585f0fb95e4ef1e`. Further capture into this sealed dataset is blocked. Remaining work: complete Roboflow membership, full export verification, one requested training run, and model accuracy/runtime evaluation.

### Reduced cloud dataset

All **6,530 image/annotation pairs** were successfully confirmed by the resumable uploader. Roboflow MCP generated version **2** of `projects-zwfft/neptune-inspection-objects`, reporting **6,530 images** and the unchanged **4,570 train / 980 validation / 980 test** split. Requested offline preprocessing and augmentation are both empty. Cloud version processing, full COCO export verification and the single training submission remain pending at this checkpoint; project-level cached counters can lag behind the version counts. The pilot version 1 is not used for production training.

### Export audit and cloud training submitted — 2026-10-11

The complete COCO export passed: **6,530 images**, unchanged splits, all class labels and boxes, and **zero maximum box-coordinate error**. Every exported image was exactly reproduced from its original pixels using Roboflow's JPEG quantization/subsampling. This verifies encoding changes rather than claiming lossless uploaded pixels. Export SHA-256: `16ec2dee78210ed305a8a000fd96ed697a200481420c4d845d39158e0722d752`. Report: `outputs/inspection-reduced-export-audit.json`.

One MCP **YOLO11n / 100 requested epochs** job was accepted with status **running**, training ID **`cf8d962d68e32878e60b`**, on version **2**. [Cloud training](https://app.roboflow.com/projects-zwfft/neptune-inspection-objects/2). The first submission only triggered the required YOLO-format export and created no job; after export readiness, the next call created this sole training. Input setting is the provider's inspected 640 template. Actual seed, batch, online augmentation, completed epochs and final model ID remain unreported at submission. Training continues on Roboflow servers if the laptop sleeps; local evaluation and simulator deployment require it to be available again.

No multiclass model is promoted yet. Remaining work after cloud completion: freeze validation-selected thresholds, evaluate the untouched test split and original pipe regression, measure full-simulator GUI FPS/inference latency, and deploy only if the measured acceptance gates pass. The pipe-only rollback remains available.

### Completed candidate evaluation and integration

[[Inspection Detector Results]] now records the finished model, frozen confidence 0.05, validation and untouched multiclass test, original pipe regression, and matched live rig comparison. New clear/moderate accuracy and live latency gates passed; original pipe regression failed at 93.78% recall, so normal promotion is blocked. The integrated model is available through explicit `bash src/tools/run-inspection.sh --candidate`. Existing startup remains unchanged. No second training run was started. The simulator and native GUI were left running with the experimental detector; the observed pre-benchmark sensor-error toggle was restored.
