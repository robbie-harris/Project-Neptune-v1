#!/usr/bin/env bash
# One bounded observation-only smoke, after unit tests and package build.
set -euo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/neptune-p4a-smoke.lock
flock -n 9 || { echo 'Another P4a smoke owns the runtime'; exit 1; }
inference_compose=(docker compose -f docker/compose.perception.yaml)
if [[ -n "$("${inference_compose[@]}" ps -q --status running inspection_inference)" ]]; then
  echo 'Inference service already running; stop it explicitly before this owned smoke'
  exit 1
fi
owned=0
cleanup() {
  if [[ "$owned" == 1 ]]; then
    timeout --kill-after=3s 20s "${inference_compose[@]}" stop -t 5 inspection_inference
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
owned=1
timeout --kill-after=5s 30s "${inference_compose[@]}" up -d --pull never inspection_inference
timeout --kill-after=3s 15s "${inference_compose[@]}" exec -T inspection_inference nvidia-smi
timeout --kill-after=10s 175s docker compose -f docker/compose.yaml exec -T dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /opt/stonefish_ws/install/setup.bash
  source /tmp/neptune-p3-final-install/setup.bash
  source /tmp/neptune-p4a-install/setup.bash
  timeout --signal=INT --kill-after=8s 165s env ROS_DOMAIN_ID=83 \
    python3 /workspace/scripts/perception_p4a_smoke.py
'
