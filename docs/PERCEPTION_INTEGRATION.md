# Perception integration — P1 / P2 / P3 / P4a / P4b / P4c / P5a

**Demo V0: FULL MOVEMENT MISSION VALIDATED — MAJOR MOVEMENT/INTEGRATION PASS.**
The user manually validated `./scripts/run_demo_v0.sh` through INITIALIZING ->
WAIT_FOR_STATE -> DIVE -> TRANSIT -> INSPECT -> RETURN -> ASCEND -> COMPLETE.
**G1/G2/G3 PASS — GRAPHICS / GPU RUNTIME VALIDATED.** Frozen runtime: accelerated
D3D12 / RTX 4080 Laptop GPU, dynamic seven-thruster Girona, 1280x720 LOW Stonefish
viewport, inspection RGB 320x240/80-degree HFOV/configured 10 Hz. Graphics plus
CUDA coexistence was proven separately in G3. GUI and camera stream are WORKING.

**Known visual issue:** camera appears AFT/backward; inspection lights appear
backward or share an incorrect mounting convention and require verification.
A local mounting-transform/orientation-convention or 180-degree issue is suspected,
not proven. Movement completion, state estimation, streaming, GUI, graphics and
seven-thruster integration were successful despite this issue. Next: inspect/correct
only Girona body-frame convention, camera mounting/optical-frame transforms and
light mounting/orientation, then a short forward-facing asset/lighting visual check.

P0/P1/P2 scene/vehicle work and P4a/P4b/P4c implementations are preserved.
**P5a IMPLEMENTED — LIVE CLOSED-LOOP VALIDATION DEFERRED.** Existing sign=0,
controller/configuration/tests/diagnostic scripts are unchanged; historical
calibration failures remain evidence. P5b NOT STARTED; Stage 2 frozen through S2.6.
Demo V1 passive perception overlays are next **after camera/light orientation fix**;
renewed P5a perception-driven alignment also requires that fix. Demo V0 starts no
inference server, detectors, fusion or P5 controller. No next task is started here.

The prior software performance and ordinary camera launches remain explicit
legacy profiles. Historical D3D12 failures and rejected P3c patches below are
superseded by the G1/G2/G3 runtime results, not deleted. **No rejected native
patch is active; no Mesa/WSL/driver/Stonefish change is part of Demo V0.**

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


## P4b Orientation A1 robust pipe detector — COMPLETE (2026-10-12)

**P4b COMPLETE; ONE bounded A1-only GPU smoke passed. P4a still passes unchanged.
P4c next: dual-model association, NOT STARTED. P5 NOT STARTED.** This supersedes
historical P4b-not-started statements above. Stage 2 remains frozen through S2.6.

### Semantics and model

Exact A1/t1 model: **projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1**.
Workspace projects-zwfft, project neptune-pipe-orientation-a, dataset version **3**,
YOLO11n. Expected class schema exactly **pipe**. Confidence **0.05**, NMS IoU
**0.7**, max detections **300**, unchanged from the task settings.

“Orientation A” refers to broader pipe orientations/viewpoints in the training
distribution. **This is a robust single-class pipe detector, NOT an angle
estimator.** Its output is an axis-aligned pipe bounding box. It produces no
physical pipe angle, rotated box, orientation category, keypoints or mask.
`orientation_valid=false` always; shared `orientation_rad` remains null. Bbox
rotation defaults describe an axis-aligned rectangle; bbox aspect ratio and
geometry never populate a physical angle.

Input is the **full received frame**, lossless PNG, followed by the managed
model's configured preprocessing. No pipe ROI crop or local resize. A1 was
trained/evaluated on full **640x480** images; runtime uses **320x240**, 145-degree
HFOV, accepted P3 software profile (prior validated ~5.399 Hz). Equivalent
accuracy at 320x240 is **not claimed**.

### Shared server and independent observations

Same existing inspection_inference service, secure read-only
`/run/secrets/roboflow_api_key` mount and linux/amd64 GPU image pin:

```text
roboflow/roboflow-inference-server-gpu@sha256:9f91f44c23c067c03182c5b1de4213e5bdd97e393cd412c9bb4bdabdf5bdca29
```

No Docker/credential/CUDA configuration changes or second GPU server. Two
independent model slots load lazily and remain in the same serial server:

| Model | Inference route | Model-specific health |
| --- | --- | --- |
| Inspection Objects (P4a) | POST /infer | GET /health |
| A1 robust pipe (P4b) | POST /infer/orientation_a | GET /health/orientation_a |

Both accept full-frame image/png requests through the existing backend and
retain independent model/schema/CUDA evidence. P4a's defaults, routes, outputs,
configuration, launch and tests are unchanged. A1 uses a small subclass of the
existing latest-frame observer plus explicit model/class validation. Each client
uses its model-specific health; `/health` continues to describe Inspection
Objects, including when only A1 is loaded. Actual P4b smoke loaded/exercised only
A1; P4a's session remained unloaded. Simultaneous operation is unmeasured; P4c
will decide scheduling and association. No fusion or N=2 scheduling is present.

| Topic | Message / data |
| --- | --- |
| /neptune/camera/inspection/image_color | sensor_msgs/Image, input only |
| /neptune/perception/orientation_a_detections | vision_msgs/Detection2DArray, pipe class/confidence, axis-aligned bbox center/extents |
| /neptune/perception/orientation_a_annotated | sensor_msgs/Image, bgr8, exact same accepted source frame |
| /neptune/perception/orientation_a_status | std_msgs/String JSON, robust pipe observation and freshness metadata |

Despite the topic names, **none reports physical orientation**. Array, individual
detection and annotated headers copy the original source sec/nanosec/frame_id:
`GIRONA500/inspection_camera_optical_frame`. Status retains model ID, source
header, image width/height, each pipe's confidence/clipped xyxy/center/normalized
errors, request start/end, processing latency, observation age, receipt age, last
valid stamp, camera silence, runtime evidence and frame counters. Error formulas:
horizontal `(u-width/2)/(width/2)`, vertical `(v-height/2)/(height/2)`; positive
right/down. Orientation validity is false at the top level and per detection;
orientation_rad is null regardless of bbox shape.

Depth-one BEST_EFFORT/VOLATILE input, one latest pending frame, one worker/request
in flight. A1 alone attempts inference on **every fresh frame when idle**, with
new arrivals replacing pending old frames while busy. No N=2 sampling or backlog.
Already-stale pending inputs are discarded. Same initial engineering threshold
**0.5 s**, steady-clock 20 Hz watchdog and explicit READY, NO_DETECTION, STALE,
MODEL_UNAVAILABLE, CAMERA_STALE and SCHEMA_ERROR states as P4a.

A1 **rejects stale completions before publishing detection arrays or annotated
images**. Their status observations are empty and observation_valid=false;
source/timing/GPU diagnostics remain visible. They do not update the last valid
observation; `rejected_stale_results` counts them. Successful observations later
expire via the existing watchdog. P4a retains its pre-existing timestamped stale
diagnostic outputs and its original status shape.

### Build and run

Reuse the existing dev container and P3 camera setup. Build A1 and the unchanged
P4a entrypoint together:

```bash
docker compose -f docker/compose.yaml exec -T dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  cd /workspace
  colcon --log-base /tmp/neptune-p4b-log build \
    --build-base /tmp/neptune-p4b-build \
    --install-base /tmp/neptune-p4b-install --packages-select neptune_perception
'
docker compose -f docker/compose.perception.yaml up -d inspection_inference
docker compose -f docker/compose.yaml exec -T dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /tmp/neptune-p4b-install/setup.bash
  ros2 launch neptune_perception orientation_a.launch.py
'
```

Use the same ROS domain as the camera. This launch starts only A1, with no
Inspection Objects node, simulator, adapter, mission or controller. The existing
P3 performance launch supplies camera frames independently. Stop A1 and the
owned inference service to return to P3; selecting the original
inspection_objects.launch.py still runs P4a with its original contract.

Focused ROS-sourced tests use the P4a documented PYTHONPATH and pytest package
directory. **46 new/additive tests passed (0.63 s)** and **all 62 original P4a
tests passed unchanged (0.48 s)**, 108 total. Covers correct model/schema,
unexpected valve/flange rejection, malformed responses, clipping/centers/errors,
empty predictions, source/latency/receipt stale completion, loss states, latest
replacement, every-fresh-frame dispatch, preserved headers, full-frame/fixed
settings/CUDA adapter, false orientation and independent server routing. An
additive test preserves P4a's existing stale-diagnostic behavior; no original
test or acceptance criterion was changed. Final neptune_perception build:
**1 package, 0.63 s**. Both installed launches, Python/Bash syntax and diff checks pass.

The explicit bounded runner is `./scripts/run_p4b_smoke.sh`, requiring the
documented P3/P4b installed overlays. It shares P4a's runtime lock, requires an
idle inference service, owns start/stop, uses isolated ROS domain **84**, and
creates temporary fixed-pose XML from the official P3 helper. One 125 s startup/
model deadline, one 20 s warm window, inner 165 s/outer 175 s execution bounds,
bounded process cleanup. It reuses P4a's header/cleanup helpers. No mission or
actuator commands. The first sandbox invocation was denied Docker access before
startup; the approved retry performed the **single actual live smoke**.

### Live evidence and limits

**PASS**: exact A1 loaded, schema pipe-only accepted, current camera frames reached
GPU inference, all three A1 ROS output topics published with preserved source
headers. RTX 4080 Laptop GPU visible in the existing container; Windows driver
**551.95**, advertised CUDA **12.4**. Actual model ONNX profiling: **238 node
events, all CUDAExecutionProvider**; automatic CPU fallback remained disabled.

| Metric | Actual A1-only measurement |
| --- | --- |
| Warm window | 20.000936789 s |
| Camera | 123 frames; 6.149711951 FPS |
| Accepted processed output | 124 frames; 6.199709609 FPS |
| Warm latency mean / median | 55.912 / 66.154 ms |
| Warm latency p95 / max | 92.284 / 114.415 ms |
| Cold first request/model initialization | 15.437542 s, STALE, output rejected |
| Valid observation age mean / max | 0.104143 / 0.185886 s at first status receipt per warm result |
| Pipe boxes over the whole smoke | 879 |
| Matched source detection/annotated pairs | 125 |
| Max pending / in flight | 1 / 1 |
| Pending replacements / rejected stale completions | 102 / 1 |
| Camera loss | CAMERA_STALE; observation_valid=false |
| Orientation validity | false; angle null throughout |
| P4a/command/thruster output publishers | zero |

An in-flight result crosses the warm-window boundary, explaining processed count
one above received camera count; the checker found no duplicate source array.
Boxes include multiple visible pipe sections, overlaps and low-confidence extra
boxes; they are not unique-object counts or accuracy metrics. Confidence was
not tuned. READY, initial MODEL_UNAVAILABLE, STALE and CAMERA_STALE were observed;
empty/schema/loss handling also has focused test coverage.

Single short fixed-pose evidence proves integration, not accuracy across broad
viewpoints, dynamic operation, long-term reliability or real-ocean performance.
Full 640x480 training/evaluation versus full 320x240 runtime remains a known
mismatch. Native stamps are readback/publication time, not verified capture time.
Cold load exceeds freshness. P4a's bounded request/shutdown and suppressed
dependency-log limitations remain; simultaneous dual-model contention is untested.

Evidence: container `/tmp/neptune-p4b-smoke-8xf6mmd4/{result.json,simulator.log,
detector.log,*.scn}`; host `/tmp/neptune-p4b-live-result.json`. /tmp is temporary.
All owned simulator/A1 observer processes exited; inference stopped cleanly
with exit **0**. Actual observer log was empty. Offline read-only credential
audit through the unchanged mount found the key in **zero of 234 repository
files**, without printing it. No secret entered source or logs. Both documents
were updated. **P4c dual-model association, P5, pipe angles, control and fusion
were not started. No commit or push occurred.**


## P4c dual-model execution + pipe association — COMPLETE (2026-10-12)

**P4c COMPLETE: one bounded N=1/N=1 dual-model GPU smoke PASSED. P5 is next
only when explicitly assigned; P5 NOT STARTED.** This supersedes historical
P4c-not-started statements. Stage 2 remains frozen through S2.6.

### Architecture and output contract

The independent, verified Inspection Objects and Orientation A observers receive
full identical camera frames from `/neptune/camera/inspection/image_color`.
Existing P4a/P4b code, configurations, launches and topics are unchanged. Both
use the existing serial GPU server and unchanged secure mounted secret:

- Inspection Objects: `projects-zwfft/neptune-inspection-objects-2-yolo11n-t1`.
- A1: `projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1`.

`pipe_fusion` consumes the existing `/neptune/perception/status` and
`/neptune/perception/orientation_a_status` JSON observations, rather than joining
arrays to a second dimensions/status stream. These already carry source headers,
dimensions, bbox geometry, separate confidence values, provenance and freshness.
`neptune_interfaces` currently contains only .gitkeep, no usable interface.
No new custom ROS message package was necessary; standard messages are reused.

| Output | Interface / contents |
| --- | --- |
| `/neptune/perception/fused_pipe_detections` | vision_msgs/Detection2DArray; every original pipe box retained, including both boxes in consensus; original confidence, source header, model ID in Detection2D.id |
| `/neptune/perception/fused_semantic_detections` | vision_msgs/Detection2DArray; unchanged Inspection Objects valve/flange geometry/class/confidence/header, model ID in Detection2D.id |
| `/neptune/perception/fused_status` | std_msgs/String JSON; authoritative unified observations, association records, selected_target, source header/dimensions, ages, valid flag, states and counters |

The status `pipes` records retain inspection/orientation_a observations, both
bbox arrays, both separate confidences, IoU (null when unmatched), association
state and model_provenance. `semantic_detections` retain the original observation
fields with the Inspection Objects model ID added. `selected_target` carries
selected bbox, center, normalized horizontal/vertical errors, bbox_source,
selected_source/model provenance, both confidences, IoU/state/valid. Source header,
image_width/image_height and observation_age_s/receipt_age_s are shared top-level
fields applying to that target. Missing target is null. `sequence` advances once
per finalized source; watchdog repeats never count as new observations. Overall
`valid` means a fresh selected pipe exists; NO_PIPE is a fresh completed frame
with valid=false. Consumers must honor fused status/freshness; arrays are event
outputs and do not latch a target's validity.

**Physical pipe angle remains unavailable.** Top-level and every pipe/selected
record retain `orientation_valid=false`; orientation_rad is null. No aspect
ratio, Hough, PCA, angle estimation, controls, autonomy, localization or actuator
work was implemented. No truth input exists.

### Matching, association and selection

Cache key is exact integer source sec/nanosec, never floating-point time or
receipt proximity. Frame ID and width/height must also agree before fusion.
Greedy one-to-one association considers edges in descending IoU order at a
configurable **IoU >= 0.30**, retaining unpaired boxes. Equal matching edges use
stable input indices. This is a simple deterministic greedy matcher, not a
maximum-total-IoU optimizer. Model confidences are never averaged or compared
across models; box geometry is never averaged.

Target policy: select the consensus pair with greatest IoU and use **Inspection
Objects geometry**. Distinct pairs tied for greatest IoU within 1e-9 are
AMBIGUOUS with no valid target. Without a pair, exactly one available pipe becomes
INSPECTION_ONLY or ORIENTATION_A_ONLY; multiple unmatched boxes become AMBIGUOUS.
Zero pipes becomes NO_PIPE. A1 can recover a pipe when Inspection Objects returns
no pipe, regardless of valve/flange presence. Valve/flange need no A1 validation.
Recovery and fallback are covered by pure tests; this fixed-pose smoke produced
consensus only and does not claim live recovery-viewpoint accuracy.

Default association window **0.20 s**, freshness **0.5 s**, capacity **8 source
entries**, configured in config/pipe_fusion.yaml. The 20 Hz steady-clock watchdog
expires unmatched entries, publishing a fresh single-model fallback without
waiting indefinitely. Source age, original detector validity, request latency,
original receipt age plus elapsed steady time are all checked. STALE completions
are excluded, no stale geometry is emitted. Exact per-model source watermarks
ignore repeated status/watchdog observations; finalized source watermarks reject
late counterparts and prevent retroactive output. A newer finalized source drops
older pending entries to preserve monotonic output. Capacity overflow finalizes
oldest pending input as a fresh fallback or STALE, with an eviction counter;
it cannot create an unbounded cache. Stale selected targets become invalid in
the watchdog even during ROS-clock stalls. MODEL_UNAVAILABLE remains explicit
at startup or after expired output and loss of both model feeds; individual
model_states always remain available alongside fallback/STALE status.

### Scheduling, validation and live evidence

**Keep N=1 for BOTH models.** Each existing worker attempts every available fresh
frame, with one replaceable pending slot and one in-flight request. Neither
model is gated by the other's detections. The existing serial server remained
adequate; no concurrency/server rewrite or N=2 sampling was needed. Exactly one
live run occurred; no N=2 comparison, mission or command was run.

- Pure P4c tests initially **40 passed**; final P4c coverage **50 tests passed**
  (45 pure + 5 ROS adapter/watchdog). All **108 existing P4a/P4b tests unchanged**.
  Final combined result **158 passed in 0.96 s**. Covers exact nanoseconds,
  mismatched stamp/frame ID/dimensions, IoU/threshold, one-to-one/multiple pipes,
  all selection states, recovery, stale/unavailable input, bounded cache/expiry,
  late/repeated/older-frame suppression, normalized errors, semantic pass-through,
  separate confidences, false orientation, ROS provenance/header and watchdog loss.
- Initial Docker socket denial required approved access. First ROS test aborted
  on synthetic integer bbox fields; explicit float conversion in the new adapter
  fixed it, with no test weakening. Subsequent combined run: 153 passed; final
  defensive stamp validation/cache tests raised the total to 158. These defensive
  validation additions occurred after the smoke; they do not change valid-frame
  runtime behavior. No additional live run was performed.
- neptune_perception build passed before smoke (1 package, 0.79 s overall), final
  build **1 package finished in 0.67 s** (package 0.59 s). Installed dual-model
  launch --show-args, Python compilation, runner Bash syntax and diff checks pass.

One isolated ROS-domain **86** test, official P3 camera-performance helper,
temporary fixed inspection pose (-18.5,0,3), yaw pi; full **320x240 / 145-degree
HFOV**, original Stonefish library, llvmpipe/eight workers/160x120 preview/low.
Warm measurement window **20.010126297 s**:

| Metric | Inspection Objects | Orientation A1 |
| --- | --- | --- |
| Warm processed frames / FPS | 134 / **6.696609** | 134 / **6.696609** |
| Latency mean / median / p95 | **52.255 / 58.088 / 68.045 ms** | **34.525 / 35.772 / 41.452 ms** |
| Latency maximum | 75.195 ms | 46.735 ms |
| Warm pending replacements | **0** | **0** |
| Whole-run pending replacements (includes cold loading) | 107 | 106 |
| Warm stale completions | **0** | **0** |
| Whole-run rejected stale completions | P4a has no rejection counter; fusion excludes invalid input | 2 |
| Maximum pending / in flight | **1 / 1** | **1 / 1** |
| Pending at warm start / end | **0 / 0** | **0 / 0** |

Camera: **134 frames / 6.696609 FPS**. Fused finalized frames and valid selected
targets: **134 / 6.696609 FPS**, above the preferred >=4 Hz. Source-stamp match
rate: **134/134 = 100%** of fused outputs and warm camera frames. Counts:
**CONSENSUS 134; INSPECTION_ONLY 0; ORIENTATION_A_ONLY 0; AMBIGUOUS 0; NO_PIPE 0;
STALE 0; MODEL_UNAVAILABLE 0** during the warm window. Status/watchdog duplicates
were excluded from output FPS/counts. Warm metrics count the full wall window.

Association IoU: n=134, **mean 0.608455; median 0.608318; p95 0.637082;
min 0.571611; max 0.642745**. Fresh selected observation age: mean **0.124983 s**,
p95 **0.151465 s**, maximum **0.153091 s**. No cache eviction, frame mismatch or
schema error appeared; final cache pending zero, three invalid/older inputs
rejected over whole run. Cold model loading causes replacements and stale
completions, as in P4a/P4b; it is not warm throughput or fresh output.

Each loaded model independently reported **238 executed nodes, all
CUDAExecutionProvider**, RTX 4080 Laptop GPU. ONNX lists both CUDA and CPU
providers, but actual profiled nodes were CUDA-only and automatic execution
fallback remains disabled. nvidia-smi: Windows driver **551.95**, advertised CUDA
**12.4**, total VRAM **12282 MiB**. Point samples while run active: utilization
**2–6%**, VRAM **924–1214 MiB** (startup sample 927 MiB); these are not averaged
utilization measurements. A later GPU sample found the service already stopped.

Valve **134** and flange **134** passed through with original Inspection Objects
provenance. Orientation validity remained false. Camera stop produced fused
**STALE / valid=false**. Zero command/thruster publishers. All owned observation
processes exited, inference stopped cleanly (**exit 0**); all three observer logs
were empty. No unbounded queue/backlog or freshness failure occurred in the warm
window.

Evidence: container `/tmp/neptune-p4c-smoke-21fmq_ws/{result.json,simulator.log,
inspection_objects.log,orientation_a.log,pipe_fusion.log,*.scn}`; host
`/tmp/neptune-p4c-live-result.json` and `/tmp/neptune-p4c-live-output.txt`.
/tmp is temporary; numeric results are retained here. Existing secure secret
mount/server configuration was reused unchanged; no key was read by the ROS
observers or introduced into source, arguments or documents.

### Running and limitations

Build in the ROS dev container from /workspace after sourcing /opt/ros/jazzy:

```bash
colcon --log-base /tmp/neptune-p4c-log build \
  --build-base /tmp/neptune-p4c-build --install-base /tmp/neptune-p4c-install \
  --packages-select neptune_perception
source /tmp/neptune-p4c-install/setup.bash
ros2 launch neptune_perception dual_models.launch.py
```

Start the existing inference Compose service and P3 performance camera separately,
in the same ROS domain. The dual launch starts only the two observers and fusion.
The explicitly bounded smoke entrypoint is `./scripts/run_p4c_smoke.sh`; it shares
the existing perception ownership lock, requires an idle inference service and
P3/P4c installed overlays, uses a 125 s warmup deadline, one 20 s window, bounded
process cleanup and inner 165 s / outer 175 s execution bounds. Stop the observers
and owned inference service to return to P3. Existing single-model launches remain.

Limitations: one short fixed pose establishes integration/performance, not dynamic
reliability, calibrated detection accuracy, long-duration scheduling or real-ocean
performance. Both models were trained/evaluated at full 640x480; equivalent accuracy
at full 320x240 is unproven. Low-confidence fragments/overlaps remain visible;
IoU 0.30 and 0.20/0.5 s timing limits are engineering defaults, not calibrated
operational thresholds. Greedy association is geometric only, with no tracking
or physical identity; ambiguous targets deliberately remain invalid. Unmatched
fallback incurs up to 0.20 s plus a 0.05 s watchdog tick. Source stamps remain
native publication/readback times, not verified capture instants. Status JSON is
an existing observation contract; future P5 consumers must parse provenance and
validity explicitly. Cold initialization and bounded request/shutdown limitations
from P4a/P4b remain. No physical pipe angle exists.

Changed files: src/neptune_perception/setup.py; new fusion.py, fusion_node.py,
config/pipe_fusion.yaml, launch/dual_models.launch.py, test/test_fusion.py and
test/test_fusion_node.py; scripts/perception_p4c_smoke.py and run_p4c_smoke.sh;
docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md. No unrelated package
changed. **P5 NOT STARTED. No commit or push occurred.**


## P5a lateral pipe centering — IMPLEMENTED / LIVE VALIDATION BLOCKED

P5a controller and standalone routing are implemented. **P5a is NOT COMPLETE:**
the one permitted positive-sway calibration pulse did not establish a reliable
image/control sign. Closed-loop validation was therefore not started. P5b is
next only after P5a acceptance and explicit assignment; **P5b NOT STARTED**.
Stage 2 remains frozen through S2.6. No commit or push occurred.

### Architecture, contract and engineering parameters

`neptune_controls.pipe_centering` is a ROS-independent proportional controller;
`pipe_centering_node` adapts the existing authoritative P4c
`/neptune/perception/fused_status` std_msgs/String JSON to
`/neptune/control/alignment_cmd_body` geometry_msgs/Twist. No typed selected-target
message exists. A strict consumer parser keeps this scope small without changing
P4c or introducing a new interface package. It checks top-level/target validity,
association, exact integer source stamp, finite geometry consistent with the
normalized error, dimensions, selected model/provenance, selected model readiness,
source age and upstream receipt/observation ages. CONSENSUS, INSPECTION_ONLY and
ORIENTATION_A_ONLY are eligible; AMBIGUOUS never commands motion. No confidence
threshold or perception/model behavior changed.

Equation outside deadband: `sway = clip(sway_sign * Kp * horizontal_error,
-max_sway, +max_sway)`. All other Twist fields are zero. Inside deadband and on
any invalid/unavailable/lost/stale input, output is zero. Parameters are read at
startup:

| Parameter | Current engineering default |
| --- | --- |
| Kp | 0.5 |
| max_sway | 0.25 (parameter constrained to <=1, so output also lies in [-1,1]) |
| horizontal deadband | 0.05, inclusive |
| freshness timeout | 0.5 s |
| confirmation count | 3 distinct fresh source stamps |
| control rate | 20 Hz, steady-clock timer |
| sway_sign | **0.0, deliberately disabled; no operational sign accepted** |

Source age and steady elapsed time both expire observations. Initial upstream
age plus steady elapsed time prevents watchdog duplicates or a frozen ROS clock
from rejuvenating old data. Fresh observations are reused between perception
updates. Repeated source stamps do not increase confirmation. Loss/staleness or
an out-of-deadband fresh observation resets consecutive confirmation. States:
WAITING_FOR_TARGET, ALIGNING, ALIGNED, TARGET_LOST, STALE, AMBIGUOUS,
INVALID_TARGET, PERCEPTION_UNAVAILABLE and SIGN_UNCALIBRATED. Status publishes on
`/neptune/control/alignment_status`. Shutdown sends a final zero while ROS is alive;
the unchanged vehicle adapter supplies its existing independent watchdog.
No integral, smoothing, tracking, angle inference, yaw control or hold axis exists.

The explicit `pipe_centering_standalone.launch.py` remaps only the dedicated
alignment output to `/neptune/cmd_body` and starts the existing seven-motor adapter.
It starts no autonomy, mission, estimator or other controller. Run only when normal
mission command publishers are stopped. This is explicit test routing, not P7
command ownership/arbitration. Default node output never publishes `/neptune/cmd_body`.
With current sign=0 configuration, the launch cannot move the vehicle.

Build after sourcing ROS and the existing vehicle overlay:

```bash
colcon --log-base /tmp/neptune-p5a-log build \
  --build-base /tmp/neptune-p5a-build --install-base /tmp/neptune-p5a-install \
  --packages-select neptune_controls
source /tmp/neptune-p5a-install/setup.bash
ros2 launch neptune_controls pipe_centering_standalone.launch.py
```

Camera/model launches remain independent and unchanged. The bounded experiment
runner is `bash scripts/run_p5a_smoke.sh sign|closed`, isolated ROS domain 87,
shared perception runtime lock, owned inference service, 185 s inner /195 s outer
bounds and bounded cleanup. It warms both P4c models at a fixed pose using the
accepted P3 320x240/145-degree llvmpipe/eight-worker/160x120-preview profile, then
restarts only its simulator at the same dynamic inspection pose. No native library,
body physics, allocation or repository scenario changes. Closed mode refuses an
uncalibrated sign before launching a simulator. The runner also rejects competing
body-command publishers. Do not rerun the sign pulse under the present one-test
authorization; an additional calibration requires a separately authorized task.

### Actual live sign experiment and failure

**Exactly one actual sway pulse; zero closed-loop trials.** Earlier startup
attempts failed before a pulse: overlay ordering hid the P3 helper, simulator
service discovery timed out, then the respawn service advertised but failed to
respond. Fixed-pose warmup followed by a simulator restart avoided that service.
An initial dynamic pose at y=0.7 m yielded error +0.040625, so the off-center guard
stopped it before any command. The actual pulse used starting pose
(-18.5, +1.5, 3.0) m, yaw pi; no pose or ground truth fed the controller.

| Sign-test measurement | Recorded value |
| --- | --- |
| Initial normalized horizontal error | +0.343750 |
| After-pulse error | +0.337500 |
| Change | -0.006250 (one pixel at width 320) |
| Initial selected center (u,v) | (215.0, 119.5) px |
| After-pulse selected center (u,v) | (214.0, 121.5) px |
| Positive pulse | +0.22 for nominal 3.0 s |
| Observed first positive command to zero interval | 3.019300 s |
| Maximum sway / other axes | 0.22 / all zero |
| Recorded body commands | 54, final command all zero |
| Unique fresh selected outputs during pulse window | 6, all CONSENSUS |
| Largest interval between recorded fresh outputs | 1.997887 s |
| Horizontal sign crossings | 0 |
| Sign response gate | FAIL: abs(delta)=0.00625 <=0.01 |

The direction weakly suggests sign +1 (positive sway decreased positive image
error), but the response is too small compared with observed half-pixel bbox
variation to accept as a reliable calibration. **No experimentally verified sign
is claimed and configuration remains zero.** Native motor thrust/displacement
was not observed; ROS command delivery alone cannot establish native actuation.
P2's graphical actuator callback limitation remains relevant but is not proven
to be the cause of this result. Dynamic fresh-output gaps also require follow-up;
the retained fixed-pose P4c ~6.7 Hz result does not establish dynamic throughput.

No closed-loop starting/final error, time to deadband, maximum closed-loop command,
overshoot, alignment state or three-frame live confirmation exists. Controller
live safety on loss was not exercised. Sign-run records retain unique sequences
rather than every watchdog repeat, so exact live stale/lost/ambiguous episode
counts cannot be reconstructed; do not claim zero stale events from these six
consensus outputs. The final runner now retains fusion state transitions for
future authorized use. Pure/ROS tests cover fail-closed behavior independently.
No continuing stale controller motion occurred because the controller was never
routed live. The manual calibration pulse ended with zero, and cleanup stopped
all owned simulator/model/adapter processes. Subsequent process audit found no
P5a processes in domain 87; inference service was stopped.

Ground truth was **not consumed at all**, including by the runner; lateral
truth displacement is unavailable. `/state/odometry` remains canonical and
`/sim/odometry` remains evaluation-only. Neither influences P5a commands.

Evidence: container `/tmp/neptune-p5a-sign-cej61wbr/result.json`, before.png,
fixed_simulator.log, dynamic_simulator.log and observer/adapter logs; host
`/tmp/neptune-p5a-sign-result.json`, `/tmp/neptune-p5a-sign-output.txt` and
`/tmp/neptune-p5a-before.png`. BEFORE frame shows the selected pipe right of
center. AFTER image was not saved because the response gate failed before that
save in the actual run; numeric after-source metadata is retained. The final
runner saves the after frame before applying its gate. No debug image is committed.
Temporary evidence can expire.

### Validation and remaining limits

- Smallest initial pure suite: 28 passed; final pure suite: **31 passed**.
- Final focused ROS controls plus unchanged perception suite: **195 passed in
  3.13 s** (37 controller/adapter tests, all 158 existing perception tests).
  Tests cover both configurable signs, positive/negative/zero/deadband outputs,
  saturation/extreme values, invalid/stale/ambiguous/unavailable/lost targets,
  multiple fresh-source confirmation, reset, frozen/backward clock, duplicate
  watchdog expiry, default topic isolation and zero unowned axes. The required
  assertion against an *experimentally verified* sign remains pending calibration.
- Controls package suite, from correct package working directory: **38 passed,
  1 failed, 1 skipped in 0.36 s**. Failure is existing flake8 import ordering in
  untouched depth_hold.py and waypoint_hold.py; new files have no lint errors.
  Pep257 passes; existing copyright test skips. An earlier invocation from the
  workspace root unintentionally linted the whole workspace and failed flake8/
  pep257; rerunning from the package isolated the relevant results. New-file
  lint errors were fixed without changing unrelated modules or weakening tests.
- neptune_controls build: **PASS, 1 package, 1.52 s** final. Initial missing
  neptune_vehicle overlay caused build failure; sourcing the existing P2 overlay
  resolved it, with the expected installed-workspace-dependency warning.
  Perception, vehicle and simulator sources are unchanged; no rebuild required.
- Installed standalone launch --show-args, Python compilation, runner bash syntax
  and diff checks pass. No additional live trial was used for these checks.

The controller is ready for a separately authorized calibration investigation,
but this is not an accepted closed-loop centering result. Engineering gains are
untuned; vehicle buoyancy can change depth during sway-only operation, and no
heading/depth hold or target identity tracking is provided. P4c geometric selection
can switch between fragments; dynamic model performance, actuation, sign and
convergence remain unresolved. **Physical pipe angle and yaw alignment remain
unimplemented. Full mission/state transitions and state estimation are unchanged.
P5b and P7 were not started. No commit or push occurred.**

Changed files: controls setup.py/package.xml; new pipe_centering.py,
pipe_centering_node.py, config/pipe_centering.yaml,
launch/pipe_centering_standalone.launch.py, test/test_pipe_centering.py,
test/test_pipe_centering_node.py; scripts/perception_p5a_smoke.py,
scripts/run_p5a_smoke.sh; docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md.


## P5a 80-degree validation and freshness investigation — BLOCKED

**P5a remains BLOCKED BY INTEGRATED PERCEPTION FRESHNESS, not COMPLETE.** The
performance camera change and fixed-pose P4 regression pass. The dynamic
calibration runtime cannot maintain its required fresh observation window.
One 80-degree pulse aborted safely; the subsequently authorized corrected attempt
failed before any nonzero command. The later no-motion diagnostic below passed at
a fixed pose, but did not establish the exact native cause of the dynamic camera
stall. No further pulse or closed-loop trial ran. P5b NOT STARTED. Stage 2 remains
frozen through S2.6. No commit or push occurred. This record supersedes the earlier
P5a record's current 145-degree profile description; prior evidence remains history.

### Performance optics and regression

Only generated performance/alignment XML changes HFOV **145 -> 80 degrees**,
still **320x240**, nominal **10 Hz**, llvmpipe/eight workers, low graphics,
160x120 preview and 100 Hz physics. Original/demo camera XML remains
640x480/145 degrees. Camera mount, image/info topics and native CameraInfo
publication are unchanged. No intrinsic is hard-coded. The narrower HFOV is
close to the donor training optics and improves servo pixel sensitivity about
3.78 times at the same resolution, reducing optical-domain mismatch without
increasing pixel count. Rendering cost is not guaranteed identical, and equivalent
model accuracy at 320x240 remains unproven.

Actual Stonefish CameraInfo: fx=fy=**190.6805748150736 px**, cx=160, cy=120;
K=[fx,0,160; 0,fy,120; 0,0,1]; P=[fx,0,160,0; 0,fy,120,0; 0,0,1,0];
D=[0,0,0,0,0], plumb_bob. Frame remains
GIRONA500/inspection_camera_optical_frame.

The first short fixed-pose check at (-16,0.4,3), yaw pi detected both models and
exact-source selections, but selected a near-centered target (median error
+0.046875, x=167.5) and included ambiguous outputs. Only the test pose was adjusted
to (-16,+0.8,3), yaw pi. Its **3.1073 s** warm regression produced **13 CONSENSUS
selected outputs**, median error **+0.24375**, x=**199 px**, valve/flange **13/13**,
100% exact camera/model/fusion source matching and pending zero. No movement ran.
Later fixed-pose windows also passed, with detector geometry variation producing
median error +0.178125/x=188.5 in the final gated-attempt warmup; target identity
tracking is not provided by P4c.

### Gated calibration attempts

The first 80-degree run gathered five individually fresh before samples with
medians **+0.24375 / 199 px**, then began +0.25 sway. It explicitly stopped when
fused status became **STALE at 1.02785 s**, before completing four seconds. Last
recorded positive command was at 1.00016 s; the stop was published but was not
captured by that attempt's local recorder before cleanup. Three unique fresh
outputs were CONSENSUS; last fresh error +0.240625. Evaluation-only displacement
was **+0.0038857643 m** along the initial body lateral axis (world displacement
approximately [0.00074484,-0.00388577,-0.10529746] m, 34 truth samples). No complete
after median or accepted sign exists. This does not demonstrate actuator failure.

The before-sample collector had retained samples across stale watchdog repeats
and gaps of approximately 0.85 and 0.54 s. This was a **harness qualification bug**,
not a controller or fusion freshness bug. The corrected collector resets on every
invalid watchdog episode and any >0.5 s receipt gap, excludes samples preceding
that invalid episode, and requires five consecutive fresh observations. Publisher
discovery now occurs before collecting the window; the pulse also checks target
validity/source age every iteration, with unchanged 0.5 s limit and magnitude/duration.
Zero publication is drained through the local observer before teardown.

The user explicitly authorized one corrected attempt and required STOP if it
failed. That attempt reached dynamic warmup but **could not collect the five-frame
window within 15 s**, and sent **zero nonzero commands**. At failure: fused STALE,
valid=false, source age **15.30529 s**, receipt age **15.20776 s**, sequence 21;
both model states **CAMERA_STALE**. No before/after calibration medians or pulse
displacement exist for this corrected attempt. All owned processes were stopped;
dynamic simulator required forced shutdown. No third pulse ran.

The only controller change remains the original P5a implementation; its algorithm
was not redesigned in this follow-up. Configuration remains sign **0.0** (motion
disabled), Kp **0.5**, max sway **0.25**, deadband **0.05**, freshness **0.5 s**,
confirmation **3 distinct fresh sources**, rate **20 Hz**. Equation remains
clip(sign*0.5*horizontal_error,-0.25,+0.25), zero inside deadband or on loss.
No experimentally accepted sign or live ALIGNED result is claimed.

### Standalone versus integrated runtime

| Aspect | Successful historical P4c smoke | Failed P5a sign runtime |
| --- | --- | --- |
| Simulator | One fixed-body instance, (-18.5,0,3), no restart | Fixed model warmup, then stop/restart with free dynamic body at (-16,0.8,3) |
| Camera | 320x240/145 degrees | 320x240/80 degrees; auxiliary vision still excluded |
| Render/runtime | llvmpipe, eight workers, 160x120/low, 100 Hz, original library | Same settings/library; free-body physics and changing view after restart |
| Observer processes | Inspection Objects, A1, pipe_fusion, smoke observer | Same, plus seven-motor adapter; controller absent during both failed sign attempts |
| Topics added to telemetry | None | CameraInfo, annotated image and evaluation-only odometry subscriptions, body-command monitoring |
| Topics added for control | None | /neptune/cmd_body and /sim/thruster_setpoints; later diagnostic also alignment_status |
| Executor model | Separate single-threaded ROS process per observer; one HTTP worker each | Same; adapter separate executor; smoke uses bounded spin_once polling |
| Logging | Redirected startup logs, result serialization after measurement | Same; no image writes or synchronous HTTP in measured callback loop |
| Telemetry QoS | P4c camera uses sensor-data BEST_EFFORT | P5a diagnostic camera/info/annotation telemetry uses RELIABLE depth 10; detectors remain BEST_EFFORT depth 1 |

The controller **was not started in the failed sign runs**, ruling out its timer
as their cause. Each detector subscription only replaces a latest-frame slot;
conversion/PNG/HTTP/response parsing execute in its own one-worker thread pool.
Single-threaded detector timers consume completed futures without waiting on HTTP.
Fusion uses a separate process, bounded exact-source cache, no HTTP or blocking
wait. Controller and adapter each have separate single-threaded executors. No
Python executor or callback group is shared between them and perception.

Native Stonefish uses rclcpp::spin(single-threaded); its 16.667 ms timer calls the
entire graphical LoopInternal. Its physics thread and llvmpipe workers are separate.
Long native render/physics work can delay native callbacks. Native physics permits
large unbounded elapsed-time catch-up. These are **candidates**, not a demonstrated
low-level root cause; no native thread trace from the failed dynamic process exists.
The actual loaded library retains SHA-256
5a566fdf108cb5246105aab5faeb29e2beeebe1bac653d77a841788beaa677f4,
matching the historical original library. No rejected P3c patch was enabled.

The **immediate fault location is established**: camera delivery stops upstream
of both detector workers, which report CAMERA_STALE; fusion correctly expires the
last source. Detection loss alone would not produce CAMERA_STALE. The exact native
reason (dynamic physics/rendering versus restart-related runtime behavior) is
**not proven**. The previous sign runner did not retain raw camera receipt timing,
per-model status timelines or native thread/resource traces, so its raw-camera FPS
and inference latency cannot be retrospectively reconstructed from selected outputs.
Do not describe selected-output gaps as measured raw camera FPS.

### One 12-second integrated no-motion diagnostic

The new `diagnostic` mode in scripts/run_p5a_smoke.sh launches both models,
fusion, the actual 20 Hz controller (explicit sign=0), seven-motor adapter and all
P5a telemetry in isolated domain 87. The vehicle is fixed to guarantee **no vehicle
motion**, not merely zero commands. There is no fixed-to-dynamic simulator restart.
After cold initialization/stable perception, it measures **12.0003194 s** and
writes timing/resource data only after that window. This is one short diagnostic,
not a repeated benchmark or proof of dynamic operation.

| Metric | Actual no-motion result |
| --- | --- |
| Camera | 56 frames / **4.666542 Hz** |
| Maximum camera receipt gap | **0.246275 s** |
| Inspection Objects | **4.583211 Hz**, latency mean **48.360 ms**, max **70.011 ms** |
| A1 | **4.666542 Hz**, latency mean **84.498 ms**, max **129.928 ms** |
| Fused fresh selected outputs | 56 / **4.666542 Hz**, all CONSENSUS |
| Maximum valid-output gap, including window edges | **0.300037 s** |
| Maximum new-output target age | **0.197152 s** |
| Maximum target age over valid watchdog repeats | **0.375537 s** |
| Controller callback rate | **19.999468 Hz** |
| Warm latest replacements / stale completions | **0 / 0**, both models |
| Max pending / in-flight | **0 / 1**, both models |
| Exact matched selected sources | **56/56** |
| Model-arrival skew mean / max | **0.037015 / 0.095857 s**, below 0.20 s association window |
| Cache pending / evictions / mismatches / schema errors | **0 / 0 / 0 / 0** |
| Body commands | All six fields zero throughout |

One result straddling the measurement boundary accounts for Inspection Objects'
counter-based count differing by one from camera/A1/fusion; no duplicate source
was counted. Timings include the whole warm window, not startup. All no-motion
stability criteria pass; there was no post-fix repeat because no runtime fix was
proven necessary at this fixed pose.

Per-process CPU means, percent of one CPU (can exceed 100): simulator **395.66%**,
Inspection **4.42%**, A1 **4.17%**, fusion **6.25%**, adapter **2.50%**, controller
**3.92%**. RSS KiB: simulator 397884; Inspection 186484; A1 186940; fusion 171600;
adapter 70652; controller 71140 (RSS includes shared mappings). No configured
container CPU quota or memory limit. GPU point samples during diagnostic/cleanup
were **8–38%**, approximately **1393–1422 MiB** while models remained loaded;
these are point samples, not a utilization integral. No resource saturation was
established. The native renderer dominates observed dev-process CPU cost, but
those numbers do not establish the failed dynamic run's CPU behavior.

Logs from failed calibration were approximately 5 KiB per simulator, zero bytes
for each perception observer and 129 bytes for adapter startup; no log flood exists.
The diagnostic likewise performs no disk writes during its measurement window.
Additional zero-control nodes therefore do **not** reproduce multi-second stale
output at a fixed pose. The remaining important difference is the unvalidated free
body/restart path, not a demonstrated model-speed or shared-executor defect.

No controller/perception/runtime safety fix was applied on speculation. Fixes are
limited to correct harness fresh-window qualification and added measurement mode.
**A further motion calibration is not justified by this fixed-pose result alone**:
the dynamic camera stall remains unresolved and the prior corrected attempt failed
its required window. No further pulse or closed-loop motion was run. P5a remains
blocked; future work must isolate the dynamic/restart path without weakening safety.

### Validation, evidence and scope

- Profile preservation test: PASS; generated 80-degree XML, original 145-degree
  demo untouched, same scalar/actuator/physics/spawn contract, auxiliary vision excluded.
- Combined relevant simulation/evaluation/control/perception tests: **237 passed
  in 2.89 s**. Earlier focused subset: 198 passed after correcting an invalid
  quaternion in the new evaluation-test fixture. New-file lint: PASS. Historical
  controls package lint failures in untouched controllers remain recorded above.
- neptune_sim, neptune_controls, neptune_evaluation build: **3 packages passed,
  1.55 s** final, expected installed vehicle/Stonefish dependency warnings.
- Final harness Python syntax, bash syntax and diff checks pass. Controller code,
  model thresholds, freshness settings, mission, estimation and allocation unchanged.
- Evidence: container `/tmp/neptune-p5a-80-regression-fn4hc0jk/result.json`,
  `/tmp/neptune-p5a-80-sign-zlci34pb/result.json`,
  `/tmp/neptune-p5a-80-sign-dkg3xni5/result.json`,
  `/tmp/neptune-p5a-80-diagnostic-07dgwbdl/result.json` (includes full model start/end/
  receipt/fusion/camera timelines and CPU/RSS data). Host temporary output files
  `/tmp/neptune-p5a-80-{regression2,sign,sign2}-output.txt`,
  `/tmp/neptune-p5a-diagnostic-output.txt`, `/tmp/neptune-p5a-diagnostic-gpu.txt`,
  and `/tmp/neptune-p5a-80-before.png`. No valid AFTER frame exists for aborted or
  pre-window-failed attempts. No debug images committed.
- Diagnostic cleanup and process audit passed; no P5a process remained and owned
  inference stopped. GPU sampler ended when its container stopped.

Changes in this follow-up: neptune_sim/perception_profile.py and new profile test;
new neptune_evaluation/lateral_motion.py and its test (truth consumed solely inside
that evaluation module, reported only after experiment decisions); both P5a smoke
scripts; docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md. Original P5a
controls additions remain uncommitted from the preceding implementation. The
controller never receives truth; /state/odometry stays canonical. **Pipe-angle and
yaw alignment remain unimplemented. P5b NOT STARTED. No commit/push occurred.**


## P5a dynamic-versus-restart isolation — BLOCKED (2026-10-13)

**P5a remains BLOCKED.** Exactly the two requested zero-command experiments ran,
within the 15-minute budget; no sway pulse or additional simulation trial ran.
A reproduced the severe camera-delivery gap with **direct dynamic startup and no
restart**. B completed a **fixed-to-fixed restart without STALE**, but its 3.50 Hz
camera /3.67 Hz fusion missed the >=4 Hz acceptance gate. Neither is an accepted
P5a calibration runtime. The severe failure is associated with the free/dynamic
path, and does not require restart. A specific native rendering/physics bottleneck
is still unproven; no speculative native/model/controller fix was applied.
P5b NOT STARTED; Stage 2 frozen through S2.6; no commit or push occurred.

### Experiments and actual measurements

Both used the unchanged P5a 320x240/80-degree performance helper, original native
library, llvmpipe/eight workers, 160x120/low preview, 100 Hz physics, intended
(-16,+0.8,3) pose/yaw pi, domain 87, both detectors, fusion, seven-motor adapter,
and controller explicitly sign=0. All six body-command fields remained zero,
including startup. Truth drift was recorded only inside neptune_evaluation.
A started one fresh free-body simulator directly; B kept its body fixed across
the same stop/relaunch helper used in the calibration runner. No respawn or sensor
enable service was called in either experiment.

| Clean measurement | A: dynamic, no restart | B: fixed after restart |
| --- | --- | --- |
| Window | 12.000220 s | 12.000740 s |
| Camera FPS | **0.333327**, 4 frames | **3.499784**, 42 frames |
| Maximum camera receipt gap, including window edges | **9.471444 s** | **0.401551 s** |
| Inspection Objects FPS | **0.249995** | **3.583112** |
| A1 FPS | **0.249995** | **3.583112** |
| Fresh selected fusion FPS | **0.249995** | **3.666440** |
| Maximum valid fused-output gap, including window edges | **9.396370 s** | **0.398585 s** |
| Maximum age over valid selected statuses | **0.480703 s** | **0.450133 s** |
| STALE entries during measurement | **1**, plus initially MODEL_UNAVAILABLE | **0**, CONSENSUS throughout |
| Zero commands | **YES** | **YES** |
| Full stability acceptance | **FAIL** | **FAIL: rate below 4 Hz**, despite fresh cadence |

Counter-based model FPS and unique fused-source FPS can differ by a window-boundary
result. No threshold was relaxed to call B a pass. B did not reproduce the severe
CAMERA_STALE gap, and shows that restart alone need not stop the camera. Since both
miss full throughput acceptance, these two runs do not establish a fully exclusive
binary root cause or reproduce the prior fixed diagnostic's 4.667 Hz performance.
The strongest causal evidence is that restart is **not necessary** for the severe
failure, whereas free-body operation plus drift changes the native rendering path.

A's zero-command startup-to-end drift: world displacement
**[+0.02752617,+0.00008646,-2.54762602] m**, initial
[-15.99999549,0.79999999,2.99994868], final
[-15.97246931,0.80008646,0.45232266] m. Body-lateral projection
-0.00008646 m; 1158 evaluation samples. This includes model warmup plus measurement,
not just the 12 s window. Buoyancy therefore moved the free vehicle substantially
without a motion command. B drift was exactly zero. Do not state that A's physical
vehicle remained stationary merely because its commands were zero.

### Camera and nonvisual lifecycle

All times below are UTC for process start; topic/image delays are steady-clock
seconds from the corresponding Popen call, so wall-clock adjustments cannot distort
the intervals. Process PID and /proc birth ticks and DDS image-publisher GIDs are
retained in result.json.

| Stage | Process start UTC | PID / birth ticks | New image-topic publisher delay | First image delay |
| --- | --- | --- | --- | --- |
| A direct dynamic | 18:13:38.405046 | 17734 / 2233745 | 1.658677 s | 2.978920 s |
| B initial fixed | 18:15:01.535448 | 17916 / 2242237 | 1.239133 s | 2.445348 s |
| B restarted fixed | 18:16:39.899912 | 18035 / 2252310 | 2.036272 s | 2.284992 s |

First five image receipt intervals:

- A: [0.354412,0.450029,0.412937,0.270288,0.311944] s.
- B initial: [0.331428,0.247366,0.268013,0.265942,0.261500] s.
- B restarted: [0.510342,0.270462,0.276912,0.270483,0.273117] s.
  The initial >0.5 s restart interval belongs to startup, not its clean window.

Image and CameraInfo moved together: A **4/4** during its window; B **42/42**.
CameraInfo did not keep arriving through the Image blackout. The native bridge
publishes the pair in one ColorCameraImageReady callback, consistent with a vision
render/readback/delivery-path gap rather than just loss of one ROS topic.

| Nonvisual stream | A FPS / max receipt gap | B FPS / max receipt gap |
| --- | --- | --- |
| IMU | 18.916320 / 0.698426 s | 19.915438 / 0.052734 s |
| DVL | 18.916320 / 0.698461 s | 19.915438 / 0.052492 s |
| Pressure | 4.749913 / 0.840739 s | 4.999692 / 0.205276 s |
| Evaluation odometry | 28.332815 / 0.688636 s | 29.998150 / 0.041711 s |

Nonvisual streams continued through A's much longer vision gap, with their own
smaller timing jitter. This is not a complete simulator/ROS bridge outage. `/clock`
had **zero messages in both**; this original native build provides wall-clock
stamps and does not publish /clock. Its absence is not evidence of a clock-topic
stall. No simulated-time or timestamp override was introduced.

### Process, service and health-gate findings

- Successful prior fixed diagnostic: one fixed simulator, model warmup, no restart.
- A: one dynamic simulator, then the same observer/zero-control processes; model
  runtime warmup and advancing source checks; no fixed warmup instance.
- B: initial fixed simulator and stable selected outputs; stop only the owned old
  simulator; retain observers/adapter/controller; relaunch fixed simulator with
  identical XML/settings. No service discovery, respawn or enable calls.
- Prior failed calibration: fixed warmup, stop owned simulator, edit temporary
  body fixed=false, start adapter, relaunch dynamic simulator, qualify observations.
  Unlike these experiments, it did not start the controller before calibration.
- Performance XML excludes auxiliary cameras/FLS and removes retained scalar
  sensor-enable service declarations. Inspection already has no enable service.
  Sensors start enabled for **each new process**, not through presumed persistence.
- B old PID exited cleanly (**0**) before Popen of the new PID. Image graph was
  already **empty immediately after stop**. Old GID
  010f7d17fc453e2b0000000000001c03 changed to
  010f7d1773461ea80000000000001c03. No old publisher remained to satisfy a topic
  health gate. The diagnostic requires a new GID, a live owned process, and image
  stamps newer than that process's start before considering its frames.
- B checked current-source detector completions after restart, rather than
  accepting the observers' old runtime/READY metadata. Source stamps advanced.
  This is useful health instrumentation, not proof of a restart defect.

The initial B warmup flag in the recorded artifact is false despite warm models
and later stable fixed selection. The diagnostic's first implementation demanded
that **every historical** source timestamp increase. Four ~0.22–0.35 s backward
stamp steps during its initial ~100 s startup/wait made that check permanently
false. The late fixed-source check succeeded, then B restarted as requested.
The helper now requires the **latest six consecutive advancing stamps**, permitting
health recovery after an old clock step. This correction was unit-tested after the
two runs; neither experiment was repeated. It does not explain A's independently
measured 9.47 s raw receipt gap (A recorded no source-stamp regression), or change
B's measured throughput failure. No freshness threshold or STALE handling changed.

### Result, scope and validation

No operational smoke-runner fix was applied: direct dynamic startup **did not
work**, so replacing the existing restart path would not fix the demonstrated
failure. No post-fix dynamic validation ran because no applicable runtime fix was
established; user policy requires stopping on dynamic-path failure. A final sign
calibration is **not justified**. P5a remains blocked; no pulse in this task.

This turn changed only: new scripts/perception_p5a_lifecycle.py,
scripts/run_p5a_lifecycle.sh and scripts/test_p5a_lifecycle.py;
neptune_evaluation/lateral_motion.py and its test (armed startup origin and receipt
telemetry); docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md. The existing
P5a smoke scripts, model/controller algorithms, 0.5 s freshness, optics, thruster
allocation, mission and state estimation are unchanged in this turn.

Focused evaluation tests initially **3 passed in 0.20 s**, then lifecycle/evaluation
checks **5 passed in 0.12 s**; initial combined collection failed because the test
PYTHONPATH omitted neptune_perception (the shared cleanup helper imports it).
Adding that existing package path fixed collection. A floating-point interval
assertion uses numeric tolerance. New evaluation-file lint passes. Relevant
neptune_evaluation build: **1 package passed, 1.29 s**. Python syntax, runner Bash
syntax and diff checks pass. No simulator/model/controller package rebuild needed.

Evidence: container `/tmp/neptune-p5a-lifecycle-A-_nt5uutp/result.json` and
`/tmp/neptune-p5a-lifecycle-B-e4tcsr1l/result.json`, with exact source/receipt times,
process identities, GUIDs and logs. Host `/tmp/neptune-p5a-lifecycle-{A,B}-result.json`
and corresponding `-output.txt`. All owned processes exited, final process audit
found none in domain 87, and inference stopped. These files are temporary.
**Commands remained zero; A passively drifted. Freshness remains 0.5 s. Ground truth
is evaluation-only. P5b NOT STARTED. No commit or push occurred.**


## P5a startup-settling validation — physical settling confirmed, P5a BLOCKED

**One fresh dynamic run only, no restart or repeat. P5a remains BLOCKED.** Girona
naturally passed the physical depth-rate/yaw-rate gate at **37.676355 s**, but no
simultaneous physical/perception window passed by the **40 s** deadline. Commands
remained all zero; sign calibration and closed-loop alignment were not started.
This narrows the earlier A/B interpretation: startup strongly worsens camera gaps,
but this run still did not produce an acceptable settled pipe-centering input.
It does not prove a generic native dynamic-physics defect. No Stonefish patch,
model/controller change, stabilizing controller, P5b work, commit or push.
Stage 2 remains frozen through S2.6.

### Single-run method and gate

Same real seven-motor free Girona, temporary initial pose (-16,+0.8,3), yaw pi,
P3 performance profile **320x240/80 degrees**, software/eight workers/160x120/low,
100 Hz physics, both independent models, P4c fusion and seven-motor adapter.
A single zero-only publisher owned /neptune/cmd_body during diagnosis. No autonomy,
heading/depth controller, respawn/enable call or simulator restart. Alignment was
conditionally permitted only after settling and successful sign calibration; the
code never reached either motion phase in this actual run.

The settling timer starts immediately before the one simulator Popen. The first
20 s are recorded as startup, not evaluated against P5a acceptance. The earliest
eligible five-second window is [20,25] s. Check subsequent rolling five-second
windows until 40 s, using **onboard sensor data**, never evaluation odometry:

- Depth = pressure/(997*9.81)+0.40, the existing validated pressure_depth formula.
- Depth rate = successive pressure-derived depths divided by original source-stamp
  difference; nonpositive or >=1 s source intervals produce an invalid rate and
  cannot qualify a window. No interpolation hides a bad time interval.
- Yaw/angular velocity come from the existing identity-mounted IMU. Body gyro-Z is
  the near-level yaw-rate equivalent used for this diagnostic; other rate axes and
  yaw are also recorded. IMU quaternion yaw uses the existing ROS convention.
- **Every** pressure-rate sample in the same five-second window must satisfy
  abs(rate)<**0.05 m/s**; every gyro-Z sample abs(rate)<**0.03 rad/s**. Both physical
  streams must cover the window with receipt gaps <0.5 s.
- The same window also needs camera and distinct fresh selected fusion output
  >=**4 Hz**, gaps <**0.5 s**, selected age <**0.5 s**, valid target throughout,
  >=5 distinct consecutive fresh targets, no CAMERA_STALE, and both models warmed.

Pressure's constant mounting offset is the existing simple calibration, not a new
attitude-dependent transform. Depth rate is the closest validated sensor-derived
vertical-rate signal; no truth velocity or depth enters motion qualification.
Truth depth/yaw/linear/angular velocities and source/receipt timestamps are
continuously recorded inside neptune_evaluation and read only for the final report.

### Actual startup and settled results

The full settling attempt ended at **40.001455 s** (normal loop scheduling rounding).
The physical five-second gate first passed at **37.676355 s**, verifying the
window **32.676355–37.676355 s**. The reported transition boundary is the start of
that verified window, not an assertion of an instantaneous physical equilibrium.
Onboard depth initially **3.007965 m**, final **0.447589 m**; the first physically
settled window ranged **0.439735–0.487929 m**. Evaluation-only truth was initially
2.999949 m and finally 0.442264 m, confirming passive buoyant rise. World displacement
approximately [0.02676104,0.00008876,-2.55768453] m; no commanded motion.

| Diagnostic interval | Startup/unsettled | From first verified physical-window start to deadline |
| --- | --- | --- |
| Time bounds | 0–32.676355 s | 32.676355–40.001455 s |
| Duration | **32.676355 s** | **7.325099 s** |
| Camera FPS | **2.846095** | **3.549440** |
| Maximum camera receipt gap, including edges | **6.580135 s** | **0.707956 s** |
| Distinct fresh selected fusion FPS | **0.612063** | **0** |
| Maximum valid selected-output gap, including edges | **18.280804 s** | **7.325099 s** (none selected) |
| Onboard depth range | **0.402974–3.007965 m** | **0.439735–0.487929 m** |
| Depth-rate range | **-0.134428–+0.090897 m/s** | **-0.037598–+0.046249 m/s** |
| IMU yaw-rate range | **-3.10977e-5–+1.87201e-5 rad/s** | **-1.02873e-5–+1.04009e-5 rad/s** |
| Fused STALE entries | **3** | **4** |
| Maximum valid selected-target age | **0.355678 s** | **unavailable: no valid selected target** |

The **exact first five-second physical settling window** had camera **3.8 Hz**,
max camera gap **0.439493 s**, selected fusion **0 Hz**, max selected gap **5 s**;
fusion alternated AMBIGUOUS and STALE (three/two entries). Thus even at physical
qualification, the camera rate missed 4 Hz and association supplied no valid target.

The final five seconds [35.001455,40.001455] remained physically qualified:
depth rate -0.035954–+0.029697 m/s, gyro-Z -1.02873e-5–+7.20943e-6 rad/s. Camera
was **3.4 Hz**, max gap **0.707956 s**, selected fusion **0 Hz**, with three AMBIGUOUS
and three STALE entries. No later common gate passed. The entire run's IMU X/Y rate
ranges were approximately [-0.000497,+0.000423] and [-0.037416,+0.042480] rad/s;
these other axes were recorded, not used to add an unrequested attitude hold.
Initial IMU yaw was approximately -pi (equivalent to yaw pi).

Physical settling therefore **does occur**, and removes most of the large startup
camera gap. It does **not fully explain or resolve** the P5a failure: after settling,
camera throughput remains below 4 Hz, a >0.5 s camera gap remains, and selected-target
association is ambiguous/stale. The vehicle has risen far from its original
inspection depth; changing view and target geometry remain material limitations,
not proof that the model itself is slow or that a native patch is needed.
The exact blocker is **no simultaneous five-second physical and fresh-valid-target
window before 40 s**. Physical instability is not the blocker at the end of this run.

### Scope, validation and evidence

Actual CameraInfo remains native: 320x240, fx=fy=190.6805748150736, cx=160, cy=120.
Continuous records include 184 pressure samples, 739 IMU and 739 DVL publications,
119 paired Image/CameraInfo publications, fused and per-model statuses, all commands,
and 1109 odometry samples kept in evaluation. Camera source stamps and receipts,
IMU yaw/all angular axes, DVL raw velocity and pressure-rate histories are retained.
No selected-target age after settling is fabricated from an invalid retained bbox.

Changes this turn: new scripts/perception_p5a_settling.py,
scripts/run_p5a_settling.sh, scripts/test_p5a_settling.py; added continuous snapshot
history to neptune_evaluation/lateral_motion.py and a focused test;
docs/PROJECT_HANDOFF.md and docs/PERCEPTION_INTEGRATION.md. All previous diagnostic
scripts, profile settings, estimator/controller/model algorithms and allocation
remain unchanged. No depth/heading stabilization was added.

- Initial focused settling/evaluation tests: **8 passed in 0.22 s**; final snapshot
  coverage: **9 passed in 0.17 s**. Covers continuous physical windows, strict rate
  boundaries, missing derivatives, sensor gaps, invalid watchdog repeats, camera
  gaps, age==0.5 rejection, CAMERA_STALE and no-target rejection.
- Relevant neptune_evaluation build: **1 package passed, 1.41 s**. New evaluation
  file lint passed; harness Python/Bash syntax and diff checks passed.
- Live evidence: container `/tmp/neptune-p5a-settling-fv9g5ezf/result.json`, simulator
  and observation logs. Host `/tmp/neptune-p5a-settling-result.json` and
  `/tmp/neptune-p5a-settling-output.txt`. Raw state and timing history is temporary.
- Owned processes exited, process list clear and owned inference stopped. No repeat.

**No sign pulse, experimental sign or closed-loop result exists for this run.**
Configured sign remains 0 (disabled); existing Kp0.5/max0.25/deadband0.05/freshness0.5/
three-source confirmation/20 Hz parameters remain unchanged. **Freshness stayed
0.5 s. Pipe-angle/yaw alignment unimplemented. P5b NOT STARTED. No commit/push.**


## Demo V0 — full movement validated; implementation and smoke history (2026-10-14)

**Graphics/runtime is frozen. No more graphics experimentation is required.**
G1/G2/G3 supersede the historical D3D12-unusable conclusions above. No driver,
Mesa, WSL, native Stonefish, camera-readback or scheduling patch was applied.

| Valid graphics trial | Camera frames / window | Hz | Max receipt / source gap |
| --- | --- | --- | --- |
| G1 reduced fixed fixture, 160x120 LOW preview | 199 / 20 s | 9.950 | 0.191531 / 0.191456 s |
| G2 dynamic integrated scene, 1280x720 LOW | 301 / 30 s | 10.033 | 0.170690 / 0.172902 s |
| G3 same dynamic scene plus both CUDA models | 302 / 30 s | 10.067 | 0.172283 / 0.177261 s |

G2/G3 camera: 320x240, 80-degree HFOV, configured 10 Hz. G1 used the retained
145-degree reduced fixture. Image/CameraInfo pairs all matched. G3 independently
recorded 238 CUDAExecutionProvider node events per model, 302 warm completions
per model, zero warm stale completions/replacements, 31.8% average GPU utilization
(22–54%), ~1791 MiB VRAM of 12282 MiB. G2 operator visual classification was smooth;
G3 camera/model/resource coexistence passed. This is bounded runtime evidence, not
model accuracy, long-duration reliability or a reason to change graphics settings.

### Demo architecture and ownership

`neptune_bringup/perception_demo.launch.py` owns one Stonefish process, the existing
seven-motor adapter, existing `pressure_depth` and `dead_reckoning_state`, existing
`mission_executive`, new `demo_readiness`, read-only `demo_gui`, and existing camera
static-TF edges. It generates the same reduced integrated scene with the existing
`neptune_sim.perception_profile.write_performance_scenario` helper; no prior /tmp
benchmark fixture is required. Original Girona body/physics, seven actuators,
lamps, pipe/flange/valve and scalar sensors are retained. Auxiliary RGB/FLS are
removed only from generated XML. Original scenes and P5a profile helper are unchanged.

Frozen DEMO defaults: accelerated NVIDIA D3D12 / OpenGL 4.6, RTX 4080 Laptop GPU,
1280x720 LOW, 100 Hz physics, inspection RGB 320x240/80 degrees/10 Hz. The launch
prepends `/usr/lib/wsl/lib` while retaining sourced ROS/Stonefish library paths,
unsets software/GL overrides and checks the hardware renderer before movement.
It does not maximize Stonefish. Windows can retain presentation-window state;
keep Stonefish restored/unmaximized at 1280x720. The native scene render target
remains the requested 1280x720. The prior larger client size corresponds to actual
WM maximization (MAXIMIZED_HORZ/VERT were observed during G3 cold loading).

Explicit legacy profiles remain available without changes:
`neptune_sim/perception_performance.launch.py` is the small-window software profile;
`perception_camera.launch.py` is the ordinary 640x480/145-degree camera profile.
They are not the default Demo V0 entrypoint. No 1600x900 trial ran.

Movement authority is exclusively `mission_executive` -> `/neptune/cmd_body` ->
`stonefish_vehicle_adapter` -> `/sim/thruster_setpoints` (seven values).
The executive already contains the proven depth PID, heading control and waypoint
guidance; standalone `depth_hold`/`waypoint_hold` are deliberately not co-launched.
No new motion controller, command mux or GUI command publisher exists.
`/state/odometry` remains the sole downstream state interface. No demo component
consumes `/sim/odometry`; it remains evaluation-only.

Demo readiness is opt-in in the existing executive (`demo_mode=false` preserves
ordinary Stage 1 startup). Demo starts in INITIALIZING with zero commands, waits
at least 15 s from initial sensor arrival plus a three-second stable window:
pressure-derived depth rate <0.05 m/s and IMU angular-Z <0.03 rad/s, with fresh,
finite advancing pressure/IMU/DVL/onboard-state streams (<0.5 s gaps/ages).
Readiness also requires exclusive executive/adapter/estimator publisher ownership.
After initial qualification, motion is allowed and only validity/freshness are
required; a moving robot is not incorrectly required to remain stationary.
Readiness/state loss pauses the executive at zero without resetting HOME or mission
phase. Duplicate publishers abort the launch. Startup has a 90 s failure deadline.
Neural health and camera detections never gate or command movement.

The executive publishes status on transitions and at 5 Hz. COMPLETE distinguishes
normal completion from the existing 420 s mission TIMEOUT; elapsed time freezes
on completion. Guidance, controller gains, route, standoff and mission transitions
are unchanged. Default automatic startup needs no button or extra terminal.
Closing the GUI/simulator or any required process exits the whole owned launch.

### GUI and teammate audit

Audited all 487 lines of `lumyn/Perception:src/neptune_gui/auv_gui.py`, its
`controls.py` and GUI runner at donor SHA
`608a3b985b8c5dbfc56f5398b8679c8038861bbe`. Reused the charcoal/cyan styling idea,
large-camera/sidebar hierarchy and background-I/O/UI separation. Donor TCP,
manual keyboard controls, native thrusters, mission buttons, truth comparisons
and perception-dependent movement were not copied.

The dev container already has OpenCV Qt5 support; Tk/PyQt bindings/Pillow are not
installed there. V0 uses the existing OpenCV native display, avoiding new packages.
A separate ROS thread only stores the latest Image and lightweight telemetry.
Decode/resize/display happen on the GUI thread, in its own process. BEST_EFFORT
KEEP_LAST depth-one camera input cannot build a backlog or backpressure Stonefish.

Application topics consumed by GUI:

- `/neptune/camera/inspection/image_color` — Image, latest native RGB frame.
- `/neptune/camera/inspection/camera_info` — CameraInfo.
- `/state/odometry` — pressure/IMU/DVL-derived depth, x/y and heading.
- `/neptune/mission/status` — String JSON, authoritative phase/time/outcome.
- `/neptune/demo/health` — String JSON, readiness and sensor/publisher health.

**GUI application topics published: NONE.** ROS's standard `/rosout` and
`/parameter_events` remain enabled; neither is a movement interface. No motor
arrays, Twist, start service call, fake detections or neural overlays originate
from the GUI. It displays PERCEPTION: DISABLED. “Onboard state LIVE” means fresh
sensor-derived telemetry, not validated covariance or an ESKF accuracy claim.
Readiness publishes only `/neptune/demo/ready` (Bool) and `/neptune/demo/health`.
The executive's optional `/neptune/mission/start` Trigger arms a ready demo when
`auto_start=false`; it is for controlled validation, not GUI driving.

### Build and one-command startup

Inside the existing dev container, source ROS and Stonefish, then build only the
Python demo/runtime packages (no native or Docker rebuild):

```bash
source /opt/ros/jazzy/setup.bash
source /opt/stonefish_ws/install/setup.bash
cd /workspace
colcon --log-base /tmp/neptune-demo-v0-log build \
  --build-base /tmp/neptune-demo-v0-build \
  --install-base /tmp/neptune-demo-v0-install \
  --packages-select neptune_sim neptune_vehicle neptune_state_estimation \
                    neptune_autonomy neptune_bringup
```

From the repository root in WSL, the obvious entrypoint is:

```bash
./scripts/run_demo_v0.sh
```

It reuses/starts only the existing Compose dev container, sources ROS/Stonefish
and the built demo overlay, selects ROS domain 92 by default, and starts the entire
stack. No inference service is started. Override ROS_DOMAIN_ID explicitly if needed;
use the same domain for observers. The runner selects a normal `/workspace/install`
demo installation first, otherwise the validated temporary install. An explicit
`NEPTUNE_DEMO_INSTALL` selects another existing build. To make the build persistent,
use normal workspace build/install directories instead of the /tmp build arguments.
No build happens implicitly during the startup command.

Equivalent single sourced-container ROS command:

```bash
source /tmp/neptune-demo-v0-install/setup.bash
ROS_DOMAIN_ID=92 ros2 launch neptune_bringup perception_demo.launch.py \
  simulation_data:=/workspace/external/stonefish/Tests/Data
```

Close the GUI/Stonefish window or Ctrl+C the launch to stop only its owned actors;
the dev container remains intact. For diagnostic screenshots, optionally pass
`evidence_directory:=/tmp/my-neptune-demo` (GUI screenshots and health JSON).
`auto_start:=false` is a validation option: initialization remains at zero until
the executive's Trigger service is called after health checks. No simulator restart.

### Earlier instrumented smoke validation (historical scope)

This section records the earlier stopped smoke run only. Its completion deferral
is superseded by the user manual full-movement validation recorded below; its
measurements and temporary evidence are retained unchanged.

Initial verification passed before arming the same simulator: live GUI frames and
onboard telemetry, stable readiness, one executive command publisher, one
seven-motor adapter publisher, one sensor-derived estimator, no neural/fusion/P5a
publishers, all 441 observed startup body commands zero. The operator supplied a
screenshot and confirmed **“ITS WORKING!”**. Stonefish was observed restored at
1280x720, LOW, accelerated D3D12; no automatic maximization code exists.

One mission was armed. Observed sequence:
**INITIALIZING -> WAIT_FOR_STATE -> DIVE -> TRANSIT**. The operator then changed
validation scope to a short demonstration and requested no full mission. We
stopped the owned launch immediately; no retry, simulator restart or second mission.
**Full mission result: NOT RUN TO COMPLETION AT OPERATOR REQUEST**, not a failed
mission or a claim of INSPECT/RETURN/ASCEND/COMPLETE.

| Short-smoke measurement | Actual result |
| --- | --- |
| First 30 s after DIVE began | 301 Images / 30 s = **10.033 Hz** |
| Image/CameraInfo pairing | **301/301** |
| Max receipt gap, including window edges | **0.138572 s** |
| Max source-stamp gap | **0.138693 s** |
| Full observed movement interval | ~113.15 s; 1135 Images, **10.031 Hz** |
| Full observed interval max receipt / source gap | **0.141199 / 0.188320 s** |
| Last reported mission elapsed / state | **113.476 s / TRANSIT** |
| Final estimated position | **(-17.6972, +0.0640, 2.9915) m** |
| GUI at shutdown | camera/state LIVE; 1256 frames displayed / 1257 received |
| Largest GUI display gap | **0.166251 s** |
| Seven-motor layout | every array length 7; channels 4/5/6 always zero |
| Final motor command | seven zeros |

Depth reached the existing 3 m target; lateral estimate reached ~0.357 m during
outbound motion and reduced to ~0.064 m. No lateral-thruster regression was observed.
No truth data entered readiness, GUI, mission or evaluation observer. Localization
is the existing clean dead-reckoning baseline; no long-duration/real-ocean claim.
Inference, P4c fusion and P5a stayed off throughout. Mission executive was the
only body-command publisher. Camera, GUI and telemetry remained live during the
observed movement; full mission/inspection/return behavior is deferred, not inferred.

Original full-mission temporary observer recorded FAIL on intentional launch exit
because it expected COMPLETE. Its raw result is retained; `assessment.json` explains
the user-directed stop and records the accepted short-smoke scope explicitly.

Shutdown exposed the pre-existing unconditional `pressure_depth` rclpy.shutdown()
after ROS's SIGINT handler had already closed the context (that component exit 1).
Added only an `if rclpy.ok()` shutdown guard; estimator math/input/output unchanged.
The other launch components stopped cleanly; adapter emitted seven zeros. Both
signal/context paths have regression tests, and an independently launched installed
pressure_depth process now exits **0** on SIGINT with no traceback. No extra simulator
or mission was run after this fix; full-stack post-fix shutdown was not rerun.

Validation: initial focused suite **12 passed**, expanded preservation suite
**30 passed**, final shutdown regression/preservation suite **32 passed in 0.61 s**.
Includes startup/arming/health expiry/invalid state, unchanged Stage 1 gains and
startup, GUI no application publishers/latest-slot/stride/color decoding, all 17
existing five/seven-motor adapter tests, and the existing profile preservation test.
Five Python ROS packages built successfully (**2.63 s**); subsequent autonomy
and estimation builds passed after final lifecycle updates. Expected installed
Stonefish dependency and disabled-bytecode warnings were nonfatal. Host runner
Bash syntax, installed imports, ROS launch --show-args, actual host runner
--show-args, and git diff --check passed. No native/image/package installation.

Evidence (temporary, copy before container replacement):
container and host `/tmp/neptune-demo-v0-validation-49fzqeje/` contain raw
`result.json`, explanatory `assessment.json`, `launch.log`, GUI health and images.
GUI screenshots: `gui/INITIALIZING.png`, `gui/INITIALIZING-live.png`, `gui/DIVE.png`,
`gui/TRANSIT.png`. Host `/tmp/neptune-demo-v0-visual/initialization-desktop.png`
(operator screenshot) and `transit-desktop.png` show native windows. Inspection,
return and completion images were not captured because those phases were not run.

Known visual issues: native OpenCV viewer toolbar/status chrome remains; the
320x240 camera is enlarged for presentation, so detail is intentionally soft.
The first camera view includes the existing dock/buoy; target-facing camera/fixture
framing and lamp appearance at INSPECT were not reviewed in this shortened run.
The free Stonefish trackball does not automatically follow the vehicle; its built-in
Trackball center selector can be used observationally. Overlapping OS windows need
normal desktop arrangement; leave Stonefish unmaximized. No scene/lighting/optics
redesign, 1600x900 trial or repeated mission was performed.

**P5a: IMPLEMENTED — LIVE CLOSED-LOOP VALIDATION DEFERRED.** All prior P5a source,
configuration, sign=0, tests and diagnostic scripts were preserved byte-for-byte.
P5b NOT STARTED. Next, only when assigned: correct and visually validate camera/light
mounting orientation before Demo V1 Inspection Objects/A1 passive GUI overlays
or renewed P5 sign calibration and lateral visual alignment. Neither phase is implemented here. Stage 2 frozen through S2.6.
**No commit or push occurred.**


### Demo V0 full movement — user manual validation (2026-10-14)

**MAJOR MOVEMENT/INTEGRATION PASS — FULL MOVEMENT MISSION VALIDATED.**
The user manually validated Demo V0 using:

```bash
./scripts/run_demo_v0.sh
```

The user observed one Stonefish simulator process, D3D12 hardware rendering on
RTX 4080, the 1280x720 LOW viewport, live inspection camera in the GUI, canonical
state estimation, mission executive, seven-motor adapter, GUI telemetry, and the
full autonomous movement mission. The successful flow was:

**INITIALIZING -> WAIT_FOR_STATE -> DIVE -> TRANSIT -> INSPECT -> RETURN ->
ASCEND -> COMPLETE.**

This manual full-movement result supersedes the earlier short-smoke-only status.
The quantitative camera measurements, elapsed time and final position above belong
only to the earlier instrumented smoke run; no new full-run duration, final position
or quantitative camera metrics were supplied. This documentation update did not
rerun the mission, tests or builds.

The frozen runtime remains D3D12 / NVIDIA GeForce RTX 4080 Laptop GPU,
1280x720 LOW Stonefish viewport, inspection RGB 320x240 / 80-degree HFOV /
configured 10 Hz. Graphics plus CUDA inference coexistence was proven separately
in G3; that result does not imply inference was enabled in Demo V0.

#### Known inspection camera/light orientation issue

During the full run, the user visually identified that the inspection camera
appears to face AFT/backward relative to the intended inspection direction.
Inspection lights also appear backward or may share the same incorrect
mounting-frame convention. The current hypothesis is a **local sensor/light
mounting-transform problem**, likely an orientation convention or 180-degree
transform issue. **The exact transform and cause are not yet proven.**

This issue did not prevent mission motion, state estimation, GUI operation,
camera streaming, D3D12 rendering, seven-thruster integration or completion of
the movement demo. It must be corrected before meaningful inspection-camera
visual validation, Demo V1 passive perception overlays, or renewed P5a
perception-driven alignment validation.

| Current status | Result |
| --- | --- |
| Demo V0 | **FULL MOVEMENT MISSION VALIDATED** |
| Graphics | **VALIDATED** |
| GUI | **WORKING** |
| Inspection camera stream | **WORKING** |
| Inspection camera mounting orientation | **KNOWN ISSUE — appears backward** |
| Inspection lights orientation | **KNOWN ISSUE — appears backward / requires verification** |
| P5a | **IMPLEMENTED — LIVE CLOSED-LOOP VALIDATION DEFERRED** |
| P5b | **NOT STARTED** |
| Demo V1 passive perception overlays | **NEXT AFTER CAMERA/LIGHT ORIENTATION FIX** |

#### Immediate next session task — mounting orientation only

Inspect and correct only:

1. Girona body-frame convention.
2. Inspection camera mounting transform.
3. Inspection camera optical-frame transform.
4. Inspection light mounting/orientation.

Then run a **short visual validation** confirming that the camera faces forward
toward the inspection asset, lights illuminate forward, and pipe/flange/valve are
visible from the intended inspection approach. Do not change mission logic,
state estimation, controllers, graphics runtime, P4 models, P5a or P5b.
Demo V1 passive overlays follow only after this orientation fix. No part of that
next task was started in this documentation-only update. P5a/P5b work is untouched;
no code/config changes, tests, simulations, rebuilds, commits or pushes occurred.
