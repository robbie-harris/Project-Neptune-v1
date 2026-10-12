---
tags: [neptune, autonomy, experiment]
date: 2026-10-11
---
# One minute mission experiment

See [[Faster Mission and View Priority]], [[Automated Inspection Mission]], [[Progress]], [[Home]].

## Requirement and hardware decision

Full sequence, including acquisition and sensor-guided return to spawn, must finish within **60 wall-clock seconds**. A timeout that cancels the mission does not count as success. All four target visits remain mandatory: closest pipe end, closest component, next component, far pipe end. Fresh YOLO confirmation remains required. The controller uses mapped scene coordinates and IMU/DVL/pressure dead reckoning; ground truth is evaluation only.

The existing three-thruster profile is preserved. Five initial fast experiments with the three-thruster layout failed; reports remain in ignored `outputs/fast60-live-1.json` through `fast60-live-5.json`. After these outcomes, the user explicitly approved adding two counter-rotating lateral thrusters to an **experimental** fast rig.

## Experimental configuration

`Simulation/scenarios/inspection_fast.scn` has five native Stonefish fluid-dynamics propellers: port/starboard, heave, forward/rear sway. Equal sway commands provide lateral translation without intentional heading changes. ROS actuator order is port, starboard, heave, front sway, rear sway. GUI manual commands remain three axes; side thrusters are zero during manual operation. Watchdog, disconnect, operator stop, stale sensors and the full-mission deadline stop all five motors.

Main propeller limits: approximately 4,000 RPM; sway: 3,000 RPM; heave: 2,000 RPM. Native first-order rotor time constant: 0.15 seconds. These are simulation design assumptions, **not measurements of Neptune hardware**. Main motor manual command scale is 0.25 to retain the prior nominal RPM range; response dynamics still differ. Geometry, hydrodynamics and mass are otherwise inherited from the inspection rig. Body standoff: 3.8 m; camera standoff at the scan line: 3.18 m. Cruise target: 1.1 m/s. Exact gains and motor origins are versioned in `mission_fast.json` and the scenario. Forward camera, local Roboflow inference, ideal/noisy switch and optical controls are retained.

Holonomic guidance holds the pipe-facing yaw while commanding longitudinal and lateral velocities. Moving confirmations require three fresh class detections near the corresponding waypoint. Return preserves orient-initial, translate-to-spawn, and final-settle phases with heading and position checks. The deadline applies across all phases, including return and perception holds.

## Actual outcomes

First lateral-thruster test confirmed all four visits and entered return at 49.51 seconds, but timed out at 60.04 seconds, still 2.16 m from spawn. It exposed excessive depth-control gain and oscillation. Report: `outputs/fast60-sway-live-1.json`. Failed profiles are not promoted as successful one-minute configurations. Depth damping is being retested; subsequent results are recorded below when measured.

Evaluation hardware: Apple M5, 16 GB RAM; ARM64 Docker Stonefish/Mesa software rendering (8 CPU allocation), local CPU Roboflow Inference server. Fresh GUI transport and inference compete with rendering on this host. No speed or timing claim transfers automatically to real deployment or noisier optical conditions.

Subsequent lateral trials retained as diagnostics:

| Trial | Outcome |
|---|---|
| 2 | 38.38 s: lateral envelope cancellation; depth controller too weak near target |
| 3 | Four targets confirmed by 20.00 s; return oscillation; timeout, spawn error 0.342 m |
| 4 | Four targets confirmed by 20.17 s; residual far-end scan momentum crossed lateral envelope at 22.44 s |

Trial 5 adds a 0.55 m/s sideways velocity target cap, final-visit speed below 0.30 m/s, and separate return tuning. Force-based depth allocation uses signed square-root rotor commands rather than applying position feedback directly as rotor speed. Outcomes remain pending until the full sequence passes. All reports are in ignored `outputs/fast60-sway-live-N.json`.

## Successful tuned profile (measured)

| Run | Views | Full wall time | True spawn error | Final yaw error |
|---|---|---:|---:|---:|
| Trial 5 | Both | 37.28 s | 0.0526 m | 0.087° |
| Repeat | Both | 36.92 s | 0.0518 m | 0.178° |
| Overview-only | AUV display off | 35.93 s | 0.0540 m | See raw report |

All four class-confirmed visits and return were completed in each run. Reports: `outputs/fast60-sway-live-5.json`, `outputs/fast60-sway-repeat.json`, `outputs/fast60-overview-only.json`. Measured peak travel speed was about 0.66 m/s; maximum observed yaw during lateral scan was about 10°, despite holding a zero-yaw target. Return uses gentler gains than inspection, and the far-end visit requires velocity below 0.30 m/s before return begins. Perception remains running while the AUV display is hidden.

The final packaged profile restores the initial roll/pitch settling gate (<0.09 rad) before return translation; a final physical verification follows that packaging change. No real-vehicle hardware timing or performance is inferred from these results. Testing used default clear water, lighting on, particles off, errors off. Under degraded sensing or optical conditions, lack of confirmation can cancel at the global deadline; this is not a guarantee that every condition will complete inspection successfully within a minute.

**78 host tests passed, four ROS-only skipped.** Native Tk controls and both view toggles passed. Live GUI protocol tests passed start/operator stop, manual override, heartbeat timeout and disconnect stop, including the side axis. The native ROS thruster array was confirmed to contain **five zeros** after disconnect (`outputs/fast60-stopped-native-motors.txt`). Existing three-axis manual protocol remains valid; lateral motion is autonomous in this milestone.

## Operating the experimental fast rig

From repository root, in separate terminals:

```bash
bash src/tools/inference-server.sh
bash src/tools/run-inspection.sh --fast
bash src/tools/gui.sh
```

Use **Start mapped inspection** / **Stop mission** in the GUI. The GUI labels the 60 s limit. `--fast` explicitly chooses the five-thruster scenario, its mission profile, and the existing three-class candidate detector. It does not promote that detector as the default model; its prior pipe-regression limitation remains. `--candidate` retains the wider three-thruster inspection rig, and the original tested image `neptune-faster-inspection` remains available. New builds include both scenarios and installed mission resources.

Libraries and versions remain the existing pinned ROS/Stonefish/NumPy/Tkinter/Roboflow stack; no additional dependency was introduced. Lateral rotor placement represents an experimental tunnel-thruster force layout; thruster tunnel flow and real fabrication clearances are not modeled.

## Final packaged verification and stopped state

Final profile passed: **35.63 s** full cycle, **5.18 cm** spawn error, **0.030°** final yaw error. Report: `outputs/fast60-final-profile.json`. This run includes the restored initial roll/pitch settling gate. The verified image is tagged `neptune-perception:latest`; prior application image is preserved as `neptune-perception:pre-fast60` and the tested three-thruster rig as `neptune-faster-inspection`. Simulator and inference were stopped after validation; no mission was left running.

## 1.7 m standoff update

User requested a closer scan line. The fast profile's `body_standoff_m` is now **1.7 m**, placing observation body X at **2.7 m**. This parameter measures body origin to pipe axis; forward-camera axis distance is **1.08 m**, approximately **0.88 m** to the intact pipe surface. The original three-thruster rollback profile remains at 3.0 m because its diagonal lateral passes need greater clearance. The fast rig uses straight sideways translation; it remains inside the existing X<3.6 m operating envelope. Nominal scan line is inside that envelope without changing its bounds.

Thirty targeted route/controller/power tests passed. A physical full-mission check follows. The user's prior optical settings (natural off, lamps on, clear water, particles on), realistic-errors toggle and autonomous power are saved for restoration after testing. The test uses clear ideal defaults at 100% power, so its timing must be distinguished from the user's restored settings.

Closer-range physical check **passed**: all four confirmed visits and return completed in **43.50 s**, true spawn error **3.46 cm**, under ideal clear defaults at 100%. Report: `outputs/standoff-1_7-live.json`. User's 70% setting, realistic errors and optics are restored after resetting to spawn. This test does not establish timing under the restored settings.
