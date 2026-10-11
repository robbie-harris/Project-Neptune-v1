---
tags: [neptune, setup]
---
# Setup and operation

Requirements: Apple Silicon Mac, running Docker Desktop, Python with Tkinter for the host GUI, and Python 3.12 for the training environment. Linux ARM64 container inference runs on CPU; Docker on macOS does not expose the Apple GPU. Host PyTorch can use MPS.

From repository root on Perception:

```bash
bash src/tools/run.sh --build
bash src/tools/run.sh
bash src/tools/gui.sh
# If needed, select Python with Tk 8.6+: NEPTUNE_GUI_PYTHON=/path/to/python bash src/tools/gui.sh
```

Optional cached reference image: append `--build-arg BASE_IMAGE=ros2-jazzy-dev` to the build command. The default build starts from `ros:jazzy`, not the sibling reference repository. Build changes after edits; installed ROS resources are copied into package shares.

Native controls: hold W/S for forward/reverse, A/D for left/right turn, R/F for up/down, or hold the matching buttons. Release cuts thrust; Space or STOP clears every command. Application deactivation, minimization, disconnect and timeout stop commands. Manual power defaults to 60%, adjustable from 20–100%. Holding a key never increments power. Both positive horizontal bars mean forward thrust, not right steering; bars show the commands acknowledged by the bridge. See [[Manual Control and Mobility]]. The simulator desktop is available at `http://localhost:6080/vnc.html`, password `ros`. TCP and VNC ports bind only to localhost.

## Data and training

Close the GUI during automated capture so manual commands cannot move the robot:

```bash
docker exec neptune-perception bash -lc 'source /opt/ros/jazzy/setup.bash; source /opt/stonefish_ws/install/setup.bash; python3 /opt/neptune/src/tools/capture_dataset.py'
python3.12 -m venv .venv-host
.venv-host/bin/pip install -r config/requirements.txt
.venv-host/bin/python src/tools/train.py
.venv-host/bin/python src/tools/evaluate.py --device mps
```

Capture temporarily disables the right/down cameras and sonar, then restores them. Use `--keep-all-sensors` to retain the full rig during acquisition. Capture supports `--resume`; it refuses to overwrite an existing dataset silently. `--limit` supports smoke captures but is not a substitute for the 1,000-image milestone. Viewpoint groups stay within one split. Labels come from OpenCV projection of the actual pipe surface at capture-time ground truth. Inspect overlays before training with `.venv-host/bin/python src/tools/review_labels.py`. Training validates 1,000 unique images, split counts, normalized labels, and group isolation before it starts.

Model artifacts: `models/pipe/best.pt`, `training.json`. Training logs: `outputs/training`. Evaluation report: `outputs/evaluation.json`. Stop the current container with `docker stop neptune-perception`, then restart simulation after new weights are ready. If already running, open the GUI directly rather than starting a second container.

## Verification

```bash
.venv-host/bin/python -m pytest -q tests
docker exec neptune-perception bash -lc 'source /opt/ros/jazzy/setup.bash; source /opt/stonefish_ws/install/setup.bash; source /opt/neptune/install/setup.bash; python3 /opt/neptune/src/tools/verify_runtime.py --require-model'
```

Close the GUI and run the actual-motion check with `docker exec neptune-perception bash -lc 'source /opt/ros/jazzy/setup.bash; source /opt/stonefish_ws/install/setup.bash; python3 /opt/neptune/src/tools/verify_controls.py'`. This resets the AUV to spawn between checks and leaves it there afterward. Stop means zero thrust, so physical momentum remains.

Run ROS launch tests inside the container with the same environments sourced. Runtime verification checks observed sensor output and shared stereo stamps; it reports rather than assumes wall-time throughput. See [[Known Issues and Fixes]] and [[Experiments]].

The current inner ceiling/floor are at NED z=0.02/3.02 m, preserving 3 m interior height while avoiding a coincident roof/water-surface rendering plane.

GUI diagnostics: `bash src/tools/gui.sh --diagnostics` reports the actual decoded/rendered stream and model-state changes. Use `--preview raw` to open with the raw stream selected. A stale or missing annotated stream falls back to the raw camera preview.

Performance defaults: 8 Mesa workers, 640×480 simulator viewer, 10 FPS maximum preview transfer, and 30 Hz GUI polling. These do not alter the three cameras' 640×480 sensor resolution. The GUI's Feed FPS field reports fresh decoded frames. To enlarge only the optional simulator desktop viewer, pass `window_width:=800 window_height:=600` to the ROS launch command; this may reduce sensor throughput.


## Error profile and return

Use the GUI realistic-error checkbox to enable/disable injection without restarting. The telemetry percentage is pose agreement against ground truth, not detector accuracy. Return first aligns the initial heading, drives/steers home, then restores heading; Space cancels it. See [[Sensor Errors and Return to Spawn]] for exact assumptions, tolerances and limitations.
