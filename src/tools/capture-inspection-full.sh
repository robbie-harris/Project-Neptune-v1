#!/usr/bin/env bash
# Run only after the 60-image local+cloud-export pilot audit has passed.
set -euo pipefail
NEPTUNE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$NEPTUNE_ROOT"
[[ ! -e data/inspection/sealed_dataset.json ]] || { echo 'Dataset is sealed; preserve this experiment and use a new output directory.' >&2; exit 1; }
[[ "$(git branch --show-current)" == Perception ]] || { echo 'Use Perception.' >&2; exit 1; }
.venv-host/bin/python - <<'PY'
import json,hashlib,sys
from pathlib import Path
sys.path.insert(0,'src/tools')
from inspection_dataset import audit
report=json.loads(Path('outputs/inspection-pilot-export-audit.json').read_text())
local=audit(Path('data/inspection'))
lines=Path('data/inspection/manifest.jsonl').read_text().splitlines(keepends=True)
pilot_hash=hashlib.sha256(''.join(lines[:60]).encode()).hexdigest()
if not report.get('passed') or report.get('images')!=60 or report.get('manifest_sha256')!=pilot_hash:
    raise RuntimeError('Capture requires the exact verified pilot export')
PY
mkdir -p data models outputs
# The pilot is already in this manifest; --resume preserves those image identities.
for variant in 0 1 2 3; do
  name="neptune-inspection-capture"
  docker run -d --name "$name" --platform linux/arm64 --cpus 8 --shm-size=1g \
    -e LP_NUM_THREADS=8 \
    -v "$NEPTUNE_ROOT/data:/workspace/data" -v "$NEPTUNE_ROOT/models:/workspace/models" \
    -v "$NEPTUNE_ROOT/outputs:/workspace/outputs" \
    neptune-perception ros2 launch neptune_sim pipe_tank.launch.py \
    "scenario:=/opt/neptune/install/neptune_sim/share/neptune_sim/scenarios/inspection_variant_${variant}.scn" \
    > "outputs/inspection-variant-${variant}-container.txt"
  cleanup() { docker stop "$name" >/dev/null 2>&1 || true; }
  trap cleanup EXIT INT TERM
  docker exec "$name" bash -lc "source /opt/ros/jazzy/setup.bash && source /opt/stonefish_ws/install/setup.bash && source /opt/neptune/install/setup.bash && python3 /opt/neptune/src/tools/capture_inspection.py --output /workspace/data/inspection --groups 900 --resume --partition-scenes --scene-variant ${variant} --disable-overview" \
    > "outputs/capture-inspection-variant-${variant}.log" 2>&1
  docker logs "$name" > "outputs/inspection-variant-${variant}-simulator.log" 2>&1
  cleanup
  docker rm "$name" >/dev/null
  trap - EXIT INT TERM
done
.venv-host/bin/python src/tools/roboflow_inspection.py prepare --data data/inspection \
  --archive outputs/inspection-full.zip --expected 9000 --full \
  > outputs/inspection-full-transfer-audit.json
