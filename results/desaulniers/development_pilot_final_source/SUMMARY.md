# Desaulniers MP Development Pilot

These are **development engineering checks**, not a final holdout or a statistical ranking. Each size has one C1 instance, DoD 0.25 and seed 0; all five methods receive the same dynamic scenario and K_ref. The published full-charge reference is used offline under the more permissive MP policy, never as an online route or objective baseline.

| Size | Method | Served | Complete | EVs | Distance | Charge visits | Charge time | Mean decision s | p95 decision s | Max decision s | Worker s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | MPC_COMPLETION | 25/25 | yes | 7 | 912.84 | 15 | 1346.32 | 0.008 | 0.020 | 0.050 | 0.2 |
| 25 | MPC_MCTS | 25/25 | yes | 6 | 812.91 | 12 | 1437.70 | 0.821 | 2.227 | 3.240 | 12.5 |
| 25 | MPC_ALNS | 25/25 | yes | 6 | 874.36 | 15 | 1565.40 | 0.234 | 0.873 | 1.091 | 3.7 |
| 25 | MPC_HGS | 25/25 | yes | 6 | 1033.89 | 21 | 2382.57 | 1.090 | 3.367 | 4.220 | 19.8 |
| 25 | MPC_ACS | 25/25 | yes | 6 | 867.39 | 15 | 1480.40 | 0.215 | 0.794 | 0.995 | 3.8 |
| 50 | MPC_COMPLETION | 49/50 | no | 9 | 1172.80 | 14 | 1675.15 | 0.015 | 0.029 | 0.249 | 1.1 |
| 50 | MPC_MCTS | 50/50 | yes | 9 | 1054.24 | 14 | 1519.96 | 1.666 | 4.612 | 4.648 | 46.9 |
| 50 | MPC_ALNS | 50/50 | yes | 8 | 1018.35 | 14 | 1724.35 | 1.657 | 4.645 | 4.652 | 43.4 |
| 50 | MPC_HGS | 50/50 | yes | 9 | 1260.53 | 21 | 2621.04 | 2.456 | 4.645 | 4.671 | 61.7 |
| 50 | MPC_ACS | 50/50 | yes | 8 | 883.92 | 12 | 1199.53 | 1.613 | 4.663 | 4.672 | 40.6 |
| 100 | MPC_COMPLETION | 89/100 | no | 12 | 1838.47 | 37 | 3112.56 | 0.049 | 0.080 | 0.679 | 6.5 |
| 100 | MPC_MCTS | 89/100 | no | 12 | 1619.66 | 28 | 2407.56 | 0.155 | 0.121 | 3.849 | 19.1 |
| 100 | MPC_ALNS | 100/100 | yes | 12 | 1614.81 | 29 | 2606.88 | 2.016 | 4.655 | 4.692 | 95.5 |
| 100 | MPC_HGS | 95/100 | no | 12 | 1647.28 | 26 | 2744.88 | 2.211 | 4.651 | 4.664 | 261.6 |
| 100 | MPC_ACS | 99/100 | no | 12 | 1416.42 | 20 | 2002.76 | 2.103 | 4.655 | 4.669 | 223.5 |

[PNG: service by size](figures/pilot_service_by_size.png)

All 15 workers were isolated and independently replay-audited. Every recorded battery, capacity, time-window, and hidden-information violation count is zero; each maximum decision latency is at most five seconds. Distance and EV count must be compared conditionally on equal service, not ranked unconditionally when methods serve different customers.

Fresh-process isolation does not imply an idle machine. Other user jobs were active during this pilot, so the worker/latency measurements are not isolated real-time benchmarks and should not support a quality-versus-compute claim.

Dataset fingerprint: `02011e3273fef190bd61cc223b4504d8265ca5be30ccf02a34f674f27d58741e`. Source fingerprint: `940725dfef5f0803fddfcfba582b44ca57c6b45ce36bd8e4abee264cd111dfbf`.

Reproduce with `python -m scripts.run_desaulniers_pilot` followed by `python -m scripts.analyze_desaulniers_pilot`. The runner reuses only raw files whose manifest SHA-256 matches and rejects protocol drift.
