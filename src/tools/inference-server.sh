#!/usr/bin/env bash
set -euo pipefail
NEPTUNE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$NEPTUNE_ROOT"
mkdir -p outputs/inference-cache
docker network inspect neptune-local >/dev/null 2>&1 || docker network create neptune-local >/dev/null
exec docker run --rm --name neptune-inference --platform linux/arm64 \
    --network neptune-local -p 127.0.0.1:9001:9001 --cpus "${NEPTUNE_INFERENCE_CPUS:-4}" --cpuset-cpus "${NEPTUNE_INFERENCE_CPUSET:-0-3}" \
    --env-file Simulation/docker/inference.env \
    -v "$NEPTUNE_ROOT/outputs/inference-cache:/tmp:rw" \
    "$(cat Simulation/docker/inference-image.txt)"
