# Final holdout overall results

| Method | Customers served, mean (total) | Service rate | Complete scenarios | Complete-service rate | Mean decision latency (s) | p95 latency (s) | Max latency (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MPC + Completion | 94.26 (5090) | 94.3% | 5 | 9.3% | 0.509 | 2.016 | 2.061 |
| MPC + MCTS | 97.52 (5266) | 97.5% | 17 | 31.5% | 1.920 | 4.751 | 4.795 |
| MPC + ALNS | **99.33 (5364)** | 99.3% | 38 | 70.4% | 3.249 | 4.752 | 4.826 |
| MPC + HGS | 98.70 (5330) | 98.7% | 36 | 66.7% | 3.520 | 4.751 | 4.791 |
| MPC + ACS | 98.59 (5324) | 98.6% | 24 | 44.4% | 3.189 | 4.758 | 4.868 |
| MPC + Portfolio | 99.06 (5349) | 99.1% | 37 | 68.5% | 3.411 | 4.751 | 4.804 |

54 paired 100-customer scenarios. Bold marks the highest mean customers served; ties share bold. Observed best fixed method MPC + ALNS minus Portfolio: 0.28 customers per scenario (95% paired bootstrap CI [-0.30, 0.89]; W/T/L 14/31/9).
