---
tags: [neptune, deployment, roboflow]
date: 2026-10-10
---
# Local Roboflow Inference

Related: [[Home]], [[Architecture]], [[Setup]], [[Roboflow Training]], [[Methods and Libraries]], [[Experiments]], [[Known Issues and Fixes]].

## Decision and architecture

The user selected local Inference after the workspace denied raw PyTorch weight export. Feed successive forward ROS camera images to a local server, using a single latest-frame worker. Webcam/RTSP/WebRTC capture is unnecessary: Stonefish already publishes images with simulation timestamps. Busy inference replaces queued images with the newest image, preserving its original header in Detection2DArray and annotated Image. No tracking or geometry enters inference.

Camera → ROS latest-frame detector → local Roboflow Inference → validated pipe boxes → existing ROS topics and native GUI.

The supplied A2 workflow was inspected through MCP. It wraps the base workflow with A2's model ID, and exposes predictions only. The base workflow's confidence is 0.4 and IoU threshold 0.3 by default. We use the official model REST API directly so all three models use explicit, identical confidence and NMS settings; the user did not request additional workflow logic. No external workflow was edited.

## Dependencies and exact settings

Official ARM64 server: Roboflow Inference 1.7.4, pinned digest `sha256:7e8c82e59549ca9dd451df6f29a7e3262d57d446cff819fdcb877df9af6c9b01`. Configuration is in `Simulation/docker/inference.env`; image pin in `inference-image.txt`. Compressed image size: 5,248,920,270 bytes (approximately 5.25 GB). The server is restricted to localhost port 9001 and the Neptune Docker network, with four CPU cores by default. CPU affinity is restricted to cores 0–3, so ONNX Runtime’s default thread pool sees the assigned cores instead of all ten Docker VM cores. Inspection of the official source showed that the initially requested ONNXRUNTIME_*_NUM_THREADS fields are unsupported; they were removed before final evaluation. Active learning and monitoring are disabled using supported server flags and request fields.

Official inference-cli and inference-sdk 1.7.4 are installed in separate `.venv-inference`; resolved versions in `config/inference-client-requirements.lock.txt`. The SDK requires NumPy >=2, which conflicts with the existing ROS/OpenCV NumPy 1.26.4 environment. ROS and offline evaluation use the server's official REST contract through Python urllib, with existing OpenCV/NumPy. No model algorithm is reimplemented. Verified REST routes/payloads match the official SDK 1.7.4 source.

Input is lossless PNG base64 at original 640×480 dimensions, with no client resize or JPEG corruption. Explicit NMS IoU 0.7, class-agnostic false, maximum 300 detections, active learning disabled. Authentication uses Authorization headers, never URL query strings. Model load timeout 180 seconds; per-frame request timeout 10 seconds. Only local endpoints are accepted; no cloud-image fallback. Cold model load needs provider access; offline behavior after caching still requires testing.

## Credentials

A user-supplied deployment key is stored only in `.secrets/roboflow_api_key` with mode 0600. `.secrets` is excluded from Git and Docker build contexts; the simulator mounts the key read-only. Never paste keys into commands, source, documentation or logs. The user pasted this key into chat; rotate it in Roboflow, replace the local file securely, and restart the detector. The key is retained for deployment as supplied; no new key was created for local Inference. Earlier temporary keys remain revoked.

## Start

Build the simulator with `bash src/tools/run.sh --build`. Start the local server in one terminal:

```bash
bash src/tools/inference-server.sh
```

After it is ready, start the simulator in another terminal (stop any older container named neptune-perception first):

```bash
bash src/tools/run-roboflow.sh model_id:=projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t2 confidence:=0.25
```

Then `bash src/tools/gui.sh`. This launches a candidate explicitly; it does not promote the cloud model or overwrite existing weights. The default normal simulator launch remains the existing Ultralytics backend until acceptance is measured.

For a single real simulator capture:

```bash
.venv-host/bin/python src/tools/inference-smoke.py --image data/orientation/images/val/o020_v02.png
```

Use a verified manifest path if the example image does not exist. Missing key/server/model access appears as unavailable/error; it must never create fake detections. The detector has bounded request timeouts and takes its next frame from the latest ROS image.

## Evaluation and later weight migration

For A1/A2/A3 respectively use model suffix t1/t2/t3 and actual training IDs 028b0b7b7ae5ba04c874 / a60cdfb1e9e27f582a05 / d6ad871de3e1ccbf613b. Evaluate validation first:

```bash
.venv-host/bin/python src/tools/evaluate.py --backend roboflow --model-id projects-zwfft/neptune-pipe-orientation-a-3-yolo11n-t1 --training-id 028b0b7b7ae5ba04c874 --split val --select-confidence --output outputs/roboflow/A1-val.json
```

Use only that report's selected confidence for its 900-image test; do not select thresholds or checkpoint from test metrics. Repeat all three, then summarize with `src/tools/summarize_repeats.py`. Reports identify server model IDs; weight hashes remain unavailable, so matching provider metrics cannot prove distinct underlying weights or independent seeded variation. Warm offline timing includes PNG encode, local HTTP, inference and decode; full-rig live timing and GUI FPS are separate.

Once compatible .pt weights become available, switch to `backend:=ultralytics weights:=/workspace/models/candidates/roboflow-v3/A2/weights.pt`. ROS topics, camera source, timestamps, GUI and control stack remain identical. Verify class mapping and rerun accuracy and latency tests because backend preprocessing/NMS can differ. Do not extract raw weights from the Inference cache to bypass export access.

## Actual verification, 2026-10-10

Neptune image built successfully. Backend unit tests passed for coordinate conversion, malformed/nonfinite outputs, input resolution, PNG pixel equality, header-only authentication and local endpoint restriction. ROS launch integration against a local test server passed exact image/detection timestamps, frame IDs and box coordinates, plus clean exit. These tests verify integration, not candidate accuracy. Actual local model loading, all three held-out evaluations and full-rig GUI tests are complete. Accuracy passed; runtime gates failed, so promotion is withheld. See [[Orientation Deployment Results]].

Sources: [Self-hosted deployment](https://docs.roboflow.com/deployment/self-hosted/self-hosted), [installation](https://docs.roboflow.com/deployment/self-hosted/inference-server/install), [header authentication](https://docs.roboflow.com/reference/inference/inference-sdk/configuration), [official SDK source](https://github.com/roboflow/inference).

Actual model access succeeded: A2 loaded through the official local server despite raw PT export denial. The real simulator-image smoke check produced a pipe box at confidence 0.2834; its first measured warm request was 415.65 ms before CPU-affinity optimization. This single partial-view prediction is not acceptance.
