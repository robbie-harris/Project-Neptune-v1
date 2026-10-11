---
tags: [neptune, project]
---
# Project overview

Neptune is a foundational AUV prototype for autonomous underwater inspection and eventual repair. The application niche is still being selected. This milestone establishes a controlled perception testbed: a torpedo-style vehicle at one end of a water-filled enclosure and a single intact horizontal pipe at the other.

Success means manually driving the vehicle while a trained YOLO model identifies the pipe in the forward camera and the native GUI displays measured detections. It does not yet mean autonomous approach, tool contact, damage diagnosis, or validated real-water operation.

The scene is 10 × 6 × 3 m with six collision boundaries. The pipe is 4 m long, diameter 0.4 m, centered at `(4.4, 0, 1.5)` in world NED. The 1.2 m AUV spawns at `(-3.8, 0, 1.5)`, facing +x.

All instrument noise, drift, and bias are zero. Water is calm; decorative suspended particles are disabled. Underwater lighting/attenuation and rigid-body physics remain simulated.

See [[Architecture]], [[Implementation Plan]], and [[Progress]].
