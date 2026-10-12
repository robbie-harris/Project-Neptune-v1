#!/usr/bin/env bash
set -euo pipefail
NEPTUNE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# Default preserves the pipe-only model. Explicit --candidate enables the
# evaluated three-class experiment; pipe regression blocks normal promotion.
if [[ "${1:-}" == --fast ]]; then
  shift
  exec bash "$NEPTUNE_ROOT/src/tools/run-roboflow.sh" \
    model_id:=projects-zwfft/neptune-inspection-objects-2-yolo11n-t1 \
    confidence:=0.05 \
    scenario:=/opt/neptune/install/neptune_sim/share/neptune_sim/scenarios/inspection_fast.scn \
    mission_config:=/opt/neptune/install/neptune_sim/share/neptune_sim/config/mission_fast.json \
    manual_scale:=0.25 lateral_enabled:=true "$@"
fi
if [[ "${1:-}" == --candidate ]]; then
  shift
  exec bash "$NEPTUNE_ROOT/src/tools/run-roboflow.sh" \
    model_id:=projects-zwfft/neptune-inspection-objects-2-yolo11n-t1 \
    confidence:=0.05 \
    scenario:=/opt/neptune/install/neptune_sim/share/neptune_sim/scenarios/inspection_tank.scn "$@"
fi
exec bash "$NEPTUNE_ROOT/src/tools/run-roboflow.sh" \
  scenario:=/opt/neptune/install/neptune_sim/share/neptune_sim/scenarios/inspection_tank.scn "$@"
