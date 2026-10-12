#!/usr/bin/env bash
set -euo pipefail
NEPTUNE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$NEPTUNE_ROOT"
test -s .secrets/roboflow_api_key || { echo 'Configure .secrets/roboflow_api_key first.' >&2; exit 1; }
if [[ "$(git branch --show-current)" != Perception ]]; then
    echo 'Switch to Perception before running.' >&2; exit 1
fi
docker network inspect neptune-local >/dev/null
exec docker run --rm -it --name neptune-perception --platform linux/arm64 \
    --network neptune-local \
    -p 127.0.0.1:5900:5900 -p 127.0.0.1:6080:6080 -p 127.0.0.1:9090:9090 \
    --cpus 8 --shm-size=1g -e LP_NUM_THREADS=8 \
    -v "$NEPTUNE_ROOT/data:/workspace/data" -v "$NEPTUNE_ROOT/models:/workspace/models" \
    -v "$NEPTUNE_ROOT/outputs:/workspace/outputs" \
    -v "$NEPTUNE_ROOT/.secrets/roboflow_api_key:/run/secrets/roboflow_api_key:ro" \
    neptune-perception ros2 launch neptune_sim pipe_tank.launch.py backend:=roboflow \
    model_id:=projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1 confidence:=0.05 "$@"
