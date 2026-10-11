---
tags: [neptune, research]
---
# Research

Primary sources informing this milestone:

- [Stonefish repository](https://github.com/patrykcieslak/stonefish): underwater simulator; reuse instead of implementing fluid dynamics or sensors.
- [Stonefish sensors](https://stonefish.readthedocs.io/en/latest/sensors.html): supported camera, FLS, IMU, pressure, DVL, and noise controls.
- [Stonefish ROS interfaces](https://stonefish-ros2.readthedocs.io/en/latest/sensors.html): native sensor message mappings.
- [YOLO11 documentation](https://docs.ultralytics.com/models/yolo11/): compact detection model and existing training/export support.
- [Ultralytics training](https://docs.ultralytics.com/modes/train/): MPS support and reusable training workflow.
- [PyTorch MPS](https://docs.pytorch.org/docs/stable/notes/mps.html): host Apple GPU execution.
- [OpenCV calibration](https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html): projection and rotation APIs for synthetic labels.

## Later candidates

- [RAFT-Stereo](https://github.com/princeton-vl/RAFT-Stereo) for learned stereo matching after a classical depth baseline.
- [ORB-SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3) for visual-inertial localization.
- [SAM 2](https://github.com/facebookresearch/sam2) for reviewed annotation assistance.
- [SegFormer](https://arxiv.org/abs/2105.15203) for continuous surface defect segmentation.

These are future candidates, not dependencies of the first detector. Synthetic performance in a single clean tank does not establish robustness across water conditions or real assets. See [[Ideas]] and [[Experiments]].

## Orientation iteration: supplied dataset and paper

The [COU authors](https://irvlab.cs.umn.edu/resources/cou-common-objects-underwater) describe underwater robot field-trial imagery across pools, lakes and oceans, including man-made objects. Local archive counts are observations from the supplied `coco.zip`, not counts inferred from the website: 9,663 images, 35 pipe-positive images, all in G18. Its supplied attribution/license is CC BY-SA 4.0. See [[Orientation Detection]] for review outcomes and [[Roboflow Training]] for the local-only restriction.

The supplied Scientific Reports paper (`s41598-026-69925-1_reference.pdf`) proposes MDP-YOLO: MDRFF directional/frequency feature fusion, DySample upsampling, a P2 head with P5 removal, and MPDIoU box loss. Its reported marine-object mAP improvements of 2.2–2.9 percentage points do not establish pipe recall or deployment latency. No official full implementation was located during this assessment. Its higher-resolution changes add computation; retain YOLO11n until corrected data coverage has been evaluated.

Verified starting points for gated component experiments: [official DySample implementation](https://github.com/tiny-smart/dysample), [MPDIoU paper](https://arxiv.org/abs/2307.07662). No paper-derived component is currently installed or trained. The supplied PDF remains outside this repository; source notes distinguish its claims from Neptune's measurements.
