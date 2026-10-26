# Hybrid GPU/CPU acceleration and service-first development pilot

Status: complete; 53/53 workers; 25/25 full-scenario pairs.
Frozen execution commit: `73059b1c0f3769c7510ffa5c469bc77ad06ce9f6`. Source SHA-256: `ae5990a4a8427a7a4217fb290329e2994e3462b4ae054a95e94bac1b2b3346cc`.
These are previously generated development parents, not an independent final test. Historical paper results remain untouched.
All five MPC engines retain the same original physical simulator, fixed fleet, objective, and five-second decision cap. Enhancements are opt-in.

## Hardware and kernel screen

RTX A2000 12GB, NVIDIA driver 596.71, CUDA runtime 13.2; Windows, Python 3.12.10; isolated CuPy 14.2.0 and Numba 0.68 environment.
The GPU benchmark includes host/device transfer and synchronization; it does not beat compiled CPU at observed insertion-batch sizes. No GPU context is used in the full MPC runs: GPU processing time and workload utilization are 0/not applicable, not missing speedups.
The hybrid dispatcher therefore selects compiled CPU on this workstation. The original Python path remains the fallback if Numba is absent.
Standalone benchmark: `kernel_benchmark.json` (SHA-256 `8bd717dc51e6aa67018409f96458db0695f6510c5b4db35b93f4d5b87ab0e0a0`).

## Fixed-work checks

| Case | Screened gaps | Compiled batches | Proven late | Python s | Compiled s | Objective/options |
| --- | --- | --- | --- | --- | --- | --- |
| c101_21_25 | 310 | 94 | 243 | 0.00421 | 0.00303 | identical |
| c201_21_50 | 227 | 75 | 167 | 0.00276 | 0.00208 | identical |
| r101_21_100 | 327 | 147 | 217 | 0.01000 | 0.00762 | identical |

## End-to-end paired results

Stage B compares original against opt-in compiled CPU plus the existing incremental screen/cache. Stage C independently compares original against opt-in quality/recovery; it does not combine Stage B and C.
Alternating pair order, fresh sequential workers, one numerical-library thread per worker. Timings are shared-machine observations.

| Stage | Method | Pairs | Original served | Enhanced served | Original complete | Enhanced complete | Original wall s | Enhanced wall s | Original CPU s | Enhanced CPU s | Equal-service pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B | MPC_COMPLETION | 3 | 166/175 | 166/175 | 2/3 | 2/3 | 6.57 | 6.66 | 0.03 | 0.02 | 3 |
| B | MPC_MCTS | 3 | 173/175 | 173/175 | 2/3 | 2/3 | 232.02 | 177.31 | 0.00 | 0.00 | 3 |
| B | MPC_ALNS | 3 | 174/175 | 174/175 | 2/3 | 2/3 | 188.15 | 149.64 | 0.02 | 0.00 | 3 |
| B | MPC_HGS | 3 | 175/175 | 174/175 | 3/3 | 2/3 | 345.63 | 303.79 | 0.02 | 0.02 | 2 |
| B | MPC_ACS | 3 | 172/175 | 171/175 | 2/3 | 2/3 | 350.94 | 303.71 | 0.02 | 0.00 | 2 |
| C | MPC_COMPLETION | 2 | 67/75 | 67/75 | 1/2 | 1/2 | 2.84 | 3.14 | 0.00 | 0.00 | 2 |
| C | MPC_MCTS | 2 | 71/75 | 71/75 | 1/2 | 1/2 | 50.30 | 51.50 | 0.00 | 0.00 | 2 |
| C | MPC_ALNS | 2 | 74/75 | 74/75 | 1/2 | 1/2 | 42.03 | 41.16 | 0.00 | 0.00 | 1 |
| C | MPC_HGS | 2 | 75/75 | 74/75 | 2/2 | 1/2 | 61.84 | 66.22 | 0.02 | 0.00 | 1 |
| C | MPC_ACS | 2 | 70/75 | 70/75 | 1/2 | 1/2 | 40.59 | 33.14 | 0.03 | 0.00 | 2 |

### Every paired case

| Stage | Case | DoD | Method | Served O/E | Complete O/E | Wall s O/E | CPU s O/E | Distance O/E (only equal-service) | Equal served IDs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B | c101_21_25 | 0.25 | MPC_COMPLETION | 25/25 | 1/1 | 1.17/1.47 | 0.02/0.00 | 912.84/912.84 | yes |
| B | c101_21_25 | 0.25 | MPC_MCTS | 25/25 | 1/1 | 9.03/6.01 | 0.00/0.00 | 812.91/812.91 | yes |
| B | c101_21_25 | 0.25 | MPC_ALNS | 25/25 | 1/1 | 3.38/2.78 | 0.02/0.00 | 874.36/874.36 | yes |
| B | c101_21_25 | 0.25 | MPC_HGS | 25/25 | 1/1 | 13.27/9.13 | 0.00/0.00 | 1033.89/1033.89 | yes |
| B | c101_21_25 | 0.25 | MPC_ACS | 25/25 | 1/1 | 3.28/2.93 | 0.02/0.00 | 867.39/867.39 | yes |
| B | c201_21_50 | 0.75 | MPC_COMPLETION | 50/50 | 1/1 | 1.92/2.28 | 0.00/0.00 | 1106.53/1106.53 | yes |
| B | c201_21_50 | 0.75 | MPC_MCTS | 50/50 | 1/1 | 193.66/146.93 | 0.00/0.00 | 1151.20/1083.34 | yes |
| B | c201_21_50 | 0.75 | MPC_ALNS | 50/50 | 1/1 | 147.72/120.54 | 0.00/0.00 | 1297.72/1007.06 | yes |
| B | c201_21_50 | 0.75 | MPC_HGS | 50/50 | 1/1 | 180.81/162.22 | 0.02/0.00 | 1031.18/1074.52 | yes |
| B | c201_21_50 | 0.75 | MPC_ACS | 50/50 | 1/1 | 71.81/40.58 | 0.00/0.00 | 762.85/762.85 | yes |
| B | r101_21_100 | 0.25 | MPC_COMPLETION | 91/91 | 0/0 | 3.48/2.92 | 0.02/0.02 | 2077.59/2077.59 | yes |
| B | r101_21_100 | 0.25 | MPC_MCTS | 98/98 | 0/0 | 29.32/24.38 | 0.00/0.00 | 2133.01/2133.01 | yes |
| B | r101_21_100 | 0.25 | MPC_ALNS | 99/99 | 0/0 | 37.05/26.33 | 0.00/0.00 | 2158.02/2158.02 | yes |
| B | r101_21_100 | 0.25 | MPC_HGS | 100/99 | 1/0 | 151.56/132.44 | 0.00/0.02 | not comparable | no |
| B | r101_21_100 | 0.25 | MPC_ACS | 97/96 | 0/0 | 275.85/260.20 | 0.00/0.00 | not comparable | no |
| C | r201_21_25 | 0.25 | MPC_COMPLETION | 25/25 | 1/1 | 1.12/1.32 | 0.00/0.00 | 642.18/594.65 | yes |
| C | r201_21_25 | 0.25 | MPC_MCTS | 25/25 | 1/1 | 33.24/33.08 | 0.00/0.00 | 590.90/547.19 | yes |
| C | r201_21_25 | 0.25 | MPC_ALNS | 25/25 | 1/1 | 34.12/33.99 | 0.00/0.00 | 604.79/636.99 | yes |
| C | r201_21_25 | 0.25 | MPC_HGS | 25/25 | 1/1 | 34.35/33.54 | 0.02/0.00 | 645.43/613.35 | yes |
| C | r201_21_25 | 0.25 | MPC_ACS | 25/25 | 1/1 | 19.16/11.80 | 0.02/0.00 | 550.55/524.96 | yes |
| C | rc101_21_50 | 0.75 | MPC_COMPLETION | 42/42 | 0/0 | 1.72/1.82 | 0.00/0.00 | 1323.97/1323.97 | yes |
| C | rc101_21_50 | 0.75 | MPC_MCTS | 46/46 | 0/0 | 17.06/18.41 | 0.00/0.00 | 1270.70/1270.70 | yes |
| C | rc101_21_50 | 0.75 | MPC_ALNS | 49/49 | 0/0 | 7.92/7.17 | 0.00/0.00 | not comparable | no |
| C | rc101_21_50 | 0.75 | MPC_HGS | 50/49 | 1/0 | 27.49/32.68 | 0.00/0.00 | not comparable | no |
| C | rc101_21_50 | 0.75 | MPC_ACS | 45/45 | 0/0 | 21.43/21.34 | 0.02/0.00 | 1262.86/1262.86 | yes |

## Full operational measurements

Travel energy is exact physical arc energy; charged energy is separately reported. Fleet workload balance is the standard deviation of customer service counts across active/known vehicles. Completion is the latest vehicle event time.
Distance, travel, energy, waiting, and charging comparisons are meaningful only when the served-customer identities match; see the paired table.

| Case | Method | Variant | Served | Distance | Travel time | Completion | Charge time | Charged energy | Travel energy | Wait time | EVs | Load SD | TW margin min/mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c101_21_25 | MPC_COMPLETION | original | 25/25 | 912.84 | 912.84 | 1236.00 | 1346.32 | 1346.32 | 3093.96 | 4142.85 | 7 | 1.59 | 8.79/47.55 |
| c101_21_25 | MPC_COMPLETION | compiled_cpu_v1 | 25/25 | 912.84 | 912.84 | 1236.00 | 1346.32 | 1346.32 | 3093.96 | 4142.85 | 7 | 1.59 | 8.79/47.55 |
| c101_21_25 | MPC_MCTS | original | 25/25 | 812.91 | 812.91 | 1236.00 | 1437.70 | 1437.70 | 2755.22 | 4151.39 | 6 | 1.76 | 29.40/57.97 |
| c101_21_25 | MPC_MCTS | compiled_cpu_v1 | 25/25 | 812.91 | 812.91 | 1236.00 | 1437.70 | 1437.70 | 2755.22 | 4151.39 | 6 | 1.76 | 29.40/57.97 |
| c101_21_25 | MPC_ALNS | original | 25/25 | 874.36 | 874.36 | 1236.00 | 1565.40 | 1565.40 | 2963.58 | 3962.24 | 6 | 1.59 | 8.79/53.73 |
| c101_21_25 | MPC_ALNS | compiled_cpu_v1 | 25/25 | 874.36 | 874.36 | 1236.00 | 1565.40 | 1565.40 | 2963.58 | 3962.24 | 6 | 1.59 | 8.79/53.73 |
| c101_21_25 | MPC_HGS | original | 25/25 | 1033.89 | 1033.89 | 1236.00 | 2382.57 | 2382.57 | 3504.30 | 2985.55 | 6 | 1.76 | 2.37/46.68 |
| c101_21_25 | MPC_HGS | compiled_cpu_v1 | 25/25 | 1033.89 | 1033.89 | 1236.00 | 2382.57 | 2382.57 | 3504.30 | 2985.55 | 6 | 1.76 | 2.37/46.68 |
| c101_21_25 | MPC_ACS | original | 25/25 | 867.39 | 867.39 | 1236.00 | 1480.40 | 1480.40 | 2939.89 | 4054.21 | 6 | 1.76 | 3.06/56.54 |
| c101_21_25 | MPC_ACS | compiled_cpu_v1 | 25/25 | 867.39 | 867.39 | 1236.00 | 1480.40 | 1480.40 | 2939.89 | 4054.21 | 6 | 1.76 | 3.06/56.54 |
| c201_21_50 | MPC_COMPLETION | original | 50/50 | 1106.53 | 1106.53 | 3390.00 | 1723.79 | 1723.79 | 2522.24 | 6229.68 | 4 | 6.80 | 4.80/111.76 |
| c201_21_50 | MPC_COMPLETION | compiled_cpu_v1 | 50/50 | 1106.53 | 1106.53 | 3390.00 | 1723.79 | 1723.79 | 2522.24 | 6229.68 | 4 | 6.80 | 4.80/111.76 |
| c201_21_50 | MPC_MCTS | original | 50/50 | 1151.20 | 1151.20 | 3390.00 | 1754.50 | 1754.50 | 2624.25 | 6154.30 | 4 | 2.29 | 2.87/123.67 |
| c201_21_50 | MPC_MCTS | compiled_cpu_v1 | 50/50 | 1083.34 | 1083.34 | 3390.00 | 1676.37 | 1676.37 | 2469.53 | 6300.29 | 4 | 2.06 | 11.29/135.66 |
| c201_21_50 | MPC_ALNS | original | 50/50 | 1297.72 | 1297.72 | 3390.00 | 2305.05 | 2305.05 | 2958.20 | 5457.24 | 4 | 2.06 | 0.30/118.85 |
| c201_21_50 | MPC_ALNS | compiled_cpu_v1 | 50/50 | 1007.06 | 1007.06 | 3390.00 | 1749.74 | 1749.74 | 2295.68 | 6303.20 | 4 | 1.50 | 30.23/142.17 |
| c201_21_50 | MPC_HGS | original | 50/50 | 1031.18 | 1031.18 | 3390.00 | 1563.38 | 1563.38 | 2350.69 | 6465.44 | 4 | 2.96 | 22.22/139.97 |
| c201_21_50 | MPC_HGS | compiled_cpu_v1 | 50/50 | 1074.52 | 1074.52 | 3390.00 | 1883.81 | 1883.81 | 2449.35 | 6101.67 | 4 | 2.96 | 1.53/134.68 |
| c201_21_50 | MPC_ACS | original | 50/50 | 762.85 | 762.85 | 3390.00 | 841.05 | 841.05 | 1738.86 | 7456.10 | 4 | 5.17 | 9.68/140.85 |
| c201_21_50 | MPC_ACS | compiled_cpu_v1 | 50/50 | 762.85 | 762.85 | 3390.00 | 841.05 | 841.05 | 1738.86 | 7456.10 | 4 | 5.17 | 9.68/140.85 |
| r101_21_100 | MPC_COMPLETION | original | 91/100 | 2077.59 | 2077.59 | 230.00 | 489.61 | 489.61 | 997.47 | 1122.80 | 20 | 1.72 | 0.03/7.29 |
| r101_21_100 | MPC_COMPLETION | compiled_cpu_v1 | 91/100 | 2077.59 | 2077.59 | 230.00 | 489.61 | 489.61 | 997.47 | 1122.80 | 20 | 1.72 | 0.03/7.29 |
| r101_21_100 | MPC_MCTS | original | 98/100 | 2133.01 | 2133.01 | 230.00 | 480.47 | 480.47 | 1024.08 | 1006.53 | 20 | 1.55 | 0.05/8.26 |
| r101_21_100 | MPC_MCTS | compiled_cpu_v1 | 98/100 | 2133.01 | 2133.01 | 230.00 | 480.47 | 480.47 | 1024.08 | 1006.53 | 20 | 1.55 | 0.05/8.26 |
| r101_21_100 | MPC_ALNS | original | 99/100 | 2158.02 | 2158.02 | 230.00 | 508.06 | 508.06 | 1036.16 | 943.92 | 20 | 1.12 | 0.05/8.22 |
| r101_21_100 | MPC_ALNS | compiled_cpu_v1 | 99/100 | 2158.02 | 2158.02 | 230.00 | 508.06 | 508.06 | 1036.16 | 943.92 | 20 | 1.12 | 0.05/8.22 |
| r101_21_100 | MPC_HGS | original | 100/100 | 2128.56 | 2128.56 | 230.00 | 519.68 | 519.68 | 1022.00 | 951.76 | 20 | 0.89 | 0.05/8.32 |
| r101_21_100 | MPC_HGS | compiled_cpu_v1 | 99/100 | 2190.86 | 2190.86 | 230.00 | 495.57 | 495.57 | 1051.88 | 923.57 | 20 | 0.92 | 0.05/8.45 |
| r101_21_100 | MPC_ACS | original | 97/100 | 2113.48 | 2113.48 | 230.00 | 473.84 | 473.84 | 1014.75 | 1042.68 | 20 | 1.24 | 0.05/7.85 |
| r101_21_100 | MPC_ACS | compiled_cpu_v1 | 96/100 | 2032.01 | 2032.01 | 230.00 | 432.43 | 432.43 | 975.61 | 1175.56 | 20 | 1.40 | 0.05/8.31 |
| r201_21_25 | MPC_COMPLETION | original | 25/25 | 642.18 | 642.18 | 1000.00 | 42.77 | 42.77 | 102.89 | 3065.05 | 2 | 6.34 | 2.03/96.38 |
| r201_21_25 | MPC_COMPLETION | quality_recovery_v1 | 25/25 | 594.65 | 594.65 | 1000.00 | 45.18 | 45.18 | 95.26 | 3110.17 | 2 | 6.34 | 33.59/94.73 |
| r201_21_25 | MPC_MCTS | original | 25/25 | 590.90 | 590.90 | 1000.00 | 44.26 | 44.26 | 94.62 | 3114.84 | 2 | 7.36 | 1.90/88.01 |
| r201_21_25 | MPC_MCTS | quality_recovery_v1 | 25/25 | 547.19 | 547.19 | 1000.00 | 41.19 | 41.19 | 87.64 | 3161.62 | 2 | 7.01 | 1.90/89.29 |
| r201_21_25 | MPC_ALNS | original | 25/25 | 604.79 | 604.79 | 1000.00 | 44.67 | 44.67 | 96.87 | 3100.54 | 2 | 7.76 | 0.30/72.38 |
| r201_21_25 | MPC_ALNS | quality_recovery_v1 | 25/25 | 636.99 | 636.99 | 1000.00 | 48.57 | 48.57 | 102.00 | 3064.44 | 2 | 7.36 | 0.30/69.09 |
| r201_21_25 | MPC_HGS | original | 25/25 | 645.43 | 645.43 | 1000.00 | 59.88 | 59.88 | 103.36 | 3044.69 | 2 | 6.34 | 3.96/97.17 |
| r201_21_25 | MPC_HGS | quality_recovery_v1 | 25/25 | 613.35 | 613.35 | 1000.00 | 67.40 | 67.40 | 98.21 | 3069.25 | 2 | 6.34 | 0.04/92.22 |
| r201_21_25 | MPC_ACS | original | 25/25 | 550.55 | 550.55 | 1000.00 | 44.04 | 44.04 | 88.19 | 3155.41 | 2 | 6.50 | 2.03/79.90 |
| r201_21_25 | MPC_ACS | quality_recovery_v1 | 25/25 | 524.96 | 524.96 | 1000.00 | 26.25 | 26.25 | 84.10 | 3198.79 | 2 | 6.72 | 8.66/92.90 |
| rc101_21_50 | MPC_COMPLETION | original | 42/50 | 1323.97 | 1323.97 | 240.00 | 183.59 | 183.59 | 503.28 | 712.45 | 11 | 0.72 | 1.13/21.07 |
| rc101_21_50 | MPC_COMPLETION | quality_recovery_v1 | 42/50 | 1323.97 | 1323.97 | 240.00 | 183.59 | 183.59 | 503.28 | 712.45 | 11 | 0.72 | 1.13/21.07 |
| rc101_21_50 | MPC_MCTS | original | 46/50 | 1270.70 | 1270.70 | 240.00 | 156.97 | 156.97 | 483.00 | 752.34 | 11 | 0.94 | 1.93/22.23 |
| rc101_21_50 | MPC_MCTS | quality_recovery_v1 | 46/50 | 1270.70 | 1270.70 | 240.00 | 156.97 | 156.97 | 483.00 | 752.34 | 11 | 0.94 | 1.93/22.23 |
| rc101_21_50 | MPC_ALNS | original | 49/50 | 1374.53 | 1374.53 | 240.00 | 205.75 | 205.75 | 522.44 | 569.72 | 11 | 1.37 | 0.71/19.10 |
| rc101_21_50 | MPC_ALNS | quality_recovery_v1 | 49/50 | 1292.78 | 1292.78 | 240.00 | 199.38 | 199.38 | 491.41 | 657.85 | 11 | 1.56 | 1.93/21.00 |
| rc101_21_50 | MPC_HGS | original | 50/50 | 1271.37 | 1271.37 | 240.00 | 177.91 | 177.91 | 483.29 | 690.72 | 11 | 1.56 | 0.44/21.08 |
| rc101_21_50 | MPC_HGS | quality_recovery_v1 | 49/50 | 1292.60 | 1292.60 | 240.00 | 184.20 | 184.20 | 491.35 | 673.20 | 11 | 1.08 | 0.44/20.39 |
| rc101_21_50 | MPC_ACS | original | 45/50 | 1262.86 | 1262.86 | 240.00 | 158.98 | 158.98 | 480.02 | 768.16 | 11 | 0.90 | 0.07/19.03 |
| rc101_21_50 | MPC_ACS | quality_recovery_v1 | 45/50 | 1262.86 | 1262.86 | 240.00 | 158.98 | 158.98 | 480.02 | 768.16 | 11 | 0.90 | 0.07/19.03 |

## Computation, deadlines, and interventions

Route decode counts are per-problem distinct keys summed across decision problems, not globally unique routes. GPU time is zero in full workers.

| Case | Method | Variant | Wall s | CPU s | Optimizations | Latency mean/p95/max s | Route decodes | Route builds | Compiled batches/proven late | Quality eligible/accepted | Recovery eligible/accepted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c101_21_25 | MPC_COMPLETION | original | 1.17 | 0.02 | 18 | 0.005/0.010/0.039 | 30 | 30 | 0/0 | 0/0 | 0/0 |
| c101_21_25 | MPC_COMPLETION | compiled_cpu_v1 | 1.47 | 0.00 | 18 | 0.003/0.008/0.025 | 30 | 30 | 346/518 | 0/0 | 0/0 |
| c101_21_25 | MPC_MCTS | original | 9.03 | 0.00 | 15 | 0.523/1.304/1.947 | 5883 | 5853 | 0/0 | 0/0 | 0/0 |
| c101_21_25 | MPC_MCTS | compiled_cpu_v1 | 6.01 | 0.00 | 15 | 0.299/0.789/0.855 | 5883 | 5853 | 346/523 | 0/0 | 0/0 |
| c101_21_25 | MPC_ALNS | original | 3.38 | 0.02 | 15 | 0.147/0.490/0.808 | 1088 | 1071 | 0/0 | 0/0 | 0/0 |
| c101_21_25 | MPC_ALNS | compiled_cpu_v1 | 2.78 | 0.00 | 15 | 0.091/0.319/0.514 | 1088 | 1071 | 2883/7486 | 0/0 | 0/0 |
| c101_21_25 | MPC_HGS | original | 13.27 | 0.00 | 18 | 0.672/1.946/2.638 | 5325 | 5276 | 0/0 | 0/0 | 0/0 |
| c101_21_25 | MPC_HGS | compiled_cpu_v1 | 9.13 | 0.00 | 18 | 0.418/1.171/1.718 | 5325 | 5276 | 21855/51783 | 0/0 | 0/0 |
| c101_21_25 | MPC_ACS | original | 3.28 | 0.02 | 17 | 0.125/0.383/0.699 | 1163 | 1115 | 0/0 | 0/0 | 0/0 |
| c101_21_25 | MPC_ACS | compiled_cpu_v1 | 2.93 | 0.00 | 17 | 0.090/0.288/0.430 | 1163 | 1115 | 10486/21669 | 0/0 | 0/0 |
| c201_21_50 | MPC_COMPLETION | original | 1.92 | 0.00 | 43 | 0.018/0.084/0.143 | 53 | 53 | 0/0 | 0/0 | 0/0 |
| c201_21_50 | MPC_COMPLETION | compiled_cpu_v1 | 2.28 | 0.00 | 43 | 0.018/0.103/0.145 | 53 | 53 | 266/891 | 0/0 | 0/0 |
| c201_21_50 | MPC_MCTS | original | 193.66 | 0.00 | 49 | 3.924/4.681/4.716 | 42147 | 42087 | 0/0 | 0/0 | 0/0 |
| c201_21_50 | MPC_MCTS | compiled_cpu_v1 | 146.93 | 0.00 | 50 | 2.901/4.646/4.697 | 54630 | 54565 | 266/893 | 0/0 | 0/0 |
| c201_21_50 | MPC_ALNS | original | 147.72 | 0.00 | 53 | 2.760/4.669/4.704 | 6077 | 6045 | 0/0 | 0/0 | 0/0 |
| c201_21_50 | MPC_ALNS | compiled_cpu_v1 | 120.54 | 0.00 | 51 | 2.330/4.669/4.752 | 7201 | 7163 | 11892/64563 | 0/0 | 0/0 |
| c201_21_50 | MPC_HGS | original | 180.81 | 0.02 | 45 | 3.987/4.733/4.791 | 14976 | 14867 | 0/0 | 0/0 | 0/0 |
| c201_21_50 | MPC_HGS | compiled_cpu_v1 | 162.22 | 0.00 | 50 | 3.208/4.755/4.807 | 19334 | 19219 | 81694/306299 | 0/0 | 0/0 |
| c201_21_50 | MPC_ACS | original | 71.81 | 0.00 | 42 | 1.677/4.665/4.721 | 9064 | 8939 | 0/0 | 0/0 | 0/0 |
| c201_21_50 | MPC_ACS | compiled_cpu_v1 | 40.58 | 0.00 | 42 | 0.925/2.132/2.641 | 9286 | 9161 | 89761/305089 | 0/0 | 0/0 |
| r101_21_100 | MPC_COMPLETION | original | 3.48 | 0.02 | 120 | 0.016/0.023/0.325 | 500 | 500 | 0/0 | 0/0 | 0/0 |
| r101_21_100 | MPC_COMPLETION | compiled_cpu_v1 | 2.92 | 0.02 | 120 | 0.008/0.010/0.215 | 500 | 500 | 49766/112981 | 0/0 | 0/0 |
| r101_21_100 | MPC_MCTS | original | 29.32 | 0.00 | 108 | 0.255/1.546/2.480 | 20293 | 20249 | 0/0 | 0/0 | 0/0 |
| r101_21_100 | MPC_MCTS | compiled_cpu_v1 | 24.38 | 0.00 | 108 | 0.206/1.313/1.696 | 20293 | 20249 | 15137/36396 | 0/0 | 0/0 |
| r101_21_100 | MPC_ALNS | original | 37.05 | 0.00 | 104 | 0.338/1.296/2.795 | 15414 | 14669 | 0/0 | 0/0 | 0/0 |
| r101_21_100 | MPC_ALNS | compiled_cpu_v1 | 26.33 | 0.00 | 104 | 0.231/0.814/1.480 | 15414 | 14669 | 137906/442185 | 0/0 | 0/0 |
| r101_21_100 | MPC_HGS | original | 151.56 | 0.00 | 81 | 1.846/4.656/4.667 | 70432 | 69553 | 0/0 | 0/0 | 0/0 |
| r101_21_100 | MPC_HGS | compiled_cpu_v1 | 132.44 | 0.02 | 117 | 1.111/4.655/4.664 | 80978 | 79825 | 1205244/3213327 | 0/0 | 0/0 |
| r101_21_100 | MPC_ACS | original | 275.85 | 0.00 | 123 | 2.228/4.654/4.660 | 29524 | 27812 | 0/0 | 0/0 | 0/0 |
| r101_21_100 | MPC_ACS | compiled_cpu_v1 | 260.20 | 0.00 | 119 | 2.167/4.665/4.695 | 28106 | 26455 | 859732/2014283 | 0/0 | 0/0 |
| r201_21_25 | MPC_COMPLETION | original | 1.12 | 0.00 | 7 | 0.007/0.005/0.020 | 25 | 25 | 0/0 | 0/0 | 0/0 |
| r201_21_25 | MPC_COMPLETION | quality_recovery_v1 | 1.32 | 0.00 | 7 | 0.029/0.031/0.110 | 107 | 107 | 0/0 | 7/3 | 0/0 |
| r201_21_25 | MPC_MCTS | original | 33.24 | 0.00 | 7 | 4.571/4.750/4.750 | 5824 | 5824 | 0/0 | 0/0 | 0/0 |
| r201_21_25 | MPC_MCTS | quality_recovery_v1 | 33.08 | 0.00 | 7 | 4.549/4.751/4.751 | 6548 | 6548 | 0/0 | 1/1 | 0/0 |
| r201_21_25 | MPC_ALNS | original | 34.12 | 0.00 | 9 | 3.654/4.726/4.756 | 576 | 576 | 0/0 | 0/0 | 0/0 |
| r201_21_25 | MPC_ALNS | quality_recovery_v1 | 33.99 | 0.00 | 8 | 4.098/4.691/4.750 | 515 | 515 | 0/0 | 1/0 | 0/0 |
| r201_21_25 | MPC_HGS | original | 34.35 | 0.02 | 9 | 3.683/4.751/4.751 | 2448 | 2434 | 0/0 | 0/0 | 0/0 |
| r201_21_25 | MPC_HGS | quality_recovery_v1 | 33.54 | 0.00 | 8 | 4.039/4.716/4.716 | 2524 | 2510 | 0/0 | 2/0 | 0/0 |
| r201_21_25 | MPC_ACS | original | 19.16 | 0.02 | 9 | 1.998/4.752/4.783 | 1774 | 1759 | 0/0 | 0/0 | 0/0 |
| r201_21_25 | MPC_ACS | quality_recovery_v1 | 11.80 | 0.00 | 9 | 1.183/1.975/4.740 | 1891 | 1876 | 0/0 | 8/2 | 0/0 |
| rc101_21_50 | MPC_COMPLETION | original | 1.72 | 0.00 | 87 | 0.006/0.014/0.029 | 230 | 230 | 0/0 | 0/0 | 0/0 |
| rc101_21_50 | MPC_COMPLETION | quality_recovery_v1 | 1.82 | 0.00 | 87 | 0.007/0.016/0.032 | 401 | 401 | 0/0 | 17/0 | 70/0 |
| rc101_21_50 | MPC_MCTS | original | 17.06 | 0.00 | 85 | 0.185/0.719/0.793 | 14976 | 14866 | 0/0 | 0/0 | 0/0 |
| rc101_21_50 | MPC_MCTS | quality_recovery_v1 | 18.41 | 0.00 | 85 | 0.200/0.802/0.920 | 15437 | 15327 | 0/0 | 26/0 | 59/0 |
| rc101_21_50 | MPC_ALNS | original | 7.92 | 0.00 | 83 | 0.079/0.209/0.340 | 4685 | 4330 | 0/0 | 0/0 | 0/0 |
| rc101_21_50 | MPC_ALNS | quality_recovery_v1 | 7.17 | 0.00 | 67 | 0.087/0.229/0.285 | 4133 | 3905 | 0/0 | 38/3 | 29/0 |
| rc101_21_50 | MPC_HGS | original | 27.49 | 0.00 | 58 | 0.450/1.056/1.303 | 19612 | 19296 | 0/0 | 0/0 | 0/0 |
| rc101_21_50 | MPC_HGS | quality_recovery_v1 | 32.68 | 0.00 | 81 | 0.386/1.136/1.599 | 25204 | 24703 | 0/0 | 32/4 | 49/0 |
| rc101_21_50 | MPC_ACS | original | 21.43 | 0.02 | 87 | 0.230/0.593/0.720 | 7828 | 7250 | 0/0 | 0/0 | 0/0 |
| rc101_21_50 | MPC_ACS | quality_recovery_v1 | 21.34 | 0.00 | 87 | 0.230/0.543/0.746 | 8270 | 7692 | 0/0 | 26/0 | 61/0 |

## Scientific interpretation

Across 25 matched pairs: 0 service gains, 3 service losses, 21 equal-served-set pairs, and 6 shorter-distance results among the latter.
A fixed-work compiled screen can match exact proposals yet change a deadline-limited search trajectory; end-to-end service and time, not micro speed, govern promotion.
The optional quality policy uses explicit risk tolerances and physical replay. It is a separate policy, not a rewrite of the historical lexicographic objective. Its intervention counts above establish whether it actually changed decisions.
Two structurally preselected Stage C development parents are too few to support a repeatable complete-service claim. No enhanced variant is promoted automatically; original remains default.
Every saved full scenario was independently replayed from disk against the original physical/information auditor and passed the five-second decision maximum.
Charged compute before report worker: 2768.88/7200 s; 300 s setup charge and 120 s report reserve. Consult `budget.json` for the final report charge.
The stopped Reliability V2 evidence was not resumed; no new final holdout was opened.

## Reproduction

```powershell
.\.venv-accel\Scripts\python.exe -m pytest -q
.\.venv-accel\Scripts\python.exe -m scripts.run_hybrid_acceleration --freeze
.\.venv-accel\Scripts\python.exe -u -m scripts.run_hybrid_acceleration
.\.venv-accel\Scripts\python.exe -m scripts.report_hybrid_acceleration
```

Use the frozen source commit and the recorded environment. Completed raw files are hash-checked and never regenerated by the runner; failed jobs require an explicit revision, not a silent retry.
