# Project Neptune

## 1. What Neptune Is

Project Neptune is a simulation-first autonomous underwater inspection stack developed under **Project Lumyn / Talon**. The demonstrated development platform is Windows 11 + WSL2 Ubuntu 24.04, ROS 2 Jazzy, Stonefish, and an NVIDIA RTX GPU using WSLg rendering. Real-vehicle deployment is future work.

This document describes the frozen Demo V0 baseline. [INTERFACES.md](INTERFACES.md) specifies public boundaries; [TEAM_CONTRACTS.md](TEAM_CONTRACTS.md) defines independent module work. The previous implementation diary, including experiment history and evidence, is preserved in [PROJECT_HISTORY.md](PROJECT_HISTORY.md). Perception details remain in [PERCEPTION_INTEGRATION.md](PERCEPTION_INTEGRATION.md).

## 2. Demo V0 Capability

```text
WAIT_FOR_STATE → DIVE → TRANSIT → INSPECT → RETURN → ASCEND → COMPLETE
```

Presentation/demo startup may show `INITIALIZING` before arming. Autonomy consumes **onboard estimated state**, not simulation truth:

- `/state/odometry`: canonical downstream navigation estimate.
- `/sim/odometry`: evaluation/debug truth only; it must never drive production mission autonomy.
- `mission_executive`: sole normal `/neptune/cmd_body` publisher.
- `stonefish_vehicle_adapter`: converts body commands to native actuator demands.

The mission establishes HOME from qualified estimated state, dives to 3 m, approaches a pipe target 20 m in negative world X with a 1.5 m standoff, inspects for 5 s, returns HOME, and ascends. The planar arrival threshold remains 0.50 m; surge cutoff is 0.45 m. Route, dwell, depth control, safety, and states are preserved.

Current source motion tuning is max surge 0.80 (previously 0.55), distance gain 0.16 (0.10), minimum moving surge 0.20 (0.15), yaw saturation ±0.60 (±0.25). Yaw P=1.40, rate damping=0.20, and the 30° translation gate are unchanged. Surge is capped by `max(0, 1-abs(yaw_command))` before differential mixing. These are normalized demands, not desired m/s or rad/s. Static tests cover scheduling, sign, authority and transitions. Earlier bounded validation encountered runtime sensor gaps; do not invent precise cruise/turn performance from those aborted runs. The operator has successfully completed an engineering mission and recorded the final presentation. A fully coherent fresh-source overlay still needs separate validation before claiming measured dynamics for that exact build.

## 3. System Data Flow

```text
Stonefish → pressure / IMU / DVL → neptune_state_estimation
         → /state/odometry → neptune_autonomy → /neptune/cmd_body
         → neptune_vehicle → Stonefish thrusters

inspection camera → neptune_perception → inspection observations
                  → future / deferred closed-loop inspection behavior
```

Demo V0 does not enable P4 inference or P5 closed-loop centering. Evaluation may observe truth and estimates; it never closes the production control loop. GUI and freeze diagnostics observe without commanding motion.

## 4. Packages

| Package | Current responsibility |
| --- | --- |
| `neptune_autonomy` | Mission executive, state transitions, estimated-state guidance and body-command generation. |
| `neptune_bringup` | Demo composition, readiness, read-only GUI, safe presentation layout and startup integration. |
| `neptune_controls` | Standalone depth/waypoint controllers and experimental perception alignment controller; not in the normal Demo V0 command chain. |
| `neptune_evaluation` | Estimate/truth metrics and Stage 2 benchmark tooling; allowed to consume simulator truth. |
| `neptune_interfaces` | Reserved directory for future shared ROS definitions; currently `.gitkeep`, no buildable ROS package or custom messages. |
| `neptune_perception` | Inspection detection, A1 pipe candidate inference, fusion and observation/status contracts. |
| `neptune_sim` | Stonefish scenes, performance-profile generation, simulation assets and opt-in degradation tools. |
| `neptune_state_estimation` | Pressure depth + IMU attitude + DVL dead reckoning; ESKF structure and legacy experimental entry points. |
| `neptune_vehicle` | Body-command/native-thruster mapping and watchdog; current backend is Stonefish. |
| `neptune_world` | Reserved environment-abstraction directory; currently `.gitkeep`, no buildable ROS package. |

## 5. Coordinate Convention

Verified from current mission guidance, adapter and scenario source:

- Body **+X bow/forward, +Y starboard, +Z down**.
- `/neptune/cmd_body` is `geometry_msgs/msg/Twist` carrying normalized demands: `linear.x` surge, `linear.y` sway, `linear.z > 0` dive, `angular.z` positive yaw about +Z. Positive yaw turns from body +X toward +Y. Roll/pitch command components are unused.
- Estimated pose is `world_ned`, child `base_link`; positions are metres, attitude is a quaternion, twist is body m/s and rad/s. Horizontal position starts at the estimator origin; depth uses pressure-derived positive-down vehicle depth.

Let `s`, `w`, `h`, `r` be clamped surge, sway, heave and yaw; `C` clamps to [-1,1]. Adapter output order is:

```text
SurgePort       = C(-s-r)
SurgeStarboard  = C(-s+r)
HeaveBow        = C(-h)
HeaveStern      = C(-h)
Sway            = C(w)
SwayFront       = C(w)   # seven-motor mode only
SwayRear        = C(w)   # seven-motor mode only
```

Demo V0 selects seven motors; the adapter defaults to five for older scenes. Native surge thrusters are configured inverted; negative native surge demands implement positive public bow-forward surge. Do not “correct” a sign without reviewing the complete mapping and physical-force tests. Adapter watchdog zeros output after 0.5 s command silence, checked every 0.1 s using its node clock.

**Source/install history needs care.** `_orient_demo_inspection` currently moves the camera to X=-0.97 m and lamps to X=-0.91 m, facing -X; the shared inspection scene faces +X. This is a retained installed-demo camera convention, not evidence that public body +X is sternward. Current source has bow-forward motion changes that may differ from older installed overlays. Verify active package paths, camera extrinsics and native actuator mappings together before rebuilding/reorienting anything. This freeze does not silently change the recorded configuration.

## 6. Demo Commands

Engineering:

```bash
./scripts/run_demo_v0.sh
```

Current tested presentation install:

```bash
NEPTUNE_DEMO_INSTALL=/tmp/neptune-safe-presentation-install \
./scripts/run_demo_v0.sh --presentation
```

The host script reuses the existing Docker dev container, sources ROS, `/opt/stonefish_ws/install`, `/workspace/install`, then the selected Demo overlay last. Default ROS domain is 92. `NEPTUNE_DEMO_INSTALL` names a path **inside the container**. `/tmp` installs are ephemeral and require their original underlays; the recorded overlay is not a reproducible permanent release artifact.

For a later coherent source build, use the provisioned container, source ROS and the Stonefish underlay, and build the actual packages (the two reserved directories are not packages):

```bash
docker exec -it docker-dev-1 bash
cd /workspace
source /opt/ros/jazzy/setup.bash
source /opt/stonefish_ws/install/setup.bash
colcon build --base-paths src --packages-select neptune_sim neptune_vehicle \
  neptune_state_estimation neptune_autonomy neptune_bringup
```

Container names may differ; discover yours through `docker compose -f docker/compose.yaml ps`. This is a build recipe, not a claim that a newly rebuilt source/camera combination has passed another mission. Source the resulting install and verify `ros2 pkg prefix` for each selected package before dynamic testing. Dependencies in ignored `external/` must already be provisioned to build the image; a clean dependency bootstrap/version manifest remains work to do. State estimation currently imports Stonefish's DVL transport message; that dependency must be accounted for even though truth is forbidden.

Both normal and presentation renderer arguments remain **1280×720**. Presentation moves Stonefish left and vertically centers it **without resizing** (including after launch); unused background space is intentional. GUI remains on the right. No unsafe oversized-render flag is provided. The shared camera/rate/physics are not altered by the geometry fix.

## 7. Rendering Issue / Diagnosis

Operator evidence: engineering mode completed the full mission. Oversized presentation rendering repeatedly caused sustained global simulator stalls. Pressure, IMU, DVL, camera, `/sim/odometry` and `/state/odometry` stopped together while Stonefish remained alive. Passive diagnostics observed `dxgvmb_send_sync_msg` during a sustained freeze, implicating WSLg/D3D12 synchronization/rendering rather than mission guidance. This is strong evidence of a shared runtime stall, not proof of a uniquely identified driver defect.

Safe presentation avoids the known trigger by preserving 1280×720 rendering. **The underlying WSLg/Stonefish bug is not fixed.** Engineering mode may still have short (~1 s) global gaps that recover. Readiness uses monotonic message receipt age for liveness (existing 0.5 s timeout); source timestamp regressions are diagnostics, not sole stale criteria. Real missing receipts still inhibit motion.

`python3 scripts/diagnose_demo_freeze.py` is a passive observer for a separately started demo. It publishes nothing, calls no services, never stops the demo, and continues through transient gaps and sustained freezes. JSONL/events/summary go under `/tmp/neptune-freeze-diagnostic-<timestamp>/`. It observes process/thread wait channels and GPU best-effort; shared receipt gaps alone cannot separate stepping from publication stalls conclusively.

## 8. Stage 2 State Estimation

| Stage | Status |
| --- | --- |
| S2.1 evaluator | Complete |
| S2.2 degradation | Complete |
| S2.3 DVL | Complete |
| S2.4 IMU | Complete |
| S2.5 pressure | Complete |
| S2.6 15-state ESKF structure | Complete: nominal/error-state and covariance structure only |
| S2.7 operational ESKF integration | Deferred |

The 15-state ESKF is **not** the fully validated operational estimator. Demo V0 runs `pressure_depth` + `dead_reckoning_state`; meaningful fused covariance is still future work (current odometry covariance remains zero). Legacy `ground_truth_state` and `hybrid_state` executables still read truth and can publish canonical state: they are historical/debug paths, prohibited in production composition and not launched by Demo V0. Their existence must not be mistaken for an approved navigation mode.

## 9. Perception

P4a inspection model recognizes **pipe / valve / flange**. P4b A1 is a pipe-only candidate detector; it does not produce a validated physical pipe angle: `orientation_valid=false`, `orientation_rad=null`. Do not treat the “orientation” node name as an angle contract.

P4c fusion is implemented: source-frame-aware association of P4a and A1 observations, semantic valve/flange retention, freshness/ambiguity status and selected pipe provenance. It preserves model confidences separately and image-space geometry; it is not a world-pose estimator. See [PERCEPTION_INTEGRATION.md](PERCEPTION_INTEGRATION.md) for model provenance, limitations and evidence. Throughput is inference-dependent, not a promised camera-rate output.

P5 closed-loop centering/advanced behavior remains deferred. Experimental P5a alignment code and standalone opt-in launch exist, with default motion signs disabled; this is not validated/enabled Demo V0 behavior. P5b angle control is not supplied by A1. Never co-launch an alternative controller with the mission command publisher.

## 10. Current Priorities

1. Preserve the successful Demo V0 baseline and its tested installation provenance.
2. Make the safe presentation build reproducible and reconcile source/install camera/body conventions explicitly.
3. Operationalize and validate the ESKF while preserving `/state/odometry`.
4. Continue perception evaluation against stable observation contracts.
5. Resume P5 only after state/perception contracts and motion validation are stable.
6. Develop hardware abstraction and real-vehicle integration afterward.

## 11. Baseline Freeze Verification

This repository freeze changed documentation, ignore patterns and boundary tests only; hashes of all previously present runtime files were checked against the initial worktree snapshot and remained identical. Existing uncommitted Demo V0 integration changes are included unchanged. The earlier diary is retained verbatim in PROJECT_HISTORY.md.

Validation without launching Stonefish or any mission:

- 97 focused motion/adapter/readiness/GUI/orientation/presentation/typed-boundary tests passed.
- 288 estimator-structure/evaluation/simulation-profile/perception/experimental-centering regression tests passed with mocked inference; no P4/P5 runtime activation.
- 15 diagnostic and pure Windows PowerShell geometry tests passed.
- Autonomy, vehicle and bringup built successfully into `/tmp/neptune-final-demo-install` in the existing dev container. The first build attempt lacked the simulator package underlay; sourcing the existing `/tmp/neptune-demo-v0-install` resolved it. Simulator and state-estimation dependencies were reused, not rebuilt or modified.
- Python compilation, launcher Bash syntax, 34 local documentation links, conflict-marker inspection and `git diff --check` passed. Secret-pattern and >50 MB audits of intended tracked/untracked files found no candidates.

These checks freeze source contracts and packaging; they do not claim a new dynamic mission, operational ESKF, or validated P5 behavior. Existing template lint suites were not part of the focused acceptance run.
