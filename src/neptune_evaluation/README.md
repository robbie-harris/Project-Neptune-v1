# S2.3 DVL dead-reckoning benchmark

S2.3 tooling and three live cases are complete; see the handoff for exact results.
The estimator and mission implementation are unchanged. Truth is consumed only
by the evaluator (and recorded for evaluation). IMU/pressure use raw topics.

## Fixed matrix

Every case uses seed **42**. Noise is independent Gaussian standard deviation
in m/s on **all three original DVL sensor axes**. Bias is additive sensor-x;
it is not vehicle surge bias. All unlisted degrader parameters are zero.

| Case | Noise sigma x/y/z (m/s each) | Bias x (m/s) | Drop probability/message |
| --- | --- | --- | --- |
| clean | 0 | 0 | 0 |
| noise_low | 0.005 | 0 | 0 |
| noise_medium | 0.02 | 0 | 0 |
| noise_high | 0.05 | 0 | 0 |
| bias_small | 0 | +0.01 | 0 |
| dropout_mild | 0 | 0 | 0.10 |
| dropout_strong | 0 | 0 | 0.40 |

These engineering stress levels are not manufacturer specifications or measured
ocean distributions. Noise spans 0.5, 2, and 5 cm/s to expose increasing integrated
error. A 0.01 m/s bias accumulates 1 m per 100 s before frame rotations and
closed-loop effects. Independent dropout retains approximately 18 and 12 Hz
from a nominal 20 Hz stream. It tests interpolation across missing samples,
not sustained bottom-lock loss. Each row isolates one effect; even clean passes
DVL through the same degrader/remapping path.

## One-command live workflow

S2.3 is complete with operator-supplied clean, low-noise and medium-noise live
results recorded exactly in [PROJECT_HANDOFF.md](../../docs/PROJECT_HANDOFF.md).
High noise, bias, both dropout cases and repeated/randomized trials are deferred
to S2.13; do not run a sweep as part of S2.3 finalization.

From the repository root run one selected case:

```bash
./scripts/run_s23_case.sh noise_medium
```

Prerequisites are the existing Docker dev image/service, GPU/display access,
verified Stonefish installation and installed overlays at `/workspace/install`,
`/tmp/neptune-s22-install`, and `/tmp/neptune-s23-install` inside the container.
The script sources ROS Jazzy and `/opt/stonefish_ws/install` itself. It uses the
verified `/workspace/external/stonefish/Tests/Data/02_port_pipe_mission.scn`
scenario with the corresponding Tests/Data root and arguments `100 800 600 low`.

The runner serializes cases, safely stops exact prior experiment executables,
starts fresh Stonefish, waits for services, respawns GIRONA500 at the known
origin, then enables dynamics/pressure/IMU filter/DVL and checks odometry/DVL
messages. It launches the degrader, adapter, pressure estimator, dead reckoning,
evaluator and mission. Only DVL is remapped to `/degraded/dvl`.

The literal COMPLETE log event is required; mission timeout and early process
exit are failures. Mission wait is bounded to 430 seconds. Evaluator shutdown
signals its actual process with SIGINT, waits at most eight seconds, then uses
bounded TERM/KILL escalation. Forced shutdown is failure; success requires valid
metrics with accepted pairs. Exit and interruption traps clean all experiment
processes including Stonefish. The whole run has a 650-second backstop with a
40-second kill deadline. Ctrl+C requires no manual node recovery.

Each invocation retains a unique container directory
`/tmp/neptune-s23-results/<case>.<suffix>`, including logs, health samples,
conditions, mission status/reason and `metrics.json`. The final output prints
case/status/metrics path/result directory and any failure reason. Copy artifacts
out before replacing the container. The runner does not automatically record a
bag or full revision/environment manifest.

The older `ros2 run neptune_evaluation dvl_benchmark` preparer and generated
`commands.txt` remain for historical provenance and specialized manual workflows;
they are not required for normal live cases. Do not mix their manual processes
with an active runner. Runner changes have quick static/helper validation; the
revised full live lifecycle awaits future live execution.

## Results and comparison

Keep each entire run directory. `metrics.json` contains unrounded horizontal and
3D RMSE, maximum and final horizontal/3D error, yaw RMSE (radians, null if
unavailable), depth metrics, accepted pairs and rejected count. Positions are
metres. `sample_count` equals `accepted_sample_count`. Rejected count follows
S2.1: invalid/repeated input messages or timestamp-skew discards; it is not the
number of lost DVL packets. The evaluator can replace pending samples without
incrementing this counter. Preserve this definition when comparing estimators.
DVL received/published/dropped counts are in `degrader.log` at 5 s intervals;
those diagnostics may precede shutdown. Bags provide a fuller audit trail.

Tabulate one row per case using metrics.json plus manifest outcome/reason.
Zero accepted pairs makes the run invalid; do not substitute zeros for null RMSE.
S2.1 aligns first accepted positions and weights accepted pairs equally, rather
than weighting by time. Final error is at the last accepted pair, which may
precede the operator endpoint during dropout. Logs/bags and stamps expose this.
Do not compare runs with different alignment, skew, clock policy, or endpoint
rules without explicitly reporting that difference.

Fixed seeds reproduce the same perturbations for the same ordered received DVL
sequence and Python runtime. DDS losses, simulator timing stalls, startup timing,
and changed closed-loop trajectories can change that sequence and the outcome.
A single seed per condition is a small initial benchmark, not a statistical
reliability study. No burst dropout, IMU/pressure degradation, EKF/ESKF, or
Monte Carlo work is included.

## Validation in the implementation environment

Finalization: 38 evaluation/degradation unit tests passed; Python compileall and
selected `neptune_evaluation` build passed. Bash syntax, exact process matching,
graceful/forced bounded shutdown helpers, seven case mappings, invalid-case
handling and whitespace checks passed. An isolated installed evaluator shutdown
check also passed: SIGINT wrote valid zero-pair JSON without a simulator. No new
live mission or startup smoke was
run. The prior combined evaluation/sim build lacked generated Stonefish
`package.sh`; a separate packaging-only sim build passed historically. Full
runner integration remains a future live check. These three supplied single-run
results are engineering evidence, not statistical performance estimates. Medium
noise was materially worse than low noise; clean need not beat every noisy run
because live timing varies. Repeated trials belong in S2.13.
