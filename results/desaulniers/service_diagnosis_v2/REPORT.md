# Corrected-final service-loss observations

All 270 corrected-final traces were independently replayed before this report. Rows describe unserved customers; they are not causal labels or proofs of infeasibility. `direct_idle_actions_at_first_decision` counts feasible immediate service actions with a safe return, not feasible route insertions or guaranteed complete routes. The decision trace does not preserve every rejected insertion or search candidate, so optimizer failure cannot be inferred solely from a missing selected plan.

Unserved customer observations: 491.

| Method | Unserved customer observations |
| --- | ---: |
| MPC_COMPLETION | 246 |
| MPC_MCTS | 126 |
| MPC_ALNS | 27 |
| MPC_HGS | 35 |
| MPC_ACS | 57 |

| Observable trace category | Count |
| --- | ---: |
| never_in_selected_plan | 429 |
| selected_in_plan_but_unserved | 62 |

## Highest-loss ALNS scenarios

These cases are retrospective descriptions of the fixed final holdout, not targets for algorithm tuning.

| Instance | DoD | Seed | ALNS served | Other methods served (Completion/MCTS/HGS/ACS) |
| --- | ---: | ---: | ---: | --- |
| c208_21_25 | 0.25 | 0 | 21/25 | 24/24/25/25 |
| r211_21_100 | 0.5 | 0 | 96/100 | 93/93/98/100 |
| r112_21_50 | 0.25 | 0 | 47/50 | 32/32/48/45 |
| r112_21_50 | 0.75 | 0 | 47/50 | 34/40/46/44 |
| rc108_21_25 | 0.5 | 0 | 22/25 | 20/23/24/22 |
| rc108_21_25 | 0.75 | 0 | 22/25 | 17/22/23/21 |
| r112_21_50 | 0.5 | 0 | 48/50 | 36/38/44/43 |
| rc108_21_25 | 0.25 | 0 | 23/25 | 19/19/23/22 |

## Example trace facts

For `c208_21_25`, DoD 0.25, seed 0, ALNS left 4 customers unserved. A selected plan can later change before its action executes; the trace does not prove why.

| Customer | Release | Deadline | Busy EVs at release | First visible decision | Direct feasible idle actions | Selected in a plan |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| C28 | 0.0 | 1993.0 | 0 | 0.0 | 2 | True |
| C44 | 0.0 | 1274.0 | 0 | 0.0 | 2 | True |
| C59 | 378.943805 | 1696.0 | 2 | 378.943805 | 0 | True |
| C98 | 0.0 | 719.0 | 0 | 0.0 | 2 | True |

The full customer-level table also records finished EVs, number of visible decisions before due, and trace category. These facts constrain, but do not establish, the causal mechanism.
