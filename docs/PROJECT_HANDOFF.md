# Project Neptune — Technical Handoff

## 1. Project goal

Project Neptune is a simulation-first autonomous underwater / marine inspection
robotics stack.

The target mission is:

HOME
→ dive
→ navigate to a subsea asset
→ approach the inspection location
→ inspect / hold
→ turn around
→ return HOME
→ ascend
→ zero thrust / complete

The project is intentionally modular so that simulator components can later be
replaced by real sensors, ArduSub / MAVLink interfaces, and physical hardware
without rewriting the autonomy stack.


# 2. Current development stage

## Stage 0 — perfect simulator state

COMPLETE.

The mission was originally validated using simulator-provided state to prove:

- vehicle command interfaces,
- depth control,
- heading guidance,
- mission-state transitions,
- outbound navigation,
- inspection behavior,
- return navigation,
- ascent.

Stage 0 existed only to prove the full system architecture.


## Stage 1 — sensor-derived onboard state

COMPLETE.

The live autonomy stack no longer requires simulator ground-truth odometry.

Current onboard state comes from:

- pressure sensor → depth,
- IMU → orientation and angular velocity,
- DVL → body-frame linear velocity,
- dead reckoning → horizontal x/y position.

Simulator `/sim/odometry` is reserved for evaluation only.


# 3. Repository architecture

The ROS packages are separated by responsibility.

    src/
      neptune_interfaces/
      neptune_state_estimation/
      neptune_perception/
      neptune_world/
      neptune_autonomy/
      neptune_controls/
      neptune_vehicle/
      neptune_evaluation/
      neptune_sim/
      neptune_bringup/

Responsibilities:

`neptune_interfaces`
    Shared Neptune ROS interfaces.

`neptune_state_estimation`
    Pressure depth estimation, IMU/DVL processing, dead reckoning,
    and future ESKF localization.

`neptune_perception`
    Future asset detection, tracking, and relative localization.

`neptune_world`
    World / environment representation.

`neptune_autonomy`
    Mission executive and high-level autonomy.

`neptune_controls`
    Depth, waypoint, heading, and future asset-relative controllers.

`neptune_vehicle`
    Vehicle-specific actuator interface.
    Current implementation includes the Stonefish adapter.

`neptune_evaluation`
    Metrics, benchmarking, ground-truth comparison, Monte Carlo evaluation.

`neptune_sim`
    Stonefish scenarios and simulation configuration.

`neptune_bringup`
    System launch / integration.


# 4. Canonical interfaces

## State

Canonical downstream state:

    /state/odometry
    nav_msgs/msg/Odometry

Controls and autonomy consume `/state/odometry`.

They should not care whether the state came from dead reckoning, an ESKF,
SLAM, or future real hardware.


## Simulator truth

    /sim/odometry
    nav_msgs/msg/Odometry

IMPORTANT:

`/sim/odometry` is evaluation-only.

It must never feed the live estimator, controller, or mission executive.


## Vehicle command

    /neptune/cmd_body
    geometry_msgs/msg/Twist

Current public convention:

    linear.x   surge
    linear.y   sway
    linear.z > 0   dive
    angular.z > 0  positive yaw


# 5. Current sensor pipeline

## Pressure

Input:

    /sim/pressure

Pressure is converted to vehicle depth.

Approximate calibration:

    rho ≈ 997 kg/m^3
    g   ≈ 9.81 m/s^2

The pressure sensor is mounted approximately 0.40 m above/below the relevant
vehicle reference offset used by the estimator.

The Stage 1 pressure-derived depth baseline reached approximately millimeter to
centimeter-level agreement with simulator truth in the clean Stonefish
configuration.


## IMU

Input:

    /sim/imu

Used for:

- orientation quaternion,
- angular velocity.

The IMU orientation is currently used directly rather than being propagated
from raw accelerometer/gyro measurements.

That is intentionally a Stage 1 simplification.


## DVL

Input:

    /sim/dvl

The DVL has a nontrivial mounting transform.

Current empirically validated DVL sensor-frame to vehicle-frame velocity
conversion is approximately:

    sqrt_half = 0.70710678

    sensor_vx = sqrt_half * (dvl_vx - dvl_vy)
    sensor_vy = -sqrt_half * (dvl_vx + dvl_vy)
    sensor_vz = -dvl_vz

The DVL is offset from the vehicle origin approximately:

    r = (-0.75, 0.0, 0.40) m

Velocity at the vehicle origin therefore accounts for:

    v_sensor = v_origin + omega × r

so:

    v_origin = v_sensor - omega × r


# 6. Current dead-reckoning estimator

Primary implementation:

    neptune_state_estimation/dead_reckoning_state.py

The node intentionally DOES NOT subscribe to:

    /sim/odometry

Inputs:

    /estimate/depth
    /sim/imu
    /sim/dvl

Output:

    /state/odometry

Current state construction:

    x/y          integrated DVL-derived world velocity
    z            pressure-derived depth
    orientation  IMU orientation
    linear twist DVL-derived vehicle velocity
    angular      IMU angular velocity

Horizontal velocity is rotated into the world frame using the full IMU
quaternion before x/y integration.

The estimator uses a local mission frame:

    HOME ≈ (0, 0)


# 7. DVL timing issue already discovered

Stonefish / WSLg currently exhibits periodic timing stalls.

Observed DVL callback gaps include approximately:

    0.5–0.65 s
    followed by
    0.83–0.88 s

These often appear roughly every 30 seconds.

The original dead-reckoning implementation discarded integration whenever:

    dt >= 0.5 s

That produced discrete along-track localization errors.

A 20 m test originally ended with approximately:

    0.391 m final horizontal localization error

The estimator was changed to:

- allow moderate timing gaps below 2 seconds,
- warn for gaps above roughly 0.15 seconds,
- use trapezoidal velocity integration,
- skip only very large invalid gaps.

After that change, the same clean 20 m baseline produced approximately:

    0.007 m final localization error

Do not remove the timing-gap diagnostics without a specific reason.


# 8. Stage 1 full autonomous mission result

Stage 1 successfully completed the complete mission using the sensor-derived
state pipeline:

    WAIT_FOR_STATE
    → DIVE
    → TRANSIT
    → INSPECT
    → RETURN
    → ASCEND
    → COMPLETE

The vehicle:

- initialized at HOME,
- dove to approximately 3 m,
- traveled toward the inspection asset,
- reached the inspection region,
- held for inspection,
- performed approximately a 180 degree return turn,
- navigated back toward HOME,
- ascended,
- entered COMPLETE.

Final estimated position from the validated run was approximately:

    x = -0.403 m
    y = -0.042 m
    z =  0.458 m

Final simulator truth was approximately:

    x = -0.371 m
    y = -0.059 m
    z =  0.448 m

Final estimator-vs-truth error was approximately:

    horizontal ≈ 0.036 m
    3D         ≈ 0.037 m

These are clean Stonefish simulation results and MUST NOT be presented as
real-ocean localization performance.


# 9. Known limitations of Stage 1

The current system is deliberately a baseline.

It does not yet model or robustly handle realistic:

- gyro bias,
- accelerometer bias,
- IMU propagation error,
- DVL measurement noise,
- DVL bottom-lock loss,
- sustained DVL dropout,
- pressure bias,
- sensor latency,
- timestamp jitter,
- ocean current uncertainty,
- global position corrections,
- estimator covariance growth.

The current IMU orientation is also cleaner than what a real underwater vehicle
would generally receive.

Therefore the next stage focuses on robustness and localization.


# 10. Stage 2 goal

Stage 2 asks:

    Can Neptune maintain useful localization and complete the mission when
    onboard sensors are imperfect?

The end-state architecture is expected to move toward:

                 IMU
                  |
                  v
         ESKF propagation
       position / velocity /
       attitude / sensor bias
                  |
          +-------+-------+
          |               |
         DVL           pressure
       update            update
          |               |
          +-------+-------+
                  |
                  v
          /state/odometry

A likely error-state vector is approximately:

    position error       3
    velocity error       3
    attitude error       3
    gyro bias            3
    accelerometer bias   3

    total               15

The ESKF MUST NOT be implemented until the baseline estimator has first been
quantitatively evaluated under controlled degradation.


# 11. Stage 2 work breakdown

S2.1
    Automated localization evaluator.

S2.2
    Configurable sensor degradation infrastructure.

S2.3
    Quantify current dead reckoning under DVL noise/dropout.

S2.4
    Quantify current dead reckoning under IMU noise/bias.

S2.5
    Quantify current dead reckoning under pressure noise/bias.

S2.6
    15-state ESKF structure and state/covariance representation.

S2.7
    IMU propagation.

S2.8
    DVL measurement update.

S2.9
    Pressure/depth measurement update.

S2.10
    Covariance initialization, measurement gating, diagnostics,
    and estimator initialization behavior.

S2.11
    Full mission integration using ESKF state.

S2.12
    Controlled dead-reckoning vs ESKF comparison.

S2.13
    Randomized repeated-run / Monte Carlo evaluation.

S2.14
    Stage 2 cleanup, documentation, final metrics, and tagged baseline.


# 12. CURRENT TASK — S2.1 ONLY

Implement an automated localization evaluation node.

The purpose is to establish objective measurement infrastructure BEFORE
changing sensor models or building an ESKF.

The evaluator belongs in:

    neptune_evaluation

It may consume:

    /state/odometry
    /sim/odometry

This is an explicit exception to the general ground-truth rule because
`neptune_evaluation` exists specifically for offline/runtime evaluation.

Ground truth must not leave the evaluation path.


## S2.1 required behavior

Create a simple ROS 2 Python localization evaluator that:

1. subscribes to:

       /state/odometry
       /sim/odometry

2. waits until both streams have valid data.

3. establishes initial alignment so that the estimator's local HOME frame can
   be fairly compared against simulator truth.

A reasonable alignment is:

    estimator displacement =
        estimator_position - initial_estimator_position

    truth displacement =
        truth_position - initial_truth_position

Then compare those displacements.

4. computes at minimum:

       horizontal position error
       3D position error
       depth / z error
       horizontal RMSE
       3D RMSE
       depth RMSE
       maximum horizontal error
       maximum 3D error
       final horizontal error
       final 3D error
       sample count

5. If orientation comparison is straightforward with current dependencies,
   also compute wrapped yaw error and yaw RMSE.

Do not introduce a large dependency solely for yaw evaluation.

6. periodically prints a concise live diagnostic.

7. prints a final summary on clean shutdown.

8. keeps metric calculation logic testable independently of ROS callbacks.

9. adds focused unit tests for metric accumulation and initial-frame alignment.

10. registers the evaluator as a normal ROS 2 executable for the
    `neptune_evaluation` package.


# 13. S2.1 non-goals

DO NOT:

- modify dead_reckoning_state.py,
- implement an EKF or ESKF,
- inject sensor noise,
- modify Stonefish sensor configuration,
- change mission_executive.py,
- change controllers,
- change `/state/odometry`,
- change the vehicle adapter,
- modify perception,
- begin S2.2.

Do not refactor unrelated code.


# 14. S2.1 validation

At minimum:

    python syntax / unit tests
    package-specific pytest where applicable
    colcon build --packages-select neptune_evaluation

The implementation should also provide a clear command showing how to run:

    localization_evaluator

during a Neptune mission.

Codex should report exactly which files changed and stop after S2.1.


# 15. Development philosophy

Neptune is being built incrementally.

Every sophisticated component must justify itself against the simpler
baseline.

Therefore Stage 2 should eventually enable a fair comparison:

    dead reckoning
        vs
    ESKF

under identical controlled sensor degradation.

Do not optimize metrics by changing the evaluation conditions.

Do not use simulator truth to improve live estimator output.

Ground truth exists only to tell us how wrong the onboard estimator is.


# 16. S2.2 completion record

Sensor degradation infrastructure implemented under `neptune_sim`, with fixed
seeds, copied messages, configurable perturbations, dropout, and ROS remapping.
23 unit tests passed. The preceding-session validation reported by the operator
validated the real Stonefish DVL message path and live +0.5 m/s DVL x-bias
injection. `/sim/odometry` remained evaluation-only. No EKF/ESKF work started.
This appended record preserves the prior history; live checks were not rerun
as part of S2.3.


# 17. S2.3 completion record

**S2.3 COMPLETE. S2.4 is next; do not begin it automatically.** S2.2 completion
in section 16 is preserved. The historical S2.1 task specification above remains
as development history, not the current task assignment.

S2.3 tooling comprises the `neptune_evaluation/dvl_benchmark.py` case preparer,
console registration and focused tests, optional evaluator `result_path` JSON
export, and `scripts/run_s23_case.sh` one-command live runner. Metric semantics,
estimator algorithm and mission/control behavior are unchanged. `/state/odometry`
remains canonical and `/sim/odometry` remains evaluation-only.

## Valid live evidence supplied by the operator

All positions/errors are metres. Noise is independent Gaussian noise on each
original DVL sensor x/y/z axis; seed 42. IMU and pressure remain raw. These are
three single live Stonefish runs, not statistically robust performance estimates.
No additional live mission was run during finalization.

| Metric | clean | noise_low (sigma 0.005 m/s) | noise_medium (sigma 0.020 m/s) |
| --- | --- | --- | --- |
| Horizontal RMSE | 0.06335722984330514 | 0.027414205798626322 | 0.09459194865242691 |
| 3D RMSE | 0.0664469991790655 | 0.03248775363551141 | 0.09597260628137308 |
| Depth RMSE | 0.020026610459220346 | 0.017433171160527203 | 0.016220493413459828 |
| Max horizontal error | 0.4224227192485452 | 0.3886168188233103 | 0.45570213376659047 |
| Max 3D error | 0.42404024159633374 | 0.3904905524168533 | 0.45711741908011977 |
| Final horizontal error | 0.048055024002437496 | 0.005267976601610907 | 0.13869381418106502 |
| Final 3D error | 0.04809153619810318 | 0.005270125609599091 | 0.13869442720587985 |
| Rejected evaluator pairs | 0 | 0 | 3 |
| Mission | COMPLETE | COMPLETE | COMPLETE |

Medium noise demonstrates materially worse trajectory accuracy than low noise
while the mission still completes. A single clean run need not numerically
outperform every noisy run: live Stonefish/DDS timing, input ordering, initial
alignment and closed-loop trajectories vary. These are engineering evidence,
not real-ocean accuracy or statistical reliability claims. Rejected evaluator
pairs are invalid/repeated messages or skew discards, not lost DVL packets.

## Runner architecture and fixes

Run exactly one selected case from the repository root:

    ./scripts/run_s23_case.sh <case>

The host invokes the existing Docker dev service. Inside, a nonblocking `flock`
serializes experiments. Existing installed ROS/Stonefish/S2.2/S2.3 overlays are
required. The runner resolves package executable paths and launches executables
directly, avoiding `ros2 run` launcher PID ambiguity. A Python exec shim restores
SIGINT handling inherited as ignored from Bash background jobs.

Prior nodes and the actual Stonefish executable are identified by exact
NUL-delimited `/proc` argv executable paths (argv[0], or Python argv[1]); process
start-time identity is rechecked before signaling. No broad pkill/regex matches
or shell command substrings are used. Old instances receive bounded TERM/KILL
cleanup before a fresh simulator is launched with the verified scenario:
`/workspace/external/stonefish/Tests/Data/02_port_pipe_mission.scn` and data root
`/workspace/external/stonefish/Tests/Data`, arguments `100 800 600 low`.

Service discovery is bounded at 40 seconds; each discovery command, service
call, and topic probe has its own timeout and kill deadline. GIRONA500 respawns
at (0,0,0), identity orientation, then dynamics, pressure, IMU filter and DVL
are enabled AFTER respawn. Service rejection fails the case. `/sim/odometry`
and `/sim/dvl` must each produce a message within eight seconds, or the runner
aborts with a clear reason.

Launch order: sensor_degrader, stonefish_adapter, pressure_depth,
dead_reckoning_state (ONLY `/sim/dvl:=/degraded/dvl` remapped), evaluator, mission.
All experiment processes are monitored for early exit. The literal
`========== COMPLETE ==========` mission log event ends the experiment;
`MISSION TIMEOUT` is failure even though mission logic also enters COMPLETE.
A 430-second wall mission deadline prevents indefinite waiting.

Evaluator shutdown targets its actual PID with SIGINT and polls for at most
eight seconds, then escalates to TERM (two seconds) and KILL. No unbounded Bash
`wait` is used for evaluator shutdown; forced shutdown is reported as failure.
Metrics must exist as valid JSON with accepted pairs before success is reported.
EXIT/INT/TERM traps shut down experiment nodes, including Stonefish, with bounded
cleanup. Host interruption signals only the exact inner runner argv. A 650-second
whole-run timeout plus 40-second kill deadline provides an outer backstop.

Each case gets a unique `/tmp/neptune-s23-results/<case>.<suffix>` directory in
the container; no previous results are deleted. Logs, health probes, conditions,
mission status, outcome reason and metrics are retained. Completion prints case,
status, metrics path, result directory and a failure reason when unsuccessful.
All seven existing cases remain selectable; there is no automatic sweep.

## Finalization validation (quick checks only)

- `bash -n scripts/run_s23_case.sh`: passed.
- Exact process matcher helper: actual dummy Python executable stopped; a shell
  merely containing its path was preserved. Passed; self-matching review passed.
- Shutdown helpers: graceful SIGINT passed; ignored SIGINT forced termination
  completed within five seconds; nonexistent PID returned immediately. Passed.
- Actual installed evaluator using the runner exec shim on isolated input topics:
  SIGINT stopped it within the three-second test bound and wrote valid metrics
  JSON with zero pairs, as expected without sensor input. Passed; no simulator
  or mission was started.
- Seven case parameter mappings and invalid-case exit code 2: passed.
- ROS-sourced evaluation/degradation pytest: **38 passed in 0.18 s**.
- Python compileall of evaluation and simulation Python modules: passed.
- Selected `neptune_evaluation` colcon build: **1 package finished**, passed.
- `git diff --check`: passed.

Initial host and container pytest collection attempts failed with missing
`nav_msgs`/`sensor_msgs`: the test invocation replaced rather than extended
PYTHONPATH. Preserving the sourced ROS PYTHONPATH fixed the invocation; all
38 tests then passed. Prior combined evaluation/sim build failure on missing
generated Stonefish `package.sh` and successful packaging-only sim build are
historical validation; no new simulator-package change was made here.

## Limitations and deferred work

Runner changes are statically reviewed and helper-tested; the revised complete
Docker/Stonefish startup, service-response formatting, interruption propagation,
mission monitoring and evaluator flush under live mission load remain to be exercised in a future
live run. No startup smoke or long mission was run during finalization. The
existing overlays, Docker access, Linux `/proc`, GNU timeout/flock, and verified
scenario installation are assumed. Cleanup matches the resolved installed
executable paths; unrelated installations/controllers are outside its ownership.
SIGKILL or loss of the container/host cannot guarantee traps or final metrics.
Results live in container /tmp; copy them out before replacing the container.
No bag or full provenance manifest is automatically recorded by this runner;
conditions and logs are retained, and the historical preparer remains available
for additional provenance. Fixed seed reproducibility needs identical ordered
inputs and Python runtime. Evaluator alignment, pair skew and equally weighted
accepted-pair semantics remain S2.1 behavior; final error is the last accepted
pair. COMPLETE is mission logic completion, not proof of physical HOME arrival.

Deferred to **S2.13**: `noise_high` (0.05 m/s/axis), `bias_small` (+0.01 m/s sensor-x),
`dropout_mild` (0.10), `dropout_strong` (0.40), and repeated/randomized trials.
No results are claimed for these cases. These are engineering stress settings,
not calibrated sensor specifications; random dropout is not sustained bottom-lock
loss. Repeated trials belong in S2.13.

Stage 2 progress: S2.1 evaluator implemented; S2.2 COMPLETE; S2.3 COMPLETE;
**S2.4 next, not started**. S2.5 and S2.6–S2.14 are not started; the above stress
experiments are assigned to future S2.13. `dead_reckoning_state.py` has no diff.
No estimator, control, perception, Stonefish source, EKF or ESKF changes were
made. No commit or push performed.


# 18. S2.4 implementation record

**S2.4 COMPLETE. S2.5 is NEXT; do not begin it until explicitly assigned.** Sections 16–17 and all prior work are preserved.
This record supersedes section 17's historical “S2.4 next, not started” status.

## Estimator / IMU dependencies

Inspection of the unchanged `dead_reckoning_state.py` confirms that the full IMU
orientation quaternion directly sets published orientation and rotates corrected
DVL body velocity into world coordinates for x/y trapezoidal integration. IMU
angular velocity does not propagate orientation, but all three rate axes affect
DVL origin velocity via `v_origin = v_sensor - omega × r`, where
`r = (-0.75, 0, 0.40)` m. Gyro imperfections therefore can affect position;
for example +0.01 rad/s z-rate bias adds +0.0075 m/s body-y velocity error before
rotation. Linear acceleration and IMU covariance fields are unused. Estimated z
comes directly from pressure depth, with no direct IMU contribution. Orientation
cases were selected because they directly stress both attitude output and the
world-frame velocity rotation; this is not an inertial propagation experiment.

## Tooling and exact experiment cases

Added `scripts/run_s24_case.sh`, a lean adaptation of the S2.3 runner, and
`docs/S2_4_IMU_VALIDATION.md` with usage, interpretation and limitations.
Run one selected case with `./scripts/run_s24_case.sh <case>`:

- `clean`: zero degradation; optional same-transport reference in addition to
  the existing S2.3 clean evidence.
- `orientation_noise`: independent Gaussian body-frame rotation-vector noise,
  sigma **0.017453292519943295 rad (1 degree)** on each x/y/z axis per IMU message;
  orientation bias zero.
- `yaw_bias`: fixed body-z rotation-vector bias
  **+0.03490658503988659 rad (2 degrees)**; orientation noise zero. This is
  approximately yaw bias when level, not exact world-yaw bias at arbitrary tilt.

S2.2 right-multiplies `q_out = q_in * delta_q`; seed **42**. All gyro,
acceleration, DVL and pressure degradation parameters retain zero defaults.
One-degree noise probes varying attitude/velocity rotation; two-degree bias
probes persistent directional error (approximately 0.70 m over 20 m in a level
open-loop straight-line approximation). These are engineering stress levels,
not calibrated real-ocean IMU specifications or predictions of closed-loop error.

Only estimator IMU is remapped: `/sim/imu:=/degraded/imu`. Raw `/sim/dvl` remains
the estimator DVL input; raw `/sim/pressure` remains the pressure_depth input.
The existing degrader also publishes unused DVL/pressure copies; those outputs
are not routed into the onboard pipeline. `/state/odometry` remains canonical;
`/sim/odometry` remains evaluation-only.

The runner retains fresh Stonefish, exact installed-executable cleanup, respawn,
sensors enabled after respawn, bounded health checks, process monitoring,
cleanup traps, 430-second mission deadline, bounded eight-second evaluator SIGINT
shutdown and 650-second outer backstop. It shares the existing S2.3 runner lock
to serialize ownership of the same processes. Additional probes verify raw
IMU/pressure and degraded IMU availability. Yaw metrics and accepted position
pairs are required before successful completion. Unique container directories
under `/tmp/neptune-s24-results` retain conditions, logs, mission outcome/reason
and evaluator metrics. No sweep is implemented.

Metrics use the unchanged S2.1 evaluator: horizontal/3D RMSE, maximum and final
horizontal/3D errors, yaw RMSE in radians, plus accepted/rejected pair counts.
Mission success/failure is recorded separately; MISSION TIMEOUT is failure.
COMPLETE means mission logic completion, not independent physical HOME arrival.

## Validation and live status

- `bash -n scripts/run_s24_case.sh`: passed.
- Three case mappings and IMU-only routing assertions: passed.
- Invalid case: expected usage and exit code 2, without Docker startup.
- ROS-sourced evaluation and simulation unit tests: **38 passed in 0.19 s**.
- Python compileall of evaluation and simulation modules: passed.
- Relevant `neptune_evaluation` colcon build: **1 package finished**, passed,
  using isolated `/tmp/neptune-s24-{build,install,log}` outputs. The first build
  invocation failed argument parsing because `--log-base` followed `build`;
  correcting it to a global colcon option fixed the invocation.
- Diff/whitespace checks: passed. Estimator source has no diff.

The above checks were performed during tooling implementation. The operator has
since supplied the completed `yaw_bias` mission recorded below. No additional
mission, test or build was run during documentation finalization. Orientation
noise and repeated IMU trials are deferred to S2.13.

## Limitations / Stage 2 progress

The operator-supplied yaw_bias result demonstrates one completed live mission;
it does not establish reliability across all startup, interruption or failure
paths. Existing installed Docker/ROS/Stonefish/workspace/S2.2/S2.3 overlays,
Linux /proc and timeout/flock are assumed.
S2.3 runner limitations remain applicable, including container-/tmp persistence,
no automatic bag, initial translation alignment and timing-dependent accepted
pairs. Final error is the last accepted pair; yaw retains fixed attitude bias.
Per-sample orientation noise is not temporally correlated inertial drift.
One seeded run per case cannot establish statistical reliability, and fixed-seed
repeatability requires identical ordered inputs and runtime.

Stage 2 progress: S2.1 evaluator implemented; S2.2 COMPLETE; S2.3 COMPLETE;
**S2.4 COMPLETE; S2.5 NEXT, not started**.
S2.6–S2.14 remain not started. No estimator algorithm, pressure_depth, autonomy,
controls, Stonefish source or perception changes. S2.5, EKF and ESKF were not
started. No commit or push performed.

## S2.4 startup retry correction

The operator's first live attempt launched fresh Stonefish but failed before
mission start on `/sim/dynamics/set_enabled` timing out. No mission metrics are
claimed from that attempt. `scripts/run_s24_case.sh` now uses a shared 120-second
budget for discovery, respawn and enabling. It waits for `/respawn_robot` and all
four set_enabled services, then retries respawn first, followed in order by
dynamics, pressure, IMU filter and DVL. Each call attempt is bounded to eight
seconds plus a two-second kill deadline (shortened near the shared deadline),
with a one-second retry delay. Only a successful command with an explicit positive
service success response advances to the next service. Waiting/retry messages
identify the service; attempt exit codes and responses are retained in services.log.
Simulator exit still fails immediately; cleanup traps and all later bounds remain.

Validation for this correction: bash syntax and static ordering, timeout, cleanup
and whitespace checks passed. No simulator, startup smoke or mission was run.
At the time of that correction, live responsiveness remained pending. The
subsequent operator-supplied completed yaw_bias result is recorded below;
S2.4 is now COMPLETE and S2.5 remains NEXT, not started.
Estimator code was not modified; no EKF/ESKF work, commit or push.

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


# 19. S2.5 implementation record

**S2.5 COMPLETE. S2.6 is NEXT, not started.** S2.4 remains COMPLETE.
The completed live result below supersedes the historical implementation and
live-pending records retained here, and earlier statements that S2.5 is not started.

Added `scripts/run_s25_case.sh` and `docs/S2_5_PRESSURE_VALIDATION.md` for one
pressure stress case: `pressure_bias=+1000.0 Pa`, seed 42, pressure noise and
dropout zero, all IMU/DVL degradation zero. Optional `clean` selects zero bias;
no sweep is implemented. Run `./scripts/run_s25_case.sh pressure_bias` from the
repository root. No live simulator or mission was run during implementation.

The unchanged pressure_depth computes `P/(997*9.81)+0.40`; +1000 Pa adds
+0.102243530 m to depth / positive-down z. The unchanged estimator takes z
from pressure depth and x/y from DVL integration using IMU orientation.
Horizontal localization has no direct pressure dependence; closed-loop motion
and timing can still vary. This is an engineering stress case, not a calibrated
real-ocean sensor specification. Mission completion was pending at implementation;
the completed live result below resolves it.

Only pressure_depth is remapped: `/sim/pressure:=/degraded/pressure`, yielding
`/sim/pressure -> sensor_degrader -> /degraded/pressure -> pressure_depth`.
Estimator DVL and IMU remain raw. `/state/odometry` stays canonical and
`/sim/odometry` stays evaluation-only, including diagnostic z snapshots.
No estimator, pressure_depth, autonomy, control, Stonefish source or perception
code changed.

The runner retains S2.4 fresh Stonefish, exact executable cleanup, shared runtime
lock, 120-second discovery/respawn/enable budget with bounded service retries,
respawn before dynamics/pressure/IMU/DVL enable, raw and degraded topic probes,
process monitoring, literal COMPLETE detection, timeout rejection, 430-second
mission deadline, bounded evaluator shutdown and cleanup traps. The inner
whole-run backstop remains 650 seconds plus a 40-second kill deadline. Host
Docker startup and exec additionally have 60/700-second bounds with 5/10-second
kill deadlines. Results, conditions, logs, mission status and outcome reason
are retained in unique container `/tmp/neptune-s25-results` directories;
completion prints metrics and the result directory.

Existing evaluator JSON retains horizontal/3D/depth RMSE, maximum and final
horizontal/3D errors, z_error, yaw RMSE and accepted/rejected samples. Crucially,
initial translation alignment includes z, so constant startup pressure bias
cancels in displacement-based z_error and depth RMSE. Those metrics must not be
claimed to demonstrate the absolute 0.102 m offset. Initial/final absolute
estimated and truth z snapshots are retained and printed for independent
inspection. They are sequential, unsynchronized samples, affected by motion
and latency; compare estimate-minus-truth against baseline calibration error
(and optional clean reference). Evaluator semantics are unchanged.

## Quick validation

- `bash -n scripts/run_s25_case.sh`: passed.
- Static two-case, pressure-only routing, startup order, deadline and cleanup
  checks: passed; invalid case returned usage and exit code 2 before Docker.
- ROS-sourced simulation/evaluation unit tests: **38 passed in 0.39 s**.
- Python compileall of simulation/evaluation modules: passed.
- Relevant `neptune_evaluation` colcon build with isolated
  `/tmp/neptune-s25-{build,install,log}` outputs: **1 package finished**, passed.
- `git diff --check`: passed; estimator and pressure_depth sources have no diff.

The initial Docker test invocation was denied access to the Docker socket;
the approved retry ran successfully. No live mission or startup smoke ran.
Full runtime paths and expected absolute depth behavior remain live-pending.
Existing Docker/ROS/Stonefish/workspace/S2.2/S2.3 overlays, Linux /proc, GNU timeout
and flock are assumed. Container /tmp is not durable across replacement; no bag
is recorded. SIGKILL/container loss cannot guarantee cleanup or metrics.
One run is not statistical evidence; COMPLETE means mission logic completion,
not independently verified physical HOME arrival.

Stage 2 progress: S2.1 evaluator implemented; S2.2 COMPLETE; S2.3 COMPLETE;
S2.4 COMPLETE; **S2.5 IMPLEMENTED / LIVE VALIDATION PENDING**;
S2.6–S2.14 remain not started. S2.6, EKF and ESKF were not begun.
No commit or push performed.


## S2.5 pressure transport diagnosis and correction

The operator's pressure-only startup evidence established raw pressure availability
and degrader initialization, yet the mission aborted at the degraded probe.
Inspection of retained failed-run logs identified the actual failure:
`degraded-pressure-health.log` said “Could not determine the type for the passed
topic”. The untyped ros2 echo command exited before discovering the newly created
publisher. Its 20-second enclosing timeout did not wait/retry type discovery.
Cleanup then stopped Stonefish; post-cleanup absence of raw pressure was expected.
The earlier invalid-node-context traceback is consistent with cleanup interrupting
initialization, not proof of a callback implementation bug.

`run_s25_case.sh` now supplies `sensor_msgs/msg/FluidPressure` explicitly for both
raw and degraded pressure checks, keeping the existing 20-second bounded degraded
probe, early-exit detection, degrader log printing, exact cleanup, service retries
and all runtime deadlines. No arbitrary sleeps or sensor_degrader implementation
changes were added. Added a real FluidPressure +1000 Pa callback regression in
`src/neptune_sim/test/test_sensor_degrader.py`; updated the S2.5 validation document.

QoS was verified rather than assumed: Stonefish source constructs the pressure
publisher with the default reliable depth profile; installed degrader source uses
sensor-data BEST_EFFORT input and reliable depth-10 output. A live topic-info smoke
test confirmed raw RELIABLE/VOLATILE -> input BEST_EFFORT/VOLATILE and degraded
RELIABLE/VOLATILE. These are compatible, including downstream pressure_depth.
QoS, DVL/IMU behavior, degradation logic and package dependencies were unchanged.

Short live proof used fresh Stonefish, respawn first, bounded service retries,
raw pressure health, installed degrader with +1000 Pa, topic info, and a
header-matched numerical pair. At stamp (1791563480, 21667172), frame
GIRONA500/pressure, raw pressure was 566.4149137165131 Pa, degraded pressure
1566.4149137165132 Pa, difference 1000.0000000000001 Pa. Container evidence:
`/tmp/neptune-s25-results/pressure_bias.Cxl9HvAU/{pair.json,raw-qos.log,degraded-qos.log}`
and associated logs. The temporary diagnostic exited before launching adapter,
state estimator, evaluator or mission; cleanup stopped simulator/degrader.
TRANSPORT_PROVEN is not mission completion; no metrics.json was expected.

Validation: **39 unit tests passed in 0.27 s**, simulation compileall passed,
`neptune_sim` build passed (one package; installed Stonefish dependency used,
with the expected colcon overlay warning). Bash syntax, static QoS/routing/probe
bounds and whitespace checks passed. Docker socket access initially required an
approved retry. No full mission ran. The corrected runner is ready for the single
future pressure_bias mission. Remaining limitations include live full-mission
behavior, absolute-z snapshot timing, and initial z alignment cancelling constant
bias in evaluator displacement metrics; no mission/depth accuracy is claimed.

Stage 2 progress remains S2.1 evaluator implemented; S2.2–S2.4 COMPLETE;
**S2.5 IMPLEMENTED / LIVE VALIDATION PENDING (pressure transport smoke PASSED)**;
S2.6–S2.14 not started. Estimator and pressure_depth sources have no diff.
No autonomy/control/Stonefish source change, EKF/ESKF work, commit or push.


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
