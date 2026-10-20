# Project Neptune

**Project Lumyn / Talon** — a simulation-first autonomous underwater inspection stack.

Demo V0 performs **DIVE → TRANSIT → INSPECT → RETURN → ASCEND → COMPLETE**, after waiting for healthy onboard estimated state. Stonefish sensors feed state estimation; autonomy consumes `/state/odometry` and sends body commands through the vehicle adapter. Simulator truth is evaluation only.

## Development platform

Windows 11, WSL2 Ubuntu 24.04, ROS 2 Jazzy, Docker, Stonefish, and an NVIDIA RTX GPU with WSLg/D3D12 rendering. This is the demonstrated platform; hardware deployment is future work.

## Quick start

Use the existing Neptune development container and its Stonefish dependencies. The image build requires local ignored `external/stonefish` and `external/stonefish_ros2` checkouts; dependencies and tested overlays must be provisioned first. See the [handoff](docs/PROJECT_HANDOFF.md) for build assumptions and current limitations.

Engineering demo, with a built Demo V0 overlay:

```bash
./scripts/run_demo_v0.sh
```

Recorded presentation workflow:

```bash
NEPTUNE_DEMO_INSTALL=/tmp/neptune-safe-presentation-install \
./scripts/run_demo_v0.sh --presentation
```

The `/tmp` path is an ephemeral **container-side** tested install, not a permanent distribution. Preserve its underlying package versions until a coherent source rebuild is validated. Presentation keeps Stonefish at **1280×720** and moves its window without resizing; the read-only Neptune GUI occupies the right side.

## Team references

- [Current project handoff](docs/PROJECT_HANDOFF.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Authoritative ROS interfaces](docs/INTERFACES.md)
- [Team contracts and change protocol](docs/TEAM_CONTRACTS.md)
- [Ownership](docs/OWNERSHIP.md)
