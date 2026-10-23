# MPC enhancement diagnosis

This is a read-only analysis of frozen traces. Development cases may guide new work; historical robustness cases are descriptive only and must not be tuning targets.

Every source raw SHA-256 was checked against its manifest; each result was independently replayed. Every scenario has an audited full-service reference whose customer dispatches occur after release. This is a **clairvoyant offline feasibility reference, not a valid online MPC competitor**.

## Audit and observations

| Cohort | Audited runs | Unserved customer observations |
| --- | ---: | ---: |
| development | 270 | 389 |
| historical_robustness | 450 | 1439 |

| Cohort | Trace observation | Count |
| --- | --- | ---: |
| development | no_direct_ready_action | 355 |
| development | selected_but_unserved | 34 |
| historical_robustness | direct_ready_action_unselected | 11 |
| historical_robustness | no_direct_ready_action | 1237 |
| historical_robustness | selected_but_unserved | 191 |

`direct_ready_action_unselected` means one immediate service action passed the plant's safe-return check at the first visible decision. It does not prove a feasible insertion preserving other work, or establish a causal error. `no_direct_ready_action` does not prove route infeasibility because a charging stop or later dispatch may work. A soft plan may be replanned before execution.

## Five-second budget

| Cohort | Method | Decisions | Mean / p95 / max latency (s) | Constructor / optimizer / other measured time (s) | Screened / decoded |
| --- | --- | ---: | --- | --- | --- |
| development | MPC_ACS | 3141 | 1.778 / 4.748 / 4.792 | 117.4 / 4812.6 / 655.7 | 427554 / 4677 |
| development | MPC_ALNS | 2906 | 1.597 / 4.751 / 4.834 | 128.2 / 3352.0 / 1160.8 | 336211 / 3695 |
| development | MPC_COMPLETION | 3308 | 0.039 / 0.166 / 2.018 | 105.5 / 6.0 / 18.5 | 658781 / 6207 |
| development | MPC_HGS | 3052 | 2.396 / 4.751 / 4.826 | 121.9 / 6108.8 / 1081.5 | 381177 / 4104 |
| development | MPC_MCTS | 3126 | 1.405 / 4.751 / 4.803 | 144.3 / 3253.7 / 995.4 | 488830 / 5043 |
| historical_robustness | MPC_ACS | 5671 | 1.665 / 4.662 / 4.782 | 145.6 / 8883.6 / 412.5 | 1089601 / 11847 |
| historical_robustness | MPC_ALNS | 4790 | 1.539 / 4.739 / 4.780 | 167.2 / 6201.3 / 1002.9 | 505786 / 8128 |
| historical_robustness | MPC_COMPLETION | 5962 | 0.041 / 0.108 / 2.012 | 208.4 / 12.0 / 26.6 | 2427830 / 32042 |
| historical_robustness | MPC_HGS | 5747 | 2.199 / 4.706 / 4.796 | 210.1 / 11582.5 / 847.7 | 970491 / 14888 |
| historical_robustness | MPC_MCTS | 5961 | 1.065 / 4.702 / 4.791 | 205.3 / 5240.6 / 904.1 | 1554817 / 20454 |

Other measured time is the residual, including final validation, coordination, and fallback; these components cannot be separated for every method from existing traces. The per-decision five-second budget remains unchanged. CSVs retain customer-level and timing evidence.

## Development failure cases

| Instance | DoD | Seed | ALNS losses | Direct-ready unselected | Selected then unserved |
| --- | ---: | ---: | ---: | ---: | ---: |
| r101_21_100 | 0.75 | 0 | 6 | 0 | 2 |
| r101_21_100 | 0.5 | 0 | 3 | 0 | 1 |
| r101_21_50 | 0.5 | 0 | 3 | 0 | 0 |
| r101_21_50 | 0.75 | 0 | 3 | 0 | 0 |
| rc101_21_25 | 0.75 | 0 | 3 | 0 | 2 |
| c101_21_100 | 0.25 | 0 | 2 | 0 | 1 |
| c101_21_100 | 0.75 | 0 | 2 | 0 | 0 |
| c201_21_100 | 0.5 | 0 | 2 | 0 | 0 |
| r101_21_25 | 0.75 | 0 | 2 | 0 | 1 |
| rc101_21_50 | 0.5 | 0 | 2 | 0 | 0 |
| c101_21_100 | 0.5 | 0 | 1 | 0 | 1 |
| r101_21_100 | 0.25 | 0 | 1 | 0 | 1 |

For ALNS development losses, 7 of 33 had at least one plant-validated, charging-aware one-customer route at their first visible decision. This does not establish a service-preserving insertion into the other selected routes.

These are measured opportunities and trace outcomes, not proofs of why a route failed. Existing traces do not retain rejected insertions, so constructor/decoder failure and online-commitment loss require separate instrumented development experiments.
