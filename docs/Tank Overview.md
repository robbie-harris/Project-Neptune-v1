---
tags: [neptune, simulation, gui]
date: 2026-10-10
---
# Tank overview

See [[Home]], [[Architecture]], [[Setup]], [[Progress]] and [[Sensor Errors and Return to Spawn]].

A fixed Stonefish color camera now publishes `/neptune/overview/image_color` and `/neptune/overview/camera_info` in frame `TankOverview`. It is a world-attached visualization camera, not mounted on Neptune, and is not passed to the detector, estimator or error adapter. It remains ideal when onboard sensor errors are enabled.

Position in world NED: `[0, 2.85, 0.35]` m; roll/pitch/yaw `[1.187267, 0, 0]` rad, looking inward and downward. Resolution 640×240; horizontal FOV 125°; requested capture rate 5 Hz; clip distances 0.05–20 m. The camera is inside the enclosure so the opaque walls/roof do not occlude the entire view. This wide perspective shows the AUV and pipe, but cannot expose every corner or surfaces hidden behind objects. It adds rendering work; requested capture rate is not a guaranteed wall-time FPS.

The bridge sends independent newline-JSON `overview` PNG packets alongside existing `img` packets, at its normal preview timer, only for new image versions. Overview stops displaying a live image after two seconds without a new frame. Forward raw/annotated selection does not switch or replace this view.

The GUI places the 640×240 overview directly below the 640×480 forward camera. Telemetry body text increased from Menlo 9 pt to 13 pt, heading from 10 to 12 pt. Video and telemetry share a scrollable area sized to the screen; manual buttons and STOP stay below this area. Mouse wheel scrolls when needed. No additional dependencies were introduced.

## Operation and actual verification

Rebuild with `bash src/tools/run.sh --build`, start the simulator as described in [[Setup]], then run `bash src/tools/gui.sh`. Existing local Roboflow launch commands remain valid. Rebuilding/restarting the simulator is necessary for the new camera; relaunch the native GUI for its new layout.

Actual Stonefish overview capture confirmed 640×240 in frame TankOverview; visual inspection showed the yellow AUV on the left and pipeline on the right. Both preview types rendered in the native GUI while live pipe detection remained ready. Reports: `outputs/tank-overview.png`, `outputs/gui-tank-overview-live.log`.

Native Tk smoke checks passed overview decoding, placement below the forward feed, larger telemetry font, and existing manual/toggle/return/STOP protections. Report: `outputs/gui-tank-overview-controls.json`. Local suite: 41 passed, 4 ROS-only skips. The final independent two-stream ROS bridge test passed fresh overview delivery without duplicate frames, ≥8 FPS synthetic forward preview, manual/automatic timeout and disconnect protections, and clean shutdown. Report: `outputs/ros-tank-overview-bridge-final.log`. An initial watchdog test failed while its fake controller callbacks were not yet initialized after a deliberate timeout; priming both streams before rearming corrected the fixture. The original failed log is retained in `outputs/ros-tank-overview-bridge.log`.

Actual simulator view at spawn:

![[attachments/tank-overview.png]]
