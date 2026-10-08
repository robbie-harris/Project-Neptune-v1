#!/usr/bin/env bash
# One case only. Requires the verified Docker/ROS overlays already installed.
set -eo pipefail
CASE=${1:-}
case "$CASE" in
  clean) NOISE=0.0; BIAS=0.0; DROP=0.0 ;;
  noise_low) NOISE=0.005; BIAS=0.0; DROP=0.0 ;;
  noise_medium) NOISE=0.02; BIAS=0.0; DROP=0.0 ;;
  noise_high) NOISE=0.05; BIAS=0.0; DROP=0.0 ;;
  bias_small) NOISE=0.0; BIAS=0.01; DROP=0.0 ;;
  dropout_mild) NOISE=0.0; BIAS=0.0; DROP=0.10 ;;
  dropout_strong) NOISE=0.0; BIAS=0.0; DROP=0.40 ;;
  *) echo 'Usage: ./scripts/run_s23_case.sh {clean|noise_low|noise_medium|noise_high|bias_small|dropout_mild|dropout_strong}' >&2; exit 2 ;;
esac

if [[ ${2:-} != --internal ]]; then
  cd "$(dirname "$0")/.."
  docker compose -f docker/compose.yaml up -d dev >/dev/null
  # The inner timeout is a final backstop, including interruption of Docker's client.
  interrupt_runner() {
    trap - INT TERM
    # Target only the exact inner Bash argv, never a substring of a shell command.
    timeout --kill-after=2s 12s docker compose -f docker/compose.yaml exec -T dev python3 -c '
import pathlib, os, signal
for root in pathlib.Path("/proc").iterdir():
    if not root.name.isdigit(): continue
    try:
        argv = (root / "cmdline").read_bytes().split(b"\0")
        if len(argv) == 5 and argv[0] == b"bash" and argv[1] == b"/workspace/scripts/run_s23_case.sh" and argv[3] == b"--internal":
            os.kill(int(root.name), signal.SIGTERM)
    except (OSError, ProcessLookupError): pass
' || true
  }
  trap 'interrupt_runner; exit 130' INT
  trap 'interrupt_runner; exit 143' TERM
  docker compose -f docker/compose.yaml exec -T dev \
    timeout --signal=TERM --kill-after=40s 650s \
    bash /workspace/scripts/run_s23_case.sh "$CASE" --internal &
  client_pid=$!
  wait "$client_pid"
  exit $?
fi

source /opt/ros/jazzy/setup.bash
source /opt/stonefish_ws/install/setup.bash
source /workspace/install/setup.bash
source /tmp/neptune-s22-install/setup.bash
source /tmp/neptune-s23-install/setup.bash
# Serialize experiments; never clean up another active runner.
exec 9>/tmp/neptune-s23-runner.lock
flock -n 9 || { echo 'ERROR: another S2.3 runner is active' >&2; exit 1; }
mkdir -p /tmp/neptune-s23-results
RESULT=$(mktemp -d "/tmp/neptune-s23-results/${CASE}.XXXXXXXX")
printf 'case=%s\nseed=42\nnoise_sigma_xyz=%s\nbias_x=%s\ndrop_probability=%s\nscenario=/workspace/external/stonefish/Tests/Data/02_port_pipe_mission.scn\n' \
  "$CASE" "$NOISE" "$BIAS" "$DROP" > "$RESULT/conditions.txt"
STATUS=FAILED
REASON='runner exited before mission completion'
PIDS=()
EVALUATOR_PID=

alive() {
  [[ -r /proc/$1/stat ]] || return 1
  local stat
  stat=$(cat "/proc/$1/stat" 2>/dev/null) || return 1
  [[ ${stat#*) } != Z* ]]
}
stop_pid() {
  local pid=$1 signal=$2 seconds=$3 deadline
  STOP_FORCED=0
  alive "$pid" || return 0
  kill -"$signal" "$pid" 2>/dev/null || true
  deadline=$((SECONDS + seconds))
  while alive "$pid" && (( SECONDS < deadline )); do sleep 0.1; done
  if alive "$pid"; then
    STOP_FORCED=1
    kill -TERM "$pid" 2>/dev/null || true
    deadline=$((SECONDS + 2))
    while alive "$pid" && (( SECONDS < deadline )); do sleep 0.1; done
  fi
  if alive "$pid"; then kill -KILL "$pid" 2>/dev/null || true; fi
  # Never wait on a potentially uninterruptible process.
}
cleanup() {
  local rc=$? pid
  trap - EXIT INT TERM
  if [[ -n $EVALUATOR_PID ]]; then stop_pid "$EVALUATOR_PID" INT 8; fi
  for pid in "${PIDS[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
  for pid in "${PIDS[@]}"; do stop_pid "$pid" TERM 1; done
  printf '\nCase: %s\nMission status: %s\nmetrics.json: %s\nResult directory: %s\n' \
    "$CASE" "$STATUS" "$RESULT/metrics.json" "$RESULT"
  if [[ $STATUS != COMPLETE ]]; then printf 'Failure: %s\n' "$REASON"; fi
  printf '%s\n' "$STATUS" > "$RESULT/mission-status.txt"
  printf '%s\n' "$REASON" > "$RESULT/outcome-reason.txt"
  exit "$rc"
}
trap cleanup EXIT
trap 'REASON="interrupted"; exit 130' INT
trap 'REASON="terminated (or runner deadline reached)"; exit 143' TERM
fail() { REASON=$*; echo "ERROR: $REASON" >&2; exit 1; }

# Resolve actual executables once. No ros2-run launcher PIDs are used.
PACKAGES=(stonefish_ros2 neptune_sim neptune_vehicle neptune_state_estimation neptune_state_estimation neptune_evaluation neptune_autonomy)
NAMES=(stonefish_simulator sensor_degrader stonefish_adapter pressure_depth dead_reckoning_state localization_evaluator mission_executive)
EXES=()
for i in "${!NAMES[@]}"; do
  prefix=$(timeout --kill-after=2s 5s ros2 pkg prefix "${PACKAGES[$i]}") || fail "missing package ${PACKAGES[$i]}"
  exe="$prefix/lib/${PACKAGES[$i]}/${NAMES[$i]}"
  [[ -x $exe ]] || fail "missing executable $exe"
  EXES+=("$exe")
done
# Inspect NUL-delimited argv, never regex/pkill command strings. Match only argv[0]
# or a Python interpreter's argv[1], and recheck identity before every signal.
python3 - "${EXES[@]}" <<'PY'
import os, pathlib, signal, sys, time
paths = set(sys.argv[1:])
def identity(pid):
    try:
        root = pathlib.Path('/proc') / str(pid)
        argv = (root / 'cmdline').read_bytes().split(b'\0')
        argv = [os.fsdecode(a) for a in argv if a]
        stat = (root / 'stat').read_text().rsplit(') ', 1)[1].split()
        match = argv and (argv[0] in paths or (
            len(argv) > 1 and pathlib.Path(argv[0]).name.startswith('python') and argv[1] in paths))
        return stat[19] if match and stat[0] != 'Z' else None
    except (OSError, IndexError):
        return None
victims = {int(p.name): identity(int(p.name)) for p in pathlib.Path('/proc').iterdir() if p.name.isdigit()}
victims = {pid: stamp for pid, stamp in victims.items() if stamp}
for sig, delay in ((signal.SIGTERM, 3), (signal.SIGKILL, 1)):
    for pid, stamp in victims.items():
        if identity(pid) == stamp:
            try: os.kill(pid, sig)
            except ProcessLookupError: pass
    end = time.monotonic() + delay
    while time.monotonic() < end and any(identity(p) == s for p, s in victims.items()):
        time.sleep(.1)
if any(identity(p) == s for p, s in victims.items()):
    sys.exit('ERROR: previous experiment process could not be stopped')
PY

launch() {
  local index=$1 log=$2
  shift 2
  # Bash backgrounds inherit ignored SIGINT. Reset it before exec so rclpy's
  # handler receives graceful shutdown, and PID remains the actual node PID.
  python3 -c 'import os,signal,sys; signal.signal(signal.SIGINT,signal.SIG_DFL); os.execv(sys.argv[1],sys.argv[1:])' \
    "${EXES[$index]}" "$@" > "$RESULT/$log.log" 2>&1 &
  LAST_PID=$!
  PIDS+=("$LAST_PID")
}
launch 0 stonefish /workspace/external/stonefish/Tests/Data \
  /workspace/external/stonefish/Tests/Data/02_port_pipe_mission.scn 100 800 600 low
SIM_PID=$LAST_PID
services=(/respawn_robot /sim/dynamics/set_enabled /sim/pressure/set_enabled /sim/imu_filter/set_enabled /sim/dvl/set_enabled)
deadline=$((SECONDS + 40))
while :; do
  alive "$SIM_PID" || fail 'Stonefish exited during startup'
  listing=$(timeout --kill-after=1s 3s ros2 service list 2>/dev/null) || listing=
  ready=1
  for service in "${services[@]}"; do
    if ! grep -Fxq "$service" <<< "$listing"; then ready=0; fi
  done
  (( ready )) && break
  (( SECONDS < deadline )) || fail 'Stonefish services did not become ready within 40s'
  sleep 1
done
service_call() {
  timeout --kill-after=2s 8s ros2 service call "$@" > "$RESULT/service-response.log" 2>&1 \
    || fail "service call failed/timed out: $1"
  cat "$RESULT/service-response.log" >> "$RESULT/services.log"
  grep -Eq 'success[=:] ?(False|false)' "$RESULT/service-response.log" && fail "service refused: $1"
  return 0
}
service_call /respawn_robot stonefish_ros2/srv/Respawn \
  '{name: GIRONA500, origin: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}}'
for service in "${services[@]:1}"; do service_call "$service" std_srvs/srv/SetBool '{data: true}'; done
for topic in /sim/odometry /sim/dvl; do
  timeout --kill-after=2s 8s ros2 topic echo --once "$topic" > "$RESULT/${topic##*/}-health.log" 2>&1 \
    || fail "no message on $topic within 8s"
done
launch 1 degrader --ros-args -p seed:=42 \
  -p dvl_noise_std_x:="$NOISE" -p dvl_noise_std_y:="$NOISE" -p dvl_noise_std_z:="$NOISE" \
  -p dvl_bias_x:="$BIAS" -p dvl_dropout_probability:="$DROP"
launch 2 adapter
launch 3 pressure
launch 4 estimator --ros-args -r /sim/dvl:=/degraded/dvl
sleep 3
launch 5 evaluator --ros-args -p result_path:="$RESULT/metrics.json"
EVALUATOR_PID=$LAST_PID
sleep 2
launch 6 mission
STATUS=RUNNING
deadline=$((SECONDS + 430))
while :; do
  grep -Fq 'MISSION TIMEOUT' "$RESULT/mission.log" && fail 'mission reported MISSION TIMEOUT'
  for pid in "${PIDS[@]}"; do alive "$pid" || fail "experiment process $pid exited early"; done
  if grep -Fq '========== COMPLETE ==========' "$RESULT/mission.log"; then break; fi
  (( SECONDS < deadline )) || fail 'mission exceeded 430s wall timeout'
  sleep 1
done
stop_pid "$EVALUATOR_PID" INT 8
(( STOP_FORCED == 0 )) || fail 'evaluator graceful shutdown exceeded 8s; forced termination'
alive "$EVALUATOR_PID" && fail 'evaluator did not exit after bounded shutdown'
EVALUATOR_PID=
REASON='evaluator metrics missing, invalid, or contain no accepted pairs'
python3 - "$RESULT/metrics.json" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    metrics = json.load(stream)
if metrics.get('accepted_sample_count', 0) <= 0:
    sys.exit('ERROR: evaluator produced no accepted pairs')
PY
STATUS=COMPLETE
REASON='normal COMPLETE log event; metrics written'
cat "$RESULT/metrics.json"
