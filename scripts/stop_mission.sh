#!/usr/bin/env bash

echo "=== NEPTUNE SAFE STOP ==="

echo "Stopping active Neptune controllers..."

# Kill high-level control/autonomy processes.
#
# The bracket trick prevents pkill from matching this shell command itself.
pkill -TERM -f "[d]epth_hold" 2>/dev/null || true
pkill -TERM -f "[w]aypoint_hold" 2>/dev/null || true
pkill -TERM -f "[m]ission_executive" 2>/dev/null || true
pkill -TERM -f "[h]eading_test" 2>/dev/null || true

sleep 0.5

echo "Publishing zero body command..."

# Never allow a ROS CLI publisher to block the emergency-stop script.
timeout 2s ros2 topic pub --once \
    /neptune/cmd_body \
    geometry_msgs/msg/Twist \
    "{}" \
    >/dev/null 2>&1 || true

echo "Publishing zero thruster command..."

# Direct Stonefish zero-thrust command.
# This is our second safety layer if the vehicle adapter is unavailable.
timeout 2s ros2 topic pub --once \
    /sim/thruster_setpoints \
    std_msgs/msg/Float64MultiArray \
    "{data: [0.0, 0.0, 0.0, 0.0, 0.0]}" \
    >/dev/null 2>&1 || true

echo "SAFE STOP COMPLETE."