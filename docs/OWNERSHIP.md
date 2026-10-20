# Ownership

Teammates implement against [INTERFACES.md](INTERFACES.md) and [TEAM_CONTRACTS.md](TEAM_CONTRACTS.md), without needing another subsystem's internal implementation.

| Ownership slot | Scope |
| --- | --- |
| Technical Lead / Integration | Cross-package contracts, composition, shared interfaces, release acceptance and bringup. |
| State Estimation | `neptune_state_estimation`, navigation quality and estimator validation. |
| Autonomy / Controls | `neptune_autonomy`, `neptune_controls`, mission and guidance behavior. |
| Perception | `neptune_perception`, models, observation contracts and evaluation inputs. |
| Simulation / World | `neptune_sim`, future `neptune_world`, environment fidelity and assets. |
| Vehicle / Hardware Interface | `neptune_vehicle`, actuator mapping and future hardware backends. |
| Evaluation / Testing | `neptune_evaluation`, metrics, datasets and cross-module regression evidence. |

These slots do not assign new teammate names. Existing repository assignments were: Sidhant (state estimation/integration/shared interfaces/bringup/vehicle oversight), Yuvi (perception/world), Robbie (autonomy), Neil (controls), and Kash (evaluation/datasets/training/benchmarking), with interfaces/sim/bringup shared. The team should confirm who fills each current slot; these historical assignments are retained for continuity, not expanded into new appointments.

Owners control internal implementation within their module when the external contract is preserved and package tests pass. Topic/type/frame/unit/sign/ownership/timing or semantic changes require Technical Lead / Integration review and affected downstream owner review. Cross-module PRs must identify affected ownership slots, update contracts and provide integration evidence. No owner may quietly redefine another package's boundary.
