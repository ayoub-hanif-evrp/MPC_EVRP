# Online Service Gap: Read-Only Final-Trace Postmortem

This supplement does not alter the frozen primary results in [RESULTS.md](../paper/RESULTS.md). The offline reference is a **feasible clairvoyant schedule**, not an online method or an optimality bound on distance.

## Reference verification

All 54 cached final scenarios and all six associated benchmark references were validated using the exact stored transition trace. Each reference serves all 100 customers with the same K_ref; every release is no later than its reference predecessor departure. This proves feasibility with advance knowledge, not attainability under online information.

## Service gap

| MPC method | Served / 5400 | Mean / 100 | Complete / 54 | Unserved |
| --- | --- | --- | --- | --- |
| MPC_ACS | 5324 | 98.59 | 24 | 76 |
| MPC_ALNS | 5364 | 99.33 | 38 | 36 |
| MPC_COMPLETION | 5090 | 94.26 | 5 | 310 |
| MPC_HGS | 5330 | 98.70 | 36 | 70 |
| MPC_MCTS | 5266 | 97.52 | 17 | 134 |
| MPC_PORTFOLIO | 5349 | 99.06 | 37 | 51 |

[PNG: service gap](figures/service_gap.png)

### Gap by family and dynamicity

Each family has nine scenarios per method; each DoD has 18. A gap of zero means every customer was served in that stratum.

| Family | Method | Unserved / 900 | Complete / 9 |
| --- | --- | --- | --- |
| C1 | MPC_ACS | 17 | 1 |
| C1 | MPC_ALNS | 4 | 6 |
| C1 | MPC_COMPLETION | 97 | 0 |
| C1 | MPC_HGS | 24 | 2 |
| C1 | MPC_MCTS | 46 | 0 |
| C1 | MPC_PORTFOLIO | 20 | 0 |
| C2 | MPC_ACS | 21 | 3 |
| C2 | MPC_ALNS | 0 | 9 |
| C2 | MPC_COMPLETION | 51 | 1 |
| C2 | MPC_HGS | 21 | 4 |
| C2 | MPC_MCTS | 24 | 3 |
| C2 | MPC_PORTFOLIO | 9 | 5 |
| R1 | MPC_ACS | 2 | 7 |
| R1 | MPC_ALNS | 0 | 9 |
| R1 | MPC_COMPLETION | 43 | 0 |
| R1 | MPC_HGS | 0 | 9 |
| R1 | MPC_MCTS | 0 | 9 |
| R1 | MPC_PORTFOLIO | 0 | 9 |
| R2 | MPC_ACS | 4 | 6 |
| R2 | MPC_ALNS | 17 | 4 |
| R2 | MPC_COMPLETION | 42 | 4 |
| R2 | MPC_HGS | 22 | 6 |
| R2 | MPC_MCTS | 14 | 3 |
| R2 | MPC_PORTFOLIO | 22 | 5 |
| RC1 | MPC_ACS | 15 | 3 |
| RC1 | MPC_ALNS | 1 | 8 |
| RC1 | MPC_COMPLETION | 39 | 0 |
| RC1 | MPC_HGS | 2 | 7 |
| RC1 | MPC_MCTS | 20 | 0 |
| RC1 | MPC_PORTFOLIO | 0 | 9 |
| RC2 | MPC_ACS | 17 | 4 |
| RC2 | MPC_ALNS | 14 | 2 |
| RC2 | MPC_COMPLETION | 38 | 0 |
| RC2 | MPC_HGS | 1 | 8 |
| RC2 | MPC_MCTS | 30 | 2 |
| RC2 | MPC_PORTFOLIO | 0 | 9 |

| DoD | Method | Unserved / 1800 | Complete / 18 |
| --- | --- | --- | --- |
| 0.25 | MPC_ACS | 22 | 8 |
| 0.25 | MPC_ALNS | 20 | 13 |
| 0.25 | MPC_COMPLETION | 95 | 2 |
| 0.25 | MPC_HGS | 24 | 14 |
| 0.25 | MPC_MCTS | 42 | 5 |
| 0.25 | MPC_PORTFOLIO | 23 | 13 |
| 0.5 | MPC_ACS | 39 | 6 |
| 0.5 | MPC_ALNS | 9 | 12 |
| 0.5 | MPC_COMPLETION | 119 | 1 |
| 0.5 | MPC_HGS | 29 | 12 |
| 0.5 | MPC_MCTS | 55 | 5 |
| 0.5 | MPC_PORTFOLIO | 15 | 10 |
| 0.75 | MPC_ACS | 15 | 10 |
| 0.75 | MPC_ALNS | 7 | 13 |
| 0.75 | MPC_COMPLETION | 96 | 2 |
| 0.75 | MPC_HGS | 17 | 10 |
| 0.75 | MPC_MCTS | 37 | 7 |
| 0.75 | MPC_PORTFOLIO | 13 | 14 |

[All missed customers and sampled decision evidence](tables/all_missed_customers.md)

## ALNS failure cases

| Instance | DoD | Seed | Served | Unserved |
| --- | --- | --- | --- | --- |
| r207_21 | 0.25 | 1 | 93 | 7 |
| r207_21 | 0.25 | 2 | 93 | 7 |
| rc204_21 | 0.25 | 1 | 96 | 4 |
| rc204_21 | 0.5 | 2 | 97 | 3 |
| rc204_21 | 0.75 | 0 | 97 | 3 |
| c102_21 | 0.5 | 0 | 98 | 2 |
| c102_21 | 0.25 | 0 | 99 | 1 |
| c102_21 | 0.75 | 2 | 99 | 1 |
| r207_21 | 0.5 | 0 | 99 | 1 |
| r207_21 | 0.5 | 1 | 99 | 1 |
| r207_21 | 0.75 | 1 | 99 | 1 |
| rc104_21 | 0.75 | 0 | 99 | 1 |
| rc204_21 | 0.25 | 0 | 99 | 1 |
| rc204_21 | 0.5 | 0 | 99 | 1 |
| rc204_21 | 0.5 | 1 | 99 | 1 |
| rc204_21 | 0.75 | 1 | 99 | 1 |

ALNS missed 36 customer opportunities. Of these, 18 appeared in a selected route at least once; 34 had a sampled direct-next-service opportunity from a ready vehicle at a recorded decision epoch.

| Descriptive evidence (exclusive) | Missed customers |
| --- | --- |
| direct service feasible at sampled decision | 16 |
| no sampled direct opportunity | 2 |
| planned in selected route | 18 |

[PNG: release versus due](figures/alns_release_due.png)

### Largest paired failure case

At r207_21, DoD 0.25, seeds 1 and 2, ALNS served 93/100 in each run with K_ref=3. The two runs account for 14/36 (39%) of ALNS's missed customers. Nine of those 14 appeared in at least one selected route; all 14 had a sampled direct-next-service opportunity. This shows that the missed customers were not uniformly invisible or individually unreachable at every recorded decision. It does not establish that serving them would have preserved the other 93 services. The case motivates development-only tests of plan retention and targeted service recovery.

### Per-customer evidence for MPC + ALNS

| Instance | DoD | Seed | Customer | Release | Due | Visible epochs | Planned epochs | Direct-feasible epochs | Last direct time | Ready/Busy/Finished at last visible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c102_21 | 0.25 | 0 | C73 | 268.2 | 361.0 | 129 | 0 | 0 | - | 1/12/0 |
| c102_21 | 0.5 | 0 | C77 | 454.1 | 600.0 | 114 | 0 | 1 | 467.0 | 1/12/0 |
| c102_21 | 0.5 | 0 | C80 | 612.4 | 689.0 | 92 | 0 | 1 | 646.0 | 1/12/0 |
| c102_21 | 0.75 | 2 | C83 | 554.9 | 618.0 | 91 | 0 | 0 | - | 1/12/0 |
| r207_21 | 0.25 | 1 | C30 | 252.0 | 694.0 | 96 | 0 | 30 | 646.0 | 1/2/0 |
| r207_21 | 0.25 | 1 | C40 | 0.0 | 901.0 | 129 | 24 | 79 | 881.0 | 1/2/0 |
| r207_21 | 0.25 | 1 | C69 | 401.2 | 650.0 | 81 | 0 | 15 | 617.9 | 1/2/0 |
| r207_21 | 0.25 | 1 | C83 | 0.0 | 968.0 | 129 | 3 | 89 | 920.6 | 1/2/0 |
| r207_21 | 0.25 | 1 | C89 | 444.8 | 746.0 | 77 | 0 | 24 | 718.6 | 1/2/0 |
| r207_21 | 0.25 | 1 | C90 | 309.6 | 704.0 | 90 | 0 | 27 | 653.2 | 1/2/0 |
| r207_21 | 0.25 | 1 | C96 | 0.0 | 974.0 | 129 | 4 | 93 | 958.7 | 1/2/0 |
| r207_21 | 0.25 | 2 | C15 | 442.3 | 959.0 | 78 | 9 | 59 | 936.2 | 1/2/0 |
| r207_21 | 0.25 | 2 | C23 | 0.0 | 953.0 | 130 | 29 | 101 | 937.4 | 1/2/0 |
| r207_21 | 0.25 | 2 | C36 | 0.0 | 948.0 | 130 | 30 | 95 | 917.5 | 1/2/0 |
| r207_21 | 0.25 | 2 | C38 | 527.1 | 780.0 | 69 | 0 | 23 | 753.4 | 1/2/0 |
| r207_21 | 0.25 | 2 | C49 | 0.0 | 946.0 | 130 | 30 | 89 | 900.8 | 1/2/0 |
| r207_21 | 0.25 | 2 | C64 | 0.0 | 890.0 | 130 | 30 | 85 | 857.3 | 1/2/0 |
| r207_21 | 0.25 | 2 | C86 | 150.1 | 954.0 | 107 | 20 | 76 | 931.7 | 1/2/0 |
| r207_21 | 0.5 | 0 | C46 | 31.5 | 276.0 | 152 | 0 | 36 | 206.7 | 1/2/0 |
| r207_21 | 0.5 | 1 | C72 | 12.9 | 298.0 | 150 | 0 | 55 | 279.5 | 1/2/0 |
| r207_21 | 0.75 | 1 | C72 | 12.9 | 298.0 | 154 | 0 | 55 | 279.5 | 1/2/0 |
| rc104_21 | 0.75 | 0 | C70 | 0.0 | 210.0 | 161 | 10 | 53 | 185.9 | 1/15/0 |
| rc204_21 | 0.25 | 0 | C89 | 524.3 | 897.0 | 77 | 6 | 33 | 867.5 | 1/3/0 |
| rc204_21 | 0.25 | 1 | C12 | 776.7 | 917.0 | 40 | 0 | 14 | 864.6 | 1/3/0 |
| rc204_21 | 0.25 | 1 | C16 | 81.2 | 300.0 | 126 | 0 | 9 | 288.3 | 1/3/0 |
| rc204_21 | 0.25 | 1 | C87 | 306.0 | 501.0 | 103 | 0 | 9 | 461.5 | 1/3/0 |
| rc204_21 | 0.25 | 1 | C94 | 0.0 | 932.0 | 138 | 8 | 86 | 920.4 | 1/3/0 |
| rc204_21 | 0.5 | 0 | C89 | 524.3 | 897.0 | 78 | 0 | 39 | 850.9 | 1/3/0 |
| rc204_21 | 0.5 | 1 | C16 | 81.2 | 300.0 | 135 | 0 | 9 | 288.3 | 1/3/0 |
| rc204_21 | 0.5 | 2 | C57 | 0.0 | 923.0 | 139 | 4 | 91 | 885.3 | 1/3/0 |
| rc204_21 | 0.5 | 2 | C66 | 0.0 | 936.0 | 139 | 10 | 100 | 916.1 | 1/3/0 |
| rc204_21 | 0.5 | 2 | C86 | 0.0 | 917.0 | 139 | 2 | 86 | 885.3 | 1/3/0 |
| rc204_21 | 0.75 | 0 | C11 | 0.0 | 916.0 | 135 | 13 | 83 | 879.0 | 1/3/0 |
| rc204_21 | 0.75 | 0 | C89 | 524.3 | 897.0 | 74 | 5 | 36 | 852.8 | 1/3/0 |
| rc204_21 | 0.75 | 0 | C9 | 0.0 | 916.0 | 135 | 12 | 85 | 899.8 | 1/3/0 |
| rc204_21 | 0.75 | 1 | C16 | 81.2 | 300.0 | 134 | 0 | 9 | 288.3 | 1/3/0 |

## Instance-clustered sensitivity

| First | Second | Paired mean gain | 95% cluster-bootstrap CI |
| --- | --- | --- | --- |
| MPC_MCTS | MPC_COMPLETION | 3.26 | [2.02, 4.50] |
| MPC_ALNS | MPC_COMPLETION | 5.07 | [3.31, 7.35] |
| MPC_ALNS | MPC_PORTFOLIO | 0.28 | [-0.57, 1.07] |

The percentile intervals enumerate all 6^6 resamples of the six benchmark instances, retaining each instance's nine DoD/seed scenarios together. They are descriptive robustness intervals with only six independent clusters; they do not replace the preregistered scenario-paired analysis or adjust for method selection.

## Interpretation and limits

A selected plan is a forecast, not an executed route. A direct-feasible observation means an immediate service action plus safe depot escape passed the common physics at one recorded decision state. It does not show a feasible multi-customer insertion or prove that taking the action would improve final service. A missing sampled direct opportunity does not prove infeasibility: charging-mediated routes, busy vehicle continuations, and states between recorded epochs are not exhaustively tested. Fleet availability counts are at the last visible decision, not necessarily at the customer's final feasible time. These are observational classifications, not causal failure labels.

The R2 r207_21 DoD 0.25 seed 1 and 2 cases are the largest ALNS losses. They can motivate hypotheses about fleet flexibility or recovery, but are seen holdout instances and must not be used to select a new policy. Any new controller must be developed on development data and evaluated in a separately preregistered unused-instance study with the fixed baselines rerun.

## Reproduction

Run `python -m scripts.diagnose_final_service_loss`. The script checks the frozen manifest, protocol/source hashes, all 324 raw checksums and audits, 54 scenario identities, and six full-service references. It reads final evidence and writes only this postmortem directory. Figures are PNG at 300 dpi; tables are Markdown.
