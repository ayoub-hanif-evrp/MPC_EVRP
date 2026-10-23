# Depot-window waiting: development mechanism pilot

This is a **selected-case development pilot**, not independent evaluation. The three cases were chosen for historical ALNS service losses before the new variants ran. Both policies used the same observable scenario, fixed fleet, service-first objective, five-second budget, and independent replay.

| Instance | DoD | Method | Original | Depot wait | Paired change | Original / wait max latency (s) |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| r101_21_100 | 0.75 | MPC_ALNS | 94/100 | 94/100 | +0 | 0.690 / 0.662 |
| r101_21_100 | 0.75 | MPC_COMPLETION | 82/100 | 82/100 | +0 | 0.042 / 0.042 |
| r101_21_50 | 0.5 | MPC_ALNS | 47/50 | 49/50 | +2 | 0.388 / 0.383 |
| r101_21_50 | 0.5 | MPC_COMPLETION | 48/50 | 48/50 | +0 | 0.038 / 0.039 |
| rc101_21_25 | 0.75 | MPC_ALNS | 22/25 | 21/25 | -1 | 0.096 / 0.098 |
| rc101_21_25 | 0.75 | MPC_COMPLETION | 23/25 | 23/25 | +0 | 0.012 / 0.014 |

## Interpretation

- MPC_COMPLETION: changes +0, +0, +0; mean +0.00 customers per selected case.
- MPC_ALNS: changes +0, +2, -1; mean +0.33 customers per selected case.

The result is mixed and too small/selected for inferential claims. The policy remains optional and is not the default. It must not be described as an established improvement or selected using historical robustness/final outcomes. No new final holdout was opened.
