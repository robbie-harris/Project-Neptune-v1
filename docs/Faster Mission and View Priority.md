---
tags: [neptune, autonomy, gui, performance]
date: 2026-10-11
---
# Faster mission and view priority

See [[Automated Inspection Mission]], [[Inspection Detector Results]], [[Tank Overview]], [[Progress]], and [[Home]].

## Implemented changes

Mission target cruise speed increases from **0.20 to 0.35 m/s**, with bounded surge authority **0.5 → 0.7**. Body standoff increases **1.8 → 3.0 m**, moving observation X from 2.6 to 1.4 m. The forward camera is 0.62 m ahead, so its direct pipe distance at the observation line is about **2.38 m**. Intermediate observation spacing increases **0.55 → 1.0 m**, yielding five stops: closest end, closest component, intermediate pipe scan, second component, far end.

The AUV has no sideways thruster. Lateral legs now use two shallow diagonal passes: first forward towards the pipe, then reverse away, with commanded body heading limited to **±35°** around the pipe-facing direction. Both legs are planned from the current sensor estimate; an unsafe intermediate X≥3.1 m rejects the leg. Observation headings remain pipe-facing. The wider clearance leaves space for these diagonal movements instead of the previous 90-degree turn/travel/turn maneuver. Cruise settings are control targets, not measured guaranteed speeds.

The GUI adds independent **AUV camera view** and **Tank overview** checkboxes. Disabled feeds stop GUI conversion/PNG transport and show `View off`. Disabling overview also disables its Stonefish camera. Display changes do not cancel the mission. Forward stereo and inference remain active when the AUV display is hidden, so autonomous inspection can continue.

Native priority requests are applied on the graphics thread, with confirmation/error/pending states shown in the GUI. Nominal requested sensor frequencies:

| Views enabled | Forward stereo | Downward / sonar | Overview |
|---|---:|---:|---:|
| Both | 10 Hz | 10 Hz | 5 Hz |
| AUV only | 10 Hz | 2 Hz | Disabled |
| Overview only | 5 Hz | 2 Hz | 10 Hz |
| Neither | 5 Hz | 2 Hz | Disabled |

IMU, pressure, DVL, physics and calibration are unchanged. Stereo cameras retain matching rates and shared capture timing. These requested frequencies are not observed wall-time FPS. Reduced auxiliary rates are deliberate in the single-view profiles; this version does not claim every sensor still operates at its original nominal rate in those profiles.

Code: mission settings in `Simulation/config/mission.json`, shallow transit in `mission.py`, view protocol in `views.py` / `bridge.py`, Tk controls in `auv_gui.py`, native patch `src/tools/patch_views.py`. Full builds apply the patch after optics. `Simulation/docker/Dockerfile.views` rebuilds the changed native/application sources on a previously verified Neptune image.

## Completed verification checkpoint

**70 host tests passed, four ROS-only skipped**. Native Tk checkbox, view-off FPS and priority confirmation checks passed. Actual Stonefish/inference testing passed all four visibility combinations and restoration to both enabled: hidden feeds transmitted zero frames, active feeds continued, and camera/inference readiness remained valid even when both views were hidden.

Twelve-second GUI-transport measurement windows on the Apple M5 / 16 GB host: AUV-only **3.0 FPS**, overview-only **2.83 FPS**, restored both AUV **2.5 FPS** / overview **2.58 FPS**. These are newly transmitted frames, not Tk repaint counts, and the short windows do not establish a guaranteed 5 FPS. Report: `outputs/view-priority-runtime.json`; GUI checks: `outputs/gui-view-controls.json`.

The wider/faster physical mission trial is in progress. Completion, measured speed, actual lateral heading and return accuracy will be appended after its outcome. The simulator and inference server will be stopped again after controlled testing, preserving the user's paused state.

The first physical shallow-pass trial exposed a reverse-leg endpoint overshoot bug: a fixed reverse direction continued away after crossing the goal X, and the 180-second leg timeout cancelled safely. Guidance now selects forward/reverse from remaining X error while keeping the shallow heading limit, allowing recovery after overshoot. A regression test checks the command direction on both sides of the endpoint. The failed trial is preserved as `outputs/faster-mission-overshoot-diagnostic.json`; **71 host tests passed, four ROS-only skipped** after the fix. The repeat physical trial is pending at this checkpoint.

## Completed bounded-profile mission

The corrected five-stop physical run completed in **293.10 seconds**, returned within **2.76 cm** of spawn, reached **0.168 m/s** measured peak travel speed, and reached **37.59°** maximum observed lateral body heading. Commanded cruise speed and heading limits do not guarantee those actual values. Report: `outputs/faster-mission-live.json`. All existing control/watchdog paths and all four display modes were verified. This profile is retained as the tested rollback rig (`neptune-faster-inspection`). It does **not** meet the later one-minute requirement. See [[One Minute Mission Experiment]].
