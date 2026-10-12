---
tags: [neptune, gui, autonomy]
date: 2026-10-11
---
# Autonomous power control

See [[One Minute Mission Experiment]], [[Automated Inspection Mission]], [[Faster Mission and View Priority]], [[Progress]], [[Home]].

The GUI includes an **Autonomous power (%)** slider beneath **Start mapped inspection**, independent of manual power. Range: 20–100%, 5% steps, startup default 100%. Changes apply while idle or during inspection/return without canceling the mission or clearing visual confirmations. The GUI shows pending and controller-confirmed applied values.

The setting is a relative translation-control level, not measured electrical wattage. Cruise and side cruise velocity targets scale by percentage; normalized translation rotor limits scale by its square root, making the nominal maximum translation thrust proportional to percentage. Actual propeller thrust depends on water flow. Yaw/depth stabilization gains and authority remain unchanged. Both mapped inspection, its return phase, and the standalone Return to spawn use the setting. The 60-second mission deadline does not change: a slow mission can time out.

The bridge validates finite numbers in [20,100], rejects booleans and malformed values, and publishes `/neptune/control/autonomous_power` (`std_msgs/Float64`, transient-local). The controller recomputes settings from immutable base profiles, so repeated changes do not compound or overwrite the nominal profile. Telemetry includes `autonomous_power_percent`. Stop, manual override, sensor-health and disconnect safeguards remain active.

Source: `src/neptune_sim/neptune_sim/autonomous_power.py`, `operator_state.py`, `bridge.py`, and `src/neptune_gui/auv_gui.py`. No dependency added.

Verification: **87 host tests passed; four ROS-only skipped**. Native Tk slider request and confirmation checks passed with existing controls. Live verification changes 100→60→100 during a mission, checks malformed requests leave the current setting unchanged, and checks all four visits plus return. Measured outcome is appended after completion. Logs/reports are ignored under `outputs/autonomous-power-*`.

Live verification **passed**: default 100%, in-mission 60% applied without canceling, malformed requests ignored, 100% restored without canceling, all four target visits plus return completed in **36.91 seconds**, true spawn error **4.83 cm**. Report: `outputs/autonomous-power-live.json`. Simulator reset to spawn and updated GUI restarted for the user. Inference remains running.
