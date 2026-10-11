# Project Neptune

Torpedo-style AUV simulation and first pipe detector, developed on **Perception**.
Built from the project's existing ROS 2 Jazzy / Stonefish / ARM64 Docker and native Tkinter GUI setup.

## Start

```bash
# From this repository, on Perception:
bash src/tools/run.sh --build
# Cached compatible reference image can speed up the first build:
# bash src/tools/run.sh --build --build-arg BASE_IMAGE=ros2-jazzy-dev
bash src/tools/run.sh
```

In a second terminal:

```bash
bash src/tools/gui.sh
# If needed, select Python with Tk 8.6+: NEPTUNE_GUI_PYTHON=/path/to/python bash src/tools/gui.sh
```

Simulator desktop: [browser VNC](http://localhost:6080/vnc.html) (password `ros`), or `vnc://localhost:5900`.
The GUI provides hold-to-drive W/S surge, A/D yaw, R/F heave, release-to-zero thrust, Space stop, a 20–100% manual-power slider, raw/annotated camera views, and detector status. See [manual control](docs/Manual%20Control%20and%20Mobility.md).

A pipe-trained model is required. Until `models/pipe/best.pt` exists, the simulator and raw preview run with explicit **model unavailable** status. COCO weights are not accepted as pipe weights.

## Orientation dataset and Roboflow training

Keep the simulator running and close the manual GUI during automated capture:

```bash
docker exec neptune-perception bash -lc 'source /opt/ros/jazzy/setup.bash; source /opt/stonefish_ws/install/setup.bash; python3 /opt/neptune/src/tools/capture_orientation.py --output /workspace/data/orientation --groups 600 --resume'
# Use a Python 3.12 host environment:
python3.12 -m venv .venv-host
.venv-host/bin/pip install -r config/requirements.txt
.venv-host/bin/python src/tools/validate_dataset.py --data data/orientation
```

Current training uses **Roboflow MCP**, with YOLO11n, 100 requested epochs and three managed repeat runs. The provider does not expose batch or seed controls here; online preprocessing/augmentation is provider-managed. Simulator uploads are public CC BY 4.0; COU stays local. See [Roboflow Training](docs/Roboflow%20Training.md) for upload, annotation, frozen-version verification and weight retrieval. The local training script remains available but is not the current training path.

After downloading a candidate to `models/candidates/roboflow-v3/A1/weights.pt`:

```bash
.venv-host/bin/python src/tools/evaluate.py --data data/orientation --weights models/candidates/roboflow-v3/A1/weights.pt --training-id 028b0b7b7ae5ba04c874 --device mps --split val --select-confidence --output outputs/rf-A-repeat-1-val.json
NEPTUNE_CONFIDENCE="$(.venv-host/bin/python -c 'import json; print(json.load(open("outputs/rf-A-repeat-1-val.json"))["confidence"])')"
.venv-host/bin/python src/tools/evaluate.py --data data/orientation --weights models/candidates/roboflow-v3/A1/weights.pt --training-id 028b0b7b7ae5ba04c874 --device mps --split test --confidence "$NEPTUNE_CONFIDENCE" --output outputs/rf-A-repeat-1-test.json
```

If the simulator is already running, open the GUI directly. Use `docker stop neptune-perception` before restarting or applying a rebuilt image.

Candidates never automatically replace `models/pipe/best.pt`. Promotion requires matching validation/test reports, live ROS checks and baseline runtime comparisons; rollback is retained. Restart after verified promotion to load the active model.
The evaluator exits nonzero when held-out acceptance targets fail.

## Layout

- `src/`: ROS packages, GUI, startup/capture/training/evaluation tools.
- `Simulation/`: Docker configuration, scene, assets, ideal rig configuration.
- `config/`: model settings and pinned Python dependencies.
- `docs/`: interlinked Obsidian vault; open [Home](docs/Home.md).
- `tests/`: geometry, safety, scenario, and ROS launch checks.
- `data/`, `models/`, `outputs/`: ignored generated artifacts.

```bash
.venv-host/bin/python -m pytest -q tests
# Inside the simulator container:
docker exec neptune-perception bash -lc 'source /opt/ros/jazzy/setup.bash; source /opt/stonefish_ws/install/setup.bash; source /opt/neptune/install/setup.bash; python3 /opt/neptune/src/tools/verify_runtime.py --require-model'
```

See [Setup](docs/Setup.md), [Architecture](docs/Architecture.md), [Progress](docs/Progress.md), and [Orientation Detection](docs/Orientation%20Detection.md) for details and measured validation. This milestone does not implement autonomous navigation, repair, or real-water generalization.

## Local Roboflow Inference

Run `bash src/tools/inference-server.sh`, then `bash src/tools/run-roboflow.sh`, then `bash src/tools/gui.sh`. The key belongs in ignored `.secrets/roboflow_api_key` (mode 0600), never source code. See [local deployment](docs/Local%20Roboflow%20Inference.md) for model IDs, evaluation and later migration to downloaded weights. Default normal startup continues to use existing Ultralytics weights until candidate acceptance is measured.


### Managed orientation candidate (2026-10-10)

A1 is integrated with the live simulator through the local Roboflow server. All three runs passed held-out simulator accuracy (100% recall, 0.444% false-positive frames), but measured live speed gates failed; the original default is preserved. Run `bash src/tools/inference-server.sh`, `bash src/tools/run-roboflow.sh`, and `bash src/tools/gui.sh` in separate terminals. The candidate launcher selects A1 at confidence 0.05. See [measured results](docs/Orientation%20Deployment%20Results.md), including the poor real COU transfer result and runtime limitations.


### Sensor-error toggle and return to spawn

The GUI includes a realistic-error checkbox, estimated/ground-truth telemetry with a defined pose agreement percentage, and Return to spawn. Launch starts ideal; add `realistic:=true` to the ROS launch arguments to start with errors. Stop, manual override, disconnect and stale sensor data cancel return. See [settings and measured verification](docs/Sensor%20Errors%20and%20Return%20to%20Spawn.md).


The GUI also includes a fixed live tank overview below the forward feed, larger telemetry text, and a scrollable camera/telemetry area. See [tank overview](docs/Tank%20Overview.md).
