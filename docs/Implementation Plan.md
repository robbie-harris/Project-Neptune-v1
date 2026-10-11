---
tags: [neptune, plan]
---
# Implementation plan

1. Package the reference Docker, Stonefish, ROS, GUI, and bridge inside Project-Neptune on Perception.
2. Build the closed tank, intact pipe, torpedo body, lights, and ideal complete sensor rig.
3. Verify transforms, sensor streams, timing, controls, and explicit missing-model behavior.
4. Capture 1,000 genuine simulator renders with geometry-derived labels. Use 100 viewpoint groups, 10 variants each, seed 42, and 70/15/15 group split; two variants per group point away from the pipe.
5. Fine-tune pretrained YOLO11n for one class `pipe`: 100 epochs, image size 640, batch 16, MPS or CPU on the host. No image-corruption augmentation.
6. Evaluate held-out viewpoints; run the trained model in Docker and verify GUI detections.
7. Record actual tests, metrics, hardware, limitations, and generated artifact locations.

## Acceptance

- Camera resolution 640 × 480, stereo baseline 0.12 m, zero noise/bias/drift.
- Intended simulation rates: cameras/sonar/DVL 10 Hz, pressure 20 Hz, IMU/physics 100 Hz. Report actual delivery rates, especially under software rendering.
- Shared simulation clock and identical stereo capture stamps.
- Manual controls and emergency/disconnect/timeout stops.
- Missing model produces no invented detections.
- Held-out pipe recall ≥90% at IoU ≥0.5.
- Pipe-absent frame false-positive rate ≤5%.
- Measured inference rate, mean latency, and p95 latency.

Automatic navigation, sensor fusion, metric target pose, damaged pipes, and repair are excluded. See [[Progress]] for actual completion.
