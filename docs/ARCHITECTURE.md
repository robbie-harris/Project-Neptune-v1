# Project Neptune Architecture

## Main Data Flow

IMU / DVL / Depth
        |
        v
State Estimation
        |
        +----------------------+
                               |
Camera / Sonar                 |
      |                        |
      v                        |
 Perception                    |
      |                        |
      v                        |
 Lightweight World Model <-----+
      |
      v
 Autonomy
 mission + planning + recovery
      |
      v
 Trajectory
      |
      v
 Controls
      |
      v
 Vehicle Setpoint
      |
      v
 Vehicle Interface
      |
  +---+---+
  |       |
Stonefish ArduSub
  |       |
Sim     Hardware

Evaluation listens to all major modules but does not command the vehicle.

## Module Responsibilities

### neptune_state_estimation
Answers:
Where is the vehicle and how is it moving?

Initial MVP:
IMU + DVL + depth -> EKF

Stage 0:
Simulator ground truth -> canonical Neptune state interface

### neptune_perception
Answers:
What does the vehicle currently see?

Initial sensors:
- camera
- imaging sonar later

Produces:
- asset detections
- obstacle observations

### neptune_world
Answers:
What do we currently know about the environment and inspection target?

Keep this lightweight.

Initial representation:
- asset identity / pose
- obstacles
- home position
- inspection progress

### neptune_autonomy
Answers:
What should the robot do next?

Contains:
- mission
- planning
- recovery

Initial mission:
Home -> Dive -> Transit -> Acquire -> Inspect -> Return

### neptune_controls
Answers:
How should the vehicle move to follow the requested trajectory?

Also contains target-relative tracking initially.

### neptune_vehicle
Converts Neptune vehicle-independent commands into simulator/autopilot-specific commands.

This is the only module allowed to depend directly on:
- Stonefish vehicle APIs
- ArduSub
- MAVROS
- MAVLink
- vendor APIs

### neptune_sim
Contains Neptune-specific simulation worlds, vehicle configuration, sensors, and launch configuration.

### neptune_evaluation
Measures:
- mission success
- inspection coverage
- localization error
- trajectory tracking error
- target loss / recovery
- completion time
- collisions

### neptune_bringup
Launches the complete Neptune stack.
