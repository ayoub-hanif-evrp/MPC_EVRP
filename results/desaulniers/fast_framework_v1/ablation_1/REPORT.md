# Controlled HGS/ACS component ablation

This is an exploratory ablation on the seen r101_21_100 development scenario, not an independent final confirmation. Fresh workers use PYTHONHASHSEED=0, one native thread, identical scenario and source, and a five-second decision maximum.

Prior study charge carried: 1948.03 s. Cumulative charge: 3860.22/7200 s.

| Method | Variant | Served | Complete | CPU s | Wall s | Max decision s | Replans | Early stops | Guard accepts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MPC_HGS | original | 100 | 1 | 148.14 | 150.03 | 4.66 | 81 | 0 | 0 |
| MPC_HGS | fast_only | 99 | 0 | 74.50 | 75.46 | 4.67 | 72 | 0 | 0 |
| MPC_HGS | adaptive_only | 100 | 1 | 142.19 | 144.36 | 4.66 | 81 | 0 | 0 |
| MPC_HGS | guard_only | 100 | 1 | 140.86 | 142.48 | 4.51 | 81 | 0 | 0 |
| MPC_HGS | combined | 99 | 0 | 118.94 | 120.29 | 4.49 | 117 | 0 | 0 |
| MPC_ACS | original | 96 | 0 | 254.56 | 257.31 | 4.68 | 119 | 0 | 0 |
| MPC_ACS | fast_only | 95 | 0 | 228.50 | 231.09 | 4.68 | 122 | 0 | 0 |
| MPC_ACS | adaptive_only | 98 | 0 | 263.95 | 266.71 | 4.66 | 122 | 0 | 0 |
| MPC_ACS | guard_only | 97 | 0 | 251.86 | 254.68 | 4.48 | 123 | 0 | 0 |
| MPC_ACS | combined | 96 | 0 | 245.25 | 248.40 | 4.49 | 119 | 0 | 0 |

The original variant remains the benchmark. Single-factor variants isolate an optional component only in this one seed; search trajectories depend on the fixed deadline. A service loss rejects promotion regardless of CPU savings. The full frozen publication study is unchanged.
