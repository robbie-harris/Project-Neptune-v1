# Tested Pipe Simulator Release

[[Home]] · [[Setup]] · [[Tank Overview]] · [[Sensor Errors and Return to Spawn]]

This release recovers the last deployed pipe-only simulator source from the retained pre-inspection container. Its image manifest `sha256:804cf60d8ec8c95b55ec148e60b69569542ee88744adc75cbec24cfc8da28134` exactly matches the final tank-overview build log. Application, simulation, configuration, tests and existing documentation were copied unchanged from that snapshot. File hashes are recorded in `config/tested-release-source.json`.

Included: torpedo AUV, original intact pipe tank, existing fixed illumination, pipe detector with local Roboflow/Ultralytics backends, corrected manual thrust and stop/watchdogs, sensor-error toggle, estimated/ground-truth telemetry, return-to-spawn sequence, larger telemetry and live tank overview.

This release precedes the valve/flange fixtures, three-class detector and new natural-light/water/particle GUI controls. The ongoing inspection implementation is separate uncommitted local work.

Host tests rerun on the recovered source on 2026-10-11: **41 passed, 4 ROS-only skipped**. Historical live ROS/GUI and physical control checks are preserved in [[Tank Overview]], [[Sensor Errors and Return to Spawn]] and [[Orientation Deployment Results]]. This recovery did not run another full simulator alongside ongoing dataset capture.

Start commands remain in README and [[Setup]]. Local trained weights, managed model caches, API credentials, datasets and runtime logs are ignored and not published. Configure the existing Roboflow key privately or provide permitted local weights to enable detection on a fresh checkout.
