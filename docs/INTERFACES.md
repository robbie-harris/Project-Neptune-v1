# Authoritative ROS Interface Contracts

This document specifies current public boundaries from source, not proposed topics. Ownership is exclusive unless explicitly described as an isolated alternative. Rates are configured/nominal simulator-time or timer rates, **not guaranteed wall-time delivery** under load or rendering stalls. Consumers must handle missing data and finite/valid payloads. Defaults refer to the seven-motor Demo V0 performance scene.

## Hard rules

1. `/state/odometry` is the canonical navigation state consumed by production autonomy.
2. `/sim/odometry` is truth. Production autonomy must never consume it; neither may production estimation, guidance or perception decision making use it as navigation input.
3. Mission executive is the sole normal `/neptune/cmd_body` publisher. Standalone test controllers are mutually exclusive alternatives, never additional command sources.
4. `neptune_vehicle` owns body-command → actuator translation.
5. Perception publishes observations, not actuator commands.
6. GUI is read-only for motion. Readiness publishes health, not movement.
7. Evaluation may consume truth but must not close the production loop using it.
8. Any topic/type/frame/unit/sign/semantic/ownership or required timing change is a **contract change** requiring [TEAM_CONTRACTS.md](TEAM_CONTRACTS.md)'s review protocol and updated tests in the same PR.

## Navigation and motion

| Topic | Exact type | Publisher owner → consumers | Frame / units | Rate / semantics and publication ownership |
| --- | --- | --- | --- | --- |
| `/state/odometry` | `nav_msgs/msg/Odometry` | `neptune_state_estimation/dead_reckoning_state` → mission, readiness, GUI, evaluation, explicitly selected standalone controllers | `world_ned` pose; child `base_link`, body-frame twist; m, quaternion, m/s, rad/s | DVL-driven, nominal 20 Hz after depth/IMU/DVL available. Header copies DVL stamp. Horizontal dead-reckoning origin; pressure-derived positive-down depth. Covariance currently zero, not validated uncertainty. No other normal publisher. |
| `/sim/odometry` | `nav_msgs/msg/Odometry` | Stonefish → evaluation and passive diagnostics only | `world_ned`; child sensor name `GIRONA500/dynamics`; m, quaternion, m/s, rad/s | Configured 30 Hz, simulator sensor origin at vehicle origin. Truth/debug only; never substitute it for canonical state. Only simulator publishes. |
| `/neptune/cmd_body` | `geometry_msgs/msg/Twist` | `mission_executive` → `stonefish_vehicle_adapter`, passive diagnostics | Implicit `base_link` (+X bow, +Y starboard, +Z down). **Normalized dimensionless demands**, despite Twist field names | Nominal 20 Hz. `linear.x` surge, `linear.y` sway, `linear.z` positive dive, `angular.z` positive yaw about +Z; other angular axes unused. Only mission publishes in normal demo. |
| `/sim/thruster_setpoints` | `std_msgs/msg/Float64MultiArray` | `stonefish_vehicle_adapter` → Stonefish; passive diagnostics may observe | No header/frame; ordered native normalized demands [-1,1] | Input-driven ~20 Hz, plus watchdog/shutdown zeros. Only adapter publishes. Array length 7 in demo, default adapter 5. Order and signs below. |
| `/sim/thruster_state` | `stonefish_ros2/msg/ThrusterState` | Stonefish → diagnostics/evaluation | Header robot name `GIRONA500`; ordered arrays | Published from simulator step loop (100 Hz configured stepping, wall rate may differ). `setpoint` is native scaled angular setpoint rad/s for current rotor models, `rpm` observed RPM, `thrust` N, `torque` N·m. This is telemetry, not a second command input; only simulator publishes. |

Current guidance: max surge .80, distance gain .16, moving floor .20, cutoff at distance ≤.45 m; translation disabled above 30° yaw error. Yaw uses P=1.40, rate damping=.20 and saturation ±.60. Planar arrival remains distance <.50 m. `surge ≤ max(0,1-abs(yaw))` reserves native differential authority before allocation.

For clamped public surge `s`, sway `w`, heave `h`, yaw `r`, and clamp `C` to [-1,1], the adapter produces:

```text
[ C(-s-r), C(-s+r), C(-h), C(-h), C(w) ]
# SurgePort, SurgeStarboard, HeaveBow, HeaveStern, Sway
# Seven-motor mode appends C(w), C(w): SwayFront, SwayRear.
```

Native surge motors have inverted setpoint configuration: positive public surge produces bow-forward force. Positive yaw preserves the historical differential and positive body-Z moment. Independent heave and sway mappings must not be inferred from surge inversion. Adapter zeros all motors after >0.5 s without a command, checked every 0.1 s using node time. Mission's demo state/readiness freshness uses monotonic receipt age with 0.5 s limits. Do not replace one timebase with another silently.

## Sensors and intermediate depth

Sensor frame names below come from Stonefish's robot-qualified sensor names. DVL is **sensor-frame**, not directly body-frame velocity. The estimator applies the mount rotation and angular lever-arm correction. These raw source topics are owned by the simulator; future hardware adapters must supply reviewed equivalent contracts rather than changing semantics silently.

| Topic | Exact type | Owner → consumers | Frame / units | Nominal rate / meaning |
| --- | --- | --- | --- | --- |
| `/sim/pressure` | `sensor_msgs/msg/FluidPressure` | Stonefish → `pressure_depth`, readiness, diagnostics; optional degradation tools | `GIRONA500/pressure`; Pa, variance Pa² | 5 Hz. Hydrostatic/gauge pressure in this simulation; sensor Z=-.40 m. Only simulator in demo. |
| `/estimate/depth` | `std_msgs/msg/Float64` | `pressure_depth` → `dead_reckoning_state` | No header; vehicle-origin positive-down depth in m | Pressure-driven 5 Hz; `pressure/(997*9.81)+0.40`. Not a separate navigation pose. Only pressure-depth node publishes. |
| `/sim/imu` | `sensor_msgs/msg/Imu` | Stonefish → estimator, readiness, diagnostics; opt-in degradation | `GIRONA500/imu_filter`, identity body mount; quaternion, rad/s, m/s² | 20 Hz. Current estimator uses attitude and angular rates. Only simulator in demo. |
| `/sim/dvl` | `stonefish_ros2/msg/DVL` | Stonefish → estimator, readiness, diagnostics; opt-in degradation | `GIRONA500/dvl`; sensor velocity m/s, covariance (m/s)², altitude m | 20 Hz. Mount at (-.75,0,.40) m, rotated by scene RPY; do not interpret raw XYZ as body surge/sway/heave. Only simulator in demo. |
| `/sim/dvl/altitude` | `sensor_msgs/msg/Range` | Stonefish → optional diagnostics | `GIRONA500/dvl_altitude`; m, field-of-view rad | 20 Hz alongside DVL. Auxiliary altitude, not canonical depth. Only simulator publishes. |
| `/sim/accelerometer` | `geometry_msgs/msg/AccelWithCovarianceStamped` | Stonefish → optional diagnostics | `GIRONA500/acc`; m/s², covariance per message | 100 Hz. Auxiliary raw acceleration, not a separate state estimate. Only simulator publishes. |
| `/sim/gps` | `sensor_msgs/msg/NavSatFix` | Stonefish → optional diagnostics | `GIRONA500/gps`; latitude/longitude degrees, altitude m | 1 Hz configured; availability/validity depends on sensor environment. Not consumed by Demo navigation. Only simulator publishes. |

Readiness determines liveness from **monotonic receipt age**, finite values and quaternion validity; source-stamp regressions remain diagnostics and must not alone mark a live stream stale. This does not weaken detection of actual receipt loss. Estimation still uses source timestamps for integration; no estimator algorithm change is implied.

## Camera

| Topic | Exact type | Owner → consumers | Frame / units | Rate / meaning / ownership |
| --- | --- | --- | --- | --- |
| `/neptune/camera/inspection/image_color` | `sensor_msgs/msg/Image` | Stonefish → GUI, optional P4a/P4b nodes, diagnostics | `GIRONA500/inspection_camera_optical_frame`; encoded pixel image | Configured 10 Hz; Demo performance profile 320×240, 80° horizontal FOV. Only simulator publishes. GUI/perception use best-effort depth-one subscriptions and latest-frame handling. |
| `/neptune/camera/inspection/camera_info` | `sensor_msgs/msg/CameraInfo` | Stonefish → GUI/optional camera consumers | Same optical sensor frame; pixel intrinsics/projection calibration | Alongside image, nominal 10 Hz. Only simulator publishes. |

Optical convention is image right/down/forward in the camera frame, not body navigation axes. Image source headers are preserved through perception. Bridge camera stamps are assigned at publication/readback, not independently measured exposure time. Current demo launch extrinsics face -X, while the shared scene faces +X; source/install provenance and this existing camera/body discrepancy are documented in [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md). Do not silently reinterpret pixel errors as body commands.

The performance profile removes auxiliary `/sim/camera` and FLS sensors from Demo V0; their non-demo scene declarations are not a guaranteed Demo interface. It also removes startup sensor-toggle services from its disposable generated scene. No `/state/health`, `/planning/trajectory`, or `/perception/assets` interface is currently implemented by this demo.

## Mission and readiness

| Topic / service | Exact type | Owner → consumers | Frame / units | Rate / semantics / ownership |
| --- | --- | --- | --- | --- |
| `/neptune/mission/status` | `std_msgs/msg/String` | mission → GUI, diagnostics | JSON, no frame; elapsed seconds | 5 Hz plus transitions, transient-local depth 10. `state`, `mission_elapsed_s`, `outcome`, `complete`, `demo_mode`, `ready`, `start_requested`, `state_fresh` and `movement_authority` reflect executive status. `COMPLETE` with timeout outcome is not success; inspect completion fields. Only mission publishes. |
| `/neptune/demo/ready` | `std_msgs/msg/Bool` | readiness → mission / passive diagnostics | No frame; Boolean | 10 Hz, transient-local depth 10. True requires qualified startup, live inputs and exclusive publishers. False inhibits motion; only readiness publishes. |
| `/neptune/demo/health` | `std_msgs/msg/String` | readiness → GUI/diagnostics | JSON, no frame; seconds/Boolean/rates as named | 10 Hz, transient-local depth 10. Receipt freshness, startup settling, ownership and source-time diagnostics. Only readiness publishes. |
| `/neptune/mission/start` (service) | `std_srvs/srv/Trigger` | mission service server ← explicit operator/client | No frame | Demo mode only; requests arming, succeeds only with readiness and fresh state. It is not a continuous motion command. |

Startup defaults: at least 15 s and a continuous 3 s stable qualification window (pressure depth-rate <.05 m/s, IMU yaw-rate <.03 rad/s), existing .5 s receipt freshness and 90 s startup deadline. Motion does not need to remain stationary after initial qualification. Demo GUI has no vehicle-motion publisher or arming client. Runtime ROS infrastructure topics (`/rosout`, `/parameter_events`, `/tf`, `/tf_static`) retain their standard ROS types; static transforms are bringup-owned, not mission commands.

## Perception outputs (opt-in, not enabled in Demo V0)

All `Detection2DArray` types below are `vision_msgs/msg/Detection2DArray`; every status is `std_msgs/msg/String` containing JSON. Detection boxes are **image pixels**, class scores dimensionless, and array/detection headers retain the input image's optical frame/stamp. Annotated image encoding follows its published Image. Only the listed owner may publish each topic.

| Exact topic | Exact type | Publisher → consumers | Rate / meaning |
| --- | --- | --- | --- |
| `/neptune/perception/object_detections` | `vision_msgs/msg/Detection2DArray` | `inspection_objects` → observation/evaluation clients | Completed P4a inference; pipe/valve/flange boxes and model scores. |
| `/neptune/perception/annotated` | `sensor_msgs/msg/Image` | `inspection_objects` → optional display/evaluation | Completed P4a inference; image with boxes. |
| `/neptune/perception/status` | `std_msgs/msg/String` | `inspection_objects` → `pipe_fusion`, diagnostics | 20 Hz watchdog plus inference updates; source header/dimensions, observations, runtime and validity. P4a can retain stale diagnostic detections; check status. |
| `/neptune/perception/orientation_a_detections` | `vision_msgs/msg/Detection2DArray` | `orientation_a` → observation/evaluation clients | Completed fresh A1 inference; pipe-only candidate boxes. |
| `/neptune/perception/orientation_a_annotated` | `sensor_msgs/msg/Image` | `orientation_a` → optional display/evaluation | Fresh A1 completions; annotated pixels. |
| `/neptune/perception/orientation_a_status` | `std_msgs/msg/String` | `orientation_a` → `pipe_fusion`, diagnostics | 20 Hz watchdog plus updates. `orientation_valid=false`, `orientation_rad=null`: no validated angle. Stale A1 completions are rejected. |
| `/neptune/perception/fused_pipe_detections` | `vision_msgs/msg/Detection2DArray` | `pipe_fusion` → evaluation/future observation clients | One publication per finalized source frame; associated/fallback pipe candidates. |
| `/neptune/perception/fused_semantic_detections` | `vision_msgs/msg/Detection2DArray` | `pipe_fusion` → evaluation/future observation clients | Finalized source frame; P4a valve/flange observations preserved. |
| `/neptune/perception/fused_status` | `std_msgs/msg/String` | `pipe_fusion` → diagnostics, opt-in `pipe_centering`, future mission consumer | 20 Hz plus updates. Eligibility, selected target, provenance and source-age/ambiguity status; normalized image errors +right/+down, not metric pose. |

No fixed achieved inference Hz is guaranteed. Consumers must check source identity, freshness and selected-target validity. Fusion joins exact stamp/frame/dimensions with an association deadline (.20 s), freshness .50 s and IoU threshold .30; it does not average independent model confidences or invent physical pipe orientation. See [PERCEPTION_INTEGRATION.md](PERCEPTION_INTEGRATION.md) for full payload examples and limitations. There is currently **no perception subscription in the mission executive**.

## Alternative controllers / experimental interfaces

These are **not** enabled by Demo V0, and must never compete with its command owner.

| Topic | Exact type | Owner → consumer | Frame / units / timing / semantics |
| --- | --- | --- | --- |
| `/control/target_depth` | `std_msgs/msg/Float64` | Explicit standalone test/operator → `depth_hold` | Positive-down target m; event-driven, no frame header. Controller publishes body commands at 20 Hz when selected alone. |
| `/control/target_position` | `geometry_msgs/msg/PointStamped` | Explicit standalone test/operator → `waypoint_hold` | Intended estimated-world X/Z metres. Current controller reads only X/Z and does not transform/enforce header frame; caller must supply matching coordinates. Event-driven; standalone body commands at 20 Hz. |
| `/neptune/control/alignment_cmd_body` | `geometry_msgs/msg/Twist` | experimental `pipe_centering` → isolated test adapter via explicit remapping only | Same normalized body convention; sway only, 20 Hz steady timer, default sign zero disables motion. P5a opt-in launch may remap it to `/neptune/cmd_body` only with mission absent. |
| `/neptune/control/alignment_status` | `std_msgs/msg/String` | `pipe_centering` → test diagnostics | JSON state/confirmation/source/target/sway, no frame; 20 Hz. Experimental, not a completed closed-loop mission contract. |

Legacy `ground_truth_state` and `hybrid_state` entry points can read truth/publish canonical state but are **excluded from approved production composition**. They are not alternative approved canonical-state owners. Their eventual removal/migration requires review; this documentation freeze does not alter runtime code.

## Verification sources

Authoritative implementation locations: `src/neptune_autonomy/neptune_autonomy/mission_executive.py`, `src/neptune_vehicle/neptune_vehicle/stonefish_adapter.py`, `src/neptune_state_estimation/neptune_state_estimation/{pressure_depth,dead_reckoning_state}.py`, `src/neptune_bringup/neptune_bringup/{demo_readiness,readiness,demo_gui}.py`, `src/neptune_bringup/launch/perception_demo.launch.py`, `src/neptune_sim/scenarios/neptune_girona_perception.scn`, `src/neptune_sim/neptune_sim/perception_profile.py`, and perception/control node implementations. Native bridge definitions come from the provisioned `external/stonefish_ros2` checkout (ignored dependency), so its revision must also be recorded when reproducing an installation.
