---
tags: [neptune, simulation, sensors, controls, verification]
date: 2026-10-10
---
# Sensor errors and return to spawn

See [[Home]], [[Setup]], [[Architecture]], [[Manual Control and Mobility]], [[Methods and Libraries]], [[Progress]], [[Known Issues and Fixes]], and [[Orientation Deployment Results]].

## Implemented architecture and operation

Stonefish remains the ideal physics/sensor source. Camera, IMU, pressure, DVL, altitude and sonar publishers now use `/neptune/ideal/...`. A new `error_adapter` publishes the existing public `/neptune/...` topics. In ideal mode it passes messages through without modifying bytes, headers or covariance. Realistic mode applies the pinned profile in `Simulation/config/errors.json` upstream of detection and navigation. Queued delayed messages are cleared when switching modes. Ground truth and `/clock` are never corrupted. Static TF and nominal CameraInfo remain unchanged; injected radial distortion and the right-image shift intentionally represent calibration mismatch. Original camera disable services still control the native sensors.

The GUI checkbox **Realistic sensor / camera errors** controls the entire profile. It starts unchecked by default; `realistic:=true` can enable it at launch. Changing the checkbox first stops manual thrust and cancels return. Existing in-flight DDS messages may finish arriving during the transition. Disabling injection does not remove accumulated dead-reckoning drift or eliminate processing latency/frame drops. The normal manual power and hold-to-drive controls remain available.

No new external library was added. Reuse: ROS 2 Jazzy/rclpy/QoS and messages, Stonefish/stonefish_ros2, cv_bridge, OpenCV 4.11.0.86, NumPy 1.26.4, Tkinter, existing Ultralytics/Roboflow inference and Docker. The adapter uses OpenCV remap/filter/blur/warp and NumPy distributions; detection boxes are never artificially altered or invented. The local inference backend still uses camera pixels only and preserves the modified input timestamp.

## Moderate error profile (engineering assumptions)

These values define a calibrated, shallow-tank test profile, not measured specifications of Neptune hardware. Seed 42 is fixed; execution scheduling can change callback order and therefore full-run random samples.

| Sensor / effect | Setting |
|---|---|
| Cameras | Gaussian pixel noise σ=2/255; 3×3 optical blur; angular-rate-scaled horizontal motion blur, exposure 20 ms, capped at 5 px |
| Water/illumination appearance | Red gain 0.94; contrast 0.96; additive backscatter 4/255; exposure variation ±3% |
| Calibration mismatch | Radial remap coefficient −0.015; right image shifted 0.5 px; nominal calibration not corrected |
| Camera missing frames | 1% probability per image |
| IMU attitude | σ=0.15°; biases [0.1,−0.1,0.2]°; yaw drift 0.3°/minute since enabling |
| IMU gyro | σ=0.002 rad/s; biases [0.0005,−0.0005,0.001] rad/s |
| IMU acceleration | σ=0.02 m/s²; biases [0.005,−0.005,0.01] m/s² |
| Pressure | σ=49.05 Pa (~5 mm depth); bias 98.1 Pa (~10 mm); 0.1% missing samples |
| DVL | σ=0.002 m/s; biases [0.0005,−0.0003,0.0002] m/s; 1% velocity scale error; 2 cm altitude noise; 1% missing samples |
| DVL bottom lock | 0.2% loss-event probability per sample; 0.3 simulated-second bursts; invalid velocity covariance and altitude markers |
| Sonar | 10% multiplicative speckle; additive σ=3/255; 0.5% missing images; weak 3%-gain echo shifted three image rows |
| Timing | Requested extra delivery delay 15±5 ms; per-capture timestamp jitter ±1 ms; right-camera offset +6 ms; DVL offset +4 ms |

The sonar ghost is an image-space multipath surrogate, not a calibrated acoustic propagation model. Camera blur, red attenuation and backscatter are approximate post-processing. Physical 3D clutter, damaged pipes, varied object materials, full scattering optics, temperature-driven bias and water currents remain outside this change. Native YOLO misses/false positives/box and confidence errors remain real model outcomes. The old ideal-distribution detection acceptance and poor COU transfer results do not establish accuracy under this new profile.

Context sources: [Water Linked A50](https://www.waterlinked.com/shop/dvl-a50-1248?category=14) specifies approximately ±1.01% long-term accuracy for its standard version; this is not the same as Gaussian sample noise. [Blue Robotics pressure guide](https://bluerobotics.com/learn/bar-sensors-guide/) distinguishes sensor ranges and use; [Bar30 product](https://bluerobotics.com/store/sensors-cameras/sensors/bar-depth-pressure-sensor/?attribute_sensor-operating-pressure-range=Bar02+-+0%E2%80%932+bar+%28~10+m%29) advertises 2 mm depth resolution, which is not absolute accuracy. Our 5 mm noise / 10 mm bias values are explicit test assumptions after zeroing, not claims about raw Bar30 accuracy.

## Telemetry, pose and percentage metric

`operator_state` uses the IMU orientation already provided by Stonefish, body-frame DVL velocities and pressure-derived depth. It initializes position from the known configured spawn, rotates DVL velocity into world NED, removes the 18 cm sensor lever-arm velocity using gyro readings, and integrates X/Y with trapezoidal dead reckoning. Pressure supplies Z. This is a simple prototype estimator, not an EKF, SLAM system, or independent absolute localization sensor.

Ground truth is subscribed only for display/comparison and never overwrites the estimator or enters return guidance. The GUI shows estimated and true XYZ/RPY, speed, pressure, DVL lock, metre/angular errors and return state. Comparison uses latest available readings and therefore includes delivery lag. Ground-truth comparisons become unavailable when reference data is stale.

**Pose accuracy (%) = 100 × [1 − min(1, max(position error / 1 m, attitude error / 15°))].** Position error is Euclidean; attitude error is quaternion geodesic angle. This is a clearly normalized agreement score, not a probability, YOLO confidence, detection recall, or certified navigation accuracy. 100% means matching pose; 0% means at least 1 m or 15° error. Limits are configurable in `errors.json`.

## Return controller

The button invokes a sensor-only sequence: `orient_initial → translate → orient_final → complete`. Initial orientation means configured heading with passive roll/pitch settled within 0.09 rad, and heading tolerance 0.06 rad (~3.4°). Initial alignment commands no surge/heave. Translation uses depth/velocity feedback and bounded differential steering. If spawn is behind the initial heading, it drives in reverse; lateral offsets require steering because this three-thruster torpedo cannot move sideways while holding a fixed heading. Final alignment restores initial heading and requires passive roll/pitch settled within 0.09 rad of their initial values. It never calls respawn or teleports the vehicle.

Settings: 180 s wall-time timeout; 12 cm horizontal and 8 cm depth completion tolerances; estimated speed <0.04 m/s and yaw rate <0.025 rad/s for final completion; maximum surge/yaw/heave efforts 0.5/0.4/0.4. The empty-tank operating envelope is X (−4.4,4.1), |Y|<2.5, Z (0.2,2.8) metres. This is direct tank return guidance, not obstacle-avoiding autonomous mission navigation. Heading/depth/position are closed-loop estimated values, so actual arrival can differ under noise.

Stop/Space, nonzero manual input, GUI disconnect, missing GUI heartbeat (1 s), stale controller output (0.5 s), error-profile change and mission timeout cancel return. IMU, pressure and DVL stream watchdogs retain a 0.75 s wall-time limit. Invalid DVL packets are marked separately; a live stream may bridge at most 0.6 simulated seconds since its last valid velocity, covering the configured 0.3 s lock-loss burst without masking a stopped stream. IMU, pressure, DVL, altitude and ground-truth consumers use sensor-data QoS; one OpenCV thread and a separate bounded image worker keep camera corruption out of navigation callbacks. At most one pending image per stream is processed; busy frames are dropped rather than queued indefinitely. Mode generations prevent previous-profile worker results appearing after a toggle. Zero commands allow physical coasting.

## Verification outcomes

Actual ideal-mode physical return passed all four stages with 0.0334 m ground-truth spawn error and 2.272° final heading error. Manual override and STOP cancellation passed. The error-adapter ROS test proved byte/header identity in ideal mode, changed pixels/timestamps when enabled, exact restoration after disabling, and clean shutdown. Native Tk tests passed toggle dispatch, telemetry text/percentage, return-button dispatch, manual repeat/release/stop/focus protections. Reports: `outputs/operator-features-qos.json`, `outputs/ros-error-adapter-contract.log`, `outputs/gui-operator-features.json`.

Earlier attempts are retained as failed outcomes: a ROS Node property name collision was fixed; reliable high-rate transport produced IMU delivery gaps; the first noisy return reached spawn XY but aborted on a short bottom-lock loss measured against wall time. Sensor-data QoS and separate stream/valid-sample watchdogs address those findings. Further runs still aborted on DVL freshness during final alignment. A delivery diagnostic found native DVL updates steady (maximum 0.112 s wall gap) and adapted sensor delays (pressure gap 0.716 s); source receipt is not proof that the controller receives a current sample. Camera/sonar work was moved to a bounded worker and all navigation scalar streams changed to sensor-data QoS. Limits were not widened. Final noisy physical return passed after the transport fixes (results below). Failed reports remain in outputs/operator-features-realistic.json, outputs/operator-features-realistic-final.json and outputs/operator-features-realistic-worker.json; the diagnostic is outputs/sensor-delivery-diagnostic.json.

### Final verification — 2026-10-10

- Final noisy physical return: **PASS**, all four stages, ground-truth arrival error **0.04073 m** and final heading error **2.199°**. Manual override and STOP cancellation passed. Final estimated/true pose agreement was **97.088%** (position disagreement 0.01939 m, attitude disagreement 0.4368°). This is one tank trajectory, not a statistical robustness guarantee. Report: `outputs/operator-features-realistic-sensor-qos.json`.
- Local suite: **41 passed, 4 skipped**; the skipped modules require ROS on the host and relevant adapter/bridge contracts ran in the container.
- Final ROS contracts: exact ideal → noisy → ideal behavior, clean shutdown, ≥8 FPS synthetic fresh preview, manual timeout/disconnect, automatic controller-output timeout, GUI-heartbeat timeout and return disconnect stop **PASS**. Log: `outputs/ros-operator-features-contracts.log`.
- Native Tk controls: repeat/release, emergency stop, slider binding, focus loss, realistic toggle, telemetry percentage, return dispatch **PASS**. Report: `outputs/gui-operator-features-final.json`.
- Actual simulator ideal stereo/TF/model check: **PASS**, 51 common stereo capture timestamps, current sensor streams, transforms and detector; observed IMU 99.75 Hz, pressure 20.01 Hz, DVL 10.00 Hz, camera ~2.82 wall FPS, simulation real-time factor 1.005. The 10 Hz camera setting does not guarantee 10 wall FPS under Mesa rendering. Report: `outputs/runtime-operator-features-ideal.json`.
- Noisy stationary live smoke check with the GUI open: **PASS**, 57 fresh frames / 20 seconds, 2.859 FPS, 58 latency samples, mean 230.686 ms / p95 order statistic 282.654 ms. Detection present in all 400 observed state packets, which include repeated predictions and must not be counted as independent true positives. Noisy-image labeled recall/false-positive accuracy remains unmeasured. Report: `outputs/noisy-live-smoke.json`; live GUI log: `outputs/gui-operator-features-live.log`.

Evaluation hardware remains the Mac's Apple M5 / 16 GB configuration documented in [[Orientation Deployment Results]], ARM64 Docker with 8 simulator CPU quota, 1 GiB shared memory, Mesa 8 workers, local inference server 4 CPU quota. Camera corruption uses one worker and one OpenCV thread. No detector retraining, promotion or paper architecture changes were made for this sensor/operator milestone.

Final packaged build re-verification, including the completion roll/pitch guard: **PASS**, true spawn error **0.04008 m**, true heading error **2.149°**, normalized pose agreement **96.427%**. Manual override and STOP still passed. Report: `outputs/operator-features-complete.json`. All 41 host checks were rerun after this final guard and passed (4 ROS-only skips).
