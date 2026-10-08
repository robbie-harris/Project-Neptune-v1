# Project Neptune — Codex Instructions

Project Neptune is a ROS 2 autonomous marine inspection stack.

Before making architectural, localization, simulation, evaluation, autonomy,
control, or integration changes, read:

    docs/PROJECT_HANDOFF.md

## Core architectural rules

1. Preserve the existing ROS package boundaries under `src/`.

2. `/state/odometry` is the canonical downstream vehicle-state interface.

3. Simulator ground truth `/sim/odometry` is EVALUATION ONLY.

   It must never be used as an input to:
   - state estimation,
   - controls,
   - mission autonomy,
   - guidance,
   - perception-driven decision making.

4. Ground truth may be consumed inside `neptune_evaluation`.

5. Do not modify unrelated packages.

6. Work only on the scope explicitly requested in the current task.

7. Do not automatically begin the next Stage 2 task after finishing the
   current task.

8. Preserve working Stage 1 behavior unless the task explicitly requires a
   change.

9. Prefer simple, understandable implementations over unnecessary abstraction.

10. Do not silently weaken tests or acceptance criteria.

## Before modifying code

Inspect the relevant existing files and understand the current implementation.

State which files you intend to modify and why.

Do not rewrite functioning modules merely for style.

## After modifying code

Run the smallest relevant tests first, followed by the relevant ROS package
build.

Report:

- files changed,
- behavior implemented,
- tests run,
- test results,
- known limitations,
- any assumptions made.

If a test fails, report the failure rather than hiding it.

## Stage 2 rule

Stage 2 is being implemented incrementally.

Each S2.x task is independent.

When assigned S2.1, implement ONLY S2.1.
Do not begin S2.2, ESKF implementation, sensor-noise injection, or unrelated
cleanup unless explicitly requested.
After completing any S2.x task, update docs/PROJECT_HANDOFF.md with the implementation summary, validation results, limitations, and updated Stage 2 progress before stopping.
