# Perception integration — P1 / P2 / P3 / P4a

P0 audit complete. P1a added the optional pipe/flange scene; P1b adds its valve.
P2 lateral thrusters + lights is implemented; unit/build and physics actuation
checks pass, but full graphical actuation remains unverified because simulator
ROS callbacks stalled. **P3 COMPLETE WITH PERCEPTION PROFILE**: the explicit
320x240 software performance profile passes the minimum >=5 Hz / <0.5 s gate.
Configured 10 Hz is not achieved wall throughput. **P4a COMPLETE: observation-only
Inspection Objects pipeline; bounded GPU smoke passed. P4b next: Orientation A1,
not started. P5 not started.**
Polished rendering is deferred to P8. Stage 2 remains frozen
through S2.6. The environment now contains pipe, flange, and valve categories;
Inspection Objects is integrated; orientation estimation remains unavailable.

P3c tested two native camera candidates; both failed acceptance. They remain
**NOT ACTIVE / NOT PART OF NORMAL BUILD / FAILED ACCEPTANCE**. The approved P3
profile uses the original native library. Historical blocked records below are
superseded by the final P3 completion record at the end of this document.

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

## P3c native camera candidates — acceptance FAILED (2026-10-12)

**P3 remains BLOCKED. P4 NOT STARTED.** Two distinct disposable candidates were
built and tested; neither reached >=5 Hz with maximum receipt/stamp gaps <0.5 s.
Live experimentation stopped after those two attempts, within the approximately
20-minute limit. No baseline rerun, hardware candidate run, final integration
benchmark, full mission, commit or push occurred. No failed candidate was wired
into Dockerfile or installed into the running container.

### Complete donor audit

Read all three scripts completely at donor `lumyn/Perception`, SHA
`608a3b985b8c5dbfc56f5398b8679c8038861bbe`. The following inventory extracts each
individual source edit, including the scripts' loop/bulk replacements. Paths
are relative to Stonefish (`SF`) or stonefish_ros2 (`ROS`). A row describing a
bulk substitution explicitly identifies its full affected region.

| Script / source file | Individual hunk / transformation | Classification |
| --- | --- | --- |
| patch_stonefish / SF Library/include/graphics/OpenGLPipeline.h | Add getCaptureTime getter after getScreenTexture | TIMESTAMPING |
| same | Add neptuneCaptureTime member after lastSimTime | TIMESTAMPING |
| patch_stonefish / SF Library/src/graphics/OpenGLPipeline.cpp | Set neptuneCaptureTime=lastSimTime before reading current simulation time | TIMESTAMPING |
| same | Before view-render loop, set updateCount=viewsQueue.size(); viewsNoUpdate.clear() | CAMERA SCHEDULING |
| same | Replace DrawParticles(camera) with a disabled-effect comment | OPTICS |
| patch_stonefish / SF Library/src/core/SimulationManager.cpp | Clamp deltaTime to 100000 microseconds before StepSimulation | GENERAL SIMULATION CLOCK |
| patch_stonefish / ROS src/stonefish_ros2/ROS2ScenarioParser.cpp | Enable-service sensors start true instead of false | SENSOR STARTUP |
| patch_stonefish / ROS src/stonefish_ros2/ROS2SimulationManager.cpp | Add GraphicalSimulationApp, OpenGLPipeline, chrono, thread and clock-message includes | TIMESTAMPING / GENERAL SIMULATION CLOCK |
| same | getCurrentTime uses steady_clock microseconds instead of ROS-clock now | GENERAL SIMULATION CLOCK |
| same | SimulationSleep uses thread sleep_for instead of ROS-clock sleep_for | GENERAL SIMULATION CLOCK |
| same | Every nh_->get_clock()->now() from SimulationStepCompleted through end of file becomes simulation-time nanoseconds | TIMESTAMPING |
| same | Lazily create neptune_clock publisher and publish /clock in SimulationStepCompleted | GENERAL SIMULATION CLOCK |
| same | In ColorCameraImageReady through before RespawnRobotService, replace simulation-time stamps with previous-render capture time (all vision callbacks in that region) | TIMESTAMPING |
| patch_stonefish / ROS src/stonefish_ros2/ROS2Interface.cpp | All ROS-clock now calls become simulation-time nanoseconds | TIMESTAMPING |
| patch_stonefish / ROS CMakeLists.txt | Add find_package(rosgraph_msgs REQUIRED) | GENERAL SIMULATION CLOCK |
| same | Add rosgraph_msgs to interface target dependencies | GENERAL SIMULATION CLOCK |
| patch_stonefish / ROS package.xml | Add rosgraph_msgs depend | GENERAL SIMULATION CLOCK |
| patch_optics / SF Library/include/graphics/OpenGLAtmosphere.h | Add SetNaturalLighting public declaration | OPTICS |
| same | Add neptuneNaturalUBO member | OPTICS |
| patch_optics / SF Library/src/graphics/OpenGLAtmosphere.cpp | Allocate lighting-toggle UBO at binding zero after sunSkyUBOData memset | OPTICS |
| same | Insert SetNaturalLighting implementation before SetupMaterialShaders | OPTICS |
| same | Delete extra UBO in destructor | OPTICS |
| patch_optics / SF Library/shaders/atmosphereApi.glsl | Add NeptuneOptics uniform block after atmosphere injection | OPTICS |
| same | For every return line containing GetSkyRadiance or atmosphere.solar_irradiance, multiply by neptuneNaturalLight | OPTICS |
| same | GetSunAndSkyIrradiance return becomes local sun value; scale both sun and sky | OPTICS |
| same | Multiply SKY_SPECTRAL_RADIANCE_TO_LUMINANCE sky scaling by toggle | OPTICS |
| same | Multiply SUN_SPECTRAL_RADIANCE_TO_LUMINANCE return by toggle | OPTICS |
| patch_optics / SF Library/src/graphics/GLSLShader.cpp | After linking, bind NeptuneOptics if present; remove opening DEBUG guard for diagnostics | OPTICS / UNRELATED (release diagnostics) |
| same | Remove matching endif before GL_LINK_STATUS | UNRELATED (release diagnostics) |
| patch_optics / SF Library/include/graphics/OpenGLPipeline.h | Add mutex include | OPTICS |
| same | Add RequestNeptuneOptics / GetNeptuneOptics with mutex guarding | OPTICS |
| same | Add optics mutex and requested/applied vectors after capture-time member | OPTICS |
| patch_optics / SF Library/src/graphics/OpenGLPipeline.cpp | Add Light include | OPTICS |
| same | After atmosphere lookup, apply water type, particles, natural light and lamps using Neptune/LightLeft and LightRight | OPTICS |
| same | Restore particle drawing conditional on ocean->hasParticles() | OPTICS |
| patch_optics / ROS src/stonefish_ros2/ROS2SimulationManager.cpp | Add cmath, sstream, StaticEntity includes | OPTICS / UNRELATED |
| same | Before Standard services, create optics request/applied endpoints and validate five-element requests | OPTICS |
| same insertion | Publish retained instance object-ID map for Pipeline, InspectionValve, InspectionFlange | UNRELATED |
| same insertion | Disable Neptune/CaptureInstances on startup | SENSOR STARTUP |
| same insertion | Add TankOverview enable service | GUI/VIEW / SENSOR STARTUP |
| same | Before timeStep suppression, publish applied optics vector each simulation step | OPTICS |
| patch_views / SF Library/include/graphics/OpenGLPipeline.h | Add requested/applied view vectors and mutex-guarded Request/GetNeptuneViews before capture getter | GUI/VIEW |
| patch_views / SF Library/src/graphics/OpenGLPipeline.cpp | Add Sensor include | GUI/VIEW |
| same | Before optics application, look up five donor-specific sensors; select camera/downward/sonar/overview frequencies 10/5/2 Hz and overview enable state | SENSOR UPDATE RATE / GUI/VIEW |
| patch_views / ROS src/stonefish_ros2/ROS2SimulationManager.cpp | Before Standard services, add view request/applied endpoints, validate three-element requests and forward to renderer | GUI/VIEW |
| same | Before timeStep suppression, publish applied view vector | GUI/VIEW |

**GPU/FRAMEBUFFER READBACK: no donor hunk in any of these three scripts.** None
changes OpenGLRealCamera, glGetTexImage, glMapBuffer, or camera framebuffer layout.
The scripts' shared replace/edit helpers and print statements are patch machinery,
not additional native-source hunks. patch_views' existing-marker early return is
its sole idempotency check; the other scripts are not generally idempotent.

Donor rationale: `docs/Decision Log.md` and `docs/Known Issues and Fixes.md`
attribute pending-view rendering to stereo synchronization; the latter explicitly
reports camera/sonar delivery below configured 10 Hz. Its clock correction followed
an accelerated/repeated-image capture incident, not a demonstrated WSL camera fix.
`docs/Faster Mission and View Priority.md` calls its rates nominal and reports
2.5–3.0 FPS GUI transport on Apple M5. Donor Dockerfile explicitly selects software
OpenGL; `docs/Methods and Libraries.md` identifies Mac Docker llvmpipe. That is
consistent with unavailable Apple GPU in Docker, not proof that WSL D3D12 readback
is unsupported or that the donor fixed it.

Both local and installed native repositories match the requested upstream SHAs:
SF `b21eb8e194c570ff2f61e91aeffb38d73dc25f42`, ROS
`6646e7ac25eed982f37f807abc7b545dbd2d6648`. ROS has no source modifications; SF
has only the existing two FLS compatibility overrides. The camera pipeline and
OpenGLRealCamera files were verified byte-identical to upstream before testing.
Therefore all audited donor changes are absent. Existing `docker/Dockerfile`
applies FLS whole-file overrides under `docker/stonefish_overrides/`; there was
no generic SHA-checked patch mechanism. The rejected P3c artifacts are isolated
under `docker/patches/p3c-experimental/`, with no normal-build hook.

Only pending-view scheduling directly supports the initial camera-publication
hypothesis. Startup changes cannot explain enabled cameras being slow; view-rate
changes alter unrelated sensors; optics changes alter image appearance; clock
changes lack evidence of being necessary for this camera-rate fix. None of those
was imported. No global-clock change was justified by these experiments.

### Exact candidates and paired results

Candidate 1 reuses exactly the donor pending-view hunk in
`Library/src/graphics/OpenGLPipeline.cpp`:

```cpp
    updateCount = viewsQueue.size();
    viewsNoUpdate.clear();
```

Candidate 2 retains that hunk and changes only
`Library/src/graphics/OpenGLRealCamera.cpp::DrawLDR` readback: bind cameraFBO,
select GL_COLOR_ATTACHMENT1, read pixels into the existing cameraPBO, then restore
framebuffer zero. It replaces glGetTexImage with:

```cpp
    OpenGLState::BindFramebuffer(cameraFBO);
    glReadBuffer(GL_COLOR_ATTACHMENT1);
    glBindBuffer(GL_PIXEL_PACK_BUFFER, cameraPBO);
    glReadPixels(0, 0, viewportWidth, viewportHeight, GL_RGB, GL_UNSIGNED_BYTE, NULL);
    glBindBuffer(GL_PIXEL_PACK_BUFFER, 0);
    OpenGLState::BindFramebuffer(0);
```

The exact unified patches are retained separately; candidate 2 contains both
hunks and must be applied to a fresh checkout, not on top of candidate 1.
Both candidates used the previous P3b fixed-pose optional perception scene with
both cameras enabled, unchanged lights/fixtures/all other sensors, 100 Hz physics,
320x240 preview, low graphics, llvmpipe and eight workers. Same RELIABLE depth-10
paired subscriptions; 12 s startup then bounded 20 s window; rates=count/window.
No FOV/resolution/XML tuning. Each process loaded only the disposable library via
LD_LIBRARY_PATH. No Neptune ROS package rebuild was needed or performed.

| Software run | Camera | Frames / window (s) | Hz | Max receipt gap (s) | Max stamp gap (s) |
| --- | --- | --- | --- | --- | --- |
| P3b baseline (retained) | existing | 19 / 20.01169 | 0.949445 | 1.216205 | 2.672112 |
| P3b baseline (retained) | inspection | 19 / 20.01169 | 0.949445 | 1.194253 | 2.676802 |
| P3c candidate 1 | existing | 32 / 20.009017 | 1.599279 | 0.687598 | 2.283006 |
| P3c candidate 1 | inspection | 32 / 20.009017 | 1.599279 | 0.671358 | 2.283014 |
| P3c candidate 2 | existing | 31 / 20.001220 | 1.549905 | 0.692256 | 0.701204 |
| P3c candidate 2 | inspection | 31 / 20.001220 | 1.549905 | 0.690156 | 0.700397 |

**Both candidates FAIL.** Scheduling increases delivered rate in these short
windows, supporting a shared scheduling contribution; it is insufficient to
restore usable publication. Framebuffer readback does not improve throughput over
candidate 1. The smaller stamp gaps in candidate 2 are not proof of a readback fix
because there was only one window per candidate. No exact remaining root cause
was established. Observed CPU use (~479% during candidate 1) and enabled graphics
work are consistent with rendering cost, but no GPU-stage timing was measured.
Publication stamps remain wall-clock readback stamps, not physical capture times.

**D3D12: no new test**, because neither software candidate passed the prerequisite.
Retained P3b evidence is existing 0 frames/0 Hz and inspection 1 frame/0.04997 Hz
in 20.01196 s; interframe receipt/stamp gaps are undefined with fewer than two
frames. A D3D12-specific framebuffer/PBO defect remains unproven. No Mesa, WSL,
NVIDIA or host graphics configuration changed. Extracted SDL2 development headers
were used only in /tmp; no graphics packages were installed or changed.

### Build, invariants, reproduction and rollback

Disposable native builds compiled one changed translation unit and relinked
against existing pinned Stonefish objects (including unchanged FLS overrides).
Candidate 1 succeeded in **3.216950 s**; candidate 2 in **1.535475 s**. Initial
candidate-1 compile failed on missing SDL2 development headers, then on its
architecture-specific include path; both failures were corrected using extracted
`libsdl2-dev` headers and both native candidate builds passed. The installed
library was not rebuilt/replaced: it still matches /opt/stonefish/build/libStonefish.so,
SHA-256 `5a566fdf108cb5246105aab5faeb29e2beeebe1bac653d77a841788beaa677f4`.

Both live candidates preserved camera dimensions, native frame IDs, and intrinsics:
existing 1360x1024, fx=fy=1306.267846340393, cx=680, cy=512;
inspection 640x480, fx=fy=100.8956124412747, cx=320, cy=240. Stamps increased
monotonically; RELIABLE/VOLATILE QoS remained. A fresh separate bounded live TF
check passed both unchanged static edges and optical quaternion (0.5,0.5,0.5,0.5).
No sensor configuration or package under src/ changed; no thruster, adapter,
mission, autonomy, controls, estimator, perception, Roboflow or GUI change.
Fixture visibility remains the retained P3 image evidence with unchanged optics;
no new candidate image was retained, so fresh candidate visibility is unverified.
This limitation does not change the already failed throughput gate.

Reproduce source patches explicitly in a **disposable** checkout:

```bash
git clone --no-hardlinks external/stonefish /tmp/neptune-p3c-source-1
python3 docker/patches/p3c-experimental/apply.py /tmp/neptune-p3c-source-1 1
# For candidate 2, use another fresh checkout and select 2 instead.
```

The helper checks the exact upstream SHA and SHA-256 of both affected source
files, checks patch applicability before mutation, verifies resulting hashes,
recognizes an exactly applied candidate, and rejects drift/mixed candidate state.
Existing unrelated FLS overrides are permitted. Neither artifact is an accepted
fix. For a complete separate native build, retain the current FLS overrides and
use the Dockerfile's Release CMake build in the disposable source; run the current
paired P3b probe with its simulator process LD_LIBRARY_PATH selecting that build's
libStonefish.so. The measured fast builds reused existing object files and changed
only the candidate translation unit; they did not rebuild unrelated packages.

Rollback: stop the owned experiment process and remove its process-local
LD_LIBRARY_PATH override. Normal launch already uses the original library; no
Dockerfile/source/installed-library rollback is required. Discard the disposable
checkout to undo experimental source changes. Do not apply these artifacts to
normal dependencies or promote them without a new authorized investigation.

Evidence: container /tmp/neptune-p3c/{source,candidate1.patch,candidate2.patch,
libStonefish.so}, /tmp/neptune-p3c-candidate{1,2}-{software.log,result.json}.
Both probe processes completed bounded cleanup; no simulator remained. Startup
retained the known SDL2 unsupported-operation warning without missing-resource
failure. Source-helper apply/idempotence/drift checks and git diff --check passed.
No final integration benchmark was run because no candidate met acceptance.
Stage 2 remains frozen through S2.6; P4 and S2.7–S2.14 were not started.

## P3c follow-up sensor-budget audit (2026-10-12)

**A blanket platform-limited conclusion is not supported.** Unpatched Stonefish
sustained >=5 Hz with <0.5 s receipt and stamp gaps in a temporary 320x240
inspection-camera-only configuration. The normal 640x480 configuration has not
passed; P3 is not promoted to complete by this diagnostic. P4 remains not started.

Exact repository camera XML in scenarios/neptune_girona_perception.scn:
`<sensor name="proscilica" type="camera" rate="10.0">` and
`<sensor name="inspection_camera_optical_frame" type="camera" rate="10.0">`.
Existing camera specs: 1360x1024/55 degrees; inspection: 640x480/145 degrees.
Native ScenarioParser reads rate directly into ColorCamera; Sensor constructor
stores it through setUpdateFrequency with no clamping or lower-rate substitution.
The ROS parser creates queue size ceil(getUpdateFrequency()) and changes only
enable state. There is no runtime rate-getter service: this frequency confirmation
is from the exact loaded pinned parser/constructor source and XML, not achieved FPS.
Normal startup has existing camera disabled by /sim/proscilica/set_enabled and
inspection enabled without an enable service. Both retain nominal 10 Hz frequency.

Complete graphical sensor/view inventory:

| Native sensor or view | Configured rate / size | Normal scene startup | Prior paired diagnostic |
| --- | --- | --- | --- |
| GIRONA500/proscilica, OpenGLRealCamera | 10 Hz; 1360x1024 | Sensor disabled by enable-service declaration | Enabled |
| GIRONA500/inspection_camera_optical_frame, OpenGLRealCamera | 10 Hz; 640x480 | Enabled | Enabled |
| GIRONA500/fls, OpenGLFLS | 2 Hz; 512 beams x 256 bins | Sensor disabled by enable-service declaration | Enabled |
| Main OpenGLTrackball view | Continuous; simulator window size | Enabled | Enabled |

There are no other camera/depth/segmentation/sonar sensors or custom views in
this scenario. Disabled sensor views remain registered and may receive initial
updates; they do not receive steady sensor-update requests. The main trackball
shares the render pipeline and continuously renders independently of camera rate.
Scene geometry, ocean/particles, atmosphere and three vehicle lamps add rendering
work but are not additional sensors/views. Cameras have on-screen display false
by default; FLS additionally generates its display image in its own sensor path.

Exactly two new SOFTWARE tests, original installed Stonefish library, llvmpipe
with eight workers, low render quality, **160x120 main window**. Temporary copies
of the prior fixed inspection-pose scene removed existing camera and FLS entirely
(to avoid even startup/cached-view work), retained inspection at rate 10.0, and
retained/enabled DVL, IMU, pressure, odometry (also accelerometer/GPS). Vehicle pose
and fixtures/lights/world were unchanged. 12 seconds startup, then each bounded
20-second measurement; reliable depth-10 subscriptions; count/full-window rate.
The second test changed only temporary inspection resolution after the first
measured <5 Hz. No repository XML, native source, native library or Docker change.

| Inspection-only resolution | Frames / window | Hz | Max receipt gap | Max stamp gap |
| --- | --- | --- | --- | --- |
| 640x480 | 75 / 20.005811 s | 3.748911 | 0.357176 s | 2.072022 s |
| 320x240 | 108 / 20.002621 s | 5.399292 | 0.214072 s | 0.214050 s |

640x480 scalar counts: DVL 435, IMU 435, pressure 109, odometry 653.
320x240 scalar counts: DVL 400, IMU 400, pressure 100, odometry 600, consistent
with configured 20/20/5/30 Hz. No existing-camera or FLS image stream was present.
CameraInfo confirmed selected dimensions, unchanged frame and FOV; at 320x240
fx=fy=50.44780622063735, cx=160, cy=120. /proc process maps verified
/usr/local/lib/libStonefish.so in both tests, with no candidate-library override.

Conclusion: sensor/view rendering budget materially affects publication in this
software runtime. Removing auxiliary vision work and reducing the main window
improved 640x480 inspection throughput from prior paired ~0.949 Hz to ~3.749 Hz;
reducing inspection pixels then reached ~5.399 Hz. These first changes were bundled,
so their individual contributions are not isolated. A WSL-specific hard <5 Hz
camera ceiling is disproven for this reduced software configuration. WSL graphics
may still contribute to total rendering cost; neither these tests nor the prior
candidates establish the exact expensive stage. D3D12 was not tested here and its
failure remains unresolved. The 640x480 stamp outlier remains unexplained; ROS
publication stamps are not physical capture timestamps. Single short windows do
not establish long-term reliability or validate 320x240 detector suitability.

Evidence: container /tmp/neptune-camera-budget/{scene.scn,robot.scn,640x480.log,
320x240.log,result.json}; host /tmp/neptune-camera-budget.py. Both simulators were
stopped with bounded cleanup; native source changes remain only the existing FLS
compatibility overrides. Rollback is simply using the unchanged repository scene;
all sensor-budget changes exist only in /tmp. No package rebuild was required.
No full mission, P4, native patch, commit or push occurred. Stage 2 stays frozen
through S2.6. Documentation and git diff --check validation only after the probes.

## P3 finalization — COMPLETE WITH PERCEPTION PROFILE

**P3 COMPLETE WITH PERCEPTION PROFILE. P4 is next, NOT STARTED.** This status
supersedes the historical blocked/native-investigation records above. The shared
Stonefish/WSL rendering budget was the limiting factor; reducing vision work and
image resolution passed the approved minimum gate without a native patch.
Polished visualization remains P8 work.

Official launch: `ros2 launch neptune_sim perception_performance.launch.py` with
required `simulation_data` pointing to the existing Stonefish resource directory.
The launch reuses perception_camera.launch.py for simulator/TF ownership and
forces software llvmpipe, eight workers (`GALLIUM_DRIVER=llvmpipe`,
`LIBGL_ALWAYS_SOFTWARE=1`, `LP_NUM_THREADS=8`), low graphics quality, 100 Hz physics,
and a 160x120 main window. No native modifications or experimental patch hooks.

The installed `neptune_sim.perception_profile` helper derives temporary scene and
vehicle XML from the installed optional perception resources at launch. It sets
inspection resolution to 320x240, preserves rate 10.0, FOV 145 degrees, pose,
clip planes, topics and frame names, and excludes other vision sensors entirely
(existing auxiliary camera and FLS), avoiding their startup/cached-view workload.
DVL, IMU, pressure and odometry remain present and start enabled; existing
accelerometer/GPS also remain enabled, matching the measured reduced runtime.
Their sensor enable-service declarations are omitted only in this generated
profile. No sensor rate/noise/physics change or motor/mission architecture change.
Ground truth /sim/odometry remains evaluation-only. The launch starts simulator
and camera static TFs only, not estimator, adapter, mission or detector nodes.

The helper preserves original HOME spawn/dynamic-body behavior, geometry, lamps,
and actuators. It writes into a unique temporary directory cleaned on launch
shutdown. Source/installed scene files are never overwritten or duplicated in
the repository. A forced process/host exit can leave temporary files in /tmp.

Ordinary visual use remains `perception_camera.launch.py`: unchanged 640x480
inspection camera, 800x600 default window, existing camera/FLS definitions and
historical enable-service defaults, native graphics default and optional explicit
software_rendering flag. Baseline vehicle/scenarios are untouched. This is a
visual/demo entrypoint, with no passing camera-throughput claim. Performance
settings are explicit in their separate launch, never silently applied to demos.

Camera contract (performance profile):

- `/neptune/camera/inspection/image_color`, native rgb8, 320x240.
- `/neptune/camera/inspection/camera_info`, native CameraInfo for 320x240.
- Both frame IDs: `GIRONA500/inspection_camera_optical_frame`.
- HFOV 145 degrees; configured rate 10 Hz; existing near/far 0.05/20 m.
- Existing camera mount/optical TF unchanged: translation (0.82,0,0.20), optical
  quaternion (0.5,0.5,0.5,0.5).

CameraInfo is generated by the unchanged native bridge from actual camera
settings; no intrinsics are manually assigned. Retained 320x240 measurement:
fx=fy=50.44780622063735, cx=160, cy=120; K/P scale with runtime resolution.

Retained approved software evidence (no additional throughput run):

| Inspection-only resolution | Frames / approximately 20 s | Hz | Max receipt gap | Max stamp gap | Result |
| --- | --- | --- | --- | --- | --- |
| 640x480 | 75 | 3.749 | 0.357 s | 2.072 s | FAIL |
| 320x240 | 108 | **5.399** | **0.214 s** | **0.214 s** | PASS minimum |

The accepted evidence used a temporary fixed inspection pose with all required
scalar streams active. It establishes the reduced settings' bounded performance,
not long-term reliability or a full mission at the repository's dynamic spawn.
Configured 10 Hz is retained; the >=8 Hz preferred goal is not met. Native stamps
remain publication/readback wall time, not validated capture timestamps. Detector
quality at 320x240 is future P4 work. D3D12 remains **unsupported/unusable for this
camera path** on the tested WSL runtime; hardware usability is not claimed.

Build verified in this session (one package, no simulator/native rebuild):

```bash
docker compose -f docker/compose.yaml exec -T dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /opt/stonefish_ws/install/setup.bash
  cd /workspace
  colcon --log-base /tmp/neptune-p3-final-log build \
    --build-base /tmp/neptune-p3-final-build \
    --install-base /tmp/neptune-p3-final-install --packages-select neptune_sim
'
```

Run the official performance profile from that verified installation:

```bash
docker compose -f docker/compose.yaml exec dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /opt/stonefish_ws/install/setup.bash
  source /tmp/neptune-p3-final-install/setup.bash
  ros2 launch neptune_sim perception_performance.launch.py \
    simulation_data:=/workspace/external/stonefish/Tests/Data
'
```

For ordinary visual/demo use, replace only the launch filename with
`perception_camera.launch.py`; its normal window/resolution defaults remain.
With a normal workspace colcon installation, source that workspace's
`install/setup.bash` instead of the temporary verified install above. No prior
/tmp scene or benchmark-generated file is required by either official launch.
Rollback/select ordinary rendering by using the original launch; there is no
native patch or Docker change to undo.

Experimental evidence retained under `docker/patches/p3c-experimental/` is
**NOT ACTIVE / NOT PART OF NORMAL BUILD / FAILED ACCEPTANCE**. Its README states
this explicitly. The patch helper is manual-only, with no normal build/launch
reference. Both rejected native candidates remain excluded from official P3.

Final quick validation: Python syntax, generated XML/config and preservation
checks, neptune_sim package build, installed helper/resources and launch wiring,
launch argument parsing, temporary-resource cleanup, and git diff --check passed.
No simulator smoke, throughput experiment, native debugging or full mission was
run during finalization. No upstream Stonefish, GUI, perception runtime, controls,
autonomy, estimator or adapter changes. P4 NOT STARTED; no commit or push.

Finalization build: neptune_sim completed successfully (1 package, 0.93 s).
The first installed-resource checker invocation failed because it treated raw
launch argument strings as substitution objects; correcting only the checker
resolved it. Final installed verification and `--show-args` passed, without
starting any simulator. No package or acceptance criterion was weakened.


## P4a Inspection Objects — COMPLETE (2026-10-12)

This record supersedes historical P4-not-started statements. P4a is observation
only. **P4b next: Orientation A1/t1, not started; P5 not started.** Stage 2 stays
frozen through S2.6. No autonomy, control, localization or simulator changes;
no mission, actuator commands, commit or push.

### Model, runtime and secret

- Workspace: `projects-zwfft`; project: `neptune-inspection-objects`; dataset
  version **2**; YOLO11n. Exact loaded model:
  **projects-zwfft/neptune-inspection-objects-2-yolo11n-t1**.
- Fixed confidence **0.05**, NMS IoU **0.7**, maximum detections **300**.
  Loaded model schema must contain exactly pipe/valve/flange, with consistent
  prediction class IDs/names. Malformed/unexpected results are rejected.
- Verified tag family: `roboflow/roboflow-inference-server-gpu:1.7.4`.
  Verified **linux/amd64** platform manifest and downloaded image; exact pin:

```text
roboflow/roboflow-inference-server-gpu@sha256:9f91f44c23c067c03182c5b1de4213e5bdd97e393cd412c9bb4bdabdf5bdca29
```

`docker/compose.perception.yaml` starts a separate GPU container with only
`127.0.0.1:9001` published. This pinned Roboflow runtime runs the constrained
`neptune_perception.inference_server` adapter, using `inference.get_model` and
the legacy YOLO11 ONNX implementation. It exposes just `/health` and `/infer`.
The ROS client sends full-frame lossless PNG bytes, without credentials. The
adapter applies the model's configured preprocessing; no local crop/resize or
invented orientation. Direct model inference does not invoke cloud image
inference or the generic server's active-learning/monitoring API routes.

Authentication uses the existing host file `~/.config/neptune/roboflow_api_key`,
read-only bind-mounted at **/run/secrets/roboflow_api_key**. Missing host files
are not created. Only the inference process reads the secret; no credential in
argv, environment, repository, YAML, Dockerfile, report or documentation.
Third-party/native stdout and stderr are discarded before imports/secret access;
Docker inference logging is disabled. Fixed HTTP error states contain no remote
body/exception. Model caches and one-shot ONNX profile are ephemeral under /tmp.
No donor ARM64 CPU image or Linux NVIDIA display driver installation.

An actual model inference is profiled: CUDAExecutionProvider must be present in
the loaded session **and** execute model nodes. A merely advertised provider is
insufficient. The adapter reports only safe provider/count/GPU-name evidence.
Automatic ONNX CPU run fallback is disabled; runtime errors remain unavailable.

### Observation and freshness contract

| Topic | Message | Contract |
| --- | --- | --- |
| /neptune/camera/inspection/image_color | sensor_msgs/Image | Full received 320x240 frame, native rgb8; input only |
| /neptune/perception/object_detections | vision_msgs/Detection2DArray | Class name in hypothesis.class_id, confidence in score, clipped axis-aligned bbox center/extents |
| /neptune/perception/annotated | sensor_msgs/Image | bgr8 annotation of that exact source frame, including empty prediction results |
| /neptune/perception/status | std_msgs/String | JSON state, source/observation/timing/GPU/freshness/counter metadata |

Array header, each Detection2D header and annotated header preserve the source
stamp (sec/nanosec) and camera frame_id
`GIRONA500/inspection_camera_optical_frame`. Status has:

- `model_id`, `source_header`, `image_width`, `image_height`, `runtime`.
- `observations`: class_name, confidence, clipped xyxy, center,
  horizontal_error `(u-width/2)/(width/2)`, vertical_error
  `(v-height/2)/(height/2)`. Right/down are positive, bounded by clipping.
- `orientation_valid=false`, `orientation_rad=null` per object; top-level
  orientation_valid=false. Axis-aligned bbox rotation is not an angle estimator.
- `source_stamp_s`, `inference_start_monotonic_s`,
  `inference_end_monotonic_s`, `processing_latency_s`, `observation_age_s`,
  `result_receipt_age_s`, `last_valid_observation_stamp_s`, `camera_silence_s`.
- `in_flight_source_stamp_s`, `in_flight_start_monotonic_s` separately describe
  a newer request; they never relabel the previous result's source stamp/header.
- `received_frames`, `replaced_frames`, `pending_frames`, `in_flight`,
  `processed_frames`, `discarded_stale_frames`, `processed_fps`. Status FPS is
  cumulative since node startup; the smoke separately measures a warm 20 s window.
- `state`, `model_state` (last result/error), `observation_valid`,
  `freshness_threshold_s`. Nullable timings mean no corresponding event yet.

| State | Meaning |
| --- | --- |
| READY | Fresh valid response with detections |
| NO_DETECTION | Fresh valid response with empty predictions |
| STALE | Source age, request latency or time since last successful receipt exceeded threshold; negative source age also invalid |
| MODEL_UNAVAILABLE | No successful runtime response, transport/model/GPU failure or timeout |
| CAMERA_STALE | Camera has been silent past the threshold, including startup with no frames |
| SCHEMA_ERROR | Loaded classes, response dimensions/structure/numbers/class IDs violate the contract |

Initial engineering freshness threshold **0.5 s**, configurable in
`config/inspection_objects.yaml`; it is not a calibrated operational safety limit.
`observation_valid` is true only in READY/NO_DETECTION. Camera silence has display
priority over the model state, which remains available separately. A **steady-clock
20 Hz watchdog** publishes state during blocked requests and ROS-clock stalls.
Source age uses ROS time; silence/receipt age use monotonic wall time. Native
camera stamps remain wall-clock readback/publication time, not proven capture time.
Stale diagnostic arrays/images retain their source stamps and may be published;
consumers must check status and age. READY never latches indefinitely.

BEST_EFFORT/VOLATILE, KEEP_LAST depth-one camera input is compatible with the
native RELIABLE/VOLATILE camera. Exactly one replaceable pending-frame slot and
one inference worker/request. New frames replace pending old frames while busy.
Already-stale pending frames are discarded before dispatch. No request per frame
is enqueued. HTTP request timeout is 120 s maximum; the watchdog remains active,
but graceful shutdown may wait for that request timeout.

### Running P4a

The dev Dockerfile now declares vision_msgs, cv_bridge and OpenCV. The current dev
container already had cv_bridge/OpenCV; vision_msgs was installed for validation.
No complete dev Docker image rebuild was performed. Existing ROS/Stonefish and P3
resources are required. Recreate the validated perception package installation:

```bash
docker compose -f docker/compose.yaml exec -T dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  cd /workspace
  colcon --log-base /tmp/neptune-p4a-log build \
    --build-base /tmp/neptune-p4a-build \
    --install-base /tmp/neptune-p4a-install --packages-select neptune_perception
'
docker compose -f docker/compose.perception.yaml up -d inspection_inference
```

Start the camera performance launch as documented in P3, then in another terminal:

```bash
docker compose -f docker/compose.yaml exec -T dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /tmp/neptune-p4a-install/setup.bash
  ros2 launch neptune_perception inspection_objects.launch.py
'
```

The observer launch starts no simulator, mission, controller, state estimator or
adapter. Stop inference with
`docker compose -f docker/compose.perception.yaml stop inspection_inference`.
Stopping the observer/inference restores the P3-only configuration; baseline
launches never include perception automatically.

Focused tests (ROS sourced):

```bash
export PYTHONPATH=/workspace/src/neptune_perception:$PYTHONPATH
ROS_DOMAIN_ID=81 python3 -m pytest -q /workspace/src/neptune_perception/test
```

For an explicitly authorized bounded diagnostic after tests/build, the repository
runner is `./scripts/run_p4a_smoke.sh`. It requires the P3/P4a temporary installed
overlays above, refuses an already-running inference service, owns its processes,
uses a unique /tmp result directory and an isolated ROS domain 83, generates the
official P3 profile, and changes only temporary fixed pose for fixture viewing.
One 125 s model/transport deadline, one 20 s warm window, bounded shutdown and
an inner 165 s/outer 175 s execution timeout. It issues no actuator commands.
Do not run a mission to validate P4a.

### Actual validation and limitations

Donor backends.py/detector.py/config inspected completely from local remote branch
`lumyn/Perception`, SHA `608a3b985b8c5dbfc56f5398b8679c8038861bbe`. Safe finite
response/class/bbox checks, annotation colors and header construction were adapted;
donor orientation defaults, mission/control logic and raw exception logging were
excluded. The initial GitHub interpretation returned 404; local branch resolved it.

Final **62 tests passed in 1.31 s**. Parsing/schema/malformed data, clipping,
centers/errors, empty responses, stale result/model loss/camera silence, latest
replacement, real ROS headers and annotations, missing/invalid secret, native/
exception log suppression, full-frame/fixed settings, actual CUDA profile gate
and CPU-only rejection are covered. Initial host socket-denial failures and a
ROS Node.context attribute collision were corrected without weakening checks.
Final ROS package build: **1 package finished in 0.82 s**. Installed launch
arguments, Python compilation, shell syntax, Compose and diff checks passed.

**ONE bounded live smoke PASSED** at a temporary fixed inspection pose, without
mission or commands. Inference-container nvidia-smi showed **RTX 4080 Laptop GPU**,
Windows driver **551.95**, advertised CUDA **12.4**. Actual loaded-model ONNX
profiling recorded **238 node events, all CUDAExecutionProvider**. Loaded schema
was pipe/valve/flange. Automatic CPU fallback was disabled after the live run
(pinned API verified), and an explicit PID-1 SIGTERM handler was added after
Docker needed forced container termination (137). Adapter/subprocess-shutdown
tests and final build passed; no second live run was performed.

| Live metric | Measured value |
| --- | --- |
| Warm window | 20.002130522 s |
| Camera | 123 frames; 6.149344934 FPS |
| Processed outputs | 124 frames; 6.199339609 FPS |
| Warm latency mean / median | 42.872 / 44.660 ms |
| Warm latency p95 / max | 76.048 / 93.799 ms |
| Cold first request including model initialization | 17.631712 s, STALE |
| Observation age mean / max | 0.106406 / 2.234397 s; outliers explicitly STALE |
| Whole-smoke detection box counts | pipe 242; valve 127; flange 126 |
| Paired source headers verified | 126 detection/annotated pairs |
| Max pending / in flight | 1 / 1 |
| Pending replacements | 102, primarily during cold initialization |
| Camera-stop result | CAMERA_STALE; observation_valid=false |
| Command / thruster publishers | 0 / 0 |

One in-flight result crosses the warm-window boundary, accounting for processed
count exceeding camera count by one; it is not duplicated inference. Box counts
span the whole smoke and include duplicate/overlapping pipe detections. They do
not count unique objects or establish accuracy. READY/STALE/initial unavailable/
camera-stale states were observed; NO_DETECTION/SCHEMA_ERROR/model-loss behavior
has focused test coverage. All owned processes and inference service stopped.

Current input is full **320x240 / 145-degree HFOV** with the accepted P3 software
profile (prior validated rate ~5.399 Hz). Original model validation used full
**640x480 simulator frames**. Equivalent accuracy at 320x240 is **not claimed**;
this is a source-frame training/validation versus runtime resolution mismatch,
not an excuse to invent a crop. Managed model preprocessing remains authoritative.
Single short fixed-pose evidence does not prove dynamic-scene reliability,
all access/failure-recovery paths or real-ocean accuracy. Source timing outliers
and cold-load freshness violations remain explicit. No confidence tuning occurred.

Evidence: container `/tmp/neptune-p4a-smoke-5x78iait/result.json` and simulator/
empty observer logs; host `/tmp/neptune-p4a-live-result.json`. /tmp is temporary.
Read-only offline credential scan through the mounted secret found its value in
**zero of 219 repository files**. Inference output/logging is discarded/disabled;
observer never sees the key and its actual log was empty. No credential entered
the repository or logs. No Orientation A integration, pipe-angle estimation,
visual control, P5, commit or push. Both required project documents were updated.
