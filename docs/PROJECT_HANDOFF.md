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

Current perception status: **P3 COMPLETE WITH PERCEPTION PROFILE**. The explicit
320x240 software profile is the accepted P3 runtime; ordinary 640x480 visual use
has not passed throughput acceptance. P4 is next, NOT STARTED. Polished rendering
is deferred to P8. See section 26 for commands, retained evidence and validation.
Stage 2 remains complete/frozen through S2.6.

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


# 20. S2.6 completion record

**S2.6 COMPLETE — state/covariance structure only. S2.7 is NEXT, not started.**
This record supersedes earlier historical S2.6-not-started statements.
S2.1 evaluator implemented; S2.2–S2.6 COMPLETE; S2.7–S2.14 not started.
Broader sensor trials remain assigned to S2.13.

Added ROS-independent `neptune_state_estimation/eskf_state.py`, focused pure
unit tests, and explicit NumPy dependencies in setup.py/package.xml. No node,
subscription, publishing, launch integration or existing estimator change.

Nominal state has 16 stored coordinates and 15 degrees of freedom:
`p_WB[3]` (m), `v_WB[3]` (m/s), `q_WB[4]` (unit quaternion),
`b_g[3]` (rad/s), `b_a[3]` (m/s^2). Defaults are zero vectors and identity
orientation. Construction and copy own their arrays; mutable state validation
rejects invalid dimensions, nonfinite values and nonunit edited quaternions.
Quaternion construction normalizes finite nonzero inputs safely.

Exact 15D error order and covariance block order:

    delta_x = [delta_p, delta_v, delta_theta, delta_b_g, delta_b_a]
    delta_p     0:3     world-frame position error (m)
    delta_v     3:6     world-frame velocity error (m/s)
    delta_theta 6:9     body-frame local attitude error (rad)
    delta_b_g   9:12    body-frame gyro-bias error (rad/s)
    delta_b_a   12:15   body-frame accel-bias error (m/s^2)

Frame convention preserves the existing estimator: W is local `world_ned`,
positive-down z, HOME-relative horizontal position; B is `base_link`.
Quaternion order is ROS `[x,y,z,w]`, Hamilton multiplication; q_WB rotates
body vectors into world. Internal v_WB is world-frame velocity, unlike the
existing Odometry body-frame twist. No world/body axis conversion is introduced.
Injection returns a new state: additive p/v/bias corrections and
`q_new = q_WB ⊗ delta_q`. The right-multiplicative delta_q uses the rotation-vector
exponential map (small-angle limit `[delta_theta/2, 1]`) and the result is
normalized. Tests include a nonidentity quaternion to verify multiplication order.

P is 15x15. Initial P is diagonal; each block accepts a scalar variance or
three axis variances. Engineering initialization defaults only, not tuned
real-world values:

| Block | Per-axis default variance | Unit |
| --- | --- | --- |
| position | 1.0 | m^2 |
| velocity | 0.01 | (m/s)^2 |
| attitude error | (pi/180)^2 = approximately 0.00030461742 | rad^2 |
| gyro bias | 0.0001 | (rad/s)^2 |
| accel bias | 0.01 | (m/s^2)^2 |

Initialization requires finite strictly positive variances. Covariance validation
copies inputs and checks dimensions, finiteness, symmetry, nonnegative diagonal
and positive semidefiniteness, with documented 1e-12 scale-relative numerical
tolerance. General validation permits zero uncertainty, unlike initialization.

Validation:

- Focused pure pytest: **49 passed in 0.13 s**.
- Final ROS-sourced package pytest: **49 passed, 2 failed, 1 skipped in 0.29 s**.
  Failures are existing package-wide flake8 (39 issues in untouched modules)
  and pep257 issues in untouched modules; copyright test is skipped by its
  existing missing-copyright-header skip decorator. Initial new-file lint issues were fixed.
  Separate ament_flake8 and ament_pep257 on both new files: passed, no problems.
  No test/acceptance criterion was weakened and unrelated modules were not fixed.
- Python compileall of estimation modules and tests: passed.
- `colcon build --packages-select neptune_state_estimation` with isolated
  `/tmp/neptune-s26-{build,install,log}` outputs: passed, **1 package finished**.
- `git diff --check`: passed. Existing dead_reckoning_state.py and pressure_depth.py
  have no diff. Docker socket denial on validation attempts required approved retries.

Limitations: **ESKF is NOT operational yet.** This is only mathematical structure.
No IMU propagation, measurement updates, gating, filter node, dead-reckoning
replacement, simulator run or mission execution. Bias axes assume future IMU
measurements are expressed in base_link; sensor transforms are future integration
work. Covariance reset/recentering after orientation injection is explicitly
**deferred to S2.8+**. Injection does not modify P and must not be treated as a
complete update with a reset covariance. Defaults are engineering assumptions;
real-world tuning and initialization behavior remain later work. No simulator
truth input exists in this core; `/state/odometry` remains canonical.
S2.7 was not started. No commit or push performed.


# 21. Perception integration P0 / P1a completion record

**P0 audit COMPLETE. P1a optional pipe + flange scene IMPLEMENTED; scene-load
smoke passed, visual appearance and full mission validation not claimed.**
P2 lateral thrusters + lights is next, NOT started. Stage 2 remains S2.1–S2.6
complete/frozen; S2.7–S2.14 not started.

Donor SHA: `608a3b985b8c5dbfc56f5398b8679c8038861bbe`. Exact source
`Simulation/assets/flange.obj` copied byte-for-byte to
`src/neptune_sim/assets/perception/flange.obj`; SHA-256
`ffce7928cbdd8f6c0391600ec601c579f2da1f3eef4dad21a3fdbe4cdb08c55b`.
Wedge geometry is absent from the donor and was not fabricated.

New selectable scene:
`src/neptune_sim/scenarios/benchmarks/03_port_pipe_perception.scn`, derived from
our current `02_port_pipe_mission.scn` (live external copy differs only in
whitespace). Pipe: donor dimensions radius 0.2 m, length 4.0 m; center
(-20, 0, 3.2) m, RPY (pi/2, 0, 0). Flange: center (-20, 0.85, 3.2) m,
RPY (0, 0, 0), scale 1; mesh bore already aligns with Y. Added one flange look,
using existing Aluminium material. Existing support legs and inspection panel
remain; supports lie beyond the shorter pipe ends. Mission target coordinates,
HOME/dock and route are preserved.

setup.py installs the new scene and mesh under share/neptune_sim. Flange uses
supported `$(find neptune_sim)` package lookup; existing Girona include and
assets retain the original Stonefish data root. No absolute donor/Mac path.
Vehicle mass/inertia/buoyancy, all sensors, five actuators and ordering, adapter,
controls, autonomy, localization, evaluation, and /neptune/cmd_body are unchanged.
Original scenarios and runners are untouched; /sim/odometry remains evaluation-only.

Validation: XML parsing, donor byte equality, 1008 vertices/1008 normals/1920
faces, no MTL dependency, 19 resolved asset/include references, semantic baseline
comparison excluding fixture changes, Python compile checks, neptune_sim colcon
build (one package), installed resource equality/checksum, and git diff --check
passed. Build used installed Stonefish dependency with expected overlay warning.
Initial semantic comparison incorrectly compared XML indentation tails; ignoring
whitespace confirmed preservation. No product change was needed for that check.

Single isolated 20-second Stonefish-only smoke loaded both flange meshes, built
GIRONA500/five motors, and reached Ready for running, without missing-asset/XML
errors. Nonfatal SDL2 unsupported-operation error and propeller texture channel
warning were logged. Shutdown exceeded the five-second SIGINT grace period and
was forced (exit 137); afterward no simulator process remained. Screenshot
capture was unavailable, so visible fixture appearance remains operator validation.
No full mission, autonomy, perception, sweep, or P2 work ran. Dynamic clearance
and mission completion in the new scene are not validated. No commit or push.
See docs/PERCEPTION_INTEGRATION.md for exact launch/build and rollback commands.


# 22. Perception integration P1b completion record

**P1b IMPLEMENTED — optional environment now contains pipe, flange, and valve,
the donor's three eventual detector categories.** Operator confirmed P1a pipe
and flange visually; prior valve/handwheel absence was intentional. Model weights
and detector remain NOT integrated. P2 lateral thrusters + lights is next, NOT
started; Stage 2 remains complete/frozen through S2.6; S2.7 not started.

Copied exact `Simulation/assets/valve.obj` from donor SHA
`608a3b985b8c5dbfc56f5398b8679c8038861bbe` to
`src/neptune_sim/assets/perception/valve.obj`, without modifying mesh bytes.
SHA-256: `a5e079de7ad15b55231f4fe7b97462e3e2c2c661da24a4b883921515c8fd4faa`.
setup.py now installs valve.obj alongside flange.obj. Portable package lookup
`$(find neptune_sim)/assets/perception/valve.obj` resolves both physical and visual
mesh references in `scenarios/benchmarks/03_port_pipe_perception.scn`.

Donor scenes/generator put valve at Y=-0.85 and flange at Y=+0.85 relative to
pipe center. Reproduced here: pipe (-20, 0, 3.2), flange (-20, +0.85, 3.2),
valve (-20, -0.85, 3.2) m; valve RPY (0, 0, 0), scale 1. Body follows Y and
intentionally surrounds pipe as inline housing; stem points upward along -Z
in NED, with wheel center Z=2.58 m above pipe top Z=3.0 m. Valve/flange mesh
Y bounds do not intersect; centers are separated by 1.7 m. No fabricated
connectors or wedge: wedge remains absent from donor. Future forward view is
plausible; actual camera FOV/occlusion testing awaits camera integration.
Added only the valve and its donor blue look using existing Aluminium material.
Vehicle, five thrusters/order, lights, controls, autonomy, estimator, camera,
perception code, GUI, and baseline scene remain untouched. Ground truth remains
evaluation-only. P1a scene placement is preserved.

Validation: byte-exact donor copy; finite vertices/nonzero normals and valid face
vertex/normal indices (1814 vertices, 1814 normals, 3608 faces); no MTL dependency;
XML parsing; 21 resolved scene/include resources; P1a scene structure preserved
except new valve/look; valve/flange bounding separation and handwheel height;
selected neptune_sim colcon build (one package); installed scene and both meshes
byte-equal to source; and git diff --check passed. Build used the installed
Stonefish overlay with the expected workspace-dependency warning.

Single isolated 15-second simulator-only smoke loaded both collision/visual valve
and flange meshes, built Girona, and reached Ready for running. No missing-asset
or XML error. The same nonfatal SDL2 unsupported-operation diagnostic and
propeller texture-channel warning as P1a occurred. TERM did not exit within the
three-second grace period; timeout forced termination (137). No simulator process
remained. Visual valve appearance was not independently verified; operator visual
confirmation remains pending. No mission or perception ran.

Limitations: mesh/scene geometry is validated statically, but final valve visual
appearance and camera visibility need operator confirmation. Intentional inline
body/pipe overlap matches donor geometry; no CAD boolean union was performed.
No full mission validation. Launch/build command is updated in
`docs/PERCEPTION_INTEGRATION.md` to use /tmp/neptune-p1b-install.
No P2 work, commit, merge, cherry-pick, or push.


# 23. Perception integration P2 implementation / validation record

**P2 implemented: Girona lateral pair and inspection lamps.** Focused tests,
builds, resource checks, and headless native actuation passed. Full graphical
actuation remains unvalidated due native ROS service/command stalls (failed
checks retained below). P3 camera is next, NOT started. Stage 2 remains frozen
through S2.6; S2.7–S2.14 not started.

Optional scene now includes installed scenarios/neptune_girona_perception.scn,
a separate copy of baseline Girona plus additions. Original Girona and baseline
port-pipe scene are unchanged. Original body/sensors/first five motor XML blocks
are identical; no new mass/buoyancy/collision/hydrodynamic body parts. No autonomy,
controls, localization, camera, perception runtime, Roboflow, GUI, or evaluation
infrastructure changes. /neptune/cmd_body remains the sole motion input and
/sim/odometry remains evaluation-only.

Ordering: 0 SurgePort, 1 SurgeStarboard, 2 HeaveBow, 3 HeaveStern, 4 Sway,
5 SwayFront, 6 SwayRear. New XYZ/RPY (metres/radians): front
(0.75,0,0.05431)/(0,0,pi/2); rear (-0.89647,0,0.05431)/(0,0,pi/2).
Computed unchanged Girona CG ~(-0.07323476,0.00026649,0.05430864) m gives equal
opposite ~0.823235 m longitudinal pair arms. Propeller disks clear hull/camera;
mount supports/tunnel effects are not modeled. Mass 143.146 kg and native
principal inertias 95.384/126.947/135.515 kg m² remain unchanged.

Donor parameters (SHA 608a3b985b8c5dbfc56f5398b8679c8038861bbe) adapted to Girona:
0.12 m diameter, max 314.16 rad/s normalized, forward/reverse kt 0.48, kq 0.05,
first-order rotor constant 0.15 s. Existing propeller mesh scaled 2/3; front
right-handed/not inverted, rear left-handed/inverted. Native local +X force
rotates to body +Y; inversion/handedness give matching positive thrust and opposing
reaction torque. Pair yaw moments nominally cancel; historical motor 4 is retained.

Adapter read-only startup motor_count defaults to 5, accepts only 5/7. C=clip to
[-1,1]: legacy [C(surge-yaw),C(surge+yaw),C(-heave),C(-heave),C(sway)]; seven mode
appends [C(sway),C(sway)], preserving outputs 0–4 exactly. All seven watchdog and
shutdown outputs zero. Shutdown signal handling corrected after observing old
ROS-context invalidation before final zero publication. Baseline mapping and
0.5 s timeout remain. Packaging installs the optional robot include; vehicle
package declares rcl_interfaces for the read-only parameter descriptor.

InspectionLightPort/Starboard XYZ (0.76,-0.24,0.5)/(0.76,+0.24,0.5), both
RPY (pi/2,0,pi/2), white, 800 lux, 0.015 m radius, 90° full cone. Optical +Z
maps to body +X; camera unchanged. Static cone geometry covers fixture centers
at inspection standoff (nearest lamp to valve/flange 42.57° <45°). Actual lit
appearance/shadows are not verified; daylight/original Omni remain present.

Validation: 17 focused adapter tests passed in both modes, exact historical
output, clamping, readonly mode, watchdog, and shutdown. Initial fixture cleanup
errors were corrected; no acceptance weakened. Python compile checks passed;
neptune_vehicle/neptune_sim colcon builds passed (2 packages, installed Stonefish
overlay warning). XML/resources (23 references), installed equality, baseline
vehicle preservation, CG balance, rotor clearance and light cone checks passed;
git diff --check passed.

Graphical scene loaded seven thrusters/lights with unchanged Girona physics.
At 800x600 and 320x240 native service requests stalled; one test delivered seven
ROS values but sampled zero native thrust/no useful sway. **Graphical actuation
checks failed/incomplete**, not counted as successful motion validation.
Render/executor starvation is suspected but unproven. Nonfatal SDL2 unsupported
operation and texture-channel warnings persisted. Bounded cleanup killed native
graphical processes; no owned processes remained. No simulator-source/renderer
changes were made to work around this.

A temporary physics-only derivative removed graphics sensors/lights, preserving
body/motors/world/fixtures. Two four-second +/-0.22 pure sway pulses at inspection
position/yaw pi passed: body lateral displacement +0.15718/-0.15407 m; yaw
-0.09904/+0.08339 degrees. Added front/rear native thrust +11.494/+11.472 N and
-11.494/-11.474 N. Live legacy output matched exactly; watchdog and SIGINT
shutdown published seven zeros; watchdog native setpoints also zero. Motion
truth was evaluation-only, never used to generate commands. Pure sway supplied
no depth trim, so vehicle rose ~0.26 m; no inspection/mission claim. Headless
results do not establish graphical mission readiness.

Evidence in container /tmp/neptune-p2-smoke-result.json, physics/simulator and
adapter logs. Full graphical actuation, actual lamp illumination, hardware
mount feasibility and future alignment tuning remain limitations. Pipe/flange/
valve retained; wedge absent and not fabricated. Model/detector remain absent.
See docs/PERCEPTION_INTEGRATION.md for complete mapping, launch/build commands,
legacy rollback and runtime limitations. No P3, mission, perception, GUI,
commit, push, merge or cherry-pick.


# 24. Perception integration P3 camera record — rate requirement NOT passed

**P3 camera implemented and visually verified; NOT declared complete.** Stable
approximately 10 Hz images have not been established. P4 is next only after
resolving stream performance/freshness, NOT started. Stage 2 remains frozen
through S2.6; S2.7 not started. Prior P2 physics validation and graphical limits
remain recorded. No detector/Roboflow/alignment/GUI integration, mission or commit.

Read AGENTS.md, this entire handoff, and PERCEPTION_INTEGRATION.md before editing.
Added only to optional perception Girona: XML sensor inspection_camera_optical_frame,
XYZ (0.82,0,0.20) m, RPY (pi/2,0,pi/2); optical +Z points body +X, image right/down
align with body +Y/+Z. Lens clears hull, front propeller, and lamps. Initial
(0.40,0,-0.16)/110° mount was rejected after bow hardware appeared in its image.
Final 145° HFOV fits separated valve/flange at unchanged 1.5 m body-origin
standoff. Resolution 640x480, nominal 10 Hz, rendering range 0.05–20 m, rgb8,
1920-byte rows. Wide optics differ deliberately from donor SHA
608a3b985b8c5dbfc56f5398b8679c8038861bbe's 80° torpedo reference.

Native topics /neptune/camera/inspection/image_color and
/neptune/camera/inspection/camera_info, both header.frame_id
GIRONA500/inspection_camera_optical_frame. No frame override/relay: native source
overrides Image only, so defaults keep Image and CameraInfo consistent.
Received K: fx=fy=100.8956124412747 px, cx=320, cy=240; P agrees, R identity,
plumb_bob D=[0,0,0,0,0]. Matched image/info stamps advance monotonically, but
native stamps are readback/publication wall time, NOT validated true capture
instants; no clock/timestamp patch or rewrite.

Measured publisher QoS (image and info) RELIABLE/VOLATILE; RMW reports history
UNKNOWN/depth 0, while source declares depth 10. Probe matched reliable QoS.
No arbitrary publisher-QoS change. Future P4 must honor freshness and these optics.

New optional perception_camera.launch.py installs with neptune_sim, launches
simulator plus two static TF publishers only. base_link -> inspection_camera_link
translation (0.82,0,0.20), identity; link -> qualified optical frame rotation
(pi/2,0,pi/2), quaternion (0.5,0.5,0.5,0.5). Live TF check passed after correcting a depth-one diagnostic subscriber queue
that dropped one of the two latched messages. No truth/state
input or world/body pose publisher. Added launch/TF/image_view dependencies;
standard viewer installed in dev container, not launched during this turn.
Optional explicit software_rendering flag defaults false; baseline environment,
Dockerfile and native simulator sources remain untouched.

Static validation/build passed: XML/resources, semantic preservation of all
existing sensors/lights/actuators/body, Python/launch compile, neptune_sim colcon
(one package, installed Stonefish overlay warning), installed resource equality,
launch argument parsing, live static TF and git diff --check. Original camera,
its transforms/topics, all seven motors, lamps, autonomy, localization, controls
and mission coordinates are unchanged. Baseline scene remains untouched.

Camera smoke **rate gate FAILED**, not weakened: hardware WSLg D3D12 on RTX 4080
Laptop/Mesa 24.0.5 advertised camera but yielded no received image within 20 s,
including matched-QoS and OpenGL 4.5 diagnostic retries. Explicit llvmpipe software
mode (8 threads, 320x240 preview) delivered images/info but final actual-scene
measurement was 3 images/~8 s (0.375 Hz), max stamp gap 3.916 s, final age 3.32 s.
Fixed inspection diagnostic delivered 8/~8 s (0.998 Hz), max gap 0.948 s.
No 10 Hz or full-runtime readiness claim. Some processes needed forced bounded
cleanup; none remain. SDL2, texture-channel and class-loader warnings recorded.

Temporary fixed-pose view at (-18.5,0,3), yaw pi, enabled legacy sensors in /tmp
copies only; repository spawn/dynamics/service defaults untouched. IMU/DVL ~20 Hz,
pressure ~5 Hz; original 1360x1024 camera delivered nine frames/~8 s. Inspection
frames visibly show pipe/flange/valve/handwheel with no bow/lamp obstruction or
severe glare/clipping; no saturated pixels. Single retained temporary image
/tmp/neptune-p3-inspection.png (initial rejected image overwritten, no repo image).
Inspection-lamps-on mean intensity 120.261/255 versus 119.697/255 with those lamps
removed in a test copy, mean absolute difference 0.760/255. Contribution modest;
Omni/daylight/particles remain, so headlights-only performance is not established.
No lamp redesign. Wedge remains absent; model/detector still not integrated.

Detailed commands, rollback and limitations in docs/PERCEPTION_INTEGRATION.md.
Camera stream/renderer issue remains unresolved within P3; do not automatically
start P4 or claim P3 complete. No autonomy, estimator, actuation, GUI, donor,
commit, push, merge or cherry-pick changes.


## P3b control-camera diagnosis — BLOCKED (2026-10-12)

**P3 remains BLOCKED; P4 was not started.** The paired control establishes a
shared Stonefish/WSLg rendering-path limitation in this runtime, rather than a
defect unique to the inspection camera. Live camera diagnostics stopped after
one hardware and one software run, well inside the ten-minute budget. No
configuration, simulator source, driver, Docker, perception, control, autonomy,
estimator, actuation, GUI, or mission changes were made. No commit or push.

### Paired measurement

Both cameras ran simultaneously in the same prior P3 temporary fixed-pose scene:
Girona (-18.5,0,3), yaw pi, fixed body; legacy sensor enable-service entries
removed in the /tmp copy so both cameras were enabled. Sensor specifications,
world, fixtures, lights and graphical sensors were otherwise retained. No
services or actuator commands were needed. Simulator arguments: 100 Hz physics,
320x240 preview, low graphics. Each run used 12 seconds startup followed by a
20.012-second measurement window; rates are counts divided by the entire window.
RELIABLE depth-10 diagnostic subscriptions matched both RELIABLE/VOLATILE native
image publishers. The original camera is disabled by its enable service in the
repository's normal startup; its control measurement here is explicitly enabled.

| Renderer | Existing /sim/camera/image_color | Inspection image_color |
| --- | --- | --- |
| D3D12 RTX 4080 Laptop, Mesa 24.0.5 | 0 frames / 20.01196 s = 0 Hz | 1 frame / 20.01196 s = 0.04997 Hz |
| llvmpipe LLVM 17.0.6, Mesa 24.0.5, 8 threads | 19 frames / 20.01169 s = 0.949445 Hz | 19 frames / 20.01169 s = 0.949445 Hz |
| Software maximum interarrival gap | 1.216205 s | 1.194253 s |
| Software maximum message-stamp gap | 2.672112 s | 2.676802 s |

The single hardware inspection image means hardware was not literally zero in
this fixed-pose rerun; it still has no usable sustained stream. No hardware
interframe gap can be calculated from one image. Earlier normal-scene hardware
zero-image/20-second result remains valid historical evidence. Earlier software
inspection rates were 0.375 Hz normal spawn and 0.998 Hz fixed pose; this paired
fixed-pose result is the final measurement, with no intervening fix. Stamp gaps
and receipt gaps are reported separately; wall-clock publication stamps and
queued delivery are not physical capture timestamps. Both software streams'
received stamps strictly increased. These short windows do not prove long-term
reliability.

### Configuration and source comparison

| Setting | Existing Girona camera | Inspection camera | Donor forward CameraLeft/Right |
| --- | --- | --- | --- |
| Sensor / native renderer | camera / ColorCamera / OpenGLRealCamera | same | camera (same native path before donor patches) |
| Rate | 10 Hz | 10 Hz | 10 Hz |
| Resolution | 1360x1024 | 640x480 | 640x480 |
| Horizontal FOV | 55 degrees | 145 degrees | 80 degrees |
| Near/far clip (m) | native defaults 0.02/100000 | 0.05/20 | 0.05/20 |
| XYZ (m) | (0.5,-0.12,0.5) | (0.82,0,0.20) | (0.62,-0.06/+0.06,0) |
| RPY (rad) | (0,0,1.571) | (pi/2,0,pi/2) | (pi/2,0,pi/2) |
| Enable state on repository startup | disabled: /sim/proscilica/set_enabled | enabled: no enable service | enable service; donor native patch starts enabled |
| Native name/frame | GIRONA500/proscilica | GIRONA500/inspection_camera_optical_frame | Neptune/CameraLeft or CameraRight |
| ROS topic prefix | /sim/camera | /neptune/camera/inspection | /neptune/ideal/camera/left or right |
| XML frame override | none | none | qualified camera name |

Both local cameras use the same bridge branch: advertise image_color, create
camera_info, install ColorCameraImageReady. Queue size is ceil(sensor rate)=10;
measured QoS is RELIABLE/VOLATILE. No renderer selector or readback-disable option
is present in either XML. Native ROS2ScenarioParser explicitly disables sensors
with enable services; their entries were absent in the measured temporary copy.
Inspection is enabled without that service. Native CameraInfo uses the sensor
name; leaving the inspection Image frame override absent keeps headers consistent.

Native ColorCamera initializes OpenGLRealCamera for both sensors. Its DrawLDR
reads RGB texture into a pixel-pack buffer with glGetTexImage; UpdateTransform
maps that PBO with glMapBuffer and invokes NewDataReady only for a non-null
mapping. The common pipeline queues non-continuous views and normally schedules
one queued view per render in addition to continuous views. These are relevant
shared bottlenecks, **not proof of a specific failed GL call or driver defect**.
Logs reached Ready for running without missing camera resources/XML errors;
existing SDL2 unsupported-operation and texture-channel warnings persisted.
Renderer identities were independently checked with glxinfo under each run's
environment. No detailed GPU timing or GL-error instrumentation was performed.

Donor SHA 608a3b985b8c5dbfc56f5398b8679c8038861bbe inspection_fast/inspection_tank
camera XML and tools/patch_stonefish.py, patch_views.py, patch_optics.py were
read only. Donor changes include rendering all pending views, particle controls,
clock/capture stamping, bounded physics catch-up and altered enable defaults;
none were applied. They do not by themselves prove a D3D12 readback fix.

### FOV decision and validation

FOV remains **145 -> 145 degrees**, resolution **640x480 -> 640x480**; exact
configuration change: **none**. Prior P3 widened the FOV to fit separated fixtures
at the unchanged 1.5 m body-origin standoff (lens-to-axis 0.68 m). Fixture centers
are approximately atan(0.85/0.68)=51.3 degrees off axis: an 80-degree horizontal
view would exclude both centers at that pose. An 80-degree view may be preferable
for later detection with a revised viewing distance, but is not established as
a throughput fix. Equal ~0.95 Hz control/inspection rates and hardware failure
of the control trigger the explicit platform-limit stop condition; no FOV tuning
or workaround was implemented.

Actual software inspection Image and CameraInfo dimensions were 640x480, frame
GIRONA500/inspection_camera_optical_frame. Received K remains
fx=fy=100.8956124412747 px, cx=320, cy=240 (not manually assigned). Existing
CameraInfo was 1360x1024 with fx=fy=1306.267846340393, cx=680, cy=512.
The unchanged two-edge static TF passed a fresh bounded live check, including
translation (0.82,0,0.20) and optical quaternion (0.5,0.5,0.5,0.5).
The retained prior P3 image /tmp/neptune-p3-inspection.png was re-inspected:
pipe/flange/valve/handwheel visible, no hull/lamp obstruction. Visibility was
not freshly captured in P3b; this is retained-image evidence with unchanged optics.
All repository sensors remain unchanged. Both probe simulator processes were
stopped with bounded cleanup; no simulator remained afterward.

Validation outcome: **FAIL** (<5 Hz and multi-second stamp gaps; hardware has no
sustained stream). TF and dimensions/CameraInfo checks passed. Only documentation
changed, so no ROS package rebuild was necessary. git diff --check passed.
Evidence is temporary container /tmp/neptune-p3b-{probe.py,result.json,hardware.log,
software.log}; numeric results are retained here because /tmp is not durable.

Remaining blocker: a rendering/runtime path that sustains at least 5 Hz with
maximum gap below 0.5 s (preferably >=8 Hz without multi-second gaps). The exact
low-level D3D12 stall remains unresolved; the proven diagnosis is shared runtime
scope, not a specific driver or PBO failure. Smallest next recommendation is a
bounded comparison on another supported accelerated runtime (for example native
Linux), using unchanged camera XML. Alternatively, separately assess the donor's
narrow view-scheduling patch; do not import its unrelated clock/optics changes.
Lower-rate perception requires explicit acceptance and a freshness policy; none
was accepted or implemented here. P4 remains NOT STARTED. Stage 2 remains frozen
through S2.6; S2.7–S2.14 were not started.


# 25. Perception integration P3c native camera investigation — BLOCKED

**P3c exhausted its two-candidate limit without a passing fix. P3 remains BLOCKED;
P4 NOT STARTED.** No normal-build patch integration, final integration benchmark,
full mission, commit or push occurred. Stage 2 remains complete/frozen through
S2.6; S2.7–S2.14 not started. The complete per-hunk donor audit and exact candidate
patches/results are recorded in `docs/PERCEPTION_INTEGRATION.md` (P3c section).

Read AGENTS.md, the complete handoff, perception integration documentation, and
all three donor scripts at lumyn/Perception SHA
608a3b985b8c5dbfc56f5398b8679c8038861bbe. Donor and Neptune both pin Stonefish
b21eb8e194c570ff2f61e91aeffb38d73dc25f42 and stonefish_ros2
6646e7ac25eed982f37f807abc7b545dbd2d6648. Installed/local camera sources match
upstream; only the pre-existing two FLS overrides modify installed SF, and ROS
sources have no diff. All donor hunks are absent locally.

Audit: patch_stonefish modifies SF OpenGLPipeline.h/.cpp, SimulationManager.cpp,
ROS ROS2ScenarioParser.cpp, ROS2SimulationManager.cpp, ROS2Interface.cpp,
CMakeLists.txt and package.xml: capture/publication stamps, pending-view scheduling,
particle suppression, bounded clock catch-up, monotonic pacing, /clock and startup
sensor enable defaults. patch_optics modifies SF OpenGLAtmosphere.h/.cpp,
atmosphereApi.glsl, GLSLShader.cpp, OpenGLPipeline.h/.cpp and ROS
ROS2SimulationManager.cpp: lighting/water/particle controls, release diagnostics,
instance metadata and donor-specific sensor startup/services. patch_views modifies
SF OpenGLPipeline.h/.cpp and ROS ROS2SimulationManager.cpp: donor-specific
camera/downward/sonar/overview rates, selection and feedback endpoints.
**No donor hunk changes camera framebuffer/PBO readback.** Donor documentation
motivates scheduling by stereo capture timing, explicitly acknowledges below-10-Hz
software delivery, and uses llvmpipe because its Mac Docker GPU is unavailable;
it contains no demonstrated WSL D3D12 fix. All clock, startup, optics, GUI/view,
auxiliary-rate and vehicle-specific changes were rejected as unnecessary or
unsupported by evidence for the requested camera fix.

Two disposable native candidates, software first, same paired P3b fixed-pose
scene with both cameras enabled, unchanged XML/optics/sensors, 12 s startup,
20 s window, reliable depth-10 subscriptions, 100 Hz physics/320x240 preview/low:

| Camera / software run | Count | Hz | Max receipt gap (s) | Max stamp gap (s) |
| --- | --- | --- | --- | --- |
| Existing P3b baseline, retained | 19 | 0.949445 | 1.216205 | 2.672112 |
| Inspection P3b baseline, retained | 19 | 0.949445 | 1.194253 | 2.676802 |
| Existing candidate 1 | 32 | 1.599279 | 0.687598 | 2.283006 |
| Inspection candidate 1 | 32 | 1.599279 | 0.671358 | 2.283014 |
| Existing candidate 2 | 31 | 1.549905 | 0.692256 | 0.701204 |
| Inspection candidate 2 | 31 | 1.549905 | 0.690156 | 0.700397 |

Candidate 1 reuses only donor OpenGLPipeline.cpp's two lines before rendering:
`updateCount = viewsQueue.size(); viewsNoUpdate.clear();`.
Candidate 2 also adapts OpenGLRealCamera.cpp::DrawLDR to read cameraFBO attachment 1
using glReadPixels into the same PBO instead of glGetTexImage, restoring framebuffer
zero afterward. **Both FAIL** >=5 Hz / <0.5 s. Scheduling contributes to the shared
rate limit, but no exact remaining root cause is proven. Readback substitution
failed to improve rate over candidate 1; its smaller stamp gaps are one-window
evidence only. No global clock change was justified or made.

D3D12 was not retested because software did not pass the prerequisite. Retained
P3b hardware evidence: existing 0 Hz/0 frames; inspection 0.04997 Hz/1 isolated
frame in 20.01196 s, with no definable interframe gaps. D3D12-specific framebuffer
failure is unresolved. No graphics driver, WSL, Mesa or host configuration changed.
No baseline rerun or repeated hypothesis test; live work stopped at two attempts,
within the approximately 20-minute experimentation budget.

Builds: one native translation unit compiled and library relinked per candidate,
using existing pinned objects and unchanged FLS compatibility overrides.
Candidate 1 passed in 3.216950 s, candidate 2 in 1.535475 s. Initial compile failures
on missing SDL2 and architecture-specific headers were resolved using development
headers extracted only into /tmp, without installing/changing graphics packages.
No Neptune package changed, so no ROS package rebuild was required/performed.
No /opt source or installed library modification; /usr/local/lib/libStonefish.so
still equals /opt/stonefish/build/libStonefish.so (SHA-256
5a566fdf108cb5246105aab5faeb29e2beeebe1bac653d77a841788beaa677f4).

CameraInfo/native dimensions/frames/intrinsics and monotonic received stamps
passed for both live candidates; RELIABLE/VOLATILE QoS unchanged. A fresh separate
live static-TF check passed (0.82,0,0.20) translation and optical quaternion
(0.5,0.5,0.5,0.5). Fixture visibility uses retained P3 image evidence; no new
candidate image was retained, so fresh candidate visibility remains unverified.
All repository sensors, thrusters, mission architecture and packages under src/
are unchanged. No autonomy/controls/estimator/adapter/perception/GUI/Roboflow work.

Reproducibility: exact rejected unified patches plus SHA/hash-checked `apply.py`
are isolated in `docker/patches/p3c-experimental/`; they are NOT used by Dockerfile.
Helper application/idempotence/source-drift/revision-mismatch checks passed;
git diff --check passed. This experimental mechanism preserves evidence, not an
accepted camera fix. Normal native dependencies retain existing FLS override
handling. Apply candidates only to fresh disposable checkouts, with candidate 2
already including candidate 1. Detailed commands are in the perception document.
Rollback is stopping the test and removing its process-local LD_LIBRARY_PATH;
normal launches already load the untouched installed library. Discard disposable
sources to undo candidate source changes. No Docker rollback is required.

Temporary evidence: container /tmp/neptune-p3c and
/tmp/neptune-p3c-candidate{1,2}-{software.log,result.json}. Both experiment processes
were stopped with bounded cleanup; no simulator remained. Known SDL2 unsupported
operation warning persisted; no missing-resource error. Short windows do not prove
long-term reliability. Further investigation requires a separate authorized task;
P4 remains NOT STARTED. No commit or push occurred.

## P3c follow-up sensor-budget audit (2026-10-12)

**A blanket platform-limited conclusion is not supported.** Unpatched Stonefish
sustained >=5 Hz with <0.5 s receipt and stamp gaps in a temporary 320x240
inspection-camera-only configuration. The normal 640x480 configuration has not
passed; P3 is not promoted to complete by this diagnostic. P4 remains not started.

Exact repository camera XML in scenarios/neptune_girona_perception.scn:
`<sensor name="proscilica" type="camera" rate="10.0">` and
`<sensor name="inspection_camera_optical_frame" type="camera" rate="10.0">`.
Existing camera specs: 1360x1024/55 degrees; inspection: 640x480/145 degrees.
Native ScenarioParser reads rate directly into ColorCamera; Sensor constructor
stores it through setUpdateFrequency with no clamping or lower-rate substitution.
The ROS parser creates queue size ceil(getUpdateFrequency()) and changes only
enable state. There is no runtime rate-getter service: this frequency confirmation
is from the exact loaded pinned parser/constructor source and XML, not achieved FPS.
Normal startup has existing camera disabled by /sim/proscilica/set_enabled and
inspection enabled without an enable service. Both retain nominal 10 Hz frequency.

Complete graphical sensor/view inventory:

| Native sensor or view | Configured rate / size | Normal scene startup | Prior paired diagnostic |
| --- | --- | --- | --- |
| GIRONA500/proscilica, OpenGLRealCamera | 10 Hz; 1360x1024 | Sensor disabled by enable-service declaration | Enabled |
| GIRONA500/inspection_camera_optical_frame, OpenGLRealCamera | 10 Hz; 640x480 | Enabled | Enabled |
| GIRONA500/fls, OpenGLFLS | 2 Hz; 512 beams x 256 bins | Sensor disabled by enable-service declaration | Enabled |
| Main OpenGLTrackball view | Continuous; simulator window size | Enabled | Enabled |

There are no other camera/depth/segmentation/sonar sensors or custom views in
this scenario. Disabled sensor views remain registered and may receive initial
updates; they do not receive steady sensor-update requests. The main trackball
shares the render pipeline and continuously renders independently of camera rate.
Scene geometry, ocean/particles, atmosphere and three vehicle lamps add rendering
work but are not additional sensors/views. Cameras have on-screen display false
by default; FLS additionally generates its display image in its own sensor path.

Exactly two new SOFTWARE tests, original installed Stonefish library, llvmpipe
with eight workers, low render quality, **160x120 main window**. Temporary copies
of the prior fixed inspection-pose scene removed existing camera and FLS entirely
(to avoid even startup/cached-view work), retained inspection at rate 10.0, and
retained/enabled DVL, IMU, pressure, odometry (also accelerometer/GPS). Vehicle pose
and fixtures/lights/world were unchanged. 12 seconds startup, then each bounded
20-second measurement; reliable depth-10 subscriptions; count/full-window rate.
The second test changed only temporary inspection resolution after the first
measured <5 Hz. No repository XML, native source, native library or Docker change.

| Inspection-only resolution | Frames / window | Hz | Max receipt gap | Max stamp gap |
| --- | --- | --- | --- | --- |
| 640x480 | 75 / 20.005811 s | 3.748911 | 0.357176 s | 2.072022 s |
| 320x240 | 108 / 20.002621 s | 5.399292 | 0.214072 s | 0.214050 s |

640x480 scalar counts: DVL 435, IMU 435, pressure 109, odometry 653.
320x240 scalar counts: DVL 400, IMU 400, pressure 100, odometry 600, consistent
with configured 20/20/5/30 Hz. No existing-camera or FLS image stream was present.
CameraInfo confirmed selected dimensions, unchanged frame and FOV; at 320x240
fx=fy=50.44780622063735, cx=160, cy=120. /proc process maps verified
/usr/local/lib/libStonefish.so in both tests, with no candidate-library override.

Conclusion: sensor/view rendering budget materially affects publication in this
software runtime. Removing auxiliary vision work and reducing the main window
improved 640x480 inspection throughput from prior paired ~0.949 Hz to ~3.749 Hz;
reducing inspection pixels then reached ~5.399 Hz. These first changes were bundled,
so their individual contributions are not isolated. A WSL-specific hard <5 Hz
camera ceiling is disproven for this reduced software configuration. WSL graphics
may still contribute to total rendering cost; neither these tests nor the prior
candidates establish the exact expensive stage. D3D12 was not tested here and its
failure remains unresolved. The 640x480 stamp outlier remains unexplained; ROS
publication stamps are not physical capture timestamps. Single short windows do
not establish long-term reliability or validate 320x240 detector suitability.

Evidence: container /tmp/neptune-camera-budget/{scene.scn,robot.scn,640x480.log,
320x240.log,result.json}; host /tmp/neptune-camera-budget.py. Both simulators were
stopped with bounded cleanup; native source changes remain only the existing FLS
compatibility overrides. Rollback is simply using the unchanged repository scene;
all sensor-budget changes exist only in /tmp. No package rebuild was required.
No full mission, P4, native patch, commit or push occurred. Stage 2 stays frozen
through S2.6. Documentation and git diff --check validation only after the probes.


# 26. P3 COMPLETE WITH PERCEPTION PROFILE — finalization

**P3 COMPLETE WITH PERCEPTION PROFILE. P4 is next, NOT STARTED.** This supersedes
all historical P3-blocked statuses in sections 24–25 and the sensor-budget audit.
Stage 2 remains complete/frozen through S2.6. Polished visualization is deferred
to P8; no detector/Roboflow/alignment integration or P4 work began.

The official entrypoint is installed
`neptune_sim/launch/perception_performance.launch.py`, with required
`simulation_data` pointing at the existing Stonefish data root. It reuses the
unchanged perception_camera.launch.py and its static camera TFs. Explicit profile:
320x240 inspection camera, 145-degree HFOV, configured rate 10 Hz; software
llvmpipe, low graphics quality, eight workers, 160x120 main simulator window and
100 Hz physics. Inspection is the sole vision sensor; auxiliary camera/FLS/other
vision sensors are excluded from the generated runtime XML. DVL, IMU, pressure,
odometry and retained accelerometer/GPS start enabled, as in the passing test.
Sensor enable-service entries are omitted only in the generated profile; their
rates/noise/settings remain unchanged. /sim/odometry is evaluation-only.

New `neptune_sim/perception_profile.py` generates temporary scene/vehicle copies
from installed resources instead of duplicating complete scenarios in the repo.
Only resolution, auxiliary vision inclusion and sensor startup-enable declarations
change. The original scene, normal HOME spawn/dynamic body, fixtures, lamps,
seven motors, interfaces and physics remain. Launch shutdown cleans its temporary
directory. No previous benchmark /tmp files are needed. The official launch starts
only simulator/static TF, not adapter, estimator, mission or perception nodes.

Ordinary visual/demo use retains `perception_camera.launch.py`, 640x480 inspection,
800x600 default window and its existing optional software-rendering flag; baseline
scenarios and all normal native dependencies are untouched. Performance profile
settings are explicit and separate from demo rendering. Tiny windows are never
forced on ordinary launches. P8 owns future polished rendering.

Camera topics unchanged: /neptune/camera/inspection/image_color and
/neptune/camera/inspection/camera_info; both frame IDs remain
GIRONA500/inspection_camera_optical_frame. Performance resolution is 320x240.
Native CameraInfo uses actual runtime settings, with no manual intrinsic override.
Retained fx=fy=50.44780622063735, cx=160, cy=120. Mount/optical static TF unchanged.

Approved retained evidence, software camera-only budget test, ~20-second windows:

| Inspection resolution | Frames | Hz | Max receipt gap | Max stamp gap | Acceptance |
| --- | --- | --- | --- | --- | --- |
| 640x480 | 75 | 3.749 | 0.357 s | 2.072 s | FAIL |
| 320x240 | 108 | **5.399** | **0.214 s** | **0.214 s** | PASS minimum |

Shared Stonefish/WSL rendering budget was the limiting factor. Configured 10 Hz
is preserved but is not achieved throughput; >=8 Hz remains unmet. Evidence was
at a fixed inspection pose, not a full mission or long-term guarantee at dynamic
HOME spawn. D3D12 remains unsupported/unusable for this path in the tested WSL
runtime. Native publication stamps remain wall-clock readback time; capture-time
accuracy and later detector quality are unvalidated. No throughput rerun occurred.

Rejected P3c native candidates are retained only as explicitly marked evidence:
`docker/patches/p3c-experimental/README.md` says **NOT ACTIVE / NOT PART OF NORMAL
BUILD / FAILED ACCEPTANCE**. No launch/Docker build invokes the manual helper.
The profile uses the original native library. No upstream Stonefish source or
Docker/driver changes; no more native debugging.

Quick validation passed: Python syntax, generated XML camera contract/scalar enable
states, unchanged scene/physics/actuators/spawn, original 640x480 visual configuration,
neptune_sim-only colcon build, installed-resource/helper verification, launch
arguments/wiring and temporary-file cleanup, git diff --check. Build outputs:
container /tmp/neptune-p3-final-{build,install,log}; expected colcon warning about
using installed Stonefish dependency. No simulator smoke or full mission ran.
Exact build/launch commands and rollback are in docs/PERCEPTION_INTEGRATION.md's
finalization section. Use the original perception_camera.launch.py to return to
ordinary visual rendering; no native rollback is required.

Files for finalization: new performance launch and profile helper, setup.py launch
registration, experimental README, both project documents. Prior experimental
patch files/helper remain unchanged. No controls, autonomy, state estimator,
stonefish_adapter, perception runtime, Roboflow, GUI or mission changes.
**P4 NOT STARTED. No commit or push occurred.**

Finalization build: neptune_sim completed successfully (1 package, 0.93 s).
The first installed-resource checker invocation failed because it treated raw
launch argument strings as substitution objects; correcting only the checker
resolved it. Final installed verification and `--show-args` passed, without
starting any simulator. No package or acceptance criterion was weakened.
