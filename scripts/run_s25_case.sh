#!/usr/bin/env bash
# One case only. Requires the verified Docker/ROS overlays already installed.
set -eo pipefail
CASE=${1:-}
case "$CASE" in
  clean) BIAS=0.0 ;;
  pressure_bias) BIAS=1000.0 ;;
  *) echo 'Usage: ./scripts/run_s25_case.sh {clean|pressure_bias}' >&2; exit 2 ;;
esac

if [[ ${2:-} != --internal ]]; then
  cd "$(dirname "$0")/.."
  timeout --kill-after=5s 60s docker compose -f docker/compose.yaml up -d dev >/dev/null
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
        if len(argv) == 5 and argv[0] == b"bash" and argv[1] == b"/workspace/scripts/run_s25_case.sh" and argv[3] == b"--internal":
            os.kill(int(root.name), signal.SIGTERM)
    except (OSError, ProcessLookupError): pass
' || true
  }
  trap 'interrupt_runner; exit 130' INT
  trap 'interrupt_runner; exit 143' TERM
  timeout --signal=TERM --kill-after=10s 700s docker compose -f docker/compose.yaml exec -T dev \
    timeout --signal=TERM --kill-after=40s 650s \
    bash /workspace/scripts/run_s25_case.sh "$CASE" --internal &
  client_pid=$!
  client_rc=0
  wait "$client_pid" || client_rc=$?
  if (( client_rc == 124 || client_rc == 137 )); then interrupt_runner; fi
  exit "$client_rc"
fi

source /opt/ros/jazzy/setup.bash
source /opt/stonefish_ws/install/setup.bash
source /workspace/install/setup.bash
source /tmp/neptune-s22-install/setup.bash
source /tmp/neptune-s23-install/setup.bash
# Serialize experiments; never clean up another active runner.
exec 9>/tmp/neptune-s23-runner.lock
flock -n 9 || { echo 'ERROR: another S2.3/S2.4/S2.5 runner is active' >&2; exit 1; }
mkdir -p /tmp/neptune-s25-results
RESULT=$(mktemp -d "/tmp/neptune-s25-results/${CASE}.XXXXXXXX")
printf 'case=%s\nseed=42\npressure_bias_pa=%s\npressure_noise_std_pa=0.0\npressure_dropout_probability=0.0\ndvl_input=/sim/dvl\npressure_input=/degraded/pressure\nimu_input=/sim/imu\nimu_dvl_degradation=zero\nscenario=/workspace/external/stonefish/Tests/Data/02_port_pipe_mission.scn\n' \
  "$CASE" "$BIAS" > "$RESULT/conditions.txt"
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
# One startup budget covers discovery, respawn and all enable responses.
STARTUP_DEADLINE=$((SECONDS + 120))
while :; do
  alive "$SIM_PID" || fail 'Stonefish exited during startup'
  remaining=$((STARTUP_DEADLINE - SECONDS))
  (( remaining > 1 )) || fail 'Stonefish service discovery exceeded 120s startup timeout'
  attempt_timeout=3
  (( remaining > 4 )) || attempt_timeout=$((remaining - 1))
  listing=$(timeout --kill-after=1s "${attempt_timeout}s" ros2 service list 2>/dev/null) || listing=
  ready=1
  for service in "${services[@]}"; do
    if ! grep -Fxq "$service" <<< "$listing"; then
      echo "Waiting for Stonefish service: $service"
      ready=0
    fi
  done
  (( ready )) && break
  (( SECONDS < STARTUP_DEADLINE )) || fail 'Stonefish service discovery exceeded 120s startup timeout'
  sleep 1
done
service_call() {
  local attempt=0 remaining attempt_timeout rc
  while :; do
    alive "$SIM_PID" || fail "Stonefish exited while waiting for service: $1"
    remaining=$((STARTUP_DEADLINE - SECONDS))
    (( remaining > 2 )) || fail "120s startup timeout waiting for successful response: $1"
    attempt_timeout=8
    # Reserve the kill deadline even for the final attempt.
    (( remaining > 10 )) || attempt_timeout=$((remaining - 2))
    attempt=$((attempt + 1))
    echo "Waiting for Stonefish service response: $1 (attempt $attempt)"
    rc=0
    timeout --kill-after=2s "${attempt_timeout}s" ros2 service call "$@" \
      > "$RESULT/service-response.log" 2>&1 || rc=$?
    printf '\nService: %s; attempt: %s; exit: %s\n' "$1" "$attempt" "$rc" >> "$RESULT/services.log"
    cat "$RESULT/service-response.log" >> "$RESULT/services.log"
    if (( rc == 0 )) && grep -Eq 'success[=:][[:space:]]*(True|true)' "$RESULT/service-response.log"; then
      echo "Stonefish service succeeded: $1"
      return 0
    fi
    echo "Retrying Stonefish service: $1 (failed, timed out, or no positive success response; exit $rc)"
    (( SECONDS < STARTUP_DEADLINE )) || fail "120s startup timeout waiting for successful response: $1"
    sleep 1
  done
}
service_call /respawn_robot stonefish_ros2/srv/Respawn \
  '{name: GIRONA500, origin: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}}'
for service in "${services[@]:1}"; do service_call "$service" std_srvs/srv/SetBool '{data: true}'; done
for topic in /sim/odometry /sim/dvl /sim/imu; do
  timeout --kill-after=2s 8s ros2 topic echo --once "$topic" > "$RESULT/${topic##*/}-health.log" 2>&1 \
    || fail "no message on $topic within 8s"
done
# Require a live raw pressure sample immediately before degrader startup.
timeout --kill-after=2s 8s ros2 topic echo --once /sim/pressure sensor_msgs/msg/FluidPressure \
  > "$RESULT/pressure-health.log" 2>&1 \
  || fail 'raw /sim/pressure produced no message within 8s before degrader startup'
# launch() execs the installed executable directly and retains its actual PID.
launch 1 degrader --ros-args -p seed:=42 \
  -p pressure_bias:="$BIAS" -p pressure_noise_std:=0.0 -p pressure_dropout_probability:=0.0
DEGRADER_PID=$LAST_PID
degrader_fail() {
  echo 'sensor_degrader startup diagnostics (degrader.log):' >&2
  cat "$RESULT/degrader.log" >&2 || true
  fail "$@"
}
alive "$DEGRADER_PID" || degrader_fail 'sensor_degrader exited immediately after launch'
# Supply the type explicitly: auto-detection exits immediately if the new
# publisher has not reached the ROS graph yet, despite the enclosing timeout.
# Allow DDS discovery/node initialization while checking for early process exit.
# Register the bounded probe for trap cleanup on interruption as well.
timeout --kill-after=2s 20s ros2 topic echo --once /degraded/pressure sensor_msgs/msg/FluidPressure \
  > "$RESULT/degraded-pressure-health.log" 2>&1 &
PRESSURE_PROBE_PID=$!
PIDS+=("$PRESSURE_PROBE_PID")
pressure_deadline=$((SECONDS + 22))
while alive "$PRESSURE_PROBE_PID"; do
  if ! alive "$DEGRADER_PID"; then
    stop_pid "$PRESSURE_PROBE_PID" TERM 1
    degrader_fail 'sensor_degrader exited while waiting for /degraded/pressure'
  fi
  if (( SECONDS >= pressure_deadline )); then
    stop_pid "$PRESSURE_PROBE_PID" TERM 1
    degrader_fail 'no /degraded/pressure message within 20s (probe shutdown deadline reached)'
  fi
  sleep 0.1
done
# The probe has exited, so this wait only collects its status; it cannot hang.
pressure_probe_rc=0
wait "$PRESSURE_PROBE_PID" || pressure_probe_rc=$?
# A successful completed probe must not appear as an exited mission process.
PIDS=("${PIDS[@]:0:${#PIDS[@]}-1}")
alive "$DEGRADER_PID" || degrader_fail 'sensor_degrader exited during degraded pressure startup check'
(( pressure_probe_rc == 0 )) \
  || degrader_fail "no /degraded/pressure message within 20s or topic probe failed (exit $pressure_probe_rc); raw pressure was verified before degrader launch"
launch 2 adapter
launch 3 pressure --ros-args -r /sim/pressure:=/degraded/pressure
launch 4 estimator
# Independent absolute-z snapshots: existing evaluator aligns away constant z bias.
# These sequential samples are diagnostic, not synchronized evaluator pairs.
vertical_snapshot() {
  local phase=$1 topic label
  for topic in /state/odometry /sim/odometry; do
    label=truth
    [[ $topic != /state/odometry ]] || label=estimate
    timeout --kill-after=2s 8s ros2 topic echo --once "$topic" --field pose.pose.position.z \
      > "$RESULT/${phase}-$label-z.log" 2>&1 \
      || fail "no absolute z snapshot on $topic within 8s"
  done
}
sleep 3
vertical_snapshot initial
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
if metrics.get('yaw_sample_count', 0) <= 0 or metrics.get('yaw_rmse') is None:
    sys.exit('ERROR: evaluator produced no yaw metrics')
if metrics.get('accepted_sample_count', 0) <= 0:
    sys.exit('ERROR: evaluator produced no accepted pairs')
PY
vertical_snapshot final
for phase in initial final; do
  printf "Absolute z snapshots (%s; sequential, unaligned):\n" "$phase"
  cat "$RESULT/$phase-estimate-z.log" "$RESULT/$phase-truth-z.log"
done
STATUS=COMPLETE
REASON='normal COMPLETE log event; metrics written'
cat "$RESULT/metrics.json"
