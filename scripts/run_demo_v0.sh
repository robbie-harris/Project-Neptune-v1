#!/usr/bin/env bash
# One host command; reuses the existing dev container and an already-built overlay.
set -euo pipefail
cd "$(dirname "$0")/.."
presentation_env=()
if [[ ${1:-} == --presentation ]]; then
  shift
  set -- presentation:=true "$@"
  powershell=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
  if [[ -x "$powershell" ]] && command -v wslpath >/dev/null; then
    window_helper=$(wslpath -w "$PWD/scripts/demo_presentation_windows.ps1")
    geometry=$("$powershell" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$window_helper" -Action geometry)
    read -r viewport_width viewport_height < <(python3 -c 'import json,sys; g=json.loads(sys.argv[1]); print(g["width"],g["height"])' "$geometry")
    presentation_env=(-e "NEPTUNE_PRESENTATION_WIDTH=$viewport_width" -e "NEPTUNE_PRESENTATION_HEIGHT=$viewport_height")
    if [[ " $* " != *" --show-args "* ]]; then
      "$powershell" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$window_helper" -Action layout > /tmp/neptune-presentation-layout.log 2>&1 &
    fi
  fi
fi
docker info >/dev/null
container=$(docker compose -f docker/compose.yaml ps -a -q dev)
[[ -n "$container" ]] || { echo 'Existing Neptune dev container missing; no image build attempted.' >&2; exit 1; }
if [[ $(docker inspect --format '{{.State.Running}}' "$container") != true ]]; then
  docker start "$container" >/dev/null
fi
exec docker exec -it "${presentation_env[@]}" -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-92}" \
  -e NEPTUNE_DEMO_INSTALL="${NEPTUNE_DEMO_INSTALL:-}" "$container" bash -c '
    set -e
    source /opt/ros/jazzy/setup.bash
    source /opt/stonefish_ws/install/setup.bash
    source /workspace/install/setup.bash
    demo_install=${NEPTUNE_DEMO_INSTALL:-/workspace/install}
    if [[ ! -f "$demo_install/neptune_bringup/share/ament_index/resource_index/packages/neptune_bringup" ]]; then
      [[ -n ${NEPTUNE_DEMO_INSTALL:-} ]] || demo_install=/tmp/neptune-demo-v0-install
    fi
    [[ -f "$demo_install/setup.bash" ]] || { echo "Build the Demo V0 packages first; missing $demo_install/setup.bash" >&2; exit 1; }
    source "$demo_install/setup.bash"
    export PYTHONDONTWRITEBYTECODE=1
    export ROS_LOG_DIR=${ROS_LOG_DIR:-/tmp/neptune-demo-v0-ros-logs}
    exec ros2 launch neptune_bringup perception_demo.launch.py \
      simulation_data:=/workspace/external/stonefish/Tests/Data "$@"
  ' bash "$@"
