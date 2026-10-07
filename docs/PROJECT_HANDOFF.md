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
