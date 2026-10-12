# S2.5 pressure degradation validation

Status: **S2.5 COMPLETE**. The operator-supplied pressure_bias mission reached
**COMPLETE**. **S2.6 is NEXT, not started.**

The current estimator sets z directly from pressure_depth, while x/y come from
DVL integration rotated by the IMU quaternion. pressure_depth computes
`depth = pressure / (997 * 9.81) + 0.40` metres. Adding +1000 Pa therefore adds
**+0.102243530 m** to estimated depth (positive-down z). Horizontal estimation
has no direct pressure dependence; closed-loop depth changes may indirectly
change trajectory and timing. The validated pressure_bias mission completed.

| Case | pressure_bias | Pressure noise / dropout | IMU / DVL degradation |
| --- | --- | --- | --- |
| clean | 0 Pa | zero | zero |
| pressure_bias | +1000 Pa | zero | zero |

Seed is 42. This is one engineering stress case, not a calibrated real-ocean
sensor specification. No sweep or estimator algorithm change is included.

Routing uses ROS remapping only:

- `/sim/pressure -> sensor_degrader -> /degraded/pressure -> pressure_depth`
  with `/sim/pressure:=/degraded/pressure` on pressure_depth.
- Raw `/sim/dvl` and raw `/sim/imu` feed dead_reckoning_state.
- `/estimate/depth` feeds estimator z; `/state/odometry` remains canonical.
- `/sim/odometry` is consumed only for evaluation, including diagnostic snapshots.

The completed live case used this command from the repository root:

```bash
./scripts/run_s25_case.sh pressure_bias
```

Optional same-transport reference: select `clean` instead. The runner starts
fresh Stonefish, uses exact executable cleanup and the shared S2.3 runtime lock,
waits for services within a shared 120-second startup budget, retries respawn
first and then dynamics/pressure/IMU/DVL enabling, and probes raw odometry,
DVL, IMU, pressure and degraded pressure. It launches the degrader, adapter,
remapped pressure_depth, raw-input estimator, evaluator and mission executive.
Literal mission COMPLETE is required; mission timeout is failure. Bounds are
430 seconds for the mission, eight seconds for evaluator SIGINT shutdown before
escalation, and a 650-second inner whole-run timeout with a 40-second kill deadline.
Cleanup traps stop owned processes. Individual ROS commands are also bounded.
Host Docker startup is bounded to 60 seconds plus a five-second kill deadline;
the Docker exec client has a 700-second bound plus a ten-second kill deadline.

Inspect metrics.json for horizontal RMSE, 3D RMSE, depth RMSE, maximum and final
horizontal/3D errors, z_error, yaw RMSE (radians), and accepted/rejected samples.
Mission status and outcome reason are retained separately. Metrics and the
unique `/tmp/neptune-s25-results/<case>.<suffix>` container directory are printed.
Logs, conditions and health probes are retained; failed runs may have partial metrics.

**Important metric limitation:** the existing evaluator initially aligns all
three position coordinates. A constant pressure-induced z offset present from
startup cancels in displacement-based z_error and depth RMSE, and need not
produce 0.102 m in those metrics. Preserve those semantics. The runner also
captures initial and final absolute estimated/truth z in `initial-estimate-z.log`,
`initial-truth-z.log`, `final-estimate-z.log`, and `final-truth-z.log`, and prints
them. Compare estimate minus truth and, if available, the clean reference: the
bias should shift absolute depth by approximately +0.102 m above baseline error.
Snapshots are sequential, unsynchronized diagnostic samples; motion and sensor
latency can affect their difference. They are not trajectory RMSE or paired data.

Existing installed Docker/ROS/Stonefish/workspace, S2.2 and S2.3 overlays are
required; Linux /proc, GNU timeout and flock are assumed. Copy container /tmp
results out before replacing the container. No bag is recorded. SIGKILL or
container loss cannot guarantee cleanup or metrics. A single run cannot establish
statistical reliability. COMPLETE means mission logic completion, not independent
proof of physical HOME arrival. Pressure-only startup, transport and cleanup passed
the historical smoke test below. The completed live mission and absolute depth
evidence are recorded at the end of this document. S2.6/EKF/ESKF are not started.

## Pressure transport integration fix

Failed-run `degraded-pressure-health.log` contained “Could not determine the type
for the passed topic”. Untyped `ros2 topic echo` exited before the newly launched
publisher was discovered; a surrounding 20-second timeout is only an upper bound
and does not retry type discovery. Cleanup then interrupted node/simulator startup.
This was a runner probe failure, not evidence of broken degrader callbacks.

The runner now supplies `sensor_msgs/msg/FluidPressure` explicitly to raw and
degraded pressure probes. This lets the bounded degraded probe wait for matching
messages, while process-liveness checks and failure log printing remain active.
No sleeps, QoS changes or degrader implementation changes were needed.

Source inspection and live `ros2 topic info -v` confirmed raw Stonefish pressure
is RELIABLE/VOLATILE, degrader input is sensor-data BEST_EFFORT/VOLATILE, and
output is RELIABLE/VOLATILE, compatible with the unchanged pressure_depth.
DVL/IMU transport and package dependencies remain unchanged. The installed
S2.2 degrader was inspected and used successfully, ruling out a stale reliable
input subscription in this environment.

A short fresh-Stonefish smoke test ran respawn, service retries and pressure
health checks, then stopped after verifying QoS and one timestamp/frame-matched
raw/degraded pair with +1000 Pa bias:

- Timestamp: sec `1791563480`, nanosec `21667172`; frame `GIRONA500/pressure`.
- Raw: **566.4149137165131 Pa**.
- Degraded: **1566.4149137165132 Pa**.
- Difference: **1000.0000000000001 Pa** (floating-point rounding).

Evidence is in container `/tmp/neptune-s25-results/pressure_bias.Cxl9HvAU`:
`pair.json`, `raw-qos.log`, `degraded-qos.log`, health probes and node/service logs.
The temporary diagnostic stopped before adapter/estimator/evaluator/mission
launch; normal cleanup stopped Stonefish and the degrader. Its status is
TRANSPORT_PROVEN, not mission COMPLETE; no evaluator metrics were expected.

Validation: 39 simulation/evaluation tests passed, including a real FluidPressure
callback +1000 Pa/header-preservation regression; simulation compileall and the
neptune_sim package build passed. Bash syntax, static QoS compatibility/routing/
probe bounds, and whitespace checks passed. At that historical point, full
mission validation remained pending; the completion record below supersedes it.


## S2.5 completed live result

**S2.5 COMPLETE. Mission: COMPLETE. S2.6 is NEXT, not started.**
This operator-supplied live result supersedes the historical live-pending records.

Configuration: pressure bias **+1000 Pa**, raw DVL and raw IMU; only pressure
was routed through sensor_degrader to pressure_depth. The theoretical positive-down
depth offset is `1000 / (997 * 9.81) ≈ +0.102 m` (+0.102243530 m).

| Absolute unaligned z snapshot | Estimated z (m) | Truth z (m) | Estimate minus truth (m) |
| --- | --- | --- | --- |
| Initial | 0.558699388317337 | 0.4477515872834421 | +0.1109478010338949 |
| Final (sequential) | 0.5147509147406254 | 0.4434643853366555 | approximately +0.0712865 |

Snapshots are sequential rather than synchronized. The initial absolute comparison
is the primary evidence of the injected constant bias: approximately +0.111 m,
close to the expected +0.102 m. Motion and latency can affect the final sequential
comparison; it is not a synchronized measure of the constant offset.

| Evaluator metric | Exact live value |
| --- | --- |
| sample_count | 6804 |
| horizontal RMSE | 0.015721932513385765 m |
| 3D RMSE | 0.026528776101284453 m |
| depth RMSE | 0.02136812578296526 m |
| max horizontal error | 0.25471932527638036 m |
| max 3D error | 0.2575564823454711 m |
| final horizontal error | 0.009473361170147968 m |
| final 3D error | 0.02222718092917588 m |
| yaw RMSE | 0.00017489360939051805 rad |
| rejected pairs | 3 |
| Mission | COMPLETE |

The evaluator aligns initial position, including z, so its depth RMSE does **not**
represent the full constant pressure offset. Horizontal localization remained
largely unaffected, as expected, and the mission still completed. This is
single-run engineering evidence, not statistical reliability or calibrated
real-ocean performance. Broader pressure noise/bias trials are deferred to **S2.13**.

Stage 2 progress: S2.1 evaluator implemented; S2.2–S2.5 COMPLETE;
**S2.6 NEXT, not started**; S2.7–S2.14 not started, with broader trials assigned
to S2.13. No S2.6/EKF/ESKF work began. Documentation finalization used the supplied
live evidence; no additional mission, tests or builds ran. No commit or push occurred.
