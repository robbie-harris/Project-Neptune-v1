# Perception integration — P1a / P1b

P0 audit complete. P1a added the optional pipe/flange scene; P1b adds its valve.
P2 lateral thrusters + lights is next and has not started. Stage 2 remains frozen
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

Girona include, five actuators/order, sensors, dynamics, autonomy, localization,
mission coordinates, and command interfaces are unchanged. Existing scenarios
and runners remain untouched. Ground truth remains evaluation-only.

Packaging installs the optional scene and both perception meshes. Stonefish resolves the flange
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

## Visual launch

From the repository root with the existing dev container running, and no other
simulator owning the same topics, use the build verified in this session:

```bash
docker compose -f docker/compose.yaml exec dev bash -lc '
  source /opt/ros/jazzy/setup.bash
  source /opt/stonefish_ws/install/setup.bash
  source /tmp/neptune-p1b-install/setup.bash
  ros2 run stonefish_ros2 stonefish_simulator \
    /workspace/external/stonefish/Tests/Data \
    /tmp/neptune-p1b-install/neptune_sim/share/neptune_sim/scenarios/benchmarks/03_port_pipe_perception.scn \
    100 800 600 low
'
```

The /tmp installation is temporary. To recreate it inside the dev container,
source ROS and the Stonefish overlay, then run from /workspace:

```bash
colcon --log-base /tmp/neptune-p1b-log build \
  --build-base /tmp/neptune-p1b-build \
  --install-base /tmp/neptune-p1b-install --packages-select neptune_sim
```

This command launches the simulator only. Close its window to stop it.
Rollback: select the original `02_port_pipe_mission.scn`; no baseline files changed.
