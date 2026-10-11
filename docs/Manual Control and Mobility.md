---
tags: [neptune, controls, simulation, verification]
date: 2026-10-10
---
# Manual control and mobility

See [[Setup]], [[Architecture]], [[Progress]], [[Known Issues and Fixes]], and [[Decision Log]].

## Problems and implemented fixes

The original GUI incremented axes on every key-repeat event and latched them after release. Forward could reach full thrust while a previous turn remained active. It also showed local requested values rather than bridge-confirmed commands. Both horizontal fluid-dynamics propellers were right-handed, adding reaction roll torque. The neutrally buoyant mass layout lacked passive roll restoration; the first counter-rotating test still rolled about 16° while turning.

`src/neptune_gui/controls.py` now uses held keys and an explicitly selected manual power (default 60%, range 20–100%). W/S and arrows command forward/reverse; A/D and arrows turn left/right; R/F command up/down. Opposites cancel and aliases do not double power. Differential mixing divides both horizontal commands by their shared saturation factor, retaining the requested turn/forward ratio. Release cuts that axis's command. Buttons use press/release with leaving the button cancelling its command. Tk release/press auto-repeat pairs are debounced for 20 ms. Space and STOP immediately send zero and prevent still-held keys from rearming until released. Focus loss, app deactivation and minimization clear thrust. The existing bridge disconnect/one-second monotonic timeout remains in place. Zero thrust allows physical coasting; it is not a position hold.

Bars now show commands acknowledged by the ROS bridge. Both horizontal bars extending right means **positive forward thrust**, not right steering. Port/starboard/heave ordering remains unchanged; inference, ideal sensors and camera topics remain unchanged.

The starboard propeller now uses `right="false"` with `inverted_setpoint="true"`, preserving positive-forward command semantics while cancelling forward reaction torque. This pairing was verified in the installed Stonefish FDThrust equation and scenario parser, not inferred from visual propeller spin. Maximum rotor setpoint increased from 52.36 to 104.72 rad/s for all three thrusters; the existing mechanical-PI rotor and fluid-dynamics thrust models remain. This is prototype tuning, not calibrated hardware performance.

The hull part's mass centre is displaced downward by 2 cm relative to its own geometric centre. Because the cylinder is rotated around Y, local `cg xyz="-0.02 0 0"` maps to body +Z (down in NED). Other masses remain unchanged, so the full compound centre shifts by the hull's mass fraction. This adds passive hydrostatic righting while retaining total mass and buoyancy; it adds no autonomy or attitude controller.

## Completed verification

Actual Stonefish six-direction test at 60% command; forward duration eight seconds, other directions four seconds. Signs use body forward +X, NED yaw right-positive, NED depth +Z (up is negative).

| Direction | Observed displacement/turn | Maximum absolute roll |
|---|---:|---:|
| forward | 0.7894 m | 0.000° |
| reverse | -0.2405 m | 0.000° |
| right | 0.4241 rad | 1.186° |
| left | -0.3834 rad | 1.142° |
| up | -0.1634 m | 0.024° |
| down | 0.1540 m | 0.011° |

Forward yaw and roll were effectively zero in this controlled run. Turn roll fell from 15.95° before the passive-stability adjustment to at most 1.187°. Disconnect zero command observed within 0.0491 s; emergency zero observed after every direction. Acceptance required forward ≥0.15 m in eight seconds, forward yaw/roll ≤0.05 rad, and turn roll ≤0.1 rad; all passed. Report: `outputs/controls-mobility-stable.json`. Earlier reports remain separately recorded in `controls-mobility-before-ballast.json` and `controls-mobility-fix.json`.

Real native Tk tests passed repeat saturation, previous-turn release, release-to-zero, auto-repeat release/press pairing, emergency-stop rearming prevention, and window hiding/focus stop. These GUI tests use a fake transport so they cannot move the simulator. Actual Tk arrow-key events while the power slider had focus also passed: driving keys are intercepted before widget class bindings, so auto-repeat cannot raise the slider value. The separate physical tests exercise the actual TCP bridge, ROS command ordering and vehicle motion. Reports: `outputs/gui-controls-verification.json` and `outputs/tests-controls-final.log` (36 passed; three ROS-only modules skipped on macOS).

## Operation and limits

The simulator and updated GUI were restarted on `Perception`. For a fresh session, build with `bash src/tools/run.sh --build`; run the existing backend with `bash src/tools/run.sh`, or the explicitly selected A1 candidate with the local server and `bash src/tools/run-roboflow.sh`. Launch GUI with `bash src/tools/gui.sh`. Hold controls rather than repeatedly tapping. Release/repress held keys after an emergency stop or focus loss. Use the power slider for slower inspection or faster transit.

This three-thruster rig supports surge, yaw and heave; lateral translation and independently commanded pitch/roll are not provided. Single-heave reaction torque and transient coupling remain small but observable (about 1° yaw over this four-second test). Manual input does not hold heading, depth or position. Roboflow runtime gates remain unmet as previously measured; this control fix does not promote candidate weights or establish real-world accuracy. See [[Orientation Deployment Results]].

Post-change full-rig runtime check passed with 61 paired stereo timestamps, preserved detector headers, all sensor topics and transforms. Report: `outputs/runtime-mobility-fixed.json`.
