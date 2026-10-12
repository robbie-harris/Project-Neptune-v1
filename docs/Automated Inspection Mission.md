---
tags: [neptune, autonomy, missions]
date: 2026-10-11
---
# Automated inspection mission

See [[Home]], [[Architecture]], [[Inspection Detector Results]], [[Sensor Errors and Return to Spawn]], and [[Progress]].

## Scope and sequence

This is a **mapped simulator mission**, configured in `Simulation/config/mission.json`, using IMU attitude, pressure depth and DVL dead reckoning. It does not discover a metric pipe map from YOLO boxes. Ground truth is used only for GUI comparison and test measurements, never steering or waypoint selection. Start the simulator at its configured spawn so the existing navigation estimate has a valid origin.

The GUI **Start mapped inspection** button sends `inspect`; **Stop mission**, Space, manual motion, GUI focus loss/disconnect, stale heartbeat, unavailable controller/sensors/camera and mode/optical changes stop autonomous commands. Stopping zeros thrust; existing vehicle momentum can still carry the AUV briefly. No pause/resume checkpoint is implemented: another Start recomputes the route from the current sensor estimate.

1. Face the pipe and confirm it in three distinct fresh YOLO frames.
2. Select the nearest configured pipe endpoint from the current estimated pose and approach a safe standoff viewpoint.
3. Face the pipe and visually confirm arrival. Visit the closer mapped component (valve or flange), then the other, confirming each class before proceeding.
4. Stop at intermediate scan viewpoints at intervals no greater than 0.55 m, then the opposite end. Confirm visible pipe at each stop.
5. Run the existing sensor-only return sequence: initial orientation, translation to spawn, final orientation/settling.

The torpedo rig has surge/yaw/heave but no sway thruster. Lateral scanning therefore uses turn-and-travel legs and facing-the-pipe observation stops. The forward camera cannot keep viewing the pipe throughout sideways travel. The detector/camera must stay healthy during transit; absence of the pipe while facing along the pipeline is expected. No tracking or fabricated observations substitute for a missing detection.

## Configuration and interfaces

Defaults: pipe endpoints `(4.4, ±2.0, 1.5)` m; valve `(4.4, -0.85, 1.5)`; flange `(4.4, +0.85, 1.5)`. Body standoff 1.8 m produces observation X=2.6 m; the forward camera is 0.62 m ahead. End viewpoints are inset by 0.15 m. Bounded cruise target 0.2 m/s; surge/yaw/heave limits 0.5/0.4/0.35; arrival tolerance 0.14 m; overall timeout 900 s; leg/alignment timeout 180 s; visual observation timeout 25 s after heading alignment. These are simulator control settings, not calibrated real-vehicle guarantees.

Mission logic: `src/neptune_sim/neptune_sim/mission.py`; ROS sensor integration/control selection: `operator_state.py`; transport arbitration and watchdog: `bridge.py`; native GUI: `src/neptune_gui/auv_gui.py`. The existing `/neptune/control/return_command` topic carries the selected bounded autonomous thruster commands for compatibility. `/neptune/telemetry` includes `inspection` phase/waypoint/target/visits/reason and combined `autonomy.active`. Only the bridge publishes actuator commands.

Use the evaluated three-class candidate: `bash src/tools/run-inspection.sh --candidate`, with the existing local inference server and GUI. The pipe-only detector cannot confirm valve/flange visits; missing targets time out rather than silently skipping a component. Changing the fixtures or pipe layout requires updating the mission map. Unknown obstacles, SLAM, arbitrary pipe discovery, visual metric localization and real deployment are outside this controller.

Build normally with `bash src/tools/run.sh --build`. For application-only changes when a compatible native image already exists:

```bash
docker build --platform linux/arm64 -f Simulation/docker/Dockerfile.app -t neptune-mission .
```

The full Dockerfile remains required for native dependencies, rendering or asset changes. The mission config is packaged with installed simulator resources.

## Verification checkpoint

Host suite: **58 passed, four ROS-only skips**. Mission tests verify nearest-end/component ordering from both sides, unique/fresh detection confirmations, missing-component timeout, navigation/camera failures, operating envelope, all observation visits before return and cancellation/zero commands. Native Tk start/stop and existing controls passed. An actual GUI disconnect during travel cancelled the controller and resulted in `[0,0,0]` thrust; the diagnostic is `outputs/mission-disconnect.json`.

Full physical sequence verification is running; completion, return errors and any limitations will be recorded below after measurement. It has reached the closest pipe-end observation waypoint. No complete mission outcome is claimed at this checkpoint.

### Completed physical trial

The real Stonefish trial completed **all nine visual observation stops** in **472.04 s (7 min 52 s)**: closest end, intermediate scan, valve, three intermediate scans, flange, intermediate scan, far end, then return. Three distinct fresh correct-class detections were required at each stop. The route trial restarted after the documented GUI-disconnect cancellation, using the current sensor-estimated pose, and returned to the original spawn.

True final position error: **0.02257 m**; true final heading error: **2.597°**. Ground truth supplied these evaluation measurements only; `ground_truth_used_for_control=false`. The complete trial used clear water, natural illumination and lamps on, particles and sensor errors off. Report: `outputs/mission-live.json`; phase log: `outputs/mission-live.log`. No complete noisy/turbid mission outcome is claimed.

The final timeout refinement gives visual confirmation its 25-second budget **after** heading alignment; overall/leg/camera/sensor watchdogs remain bounded. It also preserves a completed mission's display when an idle GUI disconnects. Motion guidance is unchanged from the successful physical trial; these final guard changes passed dedicated tests. Final host suite: **59 passed, four ROS-only skips**. Native Tk progress, start/stop and manual/optics handlers passed. The packaged simulator is reopened at spawn with the mission idle for operator use.

Final readiness gate requires fresh navigation and fresh completed camera inference before enabling Start. An early warmup control probe failed to acknowledge Start; after adding the explicit gate, the final packaged live checks all passed: operator Start/Stop, manual override and heartbeat-loss stop. Reports: `outputs/mission-controls-final.json`, `outputs/gui-mission-controls.json`; final host suite **60 passed, four ROS-only skipped**. The GUI and three-class inspection scene are running with autonomous motion stopped, ready for the operator. Keep the GUI connected and focused during the sequence; a focus loss or disconnect intentionally cancels it. No autonomous motion was left active.

## Perception interruption recovery

The original mission cancelled permanently on the first non-ready detector status or a three-second gap in completed predictions. Camera health was inferred from those predictions, conflating a live camera with delayed inference. This explained why a brief service/rendering delay could terminate inspection; the exact triggering outage in the user's prior run was not recorded.

The controller now observes actual forward-camera image headers independently. Raw camera and completed inference each retain a **3-second freshness limit**. A stale/error condition immediately outputs **zero thrust** and keeps the current phase, waypoint and visits in a recovery hold. The GUI displays **PAUSED** with a specific camera/inference reason. Both streams must deliver fresh data to resume; repeated cached status cannot refresh health or substitute for visual confirmations. Observation confirmations are cleared on recovery. Leg/visual timers exclude the hold, while the absolute 900-second mission deadline remains in force.

If perception does not recover within **25 seconds**, the controller cancels with `Perception recovery timed out: ...` and never restarts itself. Navigation failures, manual override, Stop, focus loss, disconnect and heartbeat loss still stop/cancel immediately. Return-to-spawn remains sensor-only, as before, and does not depend on object detection. Zero thrust does not instantly eliminate vehicle momentum.

Measured fault injection with Stonefish and the actual local inference server passed: zero-thrust hold during a server pause; raw camera stayed fresh; same-waypoint automatic resumption after a brief outage; cancellation on a persistent outage; no restart after recovery following cancellation. Report: `outputs/mission-perception-recovery.json`. **63 host tests passed, four ROS-only skipped**. Motion guidance and observation targets are unchanged from the completed full route; the new recovery paths were tested separately. This improves transient-failure handling without claiming to fix the source of every camera/server stall.
