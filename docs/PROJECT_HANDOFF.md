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

**Demo V0: FULL MOVEMENT MISSION VALIDATED — MAJOR MOVEMENT/INTEGRATION PASS.**
The user manually validated the complete INITIALIZING -> WAIT_FOR_STATE -> DIVE ->
TRANSIT -> INSPECT -> RETURN -> ASCEND -> COMPLETE flow using
`./scripts/run_demo_v0.sh`. Graphics/GPU runtime is VALIDATED (G1/G2/G3 PASS),
GUI and inspection camera streaming are WORKING. Frozen runtime: D3D12 / RTX 4080,
dynamic seven-thruster Girona, 1280x720 LOW, inspection RGB 320x240/80-degree HFOV/
configured 10 Hz. Graphics plus CUDA coexistence was proven separately in G3.
Demo V0 enables the camera but starts no inference, fusion or visual controller.

**Known visual issue:** inspection camera appears AFT/backward; inspection lights
also appear backward and require verification. A local mounting-transform or
orientation-convention/180-degree issue is suspected; the exact transform is not
proven. This did not prevent full movement completion. Immediate next task:
inspect/correct only Girona body-frame convention, camera mounting/optical-frame
transforms and light mounting/orientation, then short forward-facing visual
validation. Do not change mission, estimator, controllers or frozen graphics.

P4a/P4b/P4c remain COMPLETE. **P5a IMPLEMENTED — LIVE CLOSED-LOOP VALIDATION
DEFERRED**; existing work and historical calibration records are preserved.
P5b NOT STARTED. Demo V1 passive perception overlays come **after the camera/light
orientation fix**, as does renewed P5a visual alignment validation.
Stage 2 remains complete/frozen through S2.6. See the Demo V0 record below for
architecture, startup, historical smoke measurements and user manual full-movement
validation. Older graphics blockers are historical evidence superseded by G1/G2/G3.


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


# 27. P4a Inspection Objects — observation-only pipeline COMPLETE

**P4a implemented and bounded GPU smoke PASSED. P4b next: Orientation A1/t1,
NOT STARTED. P5 NOT STARTED.** Historical P4-not-started statements above are
superseded by this record. Stage 2 remains complete/frozen through S2.6.

Read AGENTS.md and both project documents completely. Inspected donor
`lumyn/Perception` (a local remote branch, not an owner/repository URL), SHA
`608a3b985b8c5dbfc56f5398b8679c8038861bbe`: backends.py, detector.py and
config/detector.yaml. Adapted finite-value/class/bbox checks, PNG/full-frame
transport, annotation colors, copied source headers, standard Detection2DArray
construction, and a steady-clock status watchdog. No wholesale donor package,
Orientation A configuration, donor control or mission code was imported.

Model: **projects-zwfft/neptune-inspection-objects-2-yolo11n-t1**, YOLO11n,
Inspection Objects dataset version 2, expected class schema exactly
`pipe / valve / flange`. Fixed confidence **0.05**, NMS IoU **0.7**, max detections
**300**. Full received frame is losslessly PNG-encoded and passed to Roboflow's
managed preprocessing; no local resize/crop, orientation estimate or threshold tuning.

Separate inference image (tag family: roboflow/roboflow-inference-server-gpu:1.7.4):

    roboflow/roboflow-inference-server-gpu@sha256:9f91f44c23c067c03182c5b1de4213e5bdd97e393cd412c9bb4bdabdf5bdca29

Registry platform manifest and downloaded image inspection both confirmed
**linux/amd64**. Optional docker/compose.perception.yaml publishes only
**127.0.0.1:9001**. The pinned Roboflow container runs a constrained Python
adapter using `inference.get_model`, legacy YOLO11 ONNX execution and managed
preprocessing, rather than exposing the complete generic server API.
It rejects unexpected loaded classes and requires an actual CUDA profile.
Credential: existing host `~/.config/neptune/roboflow_api_key` is bind-mounted
**read-only** at `/run/secrets/roboflow_api_key`, with automatic missing-file
creation disabled. Only the inference process reads it into memory. The ROS
node does not receive a key, read a key file or transmit authentication. No key
value in environment variables, argv, YAML, Dockerfiles, source or documents.
Third-party stdout/stderr (including native output) is discarded before imports
and secret access; Docker inference logging is disabled. Errors expose only fixed
states. Model/profile caches are ephemeral in container /tmp; no repository cache.
No Linux NVIDIA display driver was installed.

Input: `/neptune/camera/inspection/image_color` (sensor_msgs/Image). Outputs:
`/neptune/perception/object_detections` (vision_msgs/Detection2DArray),
`/neptune/perception/annotated` (sensor_msgs/Image, bgr8),
`/neptune/perception/status` (std_msgs/String containing documented JSON).
Array, each detection and annotated image retain source sec/nanosec/frame_id.
Status retains source header, dimensions, model, class/confidence, clipped
xyxy/center, horizontal/vertical normalized errors, latency, age, last valid
observation stamp, result-receipt age and monotonic request start/end.
Right/down errors are positive. Orientation is explicitly false/null.

Freshness: initial engineering threshold **0.5 s**, configurable; steady-clock
20 Hz watchdog. READY and NO_DETECTION expire to STALE; camera silence becomes
CAMERA_STALE; runtime loss becomes MODEL_UNAVAILABLE; invalid schema becomes
SCHEMA_ERROR. `observation_valid` is false outside READY/NO_DETECTION. No READY
latch survives loss. Diagnostic stale results may publish with original stamps
and invalid status; consumers must honor source age/status. Source timestamps
use the node's ROS clock; silence/receipt age use monotonic time. One
BEST_EFFORT/VOLATILE depth-one subscription (compatible with native RELIABLE),
one replaceable pending slot, one worker/request; pending old frames are replaced,
and already-stale pending inputs are discarded. No per-frame request backlog.

## Validation and measured evidence

- Final focused ROS-sourced tests: **62 passed in 1.31 s**. Covers parsing,
  loaded class schema, malformed responses/JSON, clipping/centers/normalized
  errors, empty results, stale result, model loss, camera silence, replacement,
  real ROS header/annotation preservation, missing/invalid secret, no secret
  in native/exception logs, full-frame/fixed-setting adapter wiring and CUDA
  evidence rejection. The first host run had 47 passes/3 socket-denial failures;
  running the same tests in Docker resolved the sandbox restriction. The first
  ROS run found a Node.context naming collision (51 passed/1 failed); corrected.
  No tests or criteria were weakened.
- Final neptune_perception colcon build: **1 package finished, 0.82 s**,
  isolated /tmp/neptune-p4a-{build,install,log}. Installed launch --show-args,
  Python compilation, runner bash syntax, Compose configuration and diff checks passed.
- **ONE** bounded live GPU/camera/ROS smoke, isolated ROS domain 83, temporary
  fixed inspection pose (-18.5,0,3), yaw pi. Accepted P3 helper generates full
  **320x240 / 145-degree HFOV**, software llvmpipe/eight workers/160x120 preview/
  low-quality camera profile. No mission, adapter, estimator or controller.
- Inference-container nvidia-smi: RTX 4080 Laptop GPU, Windows driver **551.95**,
  advertised CUDA **12.4**. Loaded-model session includes CUDAExecutionProvider;
  actual inference profile recorded **238 node events, all CUDAExecutionProvider**.
- 20.002130522 s measurement: camera **123 frames / 6.149344934 FPS**;
  processed **124 frames / 6.199339609 FPS**. An in-flight result crossing the
  window boundary explains the one-frame count difference.
- Warm request latency (PNG encoding + local HTTP/GPU/response validation):
  **mean 42.872 ms, median 44.660 ms, p95 76.048 ms, max 93.799 ms**, n=124.
  Cold first request/model import/download/load/profile: **17.631712 s**, stale.
- Output-observation age mean **0.106406 s**, max **2.234397 s**; source-time
  outliers were explicitly STALE. Native stamps remain readback/publication wall
  time, not proven capture timestamps. Live states included READY, STALE,
  initial MODEL_UNAVAILABLE and CAMERA_STALE.
- Observed labels: **pipe, valve, flange**. Whole-smoke box counts: pipe 242,
  valve 127, flange 126 (not unique objects or accuracy metrics). **126 paired
  detection/annotated source headers** verified. Pending max **1**, requests
  in flight max **1**; **102 pending replacements**, primarily during model load.
- Camera stop produced **CAMERA_STALE / observation_valid=false**. Zero
  /neptune/cmd_body and /sim/thruster_setpoints publishers in the test domain.
  All owned simulator/observer processes and inference service stopped.
- Read-only offline audit through the mounted secret: **credential value absent
  from 219 repository files**. Actual observer log was empty; inference logs
  were disabled/discarded. A source-audit exec after normal cleanup reported
  service not running; the offline audit then passed.

Evidence: container `/tmp/neptune-p4a-smoke-5x78iait/{result.json,simulator.log,
detector.log,*.scn}`; credential-free result also retained on host
`/tmp/neptune-p4a-live-result.json`. Numeric results above survive /tmp expiry.
Inference-container stop needed Docker's forced termination (exit 137); no
owned process remained. After the smoke, automatic ONNX CPU execution fallback
was explicitly disabled (pinned API availability verified), and an explicit
container-PID-1 SIGTERM handler was added. Focused adapter/subprocess-shutdown
tests and the final package build passed. No second live smoke ran.

## Limitations / scope

Original model validation used full **640x480 simulator frames**; current input
is **320x240**. Equivalent detection accuracy is **not established**. This single
fixed-pose short run proves model access/GPU/schema/ROS integration, not detector
accuracy, dynamic-scene reliability, ocean performance or all failure recovery
paths. Duplicate/overlapping pipe detections occurred with the required settings.
Cold initialization exceeds freshness, and source-stamp outliers remain.
Request timeout is bounded at 120 s; watchdog continues while inference blocks,
but clean observer shutdown can wait for that in-flight timeout. Server dependency
logs are intentionally unavailable; credential-free health states aid diagnosis.
Dev Dockerfile declares vision_msgs/cv_bridge/OpenCV; vision_msgs was installed
in the current dev container without a full dev-image rebuild.

Changed files: new src/neptune_perception package (runtime/core/adapter, packaging,
config/launch and four test files), docker/compose.perception.yaml, Dockerfile
dependency additions, scripts/perception_p4a_smoke.py, scripts/run_p4a_smoke.sh,
docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md. No controls, autonomy,
localization, simulator source/configuration or command interface changed.
/state/odometry stays canonical; perception has no truth input.
No secret entered repository or logs. **Orientation A/P4b, pipe angles, visual
control and P5 were not started. No commit or push occurred.**


# 28. P4b Orientation A1 robust pipe detector — COMPLETE

**P4b implemented; ONE bounded A1-only GPU smoke PASSED. P4a remains COMPLETE
and its original 62 tests pass unchanged. P4c next: dual-model association,
NOT STARTED. P5 NOT STARTED.** This supersedes historical P4b-not-started records.
Stage 2 remains frozen through S2.6. AGENTS.md, this entire handoff and the entire
perception integration document were read before changing code.

Exact model: **projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1**, workspace
projects-zwfft, project neptune-pipe-orientation-a, dataset version **3**, run
**A1/t1**, YOLO11n. Expected schema exactly **pipe**, confidence **0.05**, NMS IoU
**0.7**, max detections **300**. It is called “Orientation A” because its pipe
training distribution covers broader orientations/viewpoints. **It is a robust
pipe detector, NOT an angle estimator.** It outputs axis-aligned bounding boxes
only: no pipe angle, rotated box, orientation category, keypoints or mask.
`orientation_valid=false` everywhere; the inherited nullable orientation_rad
field remains null. Box aspect ratio/geometry never populates an angle.

Full received **320x240** frame is losslessly PNG-encoded, sent locally, then
processed with the managed model's configured preprocessing. **No pipe ROI crop
or local resize.** A1 was trained/evaluated on full **640x480** images; equivalent
accuracy at 320x240 is not established. Camera remains 145-degree HFOV with the
P3 software profile; previous validated P3 rate ~5.399 Hz remains historical.

Reused the existing **inspection_inference** service, read-only secret mount,
GPU/CUDA configuration and exact linux/amd64 image pin:

    roboflow/roboflow-inference-server-gpu@sha256:9f91f44c23c067c03182c5b1de4213e5bdd97e393cd412c9bb4bdabdf5bdca29

No Docker/image/credential mechanism change or second GPU server. The existing
server now has two independent lazy model slots: original `/infer` + `/health`
remain Inspection Objects; A1 uses `/infer/orientation_a` + `/health/orientation_a`.
Sessions retain their own model/schema/CUDA evidence. They load on demand and
can coexist in the same serial server; the P4b live run loaded/exercised **only
A1**, confirmed by the original slot's runtime remaining null. Simultaneous
dual-model operation, scheduling and association are deferred to P4c.

Minimal common changes: validation accepts an explicit expected model/classes
while retaining P4a defaults; REST backend accepts either fixed route; shared
observer uses class attributes for model/topics and an A1-only stale-completion
policy. The small OrientationA subclass reuses camera conversion, annotation,
standard ROS construction, latest-frame worker, freshness and status logic.
P4a configuration/launch/smoke scripts/tests are unchanged, including its stale
diagnostic publication and original status shape. An additive regression verifies
that P4a still publishes its original timestamped stale diagnostics.

Input: `/neptune/camera/inspection/image_color`. Distinct A1 outputs:

- `/neptune/perception/orientation_a_detections` — vision_msgs/Detection2DArray.
- `/neptune/perception/orientation_a_annotated` — sensor_msgs/Image, bgr8.
- `/neptune/perception/orientation_a_status` — std_msgs/String JSON.

All source sec/nanosec/frame_id values are copied into array, individual detection
and annotated headers. Status carries model ID/source header/dimensions, pipe
class/confidence, clipped xyxy/center, normalized horizontal/vertical error,
processing latency/observation age, monotonic request timing, last valid stamp,
camera silence and receipt age. Positive error is right/down; formulas are
`(u-width/2)/(width/2)` and `(v-height/2)/(height/2)`.

Depth-one BEST_EFFORT/VOLATILE camera input, one replaceable pending slot, one
in-flight request, no frame queue. A1 alone attempts each fresh frame whenever
idle; **no N=2 scheduling**. Initial engineering freshness threshold **0.5 s**,
steady 20 Hz status watchdog. READY/NO_DETECTION expire; STALE, MODEL_UNAVAILABLE,
CAMERA_STALE and SCHEMA_ERROR remain explicit. **A1 stale completions are rejected
before detection/annotated publication** and their status observations are empty;
they do not advance the last valid observation. `rejected_stale_results` counts
them. Source timing/latency/GPU diagnostics remain visible with invalid status.

## P4b validation / live evidence

- **46 new/additive tests passed in 0.63 s; all 62 original P4a tests passed
  unchanged in 0.48 s** (108 total). Exact A1 ID/pipe-only schema, rejection of
  valve/flange, malformed responses, boxes/errors, empty predictions, source/
  latency/receipt stale completion, model/schema/camera loss, latest replacement,
  full-frame/fixed-setting CUDA adapter, preserved headers, false orientation,
  every-fresh-frame dispatch and independent same-server routes are covered.
  No test was weakened. Earlier combined validation: 107 passed before adding
  the explicit P4a stale-diagnostic preservation regression.
- neptune_perception colcon build: **1 package finished in 0.63 s**, isolated
  `/tmp/neptune-p4b-{build,install,log}`. Both installed launch argument checks,
  Python compilation, Bash syntax and git diff --check passed.
- One actual bounded smoke, ROS domain **84**, temporary fixed inspection pose
  (-18.5,0,3), yaw pi; full 320x240/145-degree input, original P3 native library,
  llvmpipe/eight workers/160x120 preview/low quality. No mission or motor publisher.
  The initial host invocation was denied Docker socket access before any service
  started; the approved retry ran the single live test.
- Inference-container nvidia-smi: **RTX 4080 Laptop GPU**, Windows driver **551.95**,
  advertised CUDA **12.4**. Actual A1 model profile: **238 node events, all
  CUDAExecutionProvider**. CPU fallback remained disabled.
- Warm window **20.000936789 s**: camera **123 frames / 6.149711951 FPS**;
  accepted output **124 frames / 6.199709609 FPS**. An in-flight boundary result
  accounts for the one-frame difference; duplicate source arrays were rejected
  by the smoke checker and none occurred.
- Warm end-to-end worker latency: **mean 55.912 ms**, median **66.154 ms**,
  p95 **92.284 ms**, max **114.415 ms**, n=124. Cold model initialization/request
  **15.437542 s**, status STALE; completion rejected without an output array/image.
- Valid observation age mean **0.104143 s**, max **0.185886 s** at first status
  receipt per warm result. **879 pipe boxes** over the whole smoke, **125 matched
  detection/annotated source headers**. Box counts are not unique objects or accuracy.
- Max pending **1**, max in-flight **1**, **102 pending replacements**, one stale
  completion rejected. Camera stop produced CAMERA_STALE/observation_valid=false.
  Orientation was always false/null. No Inspection Objects output publisher,
  /neptune/cmd_body publisher or /sim/thruster_setpoints publisher existed.
- Exact process check found no owned simulator/A1 observer remaining; inference
  container stopped cleanly (**exit 0**). Actual A1 observer log was empty.
  Read-only offline secret scan found no credential value in **234 repository
  files**. Secret value was never logged, printed, copied or documented.

Evidence: container `/tmp/neptune-p4b-smoke-8xf6mmd4/{result.json,simulator.log,
detector.log,*.scn}`, host `/tmp/neptune-p4b-live-result.json`. /tmp is temporary;
numeric evidence is preserved above. No second live smoke was performed.

## P4b limitations / scope

This proves model access/CUDA/pipe schema/full-frame ROS integration, not
orientation estimation or the model's accuracy across its training distribution.
One short fixed pose does not validate broad viewpoints, dynamic operation,
long-term reliability, real-ocean accuracy or dual-model resource contention.
Multiple pipe fragments/overlapping and low-confidence extra boxes appeared;
confidence was not tuned. 640x480 training/evaluation versus 320x240 runtime
remains a known mismatch. Native stamps remain readback/publication times.
Cold load exceeds freshness; timeout/shutdown and unavailable dependency-log
limitations from P4a remain. No full dev-image rebuild was needed/performed.

Changed: perception core/backend/observer/server and setup.py; new orientation_a
module/config/launch, two test files, two A1 smoke scripts, and both documents.
No Docker, simulator, control, autonomy, localization or actuator changes.
No truth input, fusion, pipe angle, N=2 scheduling or physical orientation output.
**P4c next: dual-model association, not started. P5 not started. No commit/push.**


## P4c dual-model execution + pipe association — COMPLETE (2026-10-12)

**P4c COMPLETE: one bounded N=1/N=1 dual-model GPU smoke PASSED. P5 is next
only when explicitly assigned; P5 NOT STARTED.** This supersedes historical
P4c-not-started statements. Stage 2 remains frozen through S2.6.

### Architecture and output contract

The independent, verified Inspection Objects and Orientation A observers receive
full identical camera frames from `/neptune/camera/inspection/image_color`.
Existing P4a/P4b code, configurations, launches and topics are unchanged. Both
use the existing serial GPU server and unchanged secure mounted secret:

- Inspection Objects: `projects-zwfft/neptune-inspection-objects-2-yolo11n-t1`.
- A1: `projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1`.

`pipe_fusion` consumes the existing `/neptune/perception/status` and
`/neptune/perception/orientation_a_status` JSON observations, rather than joining
arrays to a second dimensions/status stream. These already carry source headers,
dimensions, bbox geometry, separate confidence values, provenance and freshness.
`neptune_interfaces` currently contains only .gitkeep, no usable interface.
No new custom ROS message package was necessary; standard messages are reused.

| Output | Interface / contents |
| --- | --- |
| `/neptune/perception/fused_pipe_detections` | vision_msgs/Detection2DArray; every original pipe box retained, including both boxes in consensus; original confidence, source header, model ID in Detection2D.id |
| `/neptune/perception/fused_semantic_detections` | vision_msgs/Detection2DArray; unchanged Inspection Objects valve/flange geometry/class/confidence/header, model ID in Detection2D.id |
| `/neptune/perception/fused_status` | std_msgs/String JSON; authoritative unified observations, association records, selected_target, source header/dimensions, ages, valid flag, states and counters |

The status `pipes` records retain inspection/orientation_a observations, both
bbox arrays, both separate confidences, IoU (null when unmatched), association
state and model_provenance. `semantic_detections` retain the original observation
fields with the Inspection Objects model ID added. `selected_target` carries
selected bbox, center, normalized horizontal/vertical errors, bbox_source,
selected_source/model provenance, both confidences, IoU/state/valid. Source header,
image_width/image_height and observation_age_s/receipt_age_s are shared top-level
fields applying to that target. Missing target is null. `sequence` advances once
per finalized source; watchdog repeats never count as new observations. Overall
`valid` means a fresh selected pipe exists; NO_PIPE is a fresh completed frame
with valid=false. Consumers must honor fused status/freshness; arrays are event
outputs and do not latch a target's validity.

**Physical pipe angle remains unavailable.** Top-level and every pipe/selected
record retain `orientation_valid=false`; orientation_rad is null. No aspect
ratio, Hough, PCA, angle estimation, controls, autonomy, localization or actuator
work was implemented. No truth input exists.

### Matching, association and selection

Cache key is exact integer source sec/nanosec, never floating-point time or
receipt proximity. Frame ID and width/height must also agree before fusion.
Greedy one-to-one association considers edges in descending IoU order at a
configurable **IoU >= 0.30**, retaining unpaired boxes. Equal matching edges use
stable input indices. This is a simple deterministic greedy matcher, not a
maximum-total-IoU optimizer. Model confidences are never averaged or compared
across models; box geometry is never averaged.

Target policy: select the consensus pair with greatest IoU and use **Inspection
Objects geometry**. Distinct pairs tied for greatest IoU within 1e-9 are
AMBIGUOUS with no valid target. Without a pair, exactly one available pipe becomes
INSPECTION_ONLY or ORIENTATION_A_ONLY; multiple unmatched boxes become AMBIGUOUS.
Zero pipes becomes NO_PIPE. A1 can recover a pipe when Inspection Objects returns
no pipe, regardless of valve/flange presence. Valve/flange need no A1 validation.
Recovery and fallback are covered by pure tests; this fixed-pose smoke produced
consensus only and does not claim live recovery-viewpoint accuracy.

Default association window **0.20 s**, freshness **0.5 s**, capacity **8 source
entries**, configured in config/pipe_fusion.yaml. The 20 Hz steady-clock watchdog
expires unmatched entries, publishing a fresh single-model fallback without
waiting indefinitely. Source age, original detector validity, request latency,
original receipt age plus elapsed steady time are all checked. STALE completions
are excluded, no stale geometry is emitted. Exact per-model source watermarks
ignore repeated status/watchdog observations; finalized source watermarks reject
late counterparts and prevent retroactive output. A newer finalized source drops
older pending entries to preserve monotonic output. Capacity overflow finalizes
oldest pending input as a fresh fallback or STALE, with an eviction counter;
it cannot create an unbounded cache. Stale selected targets become invalid in
the watchdog even during ROS-clock stalls. MODEL_UNAVAILABLE remains explicit
at startup or after expired output and loss of both model feeds; individual
model_states always remain available alongside fallback/STALE status.

### Scheduling, validation and live evidence

**Keep N=1 for BOTH models.** Each existing worker attempts every available fresh
frame, with one replaceable pending slot and one in-flight request. Neither
model is gated by the other's detections. The existing serial server remained
adequate; no concurrency/server rewrite or N=2 sampling was needed. Exactly one
live run occurred; no N=2 comparison, mission or command was run.

- Pure P4c tests initially **40 passed**; final P4c coverage **50 tests passed**
  (45 pure + 5 ROS adapter/watchdog). All **108 existing P4a/P4b tests unchanged**.
  Final combined result **158 passed in 0.96 s**. Covers exact nanoseconds,
  mismatched stamp/frame ID/dimensions, IoU/threshold, one-to-one/multiple pipes,
  all selection states, recovery, stale/unavailable input, bounded cache/expiry,
  late/repeated/older-frame suppression, normalized errors, semantic pass-through,
  separate confidences, false orientation, ROS provenance/header and watchdog loss.
- Initial Docker socket denial required approved access. First ROS test aborted
  on synthetic integer bbox fields; explicit float conversion in the new adapter
  fixed it, with no test weakening. Subsequent combined run: 153 passed; final
  defensive stamp validation/cache tests raised the total to 158. These defensive
  validation additions occurred after the smoke; they do not change valid-frame
  runtime behavior. No additional live run was performed.
- neptune_perception build passed before smoke (1 package, 0.79 s overall), final
  build **1 package finished in 0.67 s** (package 0.59 s). Installed dual-model
  launch --show-args, Python compilation, runner Bash syntax and diff checks pass.

One isolated ROS-domain **86** test, official P3 camera-performance helper,
temporary fixed inspection pose (-18.5,0,3), yaw pi; full **320x240 / 145-degree
HFOV**, original Stonefish library, llvmpipe/eight workers/160x120 preview/low.
Warm measurement window **20.010126297 s**:

| Metric | Inspection Objects | Orientation A1 |
| --- | --- | --- |
| Warm processed frames / FPS | 134 / **6.696609** | 134 / **6.696609** |
| Latency mean / median / p95 | **52.255 / 58.088 / 68.045 ms** | **34.525 / 35.772 / 41.452 ms** |
| Latency maximum | 75.195 ms | 46.735 ms |
| Warm pending replacements | **0** | **0** |
| Whole-run pending replacements (includes cold loading) | 107 | 106 |
| Warm stale completions | **0** | **0** |
| Whole-run rejected stale completions | P4a has no rejection counter; fusion excludes invalid input | 2 |
| Maximum pending / in flight | **1 / 1** | **1 / 1** |
| Pending at warm start / end | **0 / 0** | **0 / 0** |

Camera: **134 frames / 6.696609 FPS**. Fused finalized frames and valid selected
targets: **134 / 6.696609 FPS**, above the preferred >=4 Hz. Source-stamp match
rate: **134/134 = 100%** of fused outputs and warm camera frames. Counts:
**CONSENSUS 134; INSPECTION_ONLY 0; ORIENTATION_A_ONLY 0; AMBIGUOUS 0; NO_PIPE 0;
STALE 0; MODEL_UNAVAILABLE 0** during the warm window. Status/watchdog duplicates
were excluded from output FPS/counts. Warm metrics count the full wall window.

Association IoU: n=134, **mean 0.608455; median 0.608318; p95 0.637082;
min 0.571611; max 0.642745**. Fresh selected observation age: mean **0.124983 s**,
p95 **0.151465 s**, maximum **0.153091 s**. No cache eviction, frame mismatch or
schema error appeared; final cache pending zero, three invalid/older inputs
rejected over whole run. Cold model loading causes replacements and stale
completions, as in P4a/P4b; it is not warm throughput or fresh output.

Each loaded model independently reported **238 executed nodes, all
CUDAExecutionProvider**, RTX 4080 Laptop GPU. ONNX lists both CUDA and CPU
providers, but actual profiled nodes were CUDA-only and automatic execution
fallback remains disabled. nvidia-smi: Windows driver **551.95**, advertised CUDA
**12.4**, total VRAM **12282 MiB**. Point samples while run active: utilization
**2–6%**, VRAM **924–1214 MiB** (startup sample 927 MiB); these are not averaged
utilization measurements. A later GPU sample found the service already stopped.

Valve **134** and flange **134** passed through with original Inspection Objects
provenance. Orientation validity remained false. Camera stop produced fused
**STALE / valid=false**. Zero command/thruster publishers. All owned observation
processes exited, inference stopped cleanly (**exit 0**); all three observer logs
were empty. No unbounded queue/backlog or freshness failure occurred in the warm
window.

Evidence: container `/tmp/neptune-p4c-smoke-21fmq_ws/{result.json,simulator.log,
inspection_objects.log,orientation_a.log,pipe_fusion.log,*.scn}`; host
`/tmp/neptune-p4c-live-result.json` and `/tmp/neptune-p4c-live-output.txt`.
/tmp is temporary; numeric results are retained here. Existing secure secret
mount/server configuration was reused unchanged; no key was read by the ROS
observers or introduced into source, arguments or documents.

### Running and limitations

Build in the ROS dev container from /workspace after sourcing /opt/ros/jazzy:

```bash
colcon --log-base /tmp/neptune-p4c-log build \
  --build-base /tmp/neptune-p4c-build --install-base /tmp/neptune-p4c-install \
  --packages-select neptune_perception
source /tmp/neptune-p4c-install/setup.bash
ros2 launch neptune_perception dual_models.launch.py
```

Start the existing inference Compose service and P3 performance camera separately,
in the same ROS domain. The dual launch starts only the two observers and fusion.
The explicitly bounded smoke entrypoint is `./scripts/run_p4c_smoke.sh`; it shares
the existing perception ownership lock, requires an idle inference service and
P3/P4c installed overlays, uses a 125 s warmup deadline, one 20 s window, bounded
process cleanup and inner 165 s / outer 175 s execution bounds. Stop the observers
and owned inference service to return to P3. Existing single-model launches remain.

Limitations: one short fixed pose establishes integration/performance, not dynamic
reliability, calibrated detection accuracy, long-duration scheduling or real-ocean
performance. Both models were trained/evaluated at full 640x480; equivalent accuracy
at full 320x240 is unproven. Low-confidence fragments/overlaps remain visible;
IoU 0.30 and 0.20/0.5 s timing limits are engineering defaults, not calibrated
operational thresholds. Greedy association is geometric only, with no tracking
or physical identity; ambiguous targets deliberately remain invalid. Unmatched
fallback incurs up to 0.20 s plus a 0.05 s watchdog tick. Source stamps remain
native publication/readback times, not verified capture instants. Status JSON is
an existing observation contract; future P5 consumers must parse provenance and
validity explicitly. Cold initialization and bounded request/shutdown limitations
from P4a/P4b remain. No physical pipe angle exists.

Changed files: src/neptune_perception/setup.py; new fusion.py, fusion_node.py,
config/pipe_fusion.yaml, launch/dual_models.launch.py, test/test_fusion.py and
test/test_fusion_node.py; scripts/perception_p4c_smoke.py and run_p4c_smoke.sh;
docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md. No unrelated package
changed. **P5 NOT STARTED. No commit or push occurred.**


## P5a lateral pipe centering — IMPLEMENTED / LIVE VALIDATION BLOCKED

P5a controller and standalone routing are implemented. **P5a is NOT COMPLETE:**
the one permitted positive-sway calibration pulse did not establish a reliable
image/control sign. Closed-loop validation was therefore not started. P5b is
next only after P5a acceptance and explicit assignment; **P5b NOT STARTED**.
Stage 2 remains frozen through S2.6. No commit or push occurred.

### Architecture, contract and engineering parameters

`neptune_controls.pipe_centering` is a ROS-independent proportional controller;
`pipe_centering_node` adapts the existing authoritative P4c
`/neptune/perception/fused_status` std_msgs/String JSON to
`/neptune/control/alignment_cmd_body` geometry_msgs/Twist. No typed selected-target
message exists. A strict consumer parser keeps this scope small without changing
P4c or introducing a new interface package. It checks top-level/target validity,
association, exact integer source stamp, finite geometry consistent with the
normalized error, dimensions, selected model/provenance, selected model readiness,
source age and upstream receipt/observation ages. CONSENSUS, INSPECTION_ONLY and
ORIENTATION_A_ONLY are eligible; AMBIGUOUS never commands motion. No confidence
threshold or perception/model behavior changed.

Equation outside deadband: `sway = clip(sway_sign * Kp * horizontal_error,
-max_sway, +max_sway)`. All other Twist fields are zero. Inside deadband and on
any invalid/unavailable/lost/stale input, output is zero. Parameters are read at
startup:

| Parameter | Current engineering default |
| --- | --- |
| Kp | 0.5 |
| max_sway | 0.25 (parameter constrained to <=1, so output also lies in [-1,1]) |
| horizontal deadband | 0.05, inclusive |
| freshness timeout | 0.5 s |
| confirmation count | 3 distinct fresh source stamps |
| control rate | 20 Hz, steady-clock timer |
| sway_sign | **0.0, deliberately disabled; no operational sign accepted** |

Source age and steady elapsed time both expire observations. Initial upstream
age plus steady elapsed time prevents watchdog duplicates or a frozen ROS clock
from rejuvenating old data. Fresh observations are reused between perception
updates. Repeated source stamps do not increase confirmation. Loss/staleness or
an out-of-deadband fresh observation resets consecutive confirmation. States:
WAITING_FOR_TARGET, ALIGNING, ALIGNED, TARGET_LOST, STALE, AMBIGUOUS,
INVALID_TARGET, PERCEPTION_UNAVAILABLE and SIGN_UNCALIBRATED. Status publishes on
`/neptune/control/alignment_status`. Shutdown sends a final zero while ROS is alive;
the unchanged vehicle adapter supplies its existing independent watchdog.
No integral, smoothing, tracking, angle inference, yaw control or hold axis exists.

The explicit `pipe_centering_standalone.launch.py` remaps only the dedicated
alignment output to `/neptune/cmd_body` and starts the existing seven-motor adapter.
It starts no autonomy, mission, estimator or other controller. Run only when normal
mission command publishers are stopped. This is explicit test routing, not P7
command ownership/arbitration. Default node output never publishes `/neptune/cmd_body`.
With current sign=0 configuration, the launch cannot move the vehicle.

Build after sourcing ROS and the existing vehicle overlay:

```bash
colcon --log-base /tmp/neptune-p5a-log build \
  --build-base /tmp/neptune-p5a-build --install-base /tmp/neptune-p5a-install \
  --packages-select neptune_controls
source /tmp/neptune-p5a-install/setup.bash
ros2 launch neptune_controls pipe_centering_standalone.launch.py
```

Camera/model launches remain independent and unchanged. The bounded experiment
runner is `bash scripts/run_p5a_smoke.sh sign|closed`, isolated ROS domain 87,
shared perception runtime lock, owned inference service, 185 s inner /195 s outer
bounds and bounded cleanup. It warms both P4c models at a fixed pose using the
accepted P3 320x240/145-degree llvmpipe/eight-worker/160x120-preview profile, then
restarts only its simulator at the same dynamic inspection pose. No native library,
body physics, allocation or repository scenario changes. Closed mode refuses an
uncalibrated sign before launching a simulator. The runner also rejects competing
body-command publishers. Do not rerun the sign pulse under the present one-test
authorization; an additional calibration requires a separately authorized task.

### Actual live sign experiment and failure

**Exactly one actual sway pulse; zero closed-loop trials.** Earlier startup
attempts failed before a pulse: overlay ordering hid the P3 helper, simulator
service discovery timed out, then the respawn service advertised but failed to
respond. Fixed-pose warmup followed by a simulator restart avoided that service.
An initial dynamic pose at y=0.7 m yielded error +0.040625, so the off-center guard
stopped it before any command. The actual pulse used starting pose
(-18.5, +1.5, 3.0) m, yaw pi; no pose or ground truth fed the controller.

| Sign-test measurement | Recorded value |
| --- | --- |
| Initial normalized horizontal error | +0.343750 |
| After-pulse error | +0.337500 |
| Change | -0.006250 (one pixel at width 320) |
| Initial selected center (u,v) | (215.0, 119.5) px |
| After-pulse selected center (u,v) | (214.0, 121.5) px |
| Positive pulse | +0.22 for nominal 3.0 s |
| Observed first positive command to zero interval | 3.019300 s |
| Maximum sway / other axes | 0.22 / all zero |
| Recorded body commands | 54, final command all zero |
| Unique fresh selected outputs during pulse window | 6, all CONSENSUS |
| Largest interval between recorded fresh outputs | 1.997887 s |
| Horizontal sign crossings | 0 |
| Sign response gate | FAIL: abs(delta)=0.00625 <=0.01 |

The direction weakly suggests sign +1 (positive sway decreased positive image
error), but the response is too small compared with observed half-pixel bbox
variation to accept as a reliable calibration. **No experimentally verified sign
is claimed and configuration remains zero.** Native motor thrust/displacement
was not observed; ROS command delivery alone cannot establish native actuation.
P2's graphical actuator callback limitation remains relevant but is not proven
to be the cause of this result. Dynamic fresh-output gaps also require follow-up;
the retained fixed-pose P4c ~6.7 Hz result does not establish dynamic throughput.

No closed-loop starting/final error, time to deadband, maximum closed-loop command,
overshoot, alignment state or three-frame live confirmation exists. Controller
live safety on loss was not exercised. Sign-run records retain unique sequences
rather than every watchdog repeat, so exact live stale/lost/ambiguous episode
counts cannot be reconstructed; do not claim zero stale events from these six
consensus outputs. The final runner now retains fusion state transitions for
future authorized use. Pure/ROS tests cover fail-closed behavior independently.
No continuing stale controller motion occurred because the controller was never
routed live. The manual calibration pulse ended with zero, and cleanup stopped
all owned simulator/model/adapter processes. Subsequent process audit found no
P5a processes in domain 87; inference service was stopped.

Ground truth was **not consumed at all**, including by the runner; lateral
truth displacement is unavailable. `/state/odometry` remains canonical and
`/sim/odometry` remains evaluation-only. Neither influences P5a commands.

Evidence: container `/tmp/neptune-p5a-sign-cej61wbr/result.json`, before.png,
fixed_simulator.log, dynamic_simulator.log and observer/adapter logs; host
`/tmp/neptune-p5a-sign-result.json`, `/tmp/neptune-p5a-sign-output.txt` and
`/tmp/neptune-p5a-before.png`. BEFORE frame shows the selected pipe right of
center. AFTER image was not saved because the response gate failed before that
save in the actual run; numeric after-source metadata is retained. The final
runner saves the after frame before applying its gate. No debug image is committed.
Temporary evidence can expire.

### Validation and remaining limits

- Smallest initial pure suite: 28 passed; final pure suite: **31 passed**.
- Final focused ROS controls plus unchanged perception suite: **195 passed in
  3.13 s** (37 controller/adapter tests, all 158 existing perception tests).
  Tests cover both configurable signs, positive/negative/zero/deadband outputs,
  saturation/extreme values, invalid/stale/ambiguous/unavailable/lost targets,
  multiple fresh-source confirmation, reset, frozen/backward clock, duplicate
  watchdog expiry, default topic isolation and zero unowned axes. The required
  assertion against an *experimentally verified* sign remains pending calibration.
- Controls package suite, from correct package working directory: **38 passed,
  1 failed, 1 skipped in 0.36 s**. Failure is existing flake8 import ordering in
  untouched depth_hold.py and waypoint_hold.py; new files have no lint errors.
  Pep257 passes; existing copyright test skips. An earlier invocation from the
  workspace root unintentionally linted the whole workspace and failed flake8/
  pep257; rerunning from the package isolated the relevant results. New-file
  lint errors were fixed without changing unrelated modules or weakening tests.
- neptune_controls build: **PASS, 1 package, 1.52 s** final. Initial missing
  neptune_vehicle overlay caused build failure; sourcing the existing P2 overlay
  resolved it, with the expected installed-workspace-dependency warning.
  Perception, vehicle and simulator sources are unchanged; no rebuild required.
- Installed standalone launch --show-args, Python compilation, runner bash syntax
  and diff checks pass. No additional live trial was used for these checks.

The controller is ready for a separately authorized calibration investigation,
but this is not an accepted closed-loop centering result. Engineering gains are
untuned; vehicle buoyancy can change depth during sway-only operation, and no
heading/depth hold or target identity tracking is provided. P4c geometric selection
can switch between fragments; dynamic model performance, actuation, sign and
convergence remain unresolved. **Physical pipe angle and yaw alignment remain
unimplemented. Full mission/state transitions and state estimation are unchanged.
P5b and P7 were not started. No commit or push occurred.**

Changed files: controls setup.py/package.xml; new pipe_centering.py,
pipe_centering_node.py, config/pipe_centering.yaml,
launch/pipe_centering_standalone.launch.py, test/test_pipe_centering.py,
test/test_pipe_centering_node.py; scripts/perception_p5a_smoke.py,
scripts/run_p5a_smoke.sh; docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md.


## P5a 80-degree validation and freshness investigation — BLOCKED

**P5a remains BLOCKED BY INTEGRATED PERCEPTION FRESHNESS, not COMPLETE.** The
performance camera change and fixed-pose P4 regression pass. The dynamic
calibration runtime cannot maintain its required fresh observation window.
One 80-degree pulse aborted safely; the subsequently authorized corrected attempt
failed before any nonzero command. The later no-motion diagnostic below passed at
a fixed pose, but did not establish the exact native cause of the dynamic camera
stall. No further pulse or closed-loop trial ran. P5b NOT STARTED. Stage 2 remains
frozen through S2.6. No commit or push occurred. This record supersedes the earlier
P5a record's current 145-degree profile description; prior evidence remains history.

### Performance optics and regression

Only generated performance/alignment XML changes HFOV **145 -> 80 degrees**,
still **320x240**, nominal **10 Hz**, llvmpipe/eight workers, low graphics,
160x120 preview and 100 Hz physics. Original/demo camera XML remains
640x480/145 degrees. Camera mount, image/info topics and native CameraInfo
publication are unchanged. No intrinsic is hard-coded. The narrower HFOV is
close to the donor training optics and improves servo pixel sensitivity about
3.78 times at the same resolution, reducing optical-domain mismatch without
increasing pixel count. Rendering cost is not guaranteed identical, and equivalent
model accuracy at 320x240 remains unproven.

Actual Stonefish CameraInfo: fx=fy=**190.6805748150736 px**, cx=160, cy=120;
K=[fx,0,160; 0,fy,120; 0,0,1]; P=[fx,0,160,0; 0,fy,120,0; 0,0,1,0];
D=[0,0,0,0,0], plumb_bob. Frame remains
GIRONA500/inspection_camera_optical_frame.

The first short fixed-pose check at (-16,0.4,3), yaw pi detected both models and
exact-source selections, but selected a near-centered target (median error
+0.046875, x=167.5) and included ambiguous outputs. Only the test pose was adjusted
to (-16,+0.8,3), yaw pi. Its **3.1073 s** warm regression produced **13 CONSENSUS
selected outputs**, median error **+0.24375**, x=**199 px**, valve/flange **13/13**,
100% exact camera/model/fusion source matching and pending zero. No movement ran.
Later fixed-pose windows also passed, with detector geometry variation producing
median error +0.178125/x=188.5 in the final gated-attempt warmup; target identity
tracking is not provided by P4c.

### Gated calibration attempts

The first 80-degree run gathered five individually fresh before samples with
medians **+0.24375 / 199 px**, then began +0.25 sway. It explicitly stopped when
fused status became **STALE at 1.02785 s**, before completing four seconds. Last
recorded positive command was at 1.00016 s; the stop was published but was not
captured by that attempt's local recorder before cleanup. Three unique fresh
outputs were CONSENSUS; last fresh error +0.240625. Evaluation-only displacement
was **+0.0038857643 m** along the initial body lateral axis (world displacement
approximately [0.00074484,-0.00388577,-0.10529746] m, 34 truth samples). No complete
after median or accepted sign exists. This does not demonstrate actuator failure.

The before-sample collector had retained samples across stale watchdog repeats
and gaps of approximately 0.85 and 0.54 s. This was a **harness qualification bug**,
not a controller or fusion freshness bug. The corrected collector resets on every
invalid watchdog episode and any >0.5 s receipt gap, excludes samples preceding
that invalid episode, and requires five consecutive fresh observations. Publisher
discovery now occurs before collecting the window; the pulse also checks target
validity/source age every iteration, with unchanged 0.5 s limit and magnitude/duration.
Zero publication is drained through the local observer before teardown.

The user explicitly authorized one corrected attempt and required STOP if it
failed. That attempt reached dynamic warmup but **could not collect the five-frame
window within 15 s**, and sent **zero nonzero commands**. At failure: fused STALE,
valid=false, source age **15.30529 s**, receipt age **15.20776 s**, sequence 21;
both model states **CAMERA_STALE**. No before/after calibration medians or pulse
displacement exist for this corrected attempt. All owned processes were stopped;
dynamic simulator required forced shutdown. No third pulse ran.

The only controller change remains the original P5a implementation; its algorithm
was not redesigned in this follow-up. Configuration remains sign **0.0** (motion
disabled), Kp **0.5**, max sway **0.25**, deadband **0.05**, freshness **0.5 s**,
confirmation **3 distinct fresh sources**, rate **20 Hz**. Equation remains
clip(sign*0.5*horizontal_error,-0.25,+0.25), zero inside deadband or on loss.
No experimentally accepted sign or live ALIGNED result is claimed.

### Standalone versus integrated runtime

| Aspect | Successful historical P4c smoke | Failed P5a sign runtime |
| --- | --- | --- |
| Simulator | One fixed-body instance, (-18.5,0,3), no restart | Fixed model warmup, then stop/restart with free dynamic body at (-16,0.8,3) |
| Camera | 320x240/145 degrees | 320x240/80 degrees; auxiliary vision still excluded |
| Render/runtime | llvmpipe, eight workers, 160x120/low, 100 Hz, original library | Same settings/library; free-body physics and changing view after restart |
| Observer processes | Inspection Objects, A1, pipe_fusion, smoke observer | Same, plus seven-motor adapter; controller absent during both failed sign attempts |
| Topics added to telemetry | None | CameraInfo, annotated image and evaluation-only odometry subscriptions, body-command monitoring |
| Topics added for control | None | /neptune/cmd_body and /sim/thruster_setpoints; later diagnostic also alignment_status |
| Executor model | Separate single-threaded ROS process per observer; one HTTP worker each | Same; adapter separate executor; smoke uses bounded spin_once polling |
| Logging | Redirected startup logs, result serialization after measurement | Same; no image writes or synchronous HTTP in measured callback loop |
| Telemetry QoS | P4c camera uses sensor-data BEST_EFFORT | P5a diagnostic camera/info/annotation telemetry uses RELIABLE depth 10; detectors remain BEST_EFFORT depth 1 |

The controller **was not started in the failed sign runs**, ruling out its timer
as their cause. Each detector subscription only replaces a latest-frame slot;
conversion/PNG/HTTP/response parsing execute in its own one-worker thread pool.
Single-threaded detector timers consume completed futures without waiting on HTTP.
Fusion uses a separate process, bounded exact-source cache, no HTTP or blocking
wait. Controller and adapter each have separate single-threaded executors. No
Python executor or callback group is shared between them and perception.

Native Stonefish uses rclcpp::spin(single-threaded); its 16.667 ms timer calls the
entire graphical LoopInternal. Its physics thread and llvmpipe workers are separate.
Long native render/physics work can delay native callbacks. Native physics permits
large unbounded elapsed-time catch-up. These are **candidates**, not a demonstrated
low-level root cause; no native thread trace from the failed dynamic process exists.
The actual loaded library retains SHA-256
5a566fdf108cb5246105aab5faeb29e2beeebe1bac653d77a841788beaa677f4,
matching the historical original library. No rejected P3c patch was enabled.

The **immediate fault location is established**: camera delivery stops upstream
of both detector workers, which report CAMERA_STALE; fusion correctly expires the
last source. Detection loss alone would not produce CAMERA_STALE. The exact native
reason (dynamic physics/rendering versus restart-related runtime behavior) is
**not proven**. The previous sign runner did not retain raw camera receipt timing,
per-model status timelines or native thread/resource traces, so its raw-camera FPS
and inference latency cannot be retrospectively reconstructed from selected outputs.
Do not describe selected-output gaps as measured raw camera FPS.

### One 12-second integrated no-motion diagnostic

The new `diagnostic` mode in scripts/run_p5a_smoke.sh launches both models,
fusion, the actual 20 Hz controller (explicit sign=0), seven-motor adapter and all
P5a telemetry in isolated domain 87. The vehicle is fixed to guarantee **no vehicle
motion**, not merely zero commands. There is no fixed-to-dynamic simulator restart.
After cold initialization/stable perception, it measures **12.0003194 s** and
writes timing/resource data only after that window. This is one short diagnostic,
not a repeated benchmark or proof of dynamic operation.

| Metric | Actual no-motion result |
| --- | --- |
| Camera | 56 frames / **4.666542 Hz** |
| Maximum camera receipt gap | **0.246275 s** |
| Inspection Objects | **4.583211 Hz**, latency mean **48.360 ms**, max **70.011 ms** |
| A1 | **4.666542 Hz**, latency mean **84.498 ms**, max **129.928 ms** |
| Fused fresh selected outputs | 56 / **4.666542 Hz**, all CONSENSUS |
| Maximum valid-output gap, including window edges | **0.300037 s** |
| Maximum new-output target age | **0.197152 s** |
| Maximum target age over valid watchdog repeats | **0.375537 s** |
| Controller callback rate | **19.999468 Hz** |
| Warm latest replacements / stale completions | **0 / 0**, both models |
| Max pending / in-flight | **0 / 1**, both models |
| Exact matched selected sources | **56/56** |
| Model-arrival skew mean / max | **0.037015 / 0.095857 s**, below 0.20 s association window |
| Cache pending / evictions / mismatches / schema errors | **0 / 0 / 0 / 0** |
| Body commands | All six fields zero throughout |

One result straddling the measurement boundary accounts for Inspection Objects'
counter-based count differing by one from camera/A1/fusion; no duplicate source
was counted. Timings include the whole warm window, not startup. All no-motion
stability criteria pass; there was no post-fix repeat because no runtime fix was
proven necessary at this fixed pose.

Per-process CPU means, percent of one CPU (can exceed 100): simulator **395.66%**,
Inspection **4.42%**, A1 **4.17%**, fusion **6.25%**, adapter **2.50%**, controller
**3.92%**. RSS KiB: simulator 397884; Inspection 186484; A1 186940; fusion 171600;
adapter 70652; controller 71140 (RSS includes shared mappings). No configured
container CPU quota or memory limit. GPU point samples during diagnostic/cleanup
were **8–38%**, approximately **1393–1422 MiB** while models remained loaded;
these are point samples, not a utilization integral. No resource saturation was
established. The native renderer dominates observed dev-process CPU cost, but
those numbers do not establish the failed dynamic run's CPU behavior.

Logs from failed calibration were approximately 5 KiB per simulator, zero bytes
for each perception observer and 129 bytes for adapter startup; no log flood exists.
The diagnostic likewise performs no disk writes during its measurement window.
Additional zero-control nodes therefore do **not** reproduce multi-second stale
output at a fixed pose. The remaining important difference is the unvalidated free
body/restart path, not a demonstrated model-speed or shared-executor defect.

No controller/perception/runtime safety fix was applied on speculation. Fixes are
limited to correct harness fresh-window qualification and added measurement mode.
**A further motion calibration is not justified by this fixed-pose result alone**:
the dynamic camera stall remains unresolved and the prior corrected attempt failed
its required window. No further pulse or closed-loop motion was run. P5a remains
blocked; future work must isolate the dynamic/restart path without weakening safety.

### Validation, evidence and scope

- Profile preservation test: PASS; generated 80-degree XML, original 145-degree
  demo untouched, same scalar/actuator/physics/spawn contract, auxiliary vision excluded.
- Combined relevant simulation/evaluation/control/perception tests: **237 passed
  in 2.89 s**. Earlier focused subset: 198 passed after correcting an invalid
  quaternion in the new evaluation-test fixture. New-file lint: PASS. Historical
  controls package lint failures in untouched controllers remain recorded above.
- neptune_sim, neptune_controls, neptune_evaluation build: **3 packages passed,
  1.55 s** final, expected installed vehicle/Stonefish dependency warnings.
- Final harness Python syntax, bash syntax and diff checks pass. Controller code,
  model thresholds, freshness settings, mission, estimation and allocation unchanged.
- Evidence: container `/tmp/neptune-p5a-80-regression-fn4hc0jk/result.json`,
  `/tmp/neptune-p5a-80-sign-zlci34pb/result.json`,
  `/tmp/neptune-p5a-80-sign-dkg3xni5/result.json`,
  `/tmp/neptune-p5a-80-diagnostic-07dgwbdl/result.json` (includes full model start/end/
  receipt/fusion/camera timelines and CPU/RSS data). Host temporary output files
  `/tmp/neptune-p5a-80-{regression2,sign,sign2}-output.txt`,
  `/tmp/neptune-p5a-diagnostic-output.txt`, `/tmp/neptune-p5a-diagnostic-gpu.txt`,
  and `/tmp/neptune-p5a-80-before.png`. No valid AFTER frame exists for aborted or
  pre-window-failed attempts. No debug images committed.
- Diagnostic cleanup and process audit passed; no P5a process remained and owned
  inference stopped. GPU sampler ended when its container stopped.

Changes in this follow-up: neptune_sim/perception_profile.py and new profile test;
new neptune_evaluation/lateral_motion.py and its test (truth consumed solely inside
that evaluation module, reported only after experiment decisions); both P5a smoke
scripts; docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md. Original P5a
controls additions remain uncommitted from the preceding implementation. The
controller never receives truth; /state/odometry stays canonical. **Pipe-angle and
yaw alignment remain unimplemented. P5b NOT STARTED. No commit/push occurred.**


## P5a dynamic-versus-restart isolation — BLOCKED (2026-10-13)

**P5a remains BLOCKED.** Exactly the two requested zero-command experiments ran,
within the 15-minute budget; no sway pulse or additional simulation trial ran.
A reproduced the severe camera-delivery gap with **direct dynamic startup and no
restart**. B completed a **fixed-to-fixed restart without STALE**, but its 3.50 Hz
camera /3.67 Hz fusion missed the >=4 Hz acceptance gate. Neither is an accepted
P5a calibration runtime. The severe failure is associated with the free/dynamic
path, and does not require restart. A specific native rendering/physics bottleneck
is still unproven; no speculative native/model/controller fix was applied.
P5b NOT STARTED; Stage 2 frozen through S2.6; no commit or push occurred.

### Experiments and actual measurements

Both used the unchanged P5a 320x240/80-degree performance helper, original native
library, llvmpipe/eight workers, 160x120/low preview, 100 Hz physics, intended
(-16,+0.8,3) pose/yaw pi, domain 87, both detectors, fusion, seven-motor adapter,
and controller explicitly sign=0. All six body-command fields remained zero,
including startup. Truth drift was recorded only inside neptune_evaluation.
A started one fresh free-body simulator directly; B kept its body fixed across
the same stop/relaunch helper used in the calibration runner. No respawn or sensor
enable service was called in either experiment.

| Clean measurement | A: dynamic, no restart | B: fixed after restart |
| --- | --- | --- |
| Window | 12.000220 s | 12.000740 s |
| Camera FPS | **0.333327**, 4 frames | **3.499784**, 42 frames |
| Maximum camera receipt gap, including window edges | **9.471444 s** | **0.401551 s** |
| Inspection Objects FPS | **0.249995** | **3.583112** |
| A1 FPS | **0.249995** | **3.583112** |
| Fresh selected fusion FPS | **0.249995** | **3.666440** |
| Maximum valid fused-output gap, including window edges | **9.396370 s** | **0.398585 s** |
| Maximum age over valid selected statuses | **0.480703 s** | **0.450133 s** |
| STALE entries during measurement | **1**, plus initially MODEL_UNAVAILABLE | **0**, CONSENSUS throughout |
| Zero commands | **YES** | **YES** |
| Full stability acceptance | **FAIL** | **FAIL: rate below 4 Hz**, despite fresh cadence |

Counter-based model FPS and unique fused-source FPS can differ by a window-boundary
result. No threshold was relaxed to call B a pass. B did not reproduce the severe
CAMERA_STALE gap, and shows that restart alone need not stop the camera. Since both
miss full throughput acceptance, these two runs do not establish a fully exclusive
binary root cause or reproduce the prior fixed diagnostic's 4.667 Hz performance.
The strongest causal evidence is that restart is **not necessary** for the severe
failure, whereas free-body operation plus drift changes the native rendering path.

A's zero-command startup-to-end drift: world displacement
**[+0.02752617,+0.00008646,-2.54762602] m**, initial
[-15.99999549,0.79999999,2.99994868], final
[-15.97246931,0.80008646,0.45232266] m. Body-lateral projection
-0.00008646 m; 1158 evaluation samples. This includes model warmup plus measurement,
not just the 12 s window. Buoyancy therefore moved the free vehicle substantially
without a motion command. B drift was exactly zero. Do not state that A's physical
vehicle remained stationary merely because its commands were zero.

### Camera and nonvisual lifecycle

All times below are UTC for process start; topic/image delays are steady-clock
seconds from the corresponding Popen call, so wall-clock adjustments cannot distort
the intervals. Process PID and /proc birth ticks and DDS image-publisher GIDs are
retained in result.json.

| Stage | Process start UTC | PID / birth ticks | New image-topic publisher delay | First image delay |
| --- | --- | --- | --- | --- |
| A direct dynamic | 18:13:38.405046 | 17734 / 2233745 | 1.658677 s | 2.978920 s |
| B initial fixed | 18:15:01.535448 | 17916 / 2242237 | 1.239133 s | 2.445348 s |
| B restarted fixed | 18:16:39.899912 | 18035 / 2252310 | 2.036272 s | 2.284992 s |

First five image receipt intervals:

- A: [0.354412,0.450029,0.412937,0.270288,0.311944] s.
- B initial: [0.331428,0.247366,0.268013,0.265942,0.261500] s.
- B restarted: [0.510342,0.270462,0.276912,0.270483,0.273117] s.
  The initial >0.5 s restart interval belongs to startup, not its clean window.

Image and CameraInfo moved together: A **4/4** during its window; B **42/42**.
CameraInfo did not keep arriving through the Image blackout. The native bridge
publishes the pair in one ColorCameraImageReady callback, consistent with a vision
render/readback/delivery-path gap rather than just loss of one ROS topic.

| Nonvisual stream | A FPS / max receipt gap | B FPS / max receipt gap |
| --- | --- | --- |
| IMU | 18.916320 / 0.698426 s | 19.915438 / 0.052734 s |
| DVL | 18.916320 / 0.698461 s | 19.915438 / 0.052492 s |
| Pressure | 4.749913 / 0.840739 s | 4.999692 / 0.205276 s |
| Evaluation odometry | 28.332815 / 0.688636 s | 29.998150 / 0.041711 s |

Nonvisual streams continued through A's much longer vision gap, with their own
smaller timing jitter. This is not a complete simulator/ROS bridge outage. `/clock`
had **zero messages in both**; this original native build provides wall-clock
stamps and does not publish /clock. Its absence is not evidence of a clock-topic
stall. No simulated-time or timestamp override was introduced.

### Process, service and health-gate findings

- Successful prior fixed diagnostic: one fixed simulator, model warmup, no restart.
- A: one dynamic simulator, then the same observer/zero-control processes; model
  runtime warmup and advancing source checks; no fixed warmup instance.
- B: initial fixed simulator and stable selected outputs; stop only the owned old
  simulator; retain observers/adapter/controller; relaunch fixed simulator with
  identical XML/settings. No service discovery, respawn or enable calls.
- Prior failed calibration: fixed warmup, stop owned simulator, edit temporary
  body fixed=false, start adapter, relaunch dynamic simulator, qualify observations.
  Unlike these experiments, it did not start the controller before calibration.
- Performance XML excludes auxiliary cameras/FLS and removes retained scalar
  sensor-enable service declarations. Inspection already has no enable service.
  Sensors start enabled for **each new process**, not through presumed persistence.
- B old PID exited cleanly (**0**) before Popen of the new PID. Image graph was
  already **empty immediately after stop**. Old GID
  010f7d17fc453e2b0000000000001c03 changed to
  010f7d1773461ea80000000000001c03. No old publisher remained to satisfy a topic
  health gate. The diagnostic requires a new GID, a live owned process, and image
  stamps newer than that process's start before considering its frames.
- B checked current-source detector completions after restart, rather than
  accepting the observers' old runtime/READY metadata. Source stamps advanced.
  This is useful health instrumentation, not proof of a restart defect.

The initial B warmup flag in the recorded artifact is false despite warm models
and later stable fixed selection. The diagnostic's first implementation demanded
that **every historical** source timestamp increase. Four ~0.22–0.35 s backward
stamp steps during its initial ~100 s startup/wait made that check permanently
false. The late fixed-source check succeeded, then B restarted as requested.
The helper now requires the **latest six consecutive advancing stamps**, permitting
health recovery after an old clock step. This correction was unit-tested after the
two runs; neither experiment was repeated. It does not explain A's independently
measured 9.47 s raw receipt gap (A recorded no source-stamp regression), or change
B's measured throughput failure. No freshness threshold or STALE handling changed.

### Result, scope and validation

No operational smoke-runner fix was applied: direct dynamic startup **did not
work**, so replacing the existing restart path would not fix the demonstrated
failure. No post-fix dynamic validation ran because no applicable runtime fix was
established; user policy requires stopping on dynamic-path failure. A final sign
calibration is **not justified**. P5a remains blocked; no pulse in this task.

This turn changed only: new scripts/perception_p5a_lifecycle.py,
scripts/run_p5a_lifecycle.sh and scripts/test_p5a_lifecycle.py;
neptune_evaluation/lateral_motion.py and its test (armed startup origin and receipt
telemetry); docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md. The existing
P5a smoke scripts, model/controller algorithms, 0.5 s freshness, optics, thruster
allocation, mission and state estimation are unchanged in this turn.

Focused evaluation tests initially **3 passed in 0.20 s**, then lifecycle/evaluation
checks **5 passed in 0.12 s**; initial combined collection failed because the test
PYTHONPATH omitted neptune_perception (the shared cleanup helper imports it).
Adding that existing package path fixed collection. A floating-point interval
assertion uses numeric tolerance. New evaluation-file lint passes. Relevant
neptune_evaluation build: **1 package passed, 1.29 s**. Python syntax, runner Bash
syntax and diff checks pass. No simulator/model/controller package rebuild needed.

Evidence: container `/tmp/neptune-p5a-lifecycle-A-_nt5uutp/result.json` and
`/tmp/neptune-p5a-lifecycle-B-e4tcsr1l/result.json`, with exact source/receipt times,
process identities, GUIDs and logs. Host `/tmp/neptune-p5a-lifecycle-{A,B}-result.json`
and corresponding `-output.txt`. All owned processes exited, final process audit
found none in domain 87, and inference stopped. These files are temporary.
**Commands remained zero; A passively drifted. Freshness remains 0.5 s. Ground truth
is evaluation-only. P5b NOT STARTED. No commit or push occurred.**


## P5a startup-settling validation — physical settling confirmed, P5a BLOCKED

**One fresh dynamic run only, no restart or repeat. P5a remains BLOCKED.** Girona
naturally passed the physical depth-rate/yaw-rate gate at **37.676355 s**, but no
simultaneous physical/perception window passed by the **40 s** deadline. Commands
remained all zero; sign calibration and closed-loop alignment were not started.
This narrows the earlier A/B interpretation: startup strongly worsens camera gaps,
but this run still did not produce an acceptable settled pipe-centering input.
It does not prove a generic native dynamic-physics defect. No Stonefish patch,
model/controller change, stabilizing controller, P5b work, commit or push.
Stage 2 remains frozen through S2.6.

### Single-run method and gate

Same real seven-motor free Girona, temporary initial pose (-16,+0.8,3), yaw pi,
P3 performance profile **320x240/80 degrees**, software/eight workers/160x120/low,
100 Hz physics, both independent models, P4c fusion and seven-motor adapter.
A single zero-only publisher owned /neptune/cmd_body during diagnosis. No autonomy,
heading/depth controller, respawn/enable call or simulator restart. Alignment was
conditionally permitted only after settling and successful sign calibration; the
code never reached either motion phase in this actual run.

The settling timer starts immediately before the one simulator Popen. The first
20 s are recorded as startup, not evaluated against P5a acceptance. The earliest
eligible five-second window is [20,25] s. Check subsequent rolling five-second
windows until 40 s, using **onboard sensor data**, never evaluation odometry:

- Depth = pressure/(997*9.81)+0.40, the existing validated pressure_depth formula.
- Depth rate = successive pressure-derived depths divided by original source-stamp
  difference; nonpositive or >=1 s source intervals produce an invalid rate and
  cannot qualify a window. No interpolation hides a bad time interval.
- Yaw/angular velocity come from the existing identity-mounted IMU. Body gyro-Z is
  the near-level yaw-rate equivalent used for this diagnostic; other rate axes and
  yaw are also recorded. IMU quaternion yaw uses the existing ROS convention.
- **Every** pressure-rate sample in the same five-second window must satisfy
  abs(rate)<**0.05 m/s**; every gyro-Z sample abs(rate)<**0.03 rad/s**. Both physical
  streams must cover the window with receipt gaps <0.5 s.
- The same window also needs camera and distinct fresh selected fusion output
  >=**4 Hz**, gaps <**0.5 s**, selected age <**0.5 s**, valid target throughout,
  >=5 distinct consecutive fresh targets, no CAMERA_STALE, and both models warmed.

Pressure's constant mounting offset is the existing simple calibration, not a new
attitude-dependent transform. Depth rate is the closest validated sensor-derived
vertical-rate signal; no truth velocity or depth enters motion qualification.
Truth depth/yaw/linear/angular velocities and source/receipt timestamps are
continuously recorded inside neptune_evaluation and read only for the final report.

### Actual startup and settled results

The full settling attempt ended at **40.001455 s** (normal loop scheduling rounding).
The physical five-second gate first passed at **37.676355 s**, verifying the
window **32.676355–37.676355 s**. The reported transition boundary is the start of
that verified window, not an assertion of an instantaneous physical equilibrium.
Onboard depth initially **3.007965 m**, final **0.447589 m**; the first physically
settled window ranged **0.439735–0.487929 m**. Evaluation-only truth was initially
2.999949 m and finally 0.442264 m, confirming passive buoyant rise. World displacement
approximately [0.02676104,0.00008876,-2.55768453] m; no commanded motion.

| Diagnostic interval | Startup/unsettled | From first verified physical-window start to deadline |
| --- | --- | --- |
| Time bounds | 0–32.676355 s | 32.676355–40.001455 s |
| Duration | **32.676355 s** | **7.325099 s** |
| Camera FPS | **2.846095** | **3.549440** |
| Maximum camera receipt gap, including edges | **6.580135 s** | **0.707956 s** |
| Distinct fresh selected fusion FPS | **0.612063** | **0** |
| Maximum valid selected-output gap, including edges | **18.280804 s** | **7.325099 s** (none selected) |
| Onboard depth range | **0.402974–3.007965 m** | **0.439735–0.487929 m** |
| Depth-rate range | **-0.134428–+0.090897 m/s** | **-0.037598–+0.046249 m/s** |
| IMU yaw-rate range | **-3.10977e-5–+1.87201e-5 rad/s** | **-1.02873e-5–+1.04009e-5 rad/s** |
| Fused STALE entries | **3** | **4** |
| Maximum valid selected-target age | **0.355678 s** | **unavailable: no valid selected target** |

The **exact first five-second physical settling window** had camera **3.8 Hz**,
max camera gap **0.439493 s**, selected fusion **0 Hz**, max selected gap **5 s**;
fusion alternated AMBIGUOUS and STALE (three/two entries). Thus even at physical
qualification, the camera rate missed 4 Hz and association supplied no valid target.

The final five seconds [35.001455,40.001455] remained physically qualified:
depth rate -0.035954–+0.029697 m/s, gyro-Z -1.02873e-5–+7.20943e-6 rad/s. Camera
was **3.4 Hz**, max gap **0.707956 s**, selected fusion **0 Hz**, with three AMBIGUOUS
and three STALE entries. No later common gate passed. The entire run's IMU X/Y rate
ranges were approximately [-0.000497,+0.000423] and [-0.037416,+0.042480] rad/s;
these other axes were recorded, not used to add an unrequested attitude hold.
Initial IMU yaw was approximately -pi (equivalent to yaw pi).

Physical settling therefore **does occur**, and removes most of the large startup
camera gap. It does **not fully explain or resolve** the P5a failure: after settling,
camera throughput remains below 4 Hz, a >0.5 s camera gap remains, and selected-target
association is ambiguous/stale. The vehicle has risen far from its original
inspection depth; changing view and target geometry remain material limitations,
not proof that the model itself is slow or that a native patch is needed.
The exact blocker is **no simultaneous five-second physical and fresh-valid-target
window before 40 s**. Physical instability is not the blocker at the end of this run.

### Scope, validation and evidence

Actual CameraInfo remains native: 320x240, fx=fy=190.6805748150736, cx=160, cy=120.
Continuous records include 184 pressure samples, 739 IMU and 739 DVL publications,
119 paired Image/CameraInfo publications, fused and per-model statuses, all commands,
and 1109 odometry samples kept in evaluation. Camera source stamps and receipts,
IMU yaw/all angular axes, DVL raw velocity and pressure-rate histories are retained.
No selected-target age after settling is fabricated from an invalid retained bbox.

Changes this turn: new scripts/perception_p5a_settling.py,
scripts/run_p5a_settling.sh, scripts/test_p5a_settling.py; added continuous snapshot
history to neptune_evaluation/lateral_motion.py and a focused test;
docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md. All previous diagnostic
scripts, profile settings, estimator/controller/model algorithms and allocation
remain unchanged. No depth/heading stabilization was added.

- Initial focused settling/evaluation tests: **8 passed in 0.22 s**; final snapshot
  coverage: **9 passed in 0.17 s**. Covers continuous physical windows, strict rate
  boundaries, missing derivatives, sensor gaps, invalid watchdog repeats, camera
  gaps, age==0.5 rejection, CAMERA_STALE and no-target rejection.
- Relevant neptune_evaluation build: **1 package passed, 1.41 s**. New evaluation
  file lint passed; harness Python/Bash syntax and diff checks passed.
- Live evidence: container `/tmp/neptune-p5a-settling-fv9g5ezf/result.json`, simulator
  and observation logs. Host `/tmp/neptune-p5a-settling-result.json` and
  `/tmp/neptune-p5a-settling-output.txt`. Raw state and timing history is temporary.
- Owned processes exited, process list clear and owned inference stopped. No repeat.

**No sign pulse, experimental sign or closed-loop result exists for this run.**
Configured sign remains 0 (disabled); existing Kp0.5/max0.25/deadband0.05/freshness0.5/
three-source confirmation/20 Hz parameters remain unchanged. **Freshness stayed
0.5 s. Pipe-angle/yaw alignment unimplemented. P5b NOT STARTED. No commit/push.**


## Demo V0 — full movement validated; implementation and smoke history (2026-10-14)

**Graphics/runtime is frozen. No more graphics experimentation is required.**
G1/G2/G3 supersede the historical D3D12-unusable conclusions above. No driver,
Mesa, WSL, native Stonefish, camera-readback or scheduling patch was applied.

| Valid graphics trial | Camera frames / window | Hz | Max receipt / source gap |
| --- | --- | --- | --- |
| G1 reduced fixed fixture, 160x120 LOW preview | 199 / 20 s | 9.950 | 0.191531 / 0.191456 s |
| G2 dynamic integrated scene, 1280x720 LOW | 301 / 30 s | 10.033 | 0.170690 / 0.172902 s |
| G3 same dynamic scene plus both CUDA models | 302 / 30 s | 10.067 | 0.172283 / 0.177261 s |

G2/G3 camera: 320x240, 80-degree HFOV, configured 10 Hz. G1 used the retained
145-degree reduced fixture. Image/CameraInfo pairs all matched. G3 independently
recorded 238 CUDAExecutionProvider node events per model, 302 warm completions
per model, zero warm stale completions/replacements, 31.8% average GPU utilization
(22–54%), ~1791 MiB VRAM of 12282 MiB. G2 operator visual classification was smooth;
G3 camera/model/resource coexistence passed. This is bounded runtime evidence, not
model accuracy, long-duration reliability or a reason to change graphics settings.

### Demo architecture and ownership

`neptune_bringup/perception_demo.launch.py` owns one Stonefish process, the existing
seven-motor adapter, existing `pressure_depth` and `dead_reckoning_state`, existing
`mission_executive`, new `demo_readiness`, read-only `demo_gui`, and existing camera
static-TF edges. It generates the same reduced integrated scene with the existing
`neptune_sim.perception_profile.write_performance_scenario` helper; no prior /tmp
benchmark fixture is required. Original Girona body/physics, seven actuators,
lamps, pipe/flange/valve and scalar sensors are retained. Auxiliary RGB/FLS are
removed only from generated XML. Original scenes and P5a profile helper are unchanged.

Frozen DEMO defaults: accelerated NVIDIA D3D12 / OpenGL 4.6, RTX 4080 Laptop GPU,
1280x720 LOW, 100 Hz physics, inspection RGB 320x240/80 degrees/10 Hz. The launch
prepends `/usr/lib/wsl/lib` while retaining sourced ROS/Stonefish library paths,
unsets software/GL overrides and checks the hardware renderer before movement.
It does not maximize Stonefish. Windows can retain presentation-window state;
keep Stonefish restored/unmaximized at 1280x720. The native scene render target
remains the requested 1280x720. The prior larger client size corresponds to actual
WM maximization (MAXIMIZED_HORZ/VERT were observed during G3 cold loading).

Explicit legacy profiles remain available without changes:
`neptune_sim/perception_performance.launch.py` is the small-window software profile;
`perception_camera.launch.py` is the ordinary 640x480/145-degree camera profile.
They are not the default Demo V0 entrypoint. No 1600x900 trial ran.

Movement authority is exclusively `mission_executive` -> `/neptune/cmd_body` ->
`stonefish_vehicle_adapter` -> `/sim/thruster_setpoints` (seven values).
The executive already contains the proven depth PID, heading control and waypoint
guidance; standalone `depth_hold`/`waypoint_hold` are deliberately not co-launched.
No new motion controller, command mux or GUI command publisher exists.
`/state/odometry` remains the sole downstream state interface. No demo component
consumes `/sim/odometry`; it remains evaluation-only.

Demo readiness is opt-in in the existing executive (`demo_mode=false` preserves
ordinary Stage 1 startup). Demo starts in INITIALIZING with zero commands, waits
at least 15 s from initial sensor arrival plus a three-second stable window:
pressure-derived depth rate <0.05 m/s and IMU angular-Z <0.03 rad/s, with fresh,
finite advancing pressure/IMU/DVL/onboard-state streams (<0.5 s gaps/ages).
Readiness also requires exclusive executive/adapter/estimator publisher ownership.
After initial qualification, motion is allowed and only validity/freshness are
required; a moving robot is not incorrectly required to remain stationary.
Readiness/state loss pauses the executive at zero without resetting HOME or mission
phase. Duplicate publishers abort the launch. Startup has a 90 s failure deadline.
Neural health and camera detections never gate or command movement.

The executive publishes status on transitions and at 5 Hz. COMPLETE distinguishes
normal completion from the existing 420 s mission TIMEOUT; elapsed time freezes
on completion. Guidance, controller gains, route, standoff and mission transitions
are unchanged. Default automatic startup needs no button or extra terminal.
Closing the GUI/simulator or any required process exits the whole owned launch.

### GUI and teammate audit

Audited all 487 lines of `lumyn/Perception:src/neptune_gui/auv_gui.py`, its
`controls.py` and GUI runner at donor SHA
`608a3b985b8c5dbfc56f5398b8679c8038861bbe`. Reused the charcoal/cyan styling idea,
large-camera/sidebar hierarchy and background-I/O/UI separation. Donor TCP,
manual keyboard controls, native thrusters, mission buttons, truth comparisons
and perception-dependent movement were not copied.

The dev container already has OpenCV Qt5 support; Tk/PyQt bindings/Pillow are not
installed there. V0 uses the existing OpenCV native display, avoiding new packages.
A separate ROS thread only stores the latest Image and lightweight telemetry.
Decode/resize/display happen on the GUI thread, in its own process. BEST_EFFORT
KEEP_LAST depth-one camera input cannot build a backlog or backpressure Stonefish.

Application topics consumed by GUI:

- `/neptune/camera/inspection/image_color` — Image, latest native RGB frame.
- `/neptune/camera/inspection/camera_info` — CameraInfo.
- `/state/odometry` — pressure/IMU/DVL-derived depth, x/y and heading.
- `/neptune/mission/status` — String JSON, authoritative phase/time/outcome.
- `/neptune/demo/health` — String JSON, readiness and sensor/publisher health.

**GUI application topics published: NONE.** ROS's standard `/rosout` and
`/parameter_events` remain enabled; neither is a movement interface. No motor
arrays, Twist, start service call, fake detections or neural overlays originate
from the GUI. It displays PERCEPTION: DISABLED. “Onboard state LIVE” means fresh
sensor-derived telemetry, not validated covariance or an ESKF accuracy claim.
Readiness publishes only `/neptune/demo/ready` (Bool) and `/neptune/demo/health`.
The executive's optional `/neptune/mission/start` Trigger arms a ready demo when
`auto_start=false`; it is for controlled validation, not GUI driving.

### Build and one-command startup

Inside the existing dev container, source ROS and Stonefish, then build only the
Python demo/runtime packages (no native or Docker rebuild):

```bash
source /opt/ros/jazzy/setup.bash
source /opt/stonefish_ws/install/setup.bash
cd /workspace
colcon --log-base /tmp/neptune-demo-v0-log build \
  --build-base /tmp/neptune-demo-v0-build \
  --install-base /tmp/neptune-demo-v0-install \
  --packages-select neptune_sim neptune_vehicle neptune_state_estimation \
                    neptune_autonomy neptune_bringup
```

From the repository root in WSL, the obvious entrypoint is:

```bash
./scripts/run_demo_v0.sh
```

It reuses/starts only the existing Compose dev container, sources ROS/Stonefish
and the built demo overlay, selects ROS domain 92 by default, and starts the entire
stack. No inference service is started. Override ROS_DOMAIN_ID explicitly if needed;
use the same domain for observers. The runner selects a normal `/workspace/install`
demo installation first, otherwise the validated temporary install. An explicit
`NEPTUNE_DEMO_INSTALL` selects another existing build. To make the build persistent,
use normal workspace build/install directories instead of the /tmp build arguments.
No build happens implicitly during the startup command.

Equivalent single sourced-container ROS command:

```bash
source /tmp/neptune-demo-v0-install/setup.bash
ROS_DOMAIN_ID=92 ros2 launch neptune_bringup perception_demo.launch.py \
  simulation_data:=/workspace/external/stonefish/Tests/Data
```

Close the GUI/Stonefish window or Ctrl+C the launch to stop only its owned actors;
the dev container remains intact. For diagnostic screenshots, optionally pass
`evidence_directory:=/tmp/my-neptune-demo` (GUI screenshots and health JSON).
`auto_start:=false` is a validation option: initialization remains at zero until
the executive's Trigger service is called after health checks. No simulator restart.

### Earlier instrumented smoke validation (historical scope)

This section records the earlier stopped smoke run only. Its completion deferral
is superseded by the user manual full-movement validation recorded below; its
measurements and temporary evidence are retained unchanged.

Initial verification passed before arming the same simulator: live GUI frames and
onboard telemetry, stable readiness, one executive command publisher, one
seven-motor adapter publisher, one sensor-derived estimator, no neural/fusion/P5a
publishers, all 441 observed startup body commands zero. The operator supplied a
screenshot and confirmed **“ITS WORKING!”**. Stonefish was observed restored at
1280x720, LOW, accelerated D3D12; no automatic maximization code exists.

One mission was armed. Observed sequence:
**INITIALIZING -> WAIT_FOR_STATE -> DIVE -> TRANSIT**. The operator then changed
validation scope to a short demonstration and requested no full mission. We
stopped the owned launch immediately; no retry, simulator restart or second mission.
**Full mission result: NOT RUN TO COMPLETION AT OPERATOR REQUEST**, not a failed
mission or a claim of INSPECT/RETURN/ASCEND/COMPLETE.

| Short-smoke measurement | Actual result |
| --- | --- |
| First 30 s after DIVE began | 301 Images / 30 s = **10.033 Hz** |
| Image/CameraInfo pairing | **301/301** |
| Max receipt gap, including window edges | **0.138572 s** |
| Max source-stamp gap | **0.138693 s** |
| Full observed movement interval | ~113.15 s; 1135 Images, **10.031 Hz** |
| Full observed interval max receipt / source gap | **0.141199 / 0.188320 s** |
| Last reported mission elapsed / state | **113.476 s / TRANSIT** |
| Final estimated position | **(-17.6972, +0.0640, 2.9915) m** |
| GUI at shutdown | camera/state LIVE; 1256 frames displayed / 1257 received |
| Largest GUI display gap | **0.166251 s** |
| Seven-motor layout | every array length 7; channels 4/5/6 always zero |
| Final motor command | seven zeros |

Depth reached the existing 3 m target; lateral estimate reached ~0.357 m during
outbound motion and reduced to ~0.064 m. No lateral-thruster regression was observed.
No truth data entered readiness, GUI, mission or evaluation observer. Localization
is the existing clean dead-reckoning baseline; no long-duration/real-ocean claim.
Inference, P4c fusion and P5a stayed off throughout. Mission executive was the
only body-command publisher. Camera, GUI and telemetry remained live during the
observed movement; full mission/inspection/return behavior is deferred, not inferred.

Original full-mission temporary observer recorded FAIL on intentional launch exit
because it expected COMPLETE. Its raw result is retained; `assessment.json` explains
the user-directed stop and records the accepted short-smoke scope explicitly.

Shutdown exposed the pre-existing unconditional `pressure_depth` rclpy.shutdown()
after ROS's SIGINT handler had already closed the context (that component exit 1).
Added only an `if rclpy.ok()` shutdown guard; estimator math/input/output unchanged.
The other launch components stopped cleanly; adapter emitted seven zeros. Both
signal/context paths have regression tests, and an independently launched installed
pressure_depth process now exits **0** on SIGINT with no traceback. No extra simulator
or mission was run after this fix; full-stack post-fix shutdown was not rerun.

Validation: initial focused suite **12 passed**, expanded preservation suite
**30 passed**, final shutdown regression/preservation suite **32 passed in 0.61 s**.
Includes startup/arming/health expiry/invalid state, unchanged Stage 1 gains and
startup, GUI no application publishers/latest-slot/stride/color decoding, all 17
existing five/seven-motor adapter tests, and the existing profile preservation test.
Five Python ROS packages built successfully (**2.63 s**); subsequent autonomy
and estimation builds passed after final lifecycle updates. Expected installed
Stonefish dependency and disabled-bytecode warnings were nonfatal. Host runner
Bash syntax, installed imports, ROS launch --show-args, actual host runner
--show-args, and git diff --check passed. No native/image/package installation.

Evidence (temporary, copy before container replacement):
container and host `/tmp/neptune-demo-v0-validation-49fzqeje/` contain raw
`result.json`, explanatory `assessment.json`, `launch.log`, GUI health and images.
GUI screenshots: `gui/INITIALIZING.png`, `gui/INITIALIZING-live.png`, `gui/DIVE.png`,
`gui/TRANSIT.png`. Host `/tmp/neptune-demo-v0-visual/initialization-desktop.png`
(operator screenshot) and `transit-desktop.png` show native windows. Inspection,
return and completion images were not captured because those phases were not run.

Known visual issues: native OpenCV viewer toolbar/status chrome remains; the
320x240 camera is enlarged for presentation, so detail is intentionally soft.
The first camera view includes the existing dock/buoy; target-facing camera/fixture
framing and lamp appearance at INSPECT were not reviewed in this shortened run.
The free Stonefish trackball does not automatically follow the vehicle; its built-in
Trackball center selector can be used observationally. Overlapping OS windows need
normal desktop arrangement; leave Stonefish unmaximized. No scene/lighting/optics
redesign, 1600x900 trial or repeated mission was performed.

**P5a: IMPLEMENTED — LIVE CLOSED-LOOP VALIDATION DEFERRED.** All prior P5a source,
configuration, sign=0, tests and diagnostic scripts were preserved byte-for-byte.
P5b NOT STARTED. Next, only when assigned: correct and visually validate camera/light
mounting orientation before Demo V1 Inspection Objects/A1 passive GUI overlays
or renewed P5 sign calibration and lateral visual alignment. Neither phase is implemented here. Stage 2 frozen through S2.6.
**No commit or push occurred.**


### Demo V0 full movement — user manual validation (2026-10-14)

**MAJOR MOVEMENT/INTEGRATION PASS — FULL MOVEMENT MISSION VALIDATED.**
The user manually validated Demo V0 using:

```bash
./scripts/run_demo_v0.sh
```

The user observed one Stonefish simulator process, D3D12 hardware rendering on
RTX 4080, the 1280x720 LOW viewport, live inspection camera in the GUI, canonical
state estimation, mission executive, seven-motor adapter, GUI telemetry, and the
full autonomous movement mission. The successful flow was:

**INITIALIZING -> WAIT_FOR_STATE -> DIVE -> TRANSIT -> INSPECT -> RETURN ->
ASCEND -> COMPLETE.**

This manual full-movement result supersedes the earlier short-smoke-only status.
The quantitative camera measurements, elapsed time and final position above belong
only to the earlier instrumented smoke run; no new full-run duration, final position
or quantitative camera metrics were supplied. This documentation update did not
rerun the mission, tests or builds.

The frozen runtime remains D3D12 / NVIDIA GeForce RTX 4080 Laptop GPU,
1280x720 LOW Stonefish viewport, inspection RGB 320x240 / 80-degree HFOV /
configured 10 Hz. Graphics plus CUDA inference coexistence was proven separately
in G3; that result does not imply inference was enabled in Demo V0.

#### Known inspection camera/light orientation issue

During the full run, the user visually identified that the inspection camera
appears to face AFT/backward relative to the intended inspection direction.
Inspection lights also appear backward or may share the same incorrect
mounting-frame convention. The current hypothesis is a **local sensor/light
mounting-transform problem**, likely an orientation convention or 180-degree
transform issue. **The exact transform and cause are not yet proven.**

This issue did not prevent mission motion, state estimation, GUI operation,
camera streaming, D3D12 rendering, seven-thruster integration or completion of
the movement demo. It must be corrected before meaningful inspection-camera
visual validation, Demo V1 passive perception overlays, or renewed P5a
perception-driven alignment validation.

| Current status | Result |
| --- | --- |
| Demo V0 | **FULL MOVEMENT MISSION VALIDATED** |
| Graphics | **VALIDATED** |
| GUI | **WORKING** |
| Inspection camera stream | **WORKING** |
| Inspection camera mounting orientation | **KNOWN ISSUE — appears backward** |
| Inspection lights orientation | **KNOWN ISSUE — appears backward / requires verification** |
| P5a | **IMPLEMENTED — LIVE CLOSED-LOOP VALIDATION DEFERRED** |
| P5b | **NOT STARTED** |
| Demo V1 passive perception overlays | **NEXT AFTER CAMERA/LIGHT ORIENTATION FIX** |

#### Immediate next session task — mounting orientation only

Inspect and correct only:

1. Girona body-frame convention.
2. Inspection camera mounting transform.
3. Inspection camera optical-frame transform.
4. Inspection light mounting/orientation.

Then run a **short visual validation** confirming that the camera faces forward
toward the inspection asset, lights illuminate forward, and pipe/flange/valve are
visible from the intended inspection approach. Do not change mission logic,
state estimation, controllers, graphics runtime, P4 models, P5a or P5b.
Demo V1 passive overlays follow only after this orientation fix. No part of that
next task was started in this documentation-only update. P5a/P5b work is untouched;
no code/config changes, tests, simulations, rebuilds, commits or pushes occurred.
