# Perception integration — P1 / P2

P0 audit complete. P1a added the optional pipe/flange scene; P1b adds its valve.
P2 lateral thrusters + lights is implemented; unit/build and physics actuation
checks pass, but full graphical actuation remains unverified because simulator
ROS callbacks stalled. P3 camera is next, not started. Stage 2 remains frozen
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
with two appended motors and two added lamps. Baseline scenarios and runners
remain untouched. Ground truth remains evaluation-only.

Packaging installs the optional scene, both perception meshes, and the
perception-specific Girona include. Stonefish resolves the flange
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

## Visual launch

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
