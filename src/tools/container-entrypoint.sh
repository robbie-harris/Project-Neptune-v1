#!/usr/bin/env bash
set -e
source /opt/ros/jazzy/setup.bash
source /opt/stonefish_ws/install/setup.bash
source /opt/neptune/install/setup.bash
/opt/neptune/src/tools/start-vnc.sh >/tmp/neptune-vnc.log 2>&1
exec "$@"
