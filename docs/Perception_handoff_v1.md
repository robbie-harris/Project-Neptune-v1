---
aliases: [Perception handoff v1]
tags: [neptune, handoff, perception, windows, integration]
date: 2026-10-12
status: integration-guide
---
# Perception_handoff_v1

## Purpose and instruction to the receiving agent

Integrate Neptune's GUI, perception, thruster configuration, inspection objects, and optical controls into the recipient's **existing Stonefish + ROS 2 AUV environment on Windows**. Preserve that environment and its vehicle. First reproduce the Neptune reference in isolation, then integrate one subsystem at a time. Do not replace the friend's robot, frame tree, dynamics, actuator ordering or launch files wholesale.

Source: [Project-Neptune / Perception](https://github.com/Project-Lumyn/Project-Neptune/tree/Perception). Use the commit that contains this document; record `git rev-parse HEAD` before extracting files. The prior tested pipe-only baseline is commit `5e0b98b`; it does not contain the complete three-class/lighting/mission work. The latest branch includes experimental capabilities with the limitations below.

The simulation is stopped at handoff. This guide is grounded in source and Mac measurements; **Windows/AMD64 build and runtime have not been tested here**. The recipient's agent must record its actual versions, hardware, commit, changes and test results. Do not report Mac performance as Windows performance.

Related notes: [[Architecture]], [[Inspection Objects and Optics]], [[Inspection Detector Results]], [[Automated Inspection Mission]], [[One Minute Mission Experiment]], [[Autonomous Power Control]], [[Faster Mission and View Priority]], [[Known Issues and Fixes]], [[Methods and Libraries]], [[Progress]].

## 1. What to extract

All paths below are relative to the source repository root.

| Capability | Required files | Integration responsibility |
|---|---|---|
| Three-class detector | Entire `src/neptune_perception/`; `config/detector.yaml`; `config/requirements.txt` | ROS package metadata, `detector.py`, `backends.py`; map forward image input and output topics; retain pixel-only inference and headers |
| Native GUI | `src/neptune_gui/auv_gui.py`, `src/neptune_gui/controls.py`; `src/tools/gui.sh` as Linux reference | Tk 8.6+, TCP host/port, PNG previews, controls, telemetry, optics, autonomous power and display toggles; no ROS install needed on Windows GUI host |
| GUI bridge | `src/neptune_sim/neptune_sim/bridge.py`, `protocol.py`, `optics.py`, `views.py`, `autonomous_power.py` | Dependencies and package entry points from `src/neptune_sim/`; map topics, watchdog and actuator allocation |
| Sensors, errors, pose, missions | `rig_adapter.py`, `error_adapter.py`, `error_model.py`, `navigation.py`, `operator_state.py`, `mission.py`; `Simulation/config/{rig,errors,mission,mission_fast}.json` | Optional autonomy integration; adapt sensor geometry, pressure convention, spawn and map; keep ground truth comparison-only |
| Launch and installed resources | `src/neptune_sim/launch/pipe_tank.launch.py`, both packages' `setup.py`, `setup.cfg`, `package.xml`, `resource/` | Preserve installation paths or update packaging explicitly; avoid relying on the sibling ros2-docker folder |
| Vehicle/thruster reference | `Simulation/scenarios/inspection_fast.scn`, `inspection_tank.scn`, `pipe_tank.scn`; `Simulation/assets/propeller.obj` | Extract actuator blocks/configuration; retain recipient vehicle until thrust signs, geometry and dynamics are verified |
| Pipe/valve/flange | `Simulation/assets/valve.obj`, `flange.obj`; scene static blocks and looks/materials | Pipe is a native cylinder, not a missing pipe mesh; copy referenced materials/looks and object transforms |
| Fixture generation/variants | `src/tools/generate_inspection_scene.py`; `config/requirements-mesh.txt`; `Simulation/scenarios/inspection_variant_*.scn` | Optional regeneration/augmentation. Generator rebuilds ordinary inspection scenes, not the custom fast-thruster profile |
| Water, lighting, clock, view priority | `src/tools/patch_stonefish.py`, `patch_optics.py`, `patch_views.py`; corresponding scene ocean/sun/light/overview blocks | These modify native renderer/ROS sources. GUI toggles alone cannot implement the effects |
| Reference Docker runtime | `Simulation/docker/Dockerfile`, `inference.env`, `inference-image.txt`; `src/tools/container-entrypoint.sh`, `start-vnc.sh`, `inference-server.sh`, `run-roboflow.sh`, `run-inspection.sh`, `run.sh`; `.dockerignore` | Build a fresh AMD64 image. Existing shell launchers hardcode ARM64 and must be adapted for Windows x86 CPUs |
| Verification | `tests/`; `src/tools/verify_runtime.py`, `verify_gui_controls.py`, `verify_inspection_mission.py`, `verify_mission_controls.py`, `verify_perception_recovery.py`, `verify_views.py`, `verify_optics.py`, `verify_autonomous_power.py` | Review each tool before running: several start missions or temporarily pause inference; use isolated reference simulation |
| Training/audit provenance | `config/inspection-training.json`; capture/evaluation/sealing/Roboflow tools in `src/tools/`; research and results notes | Optional for retraining. Import inference first; no retraining or public uploads required for integration |

Keep the `src/`, `Simulation/`, `config/` relationship when copying packages: both `setup.py` files use relative paths outside their package directories to install resources. If copying packages alone into a different workspace, rewrite data-file installation to include those assets/configs, then verify the installed share directories. Do not overwrite the recipient's existing package of the same name silently.

**Not in Git:** trained weights, simulator datasets, recordings, evaluation JSON, model caches, build/install/log directories, local virtual environments and secrets. They are intentionally ignored. Results notes summarize local reports; report paths in `outputs/` are provenance references, not promised files in the clone. Request authorized datasets/weights separately if required.

## 2. Model access and inference contract

The active three-class experiment is pretrained/fine-tuned **YOLO11n**, requested input 640 and 100 managed Roboflow epochs. Provider seed, batch, online augmentation and actual completed epochs are not established by the local tooling. Training ID: `cf8d962d68e32878e60b`; dataset version 2, 6,530 simulator-only images. Class names: **`pipe`, `valve`, `flange`**. Valve includes body/stem/handwheel; flange includes paired plates and bolts; attached pipe stays pipe.

Use these ROS parameters for this model:

```yaml
backend: roboflow
model_id: projects-zwfft/neptune-inspection-objects-2-yolo11n-t1
inference_url: http://neptune-inference:9001
api_key_file: /run/secrets/roboflow_api_key
confidence: 0.05
imgsz: 640
use_sim_time: true
```

The repository's default detector YAML is pipe-only/Ultralytics; **override it explicitly**. `run-inspection.sh --fast` and `--candidate` select the three-class model; plain startup retains pipe-only behavior. Do not substitute one of the earlier orientation training runs by accident.

`RoboflowBackend` loads through `/model/add` and predicts through `/infer/object_detection`. Authentication is in the HTTP Authorization header. Each ROS frame is PNG encoded, preserving pixels; inference server returns center `x,y,width,height` boxes, which the backend converts/clips to pixel `xyxy`. Class strings enter `Detection2DArray`, not assumed numeric COCO IDs. It uses a latest-frame worker, avoids frame backlogs, retries unavailable local inference and publishes explicit unavailable/error states. There is no cloud-frame inference fallback or tracking to conceal misses.

The friend needs their own **authorized** Roboflow API key with access to the model/workspace. Repository access does not grant model access. Coordinate workspace membership/access with its owner; do not copy the owner's `.secrets` or keys from conversations. If access is denied, stop at model access and retain a visible unavailable state. Do not retrain, upload images, create keys, or change account plans without the owner's authorization.

Model export is currently plan-gated. No usable three-class `.pt` is included. Later, after an authorized download, set `backend:=ultralytics`, `weights:=/workspace/models/inspection/weights.pt`, `device:=cpu`, and the same validated threshold. Record checksum/source, verify contiguous IDs and exact class-name schema, and rerun regression/runtime tests. Both backends retain the same ROS output contract. Initial model acquisition may need internet/authentication; cached deployment is not a proven permanently offline entitlement. Treat model caches as sensitive and do not redistribute them without permission.

### Topics and data conventions

| Interface | Type / semantics |
|---|---|
| `/clock` | Single simulator clock; all ROS consumers use simulation time |
| `/neptune/camera/left/image_color` | `sensor_msgs/Image`, default forward detector input; 640×480, BGR conversion |
| `/neptune/perception/object_detections` | `vision_msgs/Detection2DArray`, all three classes |
| `/neptune/perception/pipe_detections` | Same type, pipe-only compatibility subset |
| `/neptune/perception/annotated` | `sensor_msgs/Image`, annotated BGR image |
| `/neptune/perception/status` | `std_msgs/String`, JSON readiness, reason, detections, latency, capture stamp |
| `/neptune/camera/right/image_color`, `/neptune/camera/down/image_color` | Other images; stereo baseline 0.12 m |
| `/neptune/overview/image_color` | Independent tank overview image; published directly by scene |
| `/neptune/imu`, `/neptune/pressure`, `/neptune/dvl`, `/neptune/altitude` | `Imu`, `FluidPressure`, **`stonefish_ros2/msg/DVL`**, `Range` |
| `/neptune/sonar/image` | Sonar Image |
| `/neptune/ground_truth` | Odometry for diagnostics and one-time reference startup reset, never live perception/control guidance |
| `/neptune/telemetry` | String JSON with estimated/ground-truth pose, comparison, inspection/autonomy state and applied autonomous power |
| `/neptune/thrusters` | Float64MultiArray, native actuator order; 3 or 5 values depending on selected rig |
| `/neptune/control/request` | String: `inspect`, `return`, or cancel reason; owner/controller arbitration |
| `/neptune/control/return_command` | Float64MultiArray, controller command, internal to bridge arbitration |
| `/neptune/control/autonomous_power` | Float64, 20–100%, transient-local |
| `/neptune/simulation/realistic` | Bool, transient-local, optional error injection |
| `/neptune/optics/request`, `/neptune/optics/applied` | Float64MultiArray, versioned native optical command/confirmation |
| `/neptune/views/request`, `/neptune/views/applied` | Float64MultiArray, native display-priority command/confirmation |

Detections and annotated image headers preserve the **input capture stamp and frame ID**. Inference latency uses wall time; it does not replace capture time. Verify QoS with `ros2 topic info --verbose`: the detector currently subscribes with reliable default QoS, so a best-effort recipient camera needs a compatible subscription QoS or adapter, not just a topic rename. Use `image_topic` for input mapping and ROS remaps for fixed output topics. For example, in an already built Jazzy environment:

```bash
ros2 run neptune_perception pipe_detector --ros-args \
  -p use_sim_time:=true -p backend:=roboflow \
  -p image_topic:=/friend_auv/forward/image_color \
  -p model_id:=projects-zwfft/neptune-inspection-objects-2-yolo11n-t1 \
  -p inference_url:=http://neptune-inference:9001 \
  -p api_key_file:=/run/secrets/roboflow_api_key -p confidence:=0.05
```

Use `localhost:9001` if ROS runs directly in WSL and the inference port is published there; the Docker service hostname works only on the shared Docker network. Backend URL allowlist permits localhost, 127.0.0.1, host.docker.internal and neptune-inference; do not disable it just to make arbitrary remote endpoints work.

## 3. Recipient AUV integration: frames, sensors and controls

Neptune uses **metres, radians, world NED (Z down)**, body forward +X and sideways +Y. Pipe axis is world Y. Spawn: `[-3.8,0,1.5]`, yaw 0. Forward stereo centers `[0.62,±0.06,0]`, 80° horizontal FOV; sensor optical rotation is `[π/2,0,π/2]` in scenario body coordinates. Do not copy that rotation onto a camera already using ROS optical axes without checking its physical view.

Inspect the recipient's NED/ENU convention and frame ownership. Create an explicit mapping table for world/body/optical frame names, sensor extrinsics, image topics, actuator indices/signs and light names. Publish each TF edge from one owner only. Update `rig.json`, scenario origins and native sensor lookup names consistently. `navigation.py` subtracts a **0.18 m body-Z DVL lever arm**; change it for the recipient DVL. Pressure conversion currently assumes Stonefish **gauge pressure**, density 1000 kg/m³ and gravity 9.81; atmospheric absolute pressure or a different density requires corresponding correction.

Do not launch a second Stonefish instance into the friend's graph or publish a second `/clock`. Use the same ROS distro/message definitions, ROS_DOMAIN_ID and compatible DDS configuration; a separate reference domain isolates initial experiments. Separate Docker networks alone do not guarantee DDS discovery isolation. For the existing AUV, disable `rig_adapter`'s `initialize_spawn` node parameter until its reset behavior is deliberately adapted. That helper hardcodes robot name `Neptune` in its one-time respawn request. The reference launch does not expose this as a top-level launch argument: set the node parameter in the recipient's custom launch.

### Thruster configuration to carry across

The fast rig uses the native fluid-dynamics thrust model: 0.12 m propeller diameter, thrust coefficient 0.48 in both directions, torque coefficient 0.05, normalized commands, first-order rotor time constant 0.15 s.

| Native index | Name | Origin XYZ | Origin RPY | Max rad/s | Handedness / inversion |
|---|---|---|---|---:|---|
| 0 | ThrusterPort | −0.5, −0.18, 0.01317 | 0,0,0 | 418.88 (~4,000 RPM) | right=true |
| 1 | ThrusterStarboard | −0.5, +0.18, 0.01317 | 0,0,0 | 418.88 | right=false; inverted_setpoint=true |
| 2 | ThrusterHeave | 0,0,0 | 0,π/2,0 | 209.44 (~2,000 RPM) | right=true |
| 3 | ThrusterSwayFront | 0.23,0,0.01317 | 0,0,π/2 | 314.16 (~3,000 RPM) | right=true |
| 4 | ThrusterSwayRear | −0.27,0,0.01317 | 0,0,π/2 | 314.16 | right=false; inverted_setpoint=true |

Native ROS expects an array matching the number/order of the scene's thrusters. GUI manual protocol remains **three values** `[port,starboard,heave]`. With `lateral_enabled:=true`, autonomous controller produces `[port,starboard,heave,sway]`, and the bridge expands it to **five** `[port,starboard,heave,sway,sway]`. Manual commands append two zeros. Never send a four-element vector directly to a five-thruster native subscriber. `manual_scale:=0.25` limits main-motor manual RPM in this fast rig; it is separate from GUI manual power and autonomous power.

These positions/RPM/dynamics are **experimental simulation assumptions**, not measured hardware specifications. The tunnel-thruster layout does not model tunnel flow or fabrication clearance. A different hull mass, inertia, center of gravity/buoyancy or propeller arrangement requires a new allocation matrix and tuning. Preserve the counter-rotation/inversion relationship, but do not transplant these numbers blindly. Start with the recipient's established manual controls and zero command; test surge, reverse, both yaw directions, heave and sway individually before autonomous commands. The previous W-induced-yaw bug is precisely why sign/order verification is mandatory.

The GUI TCP contract is newline-delimited JSON on port 9090. Commands include `{"cmd":[0,0,0]}`, `{"mission":"inspect"}`, `{"mission":"cancel"}`, `{"autonomous_power_percent":70}`, `{"realistic":false}`, `{"views":{"camera":true,"overview":false}}`, and the four-field optics object described below. Outbound `state` contains telemetry/health/detections; `img` and `overview` carry base64 PNGs. Use the actual handlers as schema authority. The GUI sends heartbeats every 100 ms. The bridge stops on roughly 1 s GUI heartbeat loss/disconnect and 0.5 s controller loss; manual nonzero input overrides autonomy. Space, stop, focus loss and GUI closure cancel. Do not remove these behaviors to bypass a stalled camera/model.

Autonomous power is 20–100%, default 100%; scales cruise target linearly and nominal translation-thrust cap proportionally, while yaw/depth stabilization remains active. Updates are controller-confirmed. The full mission retains its 60 s wall-time deadline; lower settings or perception recovery can cancel rather than complete. Camera/inference outages hold with zero thrust for up to 25 s, then cancel; fresh frames are required to resume the same target.

Mapped mission is optional. Its route uses configured known pipe/component coordinates plus sensor dead reckoning and visual class confirmations; it does **not** reconstruct a pipe map or metric pose from boxes. Adapt endpoints/components/spawn and operating envelopes to the recipient world. Current fast standoff **1.7 m is body-origin to pipe axis**, not hull/camera to pipe surface; camera-axis distance is 1.08 m, surface clearance approximately 0.88 m. Preserve the three-thruster `mission.json` rollback (3.0 m standoff); its diagonal passes need that clearance.

## 4. Objects, lighting, water and native patches

Extract Pipeline cylinder radius 0.2 m, length 4 m, center `[4.4,0,1.5]`, rotation `[π/2,0,0]`. Valve center `[4.4,−0.85,1.5]`; flange `[4.4,+0.85,1.5]`, separated 1.7 m. Meshes are metres, scale 1. Copy `physical` and `visual` mesh definitions, materials and looks; resolve `../assets/` paths inside installed scene resources. Keep class boundaries above. Support structures are distractors, not valve/flange classes. Preserve collision geometry and recipient scene boundaries when repositioning objects.

Lights: LightLeft and LightRight, origins `[0.61,±0.12,0]`, camera-like forward optical RPY `[π/2,0,π/2]`, **800 lux, radius 0.015 m, 90° cone**. Start defaults: natural on, lamps on, clear water, particles off, errors off. Jerlov presets **clear 0.02 / moderate 0.25 / turbid 0.65**, density 1000; these are renderer settings, not calibrated NTU.

GUI optics payload: `{"optics":{"natural":false,"lamps":true,"water":"clear","particles":true}}`. Native request is `[request_id,natural,lamps,jerlov,particles]`; applied reply appends success. Natural-off disables **both sun and sky**; headlights and native scattering remain. Renderer changes occur on the graphics thread. Overview shares the lighting and can become dark. Do not reintroduce image-space water/backscatter: native water effects already apply. Optional camera blur/noise/calibration/dropouts remain in error adapter; put the adapter upstream of perception once, not twice.

Native patch order, on clean checked-out sources:

1. `patch_stonefish.py`: sim clock/capture timing, synchronized stereo rendering and base particle changes.
2. `patch_optics.py`: native sun/sky/water/particles/light controls, optical confirmations and capture metadata.
3. `patch_views.py`: native view priority and confirmations.

Pinned Stonefish commit **`b21eb8e194c570ff2f61e91aeffb38d73dc25f42`**; stonefish_ros2 **`6646e7ac25eed982f37f807abc7b545dbd2d6648`**. Scripts check exact source anchors and fail on drift. Do not force replacements into a different Stonefish version or reapply non-idempotent patches. Preserve the friend's upstream tree; use a separate checkout, review a patch diff and port deliberately if their version differs. Rebuild **both** native Stonefish and stonefish_ros2; Python-only rebuilds cannot supply these renderer APIs.

Critical hardcoded native lookups: `Neptune/CameraLeft`, `CameraRight`, `CameraDown`, `Sonar`, `LightLeft`, `LightRight`, `CaptureInstances`, plus `TankOverview`. Rename these in patches when the recipient robot/sensors use other names; ROS remaps do not change internal C++ names. Patch topics `/neptune/optics/*` and `/neptune/views/*` must agree with bridge topics. Native view application currently requires all four listed sensors and overview; missing sonar/down/overview can cause an error even when only forward perception is needed. Either install the reference rig or deliberately adapt the native lookup/validation to available sensors and document reduced capability.

CaptureInstances is an **offline segmentation camera**, disabled by default. Keep it off for live inference. Its instance masks, metadata and simulator geometry may label/evaluate datasets but must never become detector inputs. Water/view controls require graphical Stonefish; do not pretend a headless physics-only run implements graphical optics.

## 5. Windows reference reproduction (before modifying friend's environment)

Recommended baseline: Windows with **WSL 2 Ubuntu 24.04 + Docker Desktop Linux containers**, ROS 2 Jazzy inside Linux, GUI either native Windows Python/Tk or WSLg. Keep the clone in WSL's Linux filesystem for builds. See official [Docker WSL integration](https://docs.docker.com/desktop/features/wsl/use-wsl/), [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install), and [ROS Jazzy Ubuntu packages](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html). Enable Docker Desktop integration for the chosen distro. Check `uname -m` and Docker architecture; **AMD64 below is for x86 Windows**, not Windows-on-ARM.

In an administrator PowerShell terminal if WSL is not installed:

```powershell
wsl --install -d Ubuntu-24.04
wsl --update
```

Restart if Windows requests it. The commands below run in **WSL Bash**, not PowerShell. Use separate terminals for foreground services. Configure Git credentials through the user's approved credential manager; do not put tokens in clone URLs.

```bash
mkdir -p ~/neptune-handoff
cd ~/neptune-handoff
git clone --branch Perception --single-branch https://github.com/Project-Lumyn/Project-Neptune.git
cd Project-Neptune
git rev-parse HEAD
mkdir -p data models outputs .secrets
chmod 700 .secrets
# Enter YOUR authorized key without echo, shell-history exposure or command-line arguments.
read -r -s -p 'Roboflow API key: ' neptune_rf_key
printf '\n'
printf '%s' "$neptune_rf_key" > .secrets/roboflow_api_key
unset neptune_rf_key
chmod 600 .secrets/roboflow_api_key
```

Keep a clone for reference; use an integration branch in the recipient's own repository. Avoid `/mnt/c/` for Linux builds where possible. Do not use the Mac virtualenv, local Docker images, Mac paths, MPS device selection or ARM64 launcher flags on x86 Windows.

### A. Build the complete reference simulator

```bash
docker network create neptune-local
# If this network already exists, inspect/reuse it rather than creating a second one.
docker build --platform linux/amd64 \
  -f Simulation/docker/Dockerfile -t neptune-perception:windows-amd64 .
```

Use the **full Dockerfile**, not `Dockerfile.app`/`.views` on a fresh machine: those require previously built local Neptune base images. The full file installs Jazzy, native Stonefish/ROS patches and Python dependencies. Main pinned Python versions: Python 3.12; NumPy 1.26.4, OpenCV 4.11.0.86, PyTorch 2.8.0, torchvision 0.23.0, Ultralytics 8.3.221, pytest 8.3.5, PyYAML 6.0.2. Mesh generation separately uses Trimesh 4.6.8. Roboflow SDK 1.7.1 has a separate environment/lock; **do not merge its NumPy 2 dependency stack into ROS/Ultralytics**. The live backend uses REST and does not need the SDK there. Review pinned dependency files; exact apt versions resolve at build time, so capture `dpkg-query` and `pip freeze` on the recipient machine.

### B. Start local inference with an AMD64 digest

The committed `inference-image.txt` digest is **ARM64**, verified here. Registry manifest inspection on 2026-10-12 found the companion **linux/amd64** image in the same CPU image index:

```bash
NEPTUNE_RF_IMAGE='roboflow/roboflow-inference-server-cpu@sha256:5f3cb2a41c756e43f5c957fdf79925a883988238616394e932595dbc309c3454'
docker buildx imagetools inspect "$NEPTUNE_RF_IMAGE"
mkdir -p outputs/inference-cache
docker run --rm --name neptune-inference --platform linux/amd64 \
  --network neptune-local -p 127.0.0.1:9001:9001 --cpus 4 \
  --env-file Simulation/docker/inference.env \
  -v "$PWD/outputs/inference-cache:/tmp:rw" "$NEPTUNE_RF_IMAGE"
```

This AMD64 manifest was inspected, **not pulled/executed/tested on Windows**. Verify the resulting architecture and local REST/header-auth contract before deploying. The checked-in environment disables active learning, telemetry metrics, and custom workflow Python execution, and whitelists the source workspace. Update the whitelist only if deploying an authorized model from a different workspace. CPU execution is the portability baseline. GPU deployment requires separately verified Windows/WSL/NVIDIA support, image versions, providers and latency results; do not silently assume an NVIDIA GPU or CUDA.

### C. Run the isolated reference rig

In another WSL terminal at repository root:

```bash
docker run --rm -it --name neptune-perception --platform linux/amd64 \
  --network neptune-local \
  -p 127.0.0.1:5900:5900 -p 127.0.0.1:6080:6080 -p 127.0.0.1:9090:9090 \
  --cpus 8 --shm-size=1g -e LP_NUM_THREADS=8 -e ROS_DOMAIN_ID=27 \
  -v "$PWD/data:/workspace/data" -v "$PWD/models:/workspace/models" \
  -v "$PWD/outputs:/workspace/outputs" \
  -v "$PWD/.secrets/roboflow_api_key:/run/secrets/roboflow_api_key:ro" \
  neptune-perception:windows-amd64 \
  ros2 launch neptune_sim pipe_tank.launch.py backend:=roboflow \
  model_id:=projects-zwfft/neptune-inspection-objects-2-yolo11n-t1 confidence:=0.05 \
  scenario:=/opt/neptune/install/neptune_sim/share/neptune_sim/scenarios/inspection_fast.scn \
  mission_config:=/opt/neptune/install/neptune_sim/share/neptune_sim/config/mission_fast.json \
  manual_scale:=0.25 lateral_enabled:=true realistic:=false
```

The CPU allocation is the Mac reference, not a minimum requirement; adjust it and physics threads to available resources, then measure. `LP_NUM_THREADS` affects software graphics. Preserve simulation-time/watchdog semantics when performance falls. Container VNC runs Xvfb/Mesa with OpenGL 4.5 override. Open `http://localhost:6080/vnc.html` in Windows for the simulator desktop; reference VNC password is `ros`, suitable only for the loopback-bound development ports shown. Do not expose those ports or the unauthenticated GUI TCP bridge to LAN/internet. The GUI preview below is separate from the VNC desktop.

### D. Run GUI on Windows or WSLg

Install a supported Windows Python with Tcl/Tk 8.6+ and verify `py -m tkinter`. From Windows PowerShell, use an absolute path to the cloned GUI (a Windows checkout or accessible WSL path):

```powershell
py "C:\path\to\Project-Neptune\src\neptune_gui\auv_gui.py" localhost 9090 --diagnostics
```

Copy **both** GUI Python files if separating them from the clone. Python/Tk GUI has no OpenCV/ROS dependency. Alternatively in WSL with WSLg:

```bash
sudo apt-get install python3-tk
python3 src/neptune_gui/auv_gui.py localhost 9090 --diagnostics
```

WSLg or Windows/WSL localhost forwarding depends on machine/network configuration and must be checked; a GUI connection failure does not justify binding every service to `0.0.0.0` on the host. Start with no mission. Confirm raw and annotated feeds, overview, sensor status and model readiness. Mission can begin only after navigation/perception readiness.

### E. Then integrate with the friend's existing environment

Create a custom recipient launch that starts **only** needed Neptune nodes alongside the friend's **one existing simulator**. First import detector alone and prove the image/output contract. Next add fixtures and optical/view patches in a dedicated upstream checkout. Then import GUI/bridge and explicit thruster mapping. Finally add sensor errors/telemetry and optional mapped mission, adapting all known coordinates and operating bounds.

If ROS nodes are split across WSL and multiple containers, explicitly prove discovery, matching ROS_DOMAIN_ID/RMW, one clock, and QoS. Do not assume the inference Docker network also makes DDS work; HTTP model access and ROS discovery are separate. A safe baseline places simulator and ROS consumers in one Linux runtime and inference on the private Docker network. Use `host.docker.internal:9001` only when crossing to a host-published local server deliberately. Resolve port 9090/9001/VNC conflicts without reusing another application's service accidentally.

## 6. Secure porting and acceptance checklist

- Inspect scripts and diffs before execution. Back up recipient launch/configs, use an integration branch, and retain its working AUV launch for rollback. No real actuators should consume experimental simulation commands.
- Keep `.secrets`, `.env`, caches, datasets, weights and outputs ignored in recipient Git and excluded from Docker build context. Mount only the needed key read-only. Do not bake keys into images, YAML, screenshots, prompts, shell history or model URLs. Keys previously exposed in conversations should not be reused; rotation belongs to the account owner. Do not print Authorization headers or signed download URLs.
- Retain upstream source copyright/license notices. ROS package metadata declares GPL-3.0-only; inspect upstream and dependency/model terms before distribution. The repository currently has no top-level LICENSE file; do not invent a permissive license for the code. Simulator training data were public CC BY 4.0; COU remained local, not part of this model or handoff. Dataset permission does not automatically authorize weight/cache redistribution.
- Build/install package resources and verify referenced OBJ/config files resolve. Check camera optical view, stereo transforms and identical ideal timestamps, captured rather than processing-time headers, pressure/DVL units and TF ownership. Re-evaluate error-enabled timestamp offsets separately from ideal tests.
- Verify each motor direction at low manual settings. Check positive surge does not yaw, positive yaw follows the declared convention, both heave directions and paired sway; verify correct-length native arrays. Operator stop, manual override, GUI focus loss, disconnect and heartbeat expiry must stop **all** actuators. Avoid multiple GUI clients: any client disconnect cancels the shared mission.
- Exercise all natural/lamps combinations, clear/moderate/turbid presets and particle toggle; confirm native applied states. Sun/sky-off plus lamps-off must be dark; headlights-only must illuminate geometry. Verify no doubled image-space scattering and no GUI false success when native sensor names are absent.
- Confirm camera-only, overview-only, both and neither display mode. Hidden AUV view must retain detector inputs. Nominal stereo rates are 10 Hz with AUV view on / 5 Hz off; down/sonar 10 Hz both-on / 2 Hz otherwise; overview 5 Hz both-on / 10 Hz overview-only / disabled when hidden. Measure **fresh received frames**, not repaint counters; 5 FPS is not guaranteed by frequency settings.
- Verify missing key/model, bad access, server outage, missing frames and recovery. Do not fabricate empty detections as a healthy model. Confirm restored input headers, three-class output and pipe compatibility subset. Test local-weight migration only with authorized actual weights.
- Run `python -m pytest tests -q` in a pinned host test environment; run ROS launch tests in a built Jazzy environment. Host suite last passed **87 tests with four ROS-only skips** before handoff; verify that count afresh. Run runtime tools on isolated simulation, especially those that pause inference or start autonomous motion. Stop after verification unless the owner asks to run.
- Record CPU/GPU/RAM, Windows/WSL/Docker/ROS versions, architecture, upstream commits, inference digest, model ID, latency p50/p95, inference rate, fresh GUI FPS, timestamps, settings and complete mission duration. Acceptance on one laptop cannot be transferred to another by copying a config.

## 7. Measured limitations and remaining work

New eligible clear/moderate simulator test recall at class-correct IoU≥0.5: **pipe 99.26%, valve 95.70%, flange 100%**; target-absent false-positive frames **2.78%**. Turbid recall only **13–18%**. Original untouched pipe orientation regression **93.78%**, versus prior model 100%; normal default-model promotion remains blocked. These are synthetic-data results, not real underwater accuracy. Real-world datasets and vehicle-specific evaluation remain necessary.

On Apple M5 / 16 GB, ARM64 Docker/Mesa CPU renderer and CPU local inference, earlier matched full-rig candidate p95 inference latency was **231.08 ms**, fresh GUI FPS median **2.43**. Other view-priority windows differed; 10 Hz camera settings are not 10 wall-time GUI FPS. At the **current 1.7 m standoff**, clear/ideal/100% full mission passed in **43.50 s**, returned within **3.46 cm**. Wider prior scan-line runs took 35–38 s. Mission timing at lower power, errors enabled or different optics is not established by that ideal test. All timing/recall figures must be remeasured on Windows and the friend's AUV.

This is three-class object detection plus an experimental mapped simulator mission. It does not provide metric object pose, sensor fusion with uncertainty, obstacle avoidance for arbitrary worlds, damage diagnosis, valve actuation, repair execution, or general search for out-of-FOV targets. Preserve those boundaries in the port.

## Deliverables the recipient agent should return

An integration branch/commit with extraction manifest and source SHA; topic/frame/actuator mapping; explicit Windows/AMD64 build/start/stop commands; model-access instructions without secrets; native renderer patch diffs and version locks; verified manual/stop behavior; detection and timestamp checks; measured performance and mission results; unresolved limitations and rollback instructions. Keep generated artifacts separate from source, and do not push or share secret/runtime files.

Official reference sources: [Stonefish source](https://github.com/patrykcieslak/stonefish), [stonefish_ros2 source](https://github.com/patrykcieslak/stonefish_ros2), [Stonefish environment optics](https://stonefish.readthedocs.io/en/latest/environment.html), [Roboflow Inference source](https://github.com/roboflow/inference), [Roboflow local inference ecosystem](https://inference.roboflow.com/quickstart/roboflow_ecosystem/), [Docker WSL integration](https://docs.docker.com/desktop/features/wsl/use-wsl/), [Microsoft WSL setup](https://learn.microsoft.com/en-us/windows/wsl/setup/environment).
