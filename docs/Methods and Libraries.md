---
tags: [neptune, methods, dependencies]
---
# Methods and libraries

| Method/library | Implementation and use |
|---|---|
| Stonefish 1.6.0 | Hydrodynamics, rigid-body physics, camera/sonar and scalar sensor simulation |
| stonefish_ros2 1.6.0 | Existing scenario parser, publishers, respawn service, TF |
| ROS 2 Jazzy | rclpy, launch, colcon, message interfaces, clocks |
| Ultralytics 8.3.221 | YOLO11n pretrained architecture, training, prediction, box IoU metrics |
| PyTorch 2.8.0 / torchvision 0.23.0 | MPS host evaluation and ARM64 CPU inference; current training uses Roboflow MCP |
| OpenCV 4.11.0.86 | Camera conversion, Rodrigues/projectPoints and convex silhouette/viewport clipping for labeling, PNG annotation |
| NumPy 1.26.4 | Geometry and deterministic dataset sampling |
| PyYAML 6.0.2 | Training settings and dataset configuration |
| cv_bridge, sensor_msgs, vision_msgs | Standard image and detection interfaces |
| tf2_ros, nav_msgs, rosgraph_msgs | Rig transforms, ground truth, simulation clock |
| Tkinter / socket / JSON | Reference GUI and TCP bridge reuse |
| Docker / Mesa / Xvfb / VNC | ARM64 software-rendered simulator runtime |
| pytest 8.3.5 / launch_testing | Contracts and ROS process integration checks |

Pinned Stonefish revision: `b21eb8e194c570ff2f61e91aeffb38d73dc25f42`.
Pinned ROS bridge revision: `6646e7ac25eed982f37f807abc7b545dbd2d6648`.

The simulation clock/render scheduling patch is in `src/tools/patch_stonefish.py`. It changes integration timing, not perception algorithms. The detector receives only camera imagery. Standard COCO model weights do not contain the pipe class; custom fine-tuning is required.

Ubuntu/ROS package patch versions resolve through the Jazzy repositories. Record their actual versions in each validation run; Python runtime dependencies are pinned and the resolved environment is captured in generated lock reports. Ultralytics and simulator licenses are documented upstream; this repository includes GPL-covered simulator integration.

See [[Research]], [[Architecture]], and [[Decision Log]].

## Resolved validation environment (2026-10-09)

| Installed package | Exact version |
|---|---|
| libgl1-mesa-dri | 25.2.8-0ubuntu0.24.04.4 |
| novnc | 1:1.3.0-2 |
| python3-colcon-core | 0.21.2+upstream-1 |
| ros-jazzy-cv-bridge | 4.1.0-1noble.20260911.140139 |
| ros-jazzy-launch | 3.4.11-1noble.20260603.145505 |
| ros-jazzy-launch-testing | 3.4.12-1noble.20260920.235800 |
| ros-jazzy-rclpy | 7.1.12-1noble.20260902.143245 |
| ros-jazzy-sensor-msgs | 5.3.8-1noble.20260902.133401 |
| ros-jazzy-tf2-ros | 0.36.22-1noble.20260902.154805 |
| ros-jazzy-vision-msgs | 4.1.1-3noble.20260911.091701 |
| x11vnc | 0.9.16-10 |
| xvfb | 2:21.1.12-1ubuntu1.8 |

Host Python 3.12.14; host GUI interpreter Python 3.14.6 / Tk 8.6. PyTorch/Ultralytics dependency resolution is archived in `config/requirements-host.lock.txt`; generated container and ROS package inventories are in `outputs`. Rendering uses llvmpipe (LLVM 20.1.2) with software OpenGL 4.5. Host hardware: Mac17,2, Apple M5 (10 CPU cores), ARM64, 16 GB memory, macOS 26.6.2.

Docker client and server used for validation: 29.8.0. The container is allocated 8 CPU cores and 1 GB shared memory; Mesa render workers: initially 4; optimized default 8.

Docker detector CPU inference is configured with 2 PyTorch threads, leaving rendering capacity available. A `torch.device` is supplied to the existing Ultralytics predictor so its CPU device setup preserves this explicit thread budget. Actual model-on timing is reported in [[Experiments]].

## Orientation iteration

Roboflow MCP is the current training backend. Use provider model ID `yolov11n`; the user approved three managed repeat runs after exact seed/batch/online-recipe controls were found unavailable. Local algorithms continue to use the pinned dependencies above. `roboflow_annotations.py` uses normalized YOLO TXT for positive simulator boxes and standard-library XML for explicit negatives. Cloud-managed dependency versions must be recorded from completed run metadata if exposed; they cannot be assumed identical to the local pins.

Optional Roboflow SDK 1.7.1 is installed in isolated `.venv-roboflow`; exact resolved dependencies are pinned in `config/roboflow-client-requirements.txt`. This environment is separate from the pinned perception runtime. The user authorized a temporary inherited-scope key on 2026-10-10 for official SDK bulk label transfer, with immediate revocation after transfer. Training continues through MCP. Bulk ZIP support uses the existing SDK `Workspace.upload_dataset` implementation with annotation overwrite, rather than a custom upload algorithm.


## Local Inference integration — 2026-10-10

User selected a local deployment path and supplied a key. Two configurable backends are implemented; credentials are ignored and mounted read-only. Official SDK/CLI 1.7.4 are isolated from ROS NumPy; ROS calls the official REST API with lossless pixels and original timestamps. New unit checks and ROS contract integration passed. Official ARM64 server image download is pending; candidate accuracy/runtime remain unmeasured. See [[Local Roboflow Inference]].
