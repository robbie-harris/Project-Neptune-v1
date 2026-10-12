# Perception integration — P1 / P2 / P3

P0 audit complete. P1a added the optional pipe/flange scene; P1b adds its valve.
P2 lateral thrusters + lights is implemented; unit/build and physics actuation
checks pass, but full graphical actuation remains unverified because simulator
ROS callbacks stalled. P3 camera is implemented and visually verified, but its
stable approximately 10 Hz stream requirement has NOT passed. P4 is next only
after the stream issue is resolved, and has not started. Stage 2 remains frozen
through S2.6. The environment now contains pipe, flange, and valve categories;
model weights and the detector are still not integrated.

Source: donor `608a3b985b8c5dbfc56f5398b8679c8038861bbe`, `Simulation/assets/flange.obj`, copied byte-for-byte to
`src/neptune_sim/assets/perception/flange.obj`.
Mesh SHA-256: `ffce7928cbdd8f6c0391600ec601c579f2da1f3eef4dad21a3fdbe4cdb08c55b`.
No wedge exists in the donor; none was fabricated.

The new `src/neptune_sim/scenarios/benchmarks/03_port_pipe_perception.scn`
is derived from `02_port_pipe_mission.scn`. Pipe center is (-20, 0, 3.2) m,
radius 0.2 m, length 4.0 m, RPY (pi/2, 0, 0). Flange center is
(-20, 0.85, 3.2) m, scale 1, RPY (0, 0, 0): its bore already follows Y.
The original support legs/panel and dock remain. The unchanged supports at
Y=+/-2.5 lie beyond the shortened pipe ends; repositioning them is outside P1a.

The baseline Girona definition, original five actuators/order, sensors, body
physics, autonomy, localization, mission coordinates, and command interface are
unchanged. The optional scene now selects a perception-specific Girona copy
with two appended motors, two added lamps, and one additional inspection camera.
Baseline scenarios and runners
remain untouched. Ground truth remains evaluation-only.

Packaging installs the optional scene, both perception meshes, and the
perception-specific Girona include and optional camera/TF launch. Stonefish resolves the flange
with `$(find neptune_sim)/assets/perception/flange.obj`; its existing Girona
include and original textures/meshes resolve through the existing simulator data
root. This is an overlay, not a standalone replacement for Stonefish data.

## P1a validation history

XML, byte-exact donor copy, geometry/normals (1008 vertices, 1008 normals,
1920 faces), 19 resource/include references, unchanged baseline XML structure
except fixture changes, Python compile checks, selected neptune_sim colcon build,
installed scene/mesh integrity, and git diff --check passed.
The build used the installed Stonefish overlay (colcon emitted the expected
unbuilt-workspace-dependency warning).

A single 20-second simulator-only smoke test loaded the installed flange for
both physical and visual geometry, built GIRONA500 and its five motors, and
reached Ready for running. No missing-asset/XML failure occurred. It logged
`SDL2: That operation is not supported` and the existing propeller texture's
4-versus-3-channel warning, but initialization continued. SIGINT did not finish
within the five-second shutdown grace period; timeout forced termination
(exit 137), and no Stonefish process remained afterward. No screenshot tool
was available; on-screen fixture appearance was not independently verified.
No autonomy, perception, benchmark sweep, or full mission ran. Mission completion
and dynamic clearance remain untested; placement retains the 1.5 m axis standoff.

## P1b valve fixture

Operator visual inspection confirmed the P1a pipe and flange; valve/handwheel
absence was expected. P1b copies `Simulation/assets/valve.obj` byte-for-byte from
SHA `608a3b985b8c5dbfc56f5398b8679c8038861bbe` to
`src/neptune_sim/assets/perception/valve.obj`.
SHA-256: `a5e079de7ad15b55231f4fe7b97462e3e2c2c661da24a4b883921515c8fd4faa`.

Donor inspection_tank/inspection_fast mount valve and flange at Y=-0.85/+0.85
along the pipe. Reproduced around our unchanged pipe center (-20, 0, 3.2):
valve XYZ (-20, -0.85, 3.2) m, RPY (0, 0, 0), scale 1. The elongated body
follows Y and intentionally surrounds the pipe as an inline valve housing.
Stem/handwheel extend along local -Z, upward in NED; wheel center Z=2.58 m,
above pipe top Z=3.0 m. Valve/flange are 1.7 m apart with disjoint mesh Y bounds;
there is no fixture-to-fixture intersection. This retains the donor's mounting
concept without adding fabricated connector geometry or changing the mesh.
A future forward camera facing the pipe can view fixtures on either side;
actual camera FOV/occlusion acceptance is deferred to camera integration.

Only the valve block and blue valve look are added to the P1a scene, using
existing Aluminium and `$(find neptune_sim)/assets/perception/valve.obj` for both
collision and visual meshes. Baseline scene, pipe/flange placement, vehicle,
thrusters, lights, controls, autonomy, estimator, perception code, and GUI remain
unchanged. Wedge remains absent from donor and was not invented.

Validation: byte-exact donor copy; finite vertices/nonzero normals and valid face
vertex/normal indices (1814 vertices, 1814 normals, 3608 faces); no MTL dependency;
XML parsing; 21 resolved scene/include resources; P1a scene structure preserved
except new valve/look; valve/flange bounding separation and handwheel height;
selected neptune_sim colcon build (one package); installed scene and both meshes
byte-equal to source; and git diff --check passed. Build used the installed
Stonefish overlay with the expected workspace-dependency warning.

Single isolated 15-second simulator-only smoke loaded both collision/visual valve
and flange meshes, built Girona, and reached Ready for running. No missing-asset
or XML error. The same nonfatal SDL2 unsupported-operation diagnostic and
propeller texture-channel warning as P1a occurred. TERM did not exit within the
three-second grace period; timeout forced termination (137). No simulator process
remained. Visual valve appearance was not independently verified; operator visual
confirmation remains pending. No mission or perception ran.

## P2 lateral motors and inspection lamps

The optional scene includes
`$(find neptune_sim)/scenarios/neptune_girona_perception.scn`. This copies the
existing Girona definition without rewriting its body, sensors, existing motors,
or Omni light, then appends two lateral motors and two forward lamps. Existing
`neptune_girona.scn` and `02_port_pipe_mission.scn` are untouched.

Motor ordering: 0 SurgePort, 1 SurgeStarboard, 2 HeaveBow, 3 HeaveStern,
4 Sway, 5 SwayFront, 6 SwayRear. All original five blocks are identical.

| Added motor | XYZ (m) | RPY (rad) | Right-handed | Inverted |
| --- | --- | --- | --- | --- |
| SwayFront | (0.75, 0, 0.05431) | (0, 0, pi/2) | true | false |
| SwayRear | (-0.89647, 0, 0.05431) | (0, 0, pi/2) | false | true |

Both use 0.12 m propellers, normalized maximum 314.16 rad/s, thrust coefficients
0.48 forward/reverse, torque coefficient 0.05, and first-order rotor time
constant 0.15 s. Parameters follow donor SHA
`608a3b985b8c5dbfc56f5398b8679c8038861bbe`; mounts are Girona-specific.
Existing propeller mesh is reused at scale 2/3 to match the smaller diameter.
No extra hull/duct/bracket solids are added, preserving body mass/buoyancy/drag.
Mount brackets/tunnel flow and hardware feasibility are not modeled.

CG calculated from existing mesh shell/solid properties and explicit masses:
(-0.07323476, 0.00026649, 0.05430864) m, mass 143.146 kg; native load logs
confirm unchanged mass and principal inertias 95.384/126.947/135.515 kg m².
Pair mounts have equal opposite longitudinal CG arms (~0.823235 m) at CG height.
Front disk is in the inter-hull gap at the bow; rear disk is aft of the hull.
Existing hull X bounds are roughly -0.803 to +0.704 m, with upper hulls around
Z=-0.339 and lower hull around Z=+0.361, radius ~0.1535 m. Camera remains
(0.5, -0.12, 0.5), RPY (0, 0, 1.571), 1360x1024/55°; no transform changes.

Native FD thrust follows actuator local +X. Rotation pi/2 about Z maps this to
body +Y. Right/front positive rotor speed and left/rear inverted rotor speed
both give positive axial thrust; their reaction torques oppose. Thus equal pair
commands produce +Y sway with nominally cancelling pair yaw moment. Motor 4
retains its historical thrust/inversion and its small off-CG residual moment.

Adapter startup-only, read-only ROS parameter `motor_count` defaults to 5; only
5 and 7 are accepted. Set 7 explicitly for the optional scene; a mismatched
command length is rejected by Stonefish. No auto-detection or second interface.
For C(v)=clip(v,-1,1), surge s, sway w, heave h, yaw r:

```text
legacy:     [C(s-r), C(s+r), C(-h), C(-h), C(w)]
perception: [C(s-r), C(s+r), C(-h), C(-h), C(w), C(w), C(w)]
```

Motor 4 continues participating. Supplementing it increases sway authority;
future alignment gains must be tuned for this layout. Surge/heave/yaw allocation
is unchanged. Timeout remains >0.5 s, checked every 0.1 s. Stop/shutdown uses the
same allocation, generating five/seven zeros. Signal handling now keeps ROS
alive for the final zero publication before shutting the context down; the old
SIGINT path invalidated it too early (observed and corrected during live testing).

| Lamp | XYZ (m) | RPY (rad) |
| --- | --- | --- |
| InspectionLightPort | (0.76, -0.24, 0.5) | (pi/2, 0, pi/2) |
| InspectionLightStarboard | (0.76, +0.24, 0.5) | (pi/2, 0, pi/2) |

Each lamp is white, 800 lux, radius 0.015 m, full cone 90°. Local optical +Z
rotates to body +X. Lamps sit beyond the bow and outside the camera aperture.
At the existing body-origin inspection standoff 1.5 m/depth 3 m, nearest lamp
rays to valve/flange centers are 42.57° off axis (within 45° cone), and pipe-center
rays 27.44°. Actual illumination, shadowing, and future camera view need visual
verification; the original Omni and daylight can mask their contribution.

Validation: 17 focused real-ROS adapter tests passed (both layouts, exact legacy
formula, saturation, readonly mode, watchdog boundary, shutdown zeros); Python
compile checks passed; neptune_vehicle and neptune_sim builds passed. XML,
23 resource references, installed resources, unchanged original vehicle blocks,
CG moment balance, rotor clearance and lamp cone checks passed; diff check passed.
Initial test-fixture cleanup errors were fixed without weakening assertions.

Full graphical 800x600 and 320x240 scene-load probes loaded the seven motors and
lamps, with unchanged body physics and no missing-resource/XML error. Nonfatal
SDL2/texture-channel diagnostics persisted. Native service calls stalled; one
pulse showed a correct seven-element ROS command but zero sampled native thrust,
so **full graphical actuation did not pass**. Rendering/executor starvation is
suspected, not proven. No upstream simulator/renderer change was made. Graphical
processes required bounded forced cleanup, with no remaining owned processes.

A separate temporary /tmp physics-only scene removed cameras/FLS/lights for
headless validation; body/motors/world/fixtures were unchanged. It passed two
four-second pure-sway pulses at +/-0.22 near the inspection target, yaw pi:

| Pulse | Body-Y displacement | Yaw change | Added front/rear axial thrust |
| --- | --- | --- | --- |
| +0.22 | +0.15718 m | -0.09904° | +11.494 / +11.472 N |
| -0.22 | -0.15407 m | +0.08339° | -11.494 / -11.474 N |

Live five-motor output exactly matched historical formula. Live watchdog and
SIGINT shutdown produced seven zeros; native setpoints also reached zero on
watchdog. Tests use truth only to evaluate motion, never to derive commands.
No heave hold was commanded: vehicle rose ~0.26 m during each pulse; this is a
pure actuation test, not controlled inspection. No full mission, estimator,
perception, GUI or P3 ran. Evidence: container `/tmp/neptune-p2-smoke-result.json`,
`/tmp/neptune-p2-physics.log` and adapter logs; /tmp is temporary.

## P3 forward inspection camera — rate acceptance pending

**Camera/frames implemented; image content verified. P3 is not declared complete:
the requested stable approximately 10 Hz live stream has not been established.**
No detector, Roboflow, alignment, GUI, or P4 work was started.

Camera sensor XML name: `inspection_camera_optical_frame`; native qualified name
and Image/CameraInfo frame: `GIRONA500/inspection_camera_optical_frame`.
XYZ **(0.82, 0, 0.20) m**, RPY **(pi/2, 0, pi/2)**. Optical Z points body +X;
optical X points body +Y (right), optical Y body +Z (down). Final lens is ahead
of the hull (max X ~0.704), added front rotor (max X ~0.81), and lamps (X=0.76).
No existing camera, sensor, thruster, light, body physics or topic was changed.

Initial central-gap mount (0.40,0,-0.16) / 110° showed bow hardware in the
image and was rejected by visual inspection. Final forward mount and **145°
horizontal FOV** retain the whole flange/valve/handwheel at the existing 1.5 m
body-origin standoff, leaving 0.68 m lens-to-pipe-axis distance. This wide FOV is
deliberately different from the donor 80° reference; future detector validation
must use these actual optics. Resolution **640x480**, nominal **10 Hz**,
near/far **0.05/20 m**, native **rgb8**, step **1920 bytes**.

External topics generated natively from `/neptune/camera/inspection`:

- `/neptune/camera/inspection/image_color` — sensor_msgs/Image.
- `/neptune/camera/inspection/camera_info` — sensor_msgs/CameraInfo.

No image `frame_id` override is used: inspected native source overrides only
Image, while CameraInfo always uses the sensor name. Leaving it native keeps
both headers identical without a relay or simulator-source patch.

Actual received intrinsics:

```text
K = [100.8956124412747, 0, 320;
     0, 100.8956124412747, 240;
     0, 0, 1]
P = [fx, 0, 320, 0; 0, fy, 240, 0; 0, 0, 1, 0]
D = [0, 0, 0, 0, 0], plumb_bob; R identity
```

Native Image/CameraInfo stamps matched and advanced monotonically in received
pairs. **These are ROS wall-clock readback/publication stamps**, as verified in
ColorCameraImageReady; they are not a validated physical capture-time clock.
No timestamp rewrite or donor renderer/clock patch was added. Rate and freshness
must remain explicit in P4; neither stale frames nor publish stamps establish
perception readiness.

Measured live QoS for both native publishers: **RELIABLE / VOLATILE**.
RMW endpoint metadata reported history UNKNOWN/depth 0; source declares a
10-message queue. Record this distinction rather than claiming measured depth 10.
The final probe used RELIABLE/depth-5 subscriptions after inspection of the live
publisher. Earlier best-effort diagnostics were not used to claim acceptance.

`perception_camera.launch.py` owns only these static edges:

```text
base_link -> inspection_camera_link
    translation (0.82,0,0.20), identity rotation
inspection_camera_link -> GIRONA500/inspection_camera_optical_frame
    zero translation, RPY (pi/2,0,pi/2), quaternion (0.5,0.5,0.5,0.5)
```

Live TF verification passed after increasing the diagnostic subscriber queue
from depth one to retain both latched publishers. `base_link` is the existing canonical estimator's
body frame; this launch does not publish world/body pose or consume truth.
Direct simulator execution does not start these TF publishers. Launch starts
only the simulator and two static TF nodes, no adapter/mission/perception/viewer.

Validation: scene XML/resource resolution, semantic preservation of all existing
vehicle/sensors/lights/motor blocks, package/launch compilation, neptune_sim
colcon build, installed source equality, launch argument parsing, live static TF,
and git diff --check passed. image_view and its ROS dependencies were installed
in the existing dev container; package.xml declares viewer/TF/launch dependencies.
No Docker image, simulator source, or baseline graphics default was changed.

### Short camera smoke observations

Native WSLg/D3D12 (RTX 4080 Laptop, Mesa 24.0.5) created the camera publisher but
produced no received image within 20 s, including matched-QoS retries and an
OpenGL 4.5 override. Hardware camera streaming therefore **failed**. Diagnosis
is unresolved; no driver/renderer fix is claimed.

An explicit process-local software-renderer diagnostic (llvmpipe, 8 threads,
320x240 preview; image still 640x480) delivered native images/CameraInfo:

| Final geometry test | Received images / full measurement window | Wall rate | Max stamp gap |
| --- | --- | --- | --- |
| Actual optional scene at normal HOME spawn | 3 / ~8 s | 0.375 Hz | 3.916 s |
| Fixed inspection pose with legacy sensors enabled | 8 / ~8 s | 0.998 Hz | 0.948 s |
| Same fixed pose, inspection lamps removed for comparison | 6 / ~5 s | 1.200 Hz | 0.862 s |

Rates use the full measurement window, not just the interval between a short
burst's first/last frame. Actual-scene final frame age was 3.32 s. The explicit
nominal-rate/freshness gate failed; its assertion failure was retained. Changing
the configured sensor rate to disguise this was not done. Full mission/runtime
readiness is not established by the slow diagnostic stream.

For visibility only, temporary /tmp XML fixed Girona at (-18.5,0,3), yaw pi and
enabled legacy sensors by removing their enable-service entries in that test
copy. Repository spawn/dynamics/enable states remain unchanged. Old IMU and DVL
produced ~20 Hz, pressure ~5 Hz; original `/sim/camera/image_color` delivered
nine 1360x1024 frames in the eight-second inspection window. Scalar sensors and
old camera therefore still work in the test configuration; legacy camera also
suffers graphical rate limits. No mission, state estimator or motor command ran.

Exactly one retained debug image: `/tmp/neptune-p3-inspection.png` in the container
and host, overwritten after rejecting the initial mount. Final image visibly
contains pipe, flange, valve body/stem/handwheel; bow and lamps do not obstruct
it. No saturated pixels were measured and no severe fixture clipping/glare was
visible. Pipe continues beyond the image, as expected for a long pipe.

Inspection lamps-on mean intensity was 120.261/255 versus 119.697/255 without
those two lamps; mean absolute RGB difference ~0.760/255. This is a modest
contribution, not calibrated illumination: original Omni/daylight and particles
remain present. The region is visibly lit, but headlights-only performance is
not established. P2 light geometry was left untouched.

Temporary logs: `/tmp/neptune-p3-actual.log`, `inspection.log`, `lamps-off.log`
(with the same neptune-p3 prefix). Final GPU diagnostics reused the actual log
and result JSON; numeric software measurements above were retained from probe
stdout. Some dynamic-scene processes needed bounded forced shutdown; fixed-pose
runs exited cleanly, and no owned simulator/TF process remained. Native SDL2,
texture-channel and class-loader cleanup warnings were recorded. No debug image
was committed. Wedge remains absent.

### P3 visual inspection commands

Normal optional scene with camera TFs (native graphics default; hardware stream
currently unverified):

```bash
docker compose -f docker/compose.yaml exec dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /opt/stonefish_ws/install/setup.bash
  source /tmp/neptune-p3-install/setup.bash
  ros2 launch neptune_sim perception_camera.launch.py \
    simulation_data:=/workspace/external/stonefish/Tests/Data
'
```

For the measured slow diagnostic view of the fixture, use the temporary fixed
inspection test scene and explicit software renderer in an isolated ROS domain:

```bash
docker compose -f docker/compose.yaml exec dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /opt/stonefish_ws/install/setup.bash
  source /tmp/neptune-p3-install/setup.bash
  ROS_DOMAIN_ID=74 ros2 launch neptune_sim perception_camera.launch.py \
    simulation_data:=/workspace/external/stonefish/Tests/Data \
    scenario:=/tmp/neptune-p3-view.scn software_rendering:=true \
    window_width:=320 window_height:=240
'
```

In a second terminal, view the raw inspection feed:

```bash
docker compose -f docker/compose.yaml exec dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  ROS_DOMAIN_ID=74 ros2 run image_view image_view --ros-args \
    -r image:=/neptune/camera/inspection/image_color
'
```

The /tmp test scene is a fixed-pose diagnostic, not the mission configuration.
Software mode is an explicit optional override, not a silent fallback or baseline
change. /tmp files disappear on container replacement. Rebuild neptune_sim with
/tmp/neptune-p3-{build,install,log} and installed Stonefish overlay as in P1/P2.
Rollback: original baseline scene remains unchanged; to undo only P3, remove the
added camera block and stop the two new TF publishers. P4 was not started; resolve
camera stream performance/freshness before declaring P3 complete or starting it.

## P2 launch history

From the repository root with the existing dev container running, and no other
simulator owning the same topics, use the build verified in this session:

```bash
docker compose -f docker/compose.yaml exec dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /opt/stonefish_ws/install/setup.bash
  source /tmp/neptune-p2-install/setup.bash
  ros2 run stonefish_ros2 stonefish_simulator \
    /workspace/external/stonefish/Tests/Data \
    /tmp/neptune-p2-install/neptune_sim/share/neptune_sim/scenarios/benchmarks/03_port_pipe_perception.scn \
    100 800 600 low
'
```

The /tmp installation is temporary. To recreate it inside the dev container,
source ROS and the Stonefish overlay, then run from /workspace:

```bash
colcon --log-base /tmp/neptune-p2-log build \
  --build-base /tmp/neptune-p2-build \
  --install-base /tmp/neptune-p2-install --packages-select neptune_vehicle neptune_sim
```

This command launches the simulator only. Close its window to stop it.
Rollback: select the original `02_port_pipe_mission.scn`; no baseline files changed.

For the seven-motor scene, start the adapter in a separate sourced terminal:

```bash
docker compose -f docker/compose.yaml exec dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /opt/stonefish_ws/install/setup.bash
  source /tmp/neptune-p2-install/setup.bash
  ros2 run neptune_vehicle stonefish_adapter --ros-args -p motor_count:=7
'
```

Baseline use remains default motor_count=5 with the original scene. Do not run
both adapters together. Graphical native actuation remains an unresolved runtime
check; the headless results do not establish full graphical mission readiness.


## P3b control-camera diagnosis — BLOCKED (2026-10-12)

**P3 remains BLOCKED; P4 was not started.** The paired control establishes a
shared Stonefish/WSLg rendering-path limitation in this runtime, rather than a
defect unique to the inspection camera. Live camera diagnostics stopped after
one hardware and one software run, well inside the ten-minute budget. No
configuration, simulator source, driver, Docker, perception, control, autonomy,
estimator, actuation, GUI, or mission changes were made. No commit or push.

### Paired measurement

Both cameras ran simultaneously in the same prior P3 temporary fixed-pose scene:
Girona (-18.5,0,3), yaw pi, fixed body; legacy sensor enable-service entries
removed in the /tmp copy so both cameras were enabled. Sensor specifications,
world, fixtures, lights and graphical sensors were otherwise retained. No
services or actuator commands were needed. Simulator arguments: 100 Hz physics,
320x240 preview, low graphics. Each run used 12 seconds startup followed by a
20.012-second measurement window; rates are counts divided by the entire window.
RELIABLE depth-10 diagnostic subscriptions matched both RELIABLE/VOLATILE native
image publishers. The original camera is disabled by its enable service in the
repository's normal startup; its control measurement here is explicitly enabled.

| Renderer | Existing /sim/camera/image_color | Inspection image_color |
| --- | --- | --- |
| D3D12 RTX 4080 Laptop, Mesa 24.0.5 | 0 frames / 20.01196 s = 0 Hz | 1 frame / 20.01196 s = 0.04997 Hz |
| llvmpipe LLVM 17.0.6, Mesa 24.0.5, 8 threads | 19 frames / 20.01169 s = 0.949445 Hz | 19 frames / 20.01169 s = 0.949445 Hz |
| Software maximum interarrival gap | 1.216205 s | 1.194253 s |
| Software maximum message-stamp gap | 2.672112 s | 2.676802 s |

The single hardware inspection image means hardware was not literally zero in
this fixed-pose rerun; it still has no usable sustained stream. No hardware
interframe gap can be calculated from one image. Earlier normal-scene hardware
zero-image/20-second result remains valid historical evidence. Earlier software
inspection rates were 0.375 Hz normal spawn and 0.998 Hz fixed pose; this paired
fixed-pose result is the final measurement, with no intervening fix. Stamp gaps
and receipt gaps are reported separately; wall-clock publication stamps and
queued delivery are not physical capture timestamps. Both software streams'
received stamps strictly increased. These short windows do not prove long-term
reliability.

### Configuration and source comparison

| Setting | Existing Girona camera | Inspection camera | Donor forward CameraLeft/Right |
| --- | --- | --- | --- |
| Sensor / native renderer | camera / ColorCamera / OpenGLRealCamera | same | camera (same native path before donor patches) |
| Rate | 10 Hz | 10 Hz | 10 Hz |
| Resolution | 1360x1024 | 640x480 | 640x480 |
| Horizontal FOV | 55 degrees | 145 degrees | 80 degrees |
| Near/far clip (m) | native defaults 0.02/100000 | 0.05/20 | 0.05/20 |
| XYZ (m) | (0.5,-0.12,0.5) | (0.82,0,0.20) | (0.62,-0.06/+0.06,0) |
| RPY (rad) | (0,0,1.571) | (pi/2,0,pi/2) | (pi/2,0,pi/2) |
| Enable state on repository startup | disabled: /sim/proscilica/set_enabled | enabled: no enable service | enable service; donor native patch starts enabled |
| Native name/frame | GIRONA500/proscilica | GIRONA500/inspection_camera_optical_frame | Neptune/CameraLeft or CameraRight |
| ROS topic prefix | /sim/camera | /neptune/camera/inspection | /neptune/ideal/camera/left or right |
| XML frame override | none | none | qualified camera name |

Both local cameras use the same bridge branch: advertise image_color, create
camera_info, install ColorCameraImageReady. Queue size is ceil(sensor rate)=10;
measured QoS is RELIABLE/VOLATILE. No renderer selector or readback-disable option
is present in either XML. Native ROS2ScenarioParser explicitly disables sensors
with enable services; their entries were absent in the measured temporary copy.
Inspection is enabled without that service. Native CameraInfo uses the sensor
name; leaving the inspection Image frame override absent keeps headers consistent.

Native ColorCamera initializes OpenGLRealCamera for both sensors. Its DrawLDR
reads RGB texture into a pixel-pack buffer with glGetTexImage; UpdateTransform
maps that PBO with glMapBuffer and invokes NewDataReady only for a non-null
mapping. The common pipeline queues non-continuous views and normally schedules
one queued view per render in addition to continuous views. These are relevant
shared bottlenecks, **not proof of a specific failed GL call or driver defect**.
Logs reached Ready for running without missing camera resources/XML errors;
existing SDL2 unsupported-operation and texture-channel warnings persisted.
Renderer identities were independently checked with glxinfo under each run's
environment. No detailed GPU timing or GL-error instrumentation was performed.

Donor SHA 608a3b985b8c5dbfc56f5398b8679c8038861bbe inspection_fast/inspection_tank
camera XML and tools/patch_stonefish.py, patch_views.py, patch_optics.py were
read only. Donor changes include rendering all pending views, particle controls,
clock/capture stamping, bounded physics catch-up and altered enable defaults;
none were applied. They do not by themselves prove a D3D12 readback fix.

### FOV decision and validation

FOV remains **145 -> 145 degrees**, resolution **640x480 -> 640x480**; exact
configuration change: **none**. Prior P3 widened the FOV to fit separated fixtures
at the unchanged 1.5 m body-origin standoff (lens-to-axis 0.68 m). Fixture centers
are approximately atan(0.85/0.68)=51.3 degrees off axis: an 80-degree horizontal
view would exclude both centers at that pose. An 80-degree view may be preferable
for later detection with a revised viewing distance, but is not established as
a throughput fix. Equal ~0.95 Hz control/inspection rates and hardware failure
of the control trigger the explicit platform-limit stop condition; no FOV tuning
or workaround was implemented.

Actual software inspection Image and CameraInfo dimensions were 640x480, frame
GIRONA500/inspection_camera_optical_frame. Received K remains
fx=fy=100.8956124412747 px, cx=320, cy=240 (not manually assigned). Existing
CameraInfo was 1360x1024 with fx=fy=1306.267846340393, cx=680, cy=512.
The unchanged two-edge static TF passed a fresh bounded live check, including
translation (0.82,0,0.20) and optical quaternion (0.5,0.5,0.5,0.5).
The retained prior P3 image /tmp/neptune-p3-inspection.png was re-inspected:
pipe/flange/valve/handwheel visible, no hull/lamp obstruction. Visibility was
not freshly captured in P3b; this is retained-image evidence with unchanged optics.
All repository sensors remain unchanged. Both probe simulator processes were
stopped with bounded cleanup; no simulator remained afterward.

Validation outcome: **FAIL** (<5 Hz and multi-second stamp gaps; hardware has no
sustained stream). TF and dimensions/CameraInfo checks passed. Only documentation
changed, so no ROS package rebuild was necessary. git diff --check passed.
Evidence is temporary container /tmp/neptune-p3b-{probe.py,result.json,hardware.log,
software.log}; numeric results are retained here because /tmp is not durable.

Remaining blocker: a rendering/runtime path that sustains at least 5 Hz with
maximum gap below 0.5 s (preferably >=8 Hz without multi-second gaps). The exact
low-level D3D12 stall remains unresolved; the proven diagnosis is shared runtime
scope, not a specific driver or PBO failure. Smallest next recommendation is a
bounded comparison on another supported accelerated runtime (for example native
Linux), using unchanged camera XML. Alternatively, separately assess the donor's
narrow view-scheduling patch; do not import its unrelated clock/optics changes.
Lower-rate perception requires explicit acceptance and a freshness policy; none
was accepted or implemented here. P4 remains NOT STARTED. Stage 2 remains frozen
through S2.6; S2.7–S2.14 were not started.
