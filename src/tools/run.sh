#!/usr/bin/env bash
set -euo pipefail
NEPTUNE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$NEPTUNE_ROOT"
if [[ "$(git branch --show-current)" != Perception ]]; then
    echo 'Switch Project-Neptune to Perception before using this milestone.' >&2; exit 1
fi
if [[ "${1:-}" == --build ]]; then
    shift
    docker build --platform linux/arm64 -f Simulation/docker/Dockerfile -t neptune-perception "$@" .
    exit
fi
mkdir -p data models outputs
exec docker run --rm -it --name neptune-perception --platform linux/arm64 \
    -p 127.0.0.1:5900:5900 -p 127.0.0.1:6080:6080 -p 127.0.0.1:9090:9090 \
    --cpus 8 --shm-size=1g -e LP_NUM_THREADS=8 \
    -v "$NEPTUNE_ROOT/data:/workspace/data" -v "$NEPTUNE_ROOT/models:/workspace/models" \
    -v "$NEPTUNE_ROOT/outputs:/workspace/outputs" \
    neptune-perception "$@"
