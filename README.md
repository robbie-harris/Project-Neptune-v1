# Project Neptune

Marine inspection autonomy stack.

## Goal

Build a modular underwater autonomy system that can:

1. Initialize at home
2. Dive
3. Navigate to an inspection asset
4. Detect and track the asset
5. Maintain a useful inspection path / standoff
6. Recover from basic failures
7. Return home

## Architecture

Sensors
  -> State Estimation + Perception
  -> Lightweight World Model
  -> Autonomy
  -> Controls
  -> Vehicle Interface
  -> Simulator / Real Vehicle

## Core Rule

Each module communicates through defined ROS 2 interfaces.

Only `neptune_vehicle` should know about low-level vehicle-specific systems such as:
- ArduSub
- MAVROS
- MAVLink
- Stonefish actuator interfaces
- vendor-specific hardware APIs

The rest of Neptune should remain vehicle-independent.
