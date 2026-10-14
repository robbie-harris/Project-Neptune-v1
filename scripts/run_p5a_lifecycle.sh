#!/usr/bin/env bash
# One bounded P5a trial; select sign or closed explicitly.
set -euo pipefail
cd "$(dirname "$0")/.."
mode=${1:-}
[[ "$mode" == A || "$mode" == B ]] || { echo "Usage: $0 A|B"; exit 2; }
# Serialize ownership with the unchanged P4a smoke runner.
exec 9>/tmp/neptune-p4a-smoke.lock
flock -n 9 || { echo 'Another perception smoke owns the runtime'; exit 1; }
inference_compose=(docker compose -f docker/compose.perception.yaml)
if [[ -n "$("${inference_compose[@]}" ps -q --status running inspection_inference)" ]]; then
  echo 'Inference service already running; this isolated smoke requires exclusive ownership'
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
timeout --kill-after=3s 15s "${inference_compose[@]}" exec -T inspection_inference nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv
timeout --kill-after=10s 245s docker compose -f docker/compose.yaml exec -T dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /opt/stonefish_ws/install/setup.bash
  source /tmp/neptune-p2-install/setup.bash
  source /tmp/neptune-p4c-install/setup.bash
  source /tmp/neptune-p5a-install/setup.bash
  timeout --signal=INT --kill-after=8s 235s env ROS_DOMAIN_ID=87 \
    python3 /workspace/scripts/perception_p5a_lifecycle.py "$@"
' bash "$@"
