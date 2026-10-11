---
tags: [neptune, index]
---
# Neptune project vault

Start at [[Project Overview]] and [[Setup]].

- [[Architecture]] — modules, data flow, frames, repository structure
- [[Implementation Plan]] — milestone and acceptance criteria
- [[Progress]] — implemented and actually verified work
- [[Known Issues and Fixes]] — failures, fixes, current limitations
- [[Methods and Libraries]] — reused methods and dependency pins
- [[Research]] — primary sources and applicability
- [[Decision Log]] — design choices and tradeoffs
- [[Experiments]] — measured outcomes and reproducibility
- [[Ideas]] — future work without expanding this milestone
- [[Orientation Detection]] — broader capture, baseline diagnostics and acceptance
- [[Roboflow Training]] — authorized uploads, training workflow and backend constraints
- [[Orientation Resume Checkpoint]] — current long-running work and next steps

Use dated entries and distinguish observations from hypotheses. Images belong in `attachments/` using relative links. Large generated datasets and weights remain outside this vault.

- [[Local Roboflow Inference]] — local deployment, model access and later downloaded-weight migration


## 2026-10-10 — live managed deployment

See [[Orientation Deployment Results]] for completed three-run held-out results, live CPU experiments, manual-control verification, unmet performance gates, and the COU transfer diagnostic. Accuracy passed; runtime gates failed, so the original default remains active.


## 2026-10-10 — manual mobility fix

[[Manual Control and Mobility]] records the hold-to-drive GUI, confirmed command bars, counter-rotating horizontal propellers, increased rotor authority and passive hull stability. All six physical directions, sustained straight travel, emergency stop, disconnect and native Tk repeat/release checks passed. These are simulator parameters, not measured Neptune hardware.


## Switchable sensor errors and return

[[Sensor Errors and Return to Spawn]] documents the moderate error profile, ideal bypass, sensor-only pose comparison score, GUI controls and staged tank return. Actual outcomes are recorded separately from pending verification.


[[Tank Overview]] adds a fixed live tank camera below the forward GUI feed, 13 pt telemetry text and screen-aware scrolling. Actual camera/GUI checks are recorded in that note.
