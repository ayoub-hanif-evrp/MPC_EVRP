# Multi-seed robustness v3

Protocol: `2b1455ef958f14f9d4dcabc4bfd5098fa2e79d2a644426862ab90a8b942eb266`; audited raw runs: 450/450; predeclared ineligible scenarios: 0; status: complete.

All existing raw files passed SHA-256, identity, five-second budget, and independent trace replay checks.

## Overall

Distance is conditional on the common set of complete-service scenarios.

| Method | N | Served % | Complete % | EV mean | Distance matched | Matched N |
| --- | --- | --- | --- | --- | --- | --- |
| MPC_COMPLETION | 90 | 87.35 | 44.4 | 7.22 | 995.36 | 39 |
| MPC_MCTS | 90 | 92.84 | 50.0 | 7.09 | 1001.41 | 39 |
| MPC_ALNS | 90 | 98.95 | 70.0 | 7.01 | 1017.67 | 39 |
| MPC_HGS | 90 | 97.47 | 64.4 | 7.02 | 1044.99 | 39 |
| MPC_ACS | 90 | 95.98 | 54.4 | 7.09 | 772.34 | 39 |

## Runtime and operations

Decision statistics pool all recorded optimization decisions. Worker time is sequential wall time per isolated run; charging and waiting use benchmark model-time units. Violation totals include hidden-information, time-window, battery, capacity, and duplicate-service checks.

| Method | Decisions | Mean s | p95 s | Max s | Worker mean s | Worker total h | Charge visits mean | Charge time mean | Wait time mean | Violations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MPC_COMPLETION | 5962 | 0.041 | 0.108 | 2.012 | 2.9 | 0.07 | 18.6 | 942.7 | 2722.9 | 0 |
| MPC_MCTS | 5961 | 1.065 | 4.702 | 4.791 | 70.7 | 1.77 | 16.1 | 831.4 | 2742.4 | 0 |
| MPC_ALNS | 4790 | 1.539 | 4.739 | 4.780 | 82.1 | 2.05 | 17.5 | 835.6 | 2591.1 | 0 |
| MPC_HGS | 5747 | 2.199 | 4.706 | 4.796 | 140.7 | 3.52 | 19.0 | 978.5 | 2440.5 | 0 |
| MPC_ACS | 5671 | 1.665 | 4.662 | 4.782 | 105.1 | 2.63 | 14.9 | 573.1 | 3051.4 | 0 |

## By seed

| Seed | Method | N | Served % | Complete % |
| --- | --- | --- | --- | --- |
| 1 | MPC_COMPLETION | 18 | 87.05 | 50.0 |
| 1 | MPC_MCTS | 18 | 93.52 | 44.4 |
| 1 | MPC_ALNS | 18 | 98.95 | 72.2 |
| 1 | MPC_HGS | 18 | 97.43 | 55.6 |
| 1 | MPC_ACS | 18 | 96.86 | 55.6 |
| 2 | MPC_COMPLETION | 18 | 87.14 | 44.4 |
| 2 | MPC_MCTS | 18 | 93.14 | 50.0 |
| 2 | MPC_ALNS | 18 | 98.76 | 66.7 |
| 2 | MPC_HGS | 18 | 97.62 | 66.7 |
| 2 | MPC_ACS | 18 | 95.62 | 50.0 |
| 3 | MPC_COMPLETION | 18 | 86.86 | 44.4 |
| 3 | MPC_MCTS | 18 | 92.00 | 55.6 |
| 3 | MPC_ALNS | 18 | 99.33 | 72.2 |
| 3 | MPC_HGS | 18 | 97.43 | 66.7 |
| 3 | MPC_ACS | 18 | 95.71 | 55.6 |
| 4 | MPC_COMPLETION | 18 | 87.81 | 38.9 |
| 4 | MPC_MCTS | 18 | 92.48 | 50.0 |
| 4 | MPC_ALNS | 18 | 98.38 | 66.7 |
| 4 | MPC_HGS | 18 | 97.81 | 66.7 |
| 4 | MPC_ACS | 18 | 95.71 | 55.6 |
| 5 | MPC_COMPLETION | 18 | 87.90 | 44.4 |
| 5 | MPC_MCTS | 18 | 93.05 | 50.0 |
| 5 | MPC_ALNS | 18 | 99.33 | 72.2 |
| 5 | MPC_HGS | 18 | 97.05 | 66.7 |
| 5 | MPC_ACS | 18 | 96.00 | 55.6 |

## By size

| Size | Method | N | Served % | Complete % |
| --- | --- | --- | --- | --- |
| 25 | MPC_COMPLETION | 30 | 92.53 | 50.0 |
| 25 | MPC_MCTS | 30 | 95.87 | 53.3 |
| 25 | MPC_ALNS | 30 | 98.40 | 66.7 |
| 25 | MPC_HGS | 30 | 99.33 | 86.7 |
| 25 | MPC_ACS | 30 | 96.67 | 53.3 |
| 50 | MPC_COMPLETION | 30 | 99.40 | 83.3 |
| 50 | MPC_MCTS | 30 | 99.60 | 96.7 |
| 50 | MPC_ALNS | 30 | 100.00 | 100.0 |
| 50 | MPC_HGS | 30 | 100.00 | 100.0 |
| 50 | MPC_ACS | 30 | 100.00 | 100.0 |
| 100 | MPC_COMPLETION | 30 | 80.03 | 0.0 |
| 100 | MPC_MCTS | 30 | 88.70 | 0.0 |
| 100 | MPC_ALNS | 30 | 98.57 | 43.3 |
| 100 | MPC_HGS | 30 | 95.73 | 6.7 |
| 100 | MPC_ACS | 30 | 93.80 | 10.0 |

## By family

| Family | Method | N | Served % | Complete % |
| --- | --- | --- | --- | --- |
| C1 | MPC_COMPLETION | 15 | 83.20 | 0.0 |
| C1 | MPC_MCTS | 15 | 91.60 | 0.0 |
| C1 | MPC_ALNS | 15 | 99.47 | 66.7 |
| C1 | MPC_HGS | 15 | 96.47 | 13.3 |
| C1 | MPC_ACS | 15 | 98.00 | 20.0 |
| C2 | MPC_COMPLETION | 15 | 98.80 | 66.7 |
| C2 | MPC_MCTS | 15 | 99.20 | 93.3 |
| C2 | MPC_ALNS | 15 | 100.00 | 100.0 |
| C2 | MPC_HGS | 15 | 100.00 | 100.0 |
| C2 | MPC_ACS | 15 | 100.00 | 100.0 |
| R1 | MPC_COMPLETION | 15 | 76.87 | 0.0 |
| R1 | MPC_MCTS | 15 | 85.80 | 0.0 |
| R1 | MPC_ALNS | 15 | 97.67 | 20.0 |
| R1 | MPC_HGS | 15 | 95.00 | 0.0 |
| R1 | MPC_ACS | 15 | 89.60 | 0.0 |
| R2 | MPC_COMPLETION | 15 | 100.00 | 100.0 |
| R2 | MPC_MCTS | 15 | 100.00 | 100.0 |
| R2 | MPC_ALNS | 15 | 100.00 | 100.0 |
| R2 | MPC_HGS | 15 | 100.00 | 100.0 |
| R2 | MPC_ACS | 15 | 100.00 | 100.0 |
| RC1 | MPC_COMPLETION | 15 | 85.07 | 0.0 |
| RC1 | MPC_MCTS | 15 | 91.73 | 6.7 |
| RC1 | MPC_ALNS | 15 | 96.80 | 33.3 |
| RC1 | MPC_HGS | 15 | 98.67 | 73.3 |
| RC1 | MPC_ACS | 15 | 93.33 | 6.7 |
| RC2 | MPC_COMPLETION | 15 | 100.00 | 100.0 |
| RC2 | MPC_MCTS | 15 | 100.00 | 100.0 |
| RC2 | MPC_ALNS | 15 | 100.00 | 100.0 |
| RC2 | MPC_HGS | 15 | 100.00 | 100.0 |
| RC2 | MPC_ACS | 15 | 100.00 | 100.0 |

## By target dod

| Target DoD | Method | N | Served % | Complete % |
| --- | --- | --- | --- | --- |
| 0.25 | MPC_COMPLETION | 30 | 89.03 | 46.7 |
| 0.25 | MPC_MCTS | 30 | 92.23 | 50.0 |
| 0.25 | MPC_ALNS | 30 | 99.43 | 80.0 |
| 0.25 | MPC_HGS | 30 | 97.03 | 70.0 |
| 0.25 | MPC_ACS | 30 | 96.69 | 63.3 |
| 0.5 | MPC_COMPLETION | 30 | 85.14 | 40.0 |
| 0.5 | MPC_MCTS | 30 | 92.80 | 46.7 |
| 0.5 | MPC_ALNS | 30 | 99.26 | 70.0 |
| 0.5 | MPC_HGS | 30 | 97.71 | 63.3 |
| 0.5 | MPC_ACS | 30 | 95.54 | 50.0 |
| 0.75 | MPC_COMPLETION | 30 | 87.89 | 46.7 |
| 0.75 | MPC_MCTS | 30 | 93.49 | 53.3 |
| 0.75 | MPC_ALNS | 30 | 98.17 | 60.0 |
| 0.75 | MPC_HGS | 30 | 97.66 | 60.0 |
| 0.75 | MPC_ACS | 30 | 95.71 | 50.0 |

## Paired contrasts

Descriptive 95% percentile intervals resample base instances (6 clusters), retaining all DoD and seed repeats. They are not confirmatory multiple-testing-adjusted significance claims.

| Method | Baseline | Mean pp | Cluster 95% CI pp | Wins | Ties | Losses |
| --- | --- | --- | --- | --- | --- | --- |
| MPC_MCTS | MPC_COMPLETION | +4.07 | [+1.18, +7.09] | 45 | 43 | 2 |
| MPC_ALNS | MPC_COMPLETION | +8.33 | [+2.16, +15.07] | 50 | 40 | 0 |
| MPC_HGS | MPC_COMPLETION | +7.70 | [+2.27, +13.54] | 50 | 40 | 0 |
| MPC_ACS | MPC_COMPLETION | +6.17 | [+1.58, +11.10] | 47 | 42 | 1 |
| MPC_ALNS | MPC_HGS | +0.63 | [-0.62, +1.94] | 25 | 54 | 11 |
