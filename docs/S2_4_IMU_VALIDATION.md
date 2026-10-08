# S2.4 IMU degradation validation

Status: **S2.4 COMPLETE**. The operator-supplied `yaw_bias` live result is recorded below.
`orientation_noise` and repeated IMU trials are deferred to S2.13.

Run one case from the repository root (each command starts a fresh Stonefish):

```bash
./scripts/run_s24_case.sh clean
./scripts/run_s24_case.sh orientation_noise
./scripts/run_s24_case.sh yaw_bias
```

These are separate selectable experiments, not an automatic sweep. Run only the
case you intend to validate. The existing S2.3 clean result remains the historical
reference; the optional clean case here uses zero-degradation IMU transport for a
closer comparison with these runs.

| Case | Orientation noise sigma per body x/y/z axis | Fixed body-z rotation bias |
| --- | --- | --- |
| clean | 0 | 0 |
| orientation_noise | 0.017453292519943295 rad (1 degree) | 0 |
| yaw_bias | 0 | +0.03490658503988659 rad (2 degrees) |

Seed is 42. S2.2 applies independent Gaussian rotation-vector components per IMU
message and right-multiplies the input quaternion by the perturbation quaternion.
The fixed body-z bias approximates a yaw bias when level; it is not an exact
world-yaw offset under arbitrary roll/pitch. Gyro and acceleration degradation
remain zero. These are engineering stress levels, not calibrated real-ocean IMU
specifications. One-degree noise probes varying velocity rotation and attitude;
two-degree bias probes a persistent directional error (about 0.70 m cross-track
over 20 m of straight travel in an open-loop level approximation). Closed-loop
mission behavior can differ from that approximation.

The estimator directly publishes IMU orientation and uses its full quaternion to
rotate DVL-derived vehicle velocity before integrating x/y. Angular velocity is
not integrated into attitude, but all three rate components enter the DVL
lever-arm correction with r=(-0.75, 0, 0.40) m. Thus gyro bias/noise can affect
position even without attitude propagation; it must not be described as inert.
For example, +0.01 rad/s z-rate bias induces +0.0075 m/s body-y velocity error
before rotation. Linear acceleration and IMU covariance fields are unused.
Estimated z is pressure-derived, with no direct IMU contribution.

Routing uses only ROS remapping:

- `/sim/dvl` -> unchanged dead reckoning DVL input.
- `/sim/imu` -> S2.2 degrader -> `/degraded/imu` -> estimator IMU input.
- `/sim/pressure` -> unchanged pressure_depth input.
- `/sim/odometry` -> evaluator only; never used for onboard state.

The runner preserves S2.3's exact executable cleanup, fresh simulator, respawn
followed by sensor enabling, process health checks, cleanup traps, 430-second
mission deadline, eight-second evaluator shutdown deadline and 650-second outer
backstop. It shares the S2.3 lock because both runners own the same processes.
It additionally probes raw IMU/pressure and degraded IMU before the mission.

Requires the existing Docker dev service and installed ROS, Stonefish, workspace,
S2.2 (`/tmp/neptune-s22-install`) and S2.3 (`/tmp/neptune-s23-install`) overlays.
No new ROS executable or installation is required for this shell runner.
Results are retained inside the container under
`/tmp/neptune-s24-results/<case>.<unique suffix>`: conditions, health probes,
node logs, mission-status.txt, outcome-reason.txt, and metrics.json when flushed.
Copy results out before replacing the container. Invalid cases exit with code 2.

Record horizontal/3D RMSE, maximum horizontal/3D error, final horizontal/3D error,
yaw RMSE (radians), accepted/rejected pair counts and mission success/failure.
The runner prints metrics JSON and reports COMPLETE only after the normal mission
completion event and valid position/yaw metrics; timeouts are failures. Failed
runs may still retain partial metrics. COMPLETE is a mission-logic outcome, not
independent proof of physical HOME arrival. Evaluator positions are initially
translation-aligned; yaw error is wrapped and is not initial-bias-subtracted.
Final error means the last accepted pair. Preserve these S2.1 metric semantics.

Single runs and fixed seeds do not establish statistical reliability;
identical ordered inputs/runtime are needed for repeatability. This model is
per-sample orientation perturbation, not physical inertial drift, temporal
correlation or gyro-derived attitude propagation. Existing S2.3 timing, cleanup
and runtime limitations also apply. S2.5 is NEXT; EKF/ESKF is untouched.

## S2.4 completed live result

**S2.4 COMPLETE. Mission: COMPLETE. S2.5: NEXT, not started.**

Operator-supplied live evidence: case `yaw_bias`, fixed IMU body-z orientation
bias **+2 degrees (+0.03490658503988659 rad)**, seed **42**. DVL and pressure
remained raw. Only IMU was routed through the degraded stream:
`/sim/imu -> sensor_degrader -> /degraded/imu -> dead_reckoning_state`.
Orientation noise, gyro and acceleration degradation remained zero.

| Metric | Exact live value |
| --- | --- |
| sample_count | 7185 |
| horizontal_error | 0.012065409590277545 m |
| position_3d_error | 0.016093726452512957 m |
| z_error | 0.010650536256318455 m |
| horizontal_rmse | 0.4430772621576315 m |
| position_3d_rmse | 0.4435698295205001 m |
| depth_rmse | 0.020898167856143065 m |
| max_horizontal_error | 0.634368360456643 m |
| max_3d_error | 0.6357113629012187 m |
| final_horizontal_error | 0.012065409590277545 m |
| final_3d_error | 0.016093726452512957 m |
| yaw_error | 0.03492110364428225 rad |
| yaw_rmse | 0.03497433930756844 rad |
| rejected pairs | 0 |
| Mission | COMPLETE |

The +2 degree bias produced approximately 2 degree yaw RMSE, as expected.
The current dead-reckoning estimator directly uses the IMU orientation quaternion
to rotate DVL body-frame velocity into world coordinates. The orientation bias
therefore produced substantial horizontal trajectory error: approximately
0.443 m horizontal RMSE. The mission still completed successfully.

The small final position error does not mean the trajectory was accurate or
erase the large trajectory RMSE. Error accumulated differently over mission
segments and partially cancelled by the end.

This is single-run engineering evidence only, not a statistical reliability
estimate or calibrated real-ocean IMU performance claim. `orientation_noise` and
repeated IMU trials are deferred to **S2.13**; they are not required to complete
this lean S2.4 task. The existing S2.3 clean result remains historical reference
evidence. No additional mission, test or build was run during this documentation
finalization. S2.5 was not started; no commit or push occurred.
