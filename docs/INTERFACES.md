# Project Neptune Interface Contracts

These are the initial module boundaries.

Exact custom ROS messages will be created later.

## State Estimation

Inputs:
- IMU
- DVL velocity
- depth / pressure

Outputs:
- /state/odometry
- /state/health

Primary state type:
nav_msgs/Odometry

Stage 0 may use simulator ground truth internally, but must still publish the same Neptune state interface.

---

## Perception

Inputs:
- camera
- sonar
- /state/odometry when needed

Outputs:
- /perception/assets
- /perception/obstacles

Responsibility:
Produce observations only.

Perception does not plan missions or control the vehicle.

---

## World

Inputs:
- /perception/assets
- /perception/obstacles
- /state/odometry

Outputs:
- /world/assets
- /world/inspection_state

Initial world model stays lightweight.

---

## Autonomy

Inputs:
- /state/odometry
- /state/health
- /world/assets
- /world/inspection_state
- obstacle information
- /vehicle/health

Outputs:
- /planning/trajectory
- /mission/status

Internal structure:
- mission
- planning
- recovery

---

## Controls

Inputs:
- /planning/trajectory
- /state/odometry
- /target/relative_pose

Outputs:
- /control/setpoint

Target-relative perception may initially live inside:
neptune_controls/target_tracking

---

## Vehicle

Inputs:
- /control/setpoint

Outputs:
- /vehicle/health

Responsibility:
Translate Neptune commands into backend-specific commands.

Backends may later include:
- Stonefish
- ArduSub / MAVROS
- other commercial vehicles

No other Neptune module should directly depend on those systems.

---

## Evaluation

Observes:
- state
- perception
- world
- autonomy
- controls
- vehicle status

Evaluation does not participate in the control loop.
