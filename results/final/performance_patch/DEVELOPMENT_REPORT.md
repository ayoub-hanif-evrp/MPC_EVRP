# Final Performance Patch: Development Verdict

Frozen source SHA-256: `4cdead8ab9956362ba9921c0818b7bcc9690487ab11ba001d087abebe43176b6`; Git commit: `30e485d`.
All 36 runs completed, passed independent trace audit, shared their paired
scenario hashes, and stayed below five seconds per optimization call.
The six-static prerequisite passed at 600/600. No holdout was run.

## Primary Benchmark Outcomes

Service: Fleet MPC-MCTS **1180/1200**, Rolling-LNS **1196/1200**, completion-only **1132/1200**. Complete-instance rates: 3/12, 10/12, and 0/12, respectively.
Fleet vs Rolling-LNS service W/T/L: **1/3/8**; Fleet vs completion-only: **11/1/0**.

| Instance | Seed | Fleet | LNS | Completion | Fleet-LNS | Fleet-Completion | EVs F/L/C | Distance F/L/C | Conditional EV F-L | Conditional distance F-L |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
| c101_21 | 0 | 99 | 100 | 92 | -1 | +7 | 13/12/13 | 1477.8/1180.2/1815.6 | n/a | n/a |
| c101_21 | 1 | 97 | 99 | 92 | -2 | +5 | 13/13/13 | 1562.4/1332.5/1742.6 | n/a | n/a |
| c201_21 | 0 | 97 | 100 | 93 | -3 | +4 | 5/5/5 | 1597.9/912.0/1551.5 | n/a | n/a |
| c201_21 | 1 | 100 | 100 | 97 | +0 | +3 | 5/5/5 | 1364.2/1312.8/1532.4 | 0 | 51.4 |
| r101_21 | 0 | 97 | 100 | 92 | -3 | +5 | 20/20/20 | 1975.3/1800.8/2088.2 | n/a | n/a |
| r101_21 | 1 | 99 | 97 | 93 | +2 | +6 | 20/20/20 | 2038.4/1734.5/2122.2 | n/a | n/a |
| r201_21 | 0 | 100 | 100 | 99 | +0 | +1 | 4/4/4 | 1967.0/1894.6/2086.2 | 0 | 72.3 |
| r201_21 | 1 | 99 | 100 | 97 | -1 | +2 | 4/4/4 | 2170.0/1709.5/1914.0 | n/a | n/a |
| rc101_21 | 0 | 96 | 100 | 89 | -4 | +7 | 20/21/21 | 2152.5/2206.0/2571.1 | n/a | n/a |
| rc101_21 | 1 | 99 | 100 | 94 | -1 | +5 | 21/20/21 | 2452.1/2085.6/2722.9 | n/a | n/a |
| rc201_21 | 0 | 97 | 100 | 97 | -3 | +0 | 5/5/5 | 2938.6/1988.8/2493.2 | n/a | n/a |
| rc201_21 | 1 | 100 | 100 | 97 | +0 | +3 | 5/5/5 | 2597.3/2459.9/2557.4 | 0 | 137.3 |

Raw EV and distance columns are descriptive only. The conditional EV
difference is shown only at equal service; the conditional distance
difference is shown only at equal service and equal activated EVs.

## Internal MPC Search Diagnostics

`R_CTRL` and `R_FLEX` are search guidance, not primary benchmark wins.
The root-to-final column counts additional released customers reserved
within MCTS calls, not extra physical services over the paired ablation.

| Instance | Seed | R_CTRL | R_FLEX | MCTS calls / service-gain calls | Root-to-final gain | Equal-service objective / EV / distance gain calls | Iterations / nodes | Rollouts / mean inserted | Screens / decodes | Cache hit | p95 / max trigger s | Wall s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| c101_21 | 0 | 0.283 | 0.525 | 113 / 0 | 0 (0.00/call) | 39/5/18 | 27993 / 9561 | 27993 / 0.000 | 5966 / 54 (110.5:1) | 99.7% | 4.604 / 4.623 | 146.8 |
| c101_21 | 1 | 0.264 | 0.516 | 128 / 1 | 1 (0.01/call) | 31/4/14 | 31002 / 7964 | 31002 / 0.000 | 16164 / 168 (96.2:1) | 99.5% | 4.615 / 4.632 | 170.9 |
| c201_21 | 0 | 0.249 | 0.539 | 125 / 1 | 1 (0.01/call) | 21/1/6 | 23999 / 191 | 23999 / 0.000 | 9188 / 525 (17.5:1) | 96.1% | 4.698 / 4.756 | 152.8 |
| c201_21 | 1 | 0.182 | 0.448 | 67 / 0 | 0 (0.00/call) | 45/0/16 | 5381 / 4207 | 5381 / 0.000 | 0 / 0 (0.0:1) | 99.5% | 4.750 / 4.787 | 250.3 |
| r101_21 | 0 | 0.218 | 0.485 | 137 / 0 | 0 (0.00/call) | 31/5/17 | 35072 / 8548 | 35072 / 0.000 | 11883 / 136 (87.4:1) | 99.5% | 1.555 / 2.134 | 47.1 |
| r101_21 | 1 | 0.213 | 0.528 | 118 / 1 | 1 (0.01/call) | 41/9/14 | 30208 / 11747 | 30208 / 0.000 | 3291 / 995 (3.3:1) | 99.7% | 2.077 / 2.298 | 79.1 |
| r201_21 | 0 | 0.143 | 0.594 | 56 / 1 | 1 (0.02/call) | 15/0/7 | 2316 / 946 | 2316 / 0.000 | 2040 / 196 (10.4:1) | 99.0% | 4.762 / 4.783 | 228.5 |
| r201_21 | 1 | 0.196 | 0.612 | 121 / 2 | 3 (0.02/call) | 1/0/0 | 21519 / 18 | 21519 / 0.000 | 11199 / 64 (175.0:1) | 92.9% | 4.751 / 4.860 | 182.4 |
| rc101_21 | 0 | 0.208 | 0.574 | 149 / 0 | 0 (0.00/call) | 26/7/14 | 38116 / 7908 | 38116 / 0.000 | 19648 / 26 (755.7:1) | 99.2% | 2.107 / 4.605 | 62.2 |
| rc101_21 | 1 | 0.222 | 0.586 | 156 / 0 | 0 (0.00/call) | 28/7/13 | 39936 / 8167 | 39936 / 0.000 | 13046 / 20 (652.3:1) | 99.5% | 3.647 / 4.435 | 102.1 |
| rc201_21 | 0 | 0.201 | 0.633 | 134 / 2 | 3 (0.02/call) | 6/0/4 | 28976 / 48 | 28976 / 0.000 | 15547 / 331 (47.0:1) | 92.7% | 4.750 / 4.775 | 110.8 |
| rc201_21 | 1 | 0.151 | 0.574 | 59 / 1 | 8 (0.14/call) | 13/0/5 | 2427 / 1266 | 2427 / 0.005 | 3158 / 18 (175.4:1) | 98.9% | 4.752 / 4.762 | 242.1 |

Across all Fleet calls, `EJECTION_CHAIN_2` generated 513 chains, found 13 feasible chains, and selected 13 tree actions.
Screens/decodes and their ratio use service-phase MCTS calls only;
the CSV separately retains exact decoder calls over all MCTS calls.
The CSV contains per-case wall/p95/max timings for all three methods.

## Stop-Rule Verdict

**Strong development is not achieved.** Fleet MPC-MCTS improves service
over its shared-constructor completion-only ablation on multiple cases,
but serves 16 fewer customers than Rolling-LNS overall and loses service
on 8 of 12 matched scenarios. The static 600/600 success
therefore does not establish dynamic service competitiveness.
Per the absolute stop rule, no further algorithm tuning, secondary route
pool, or untouched holdout campaign is run. This is a limitation report,
not a positive final-paper performance claim. No optimality is claimed.
No figures were generated; no PDF artifacts were created.
