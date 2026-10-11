---
tags: [neptune, decisions]
---
# Decision log

## 2026-10-08

- Work in Project-Neptune on Perception, with source under `src` and rig/build assets under `Simulation`.
- Reuse the existing native GUI, newline-JSON TCP bridge, Docker/VNC, and Stonefish architecture.
- Horizontal broadside pipe at the far end; user selected this layout.
- Host Mac training; user selected this compute path. Container inference uses CPU.
- YOLO11n detection, rather than segmentation, for the initial bounding-box milestone and limited software-rendering budget.
- Use a compound primitive torpedo body with fins; retain three controllable thrusters to support repeatable manual tests without claiming realistic torpedo navigation/control design.
- Preserve explicit NED/forward-right-down frames to avoid hidden coordinate conversion mistakes.
- Add narrowly scoped upstream clock and render scheduling integration fixes because wall-clock stamps and round-robin rendering violate ideal stereo timing.
- Disable decorative particles for clear-water images. Do not add sensor noise, corruption augmentation, or drift.
- Keep data/weights/logs ignored by Git; record settings and actual results in the vault.

See [[Architecture]], [[Known Issues and Fixes]], and [[Progress]].

## 2026-10-09

- Clip the visible cylinder silhouette before computing labels, and recapture affected views.
- Improve actual video throughput with 8 Mesa workers, a smaller independent viewer, fresh-frame streaming at up to 10 FPS, and 30 Hz GUI polling. Camera resolution and lighting remain unchanged.
- Budget Docker YOLO CPU inference at 2 threads to share rendering capacity.
- Use one existing simulator respawn request at startup to remove initial-condition drift; no ongoing attitude or navigation control is added.


## 2026-10-10 — manual mobility fix

[[Manual Control and Mobility]] records the hold-to-drive GUI, confirmed command bars, counter-rotating horizontal propellers, increased rotor authority and passive hull stability. All six physical directions, sustained straight travel, emergency stop, disconnect and native Tk repeat/release checks passed. These are simulator parameters, not measured Neptune hardware.
