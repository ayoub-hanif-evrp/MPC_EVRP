# Conditional fleet and distance efficiency

| Comparison (left - right) | Equal-service scenarios n | Delta EVs at equal service | Equal-service + equal-EV scenarios n | Delta distance at equal service/equal EV |
| --- | --- | --- | --- | --- |
| MPC + MCTS - MPC + Completion | 10 | 0.00 | 10 | -30.93 |
| MPC + ALNS - MPC + Completion | 7 | 0.00 | 7 | 45.11 |
| MPC + HGS - MPC + Completion | 6 | 0.00 | 6 | 119.59 |
| MPC + ACS - MPC + Completion | 9 | 0.00 | 9 | -79.62 |
| MPC + Portfolio - MPC + Completion | 6 | 0.00 | 6 | 82.58 |
| MPC + MCTS - MPC + ALNS | 16 | 0.94 | 8 | -31.79 |
| MPC + MCTS - MPC + HGS | 18 | -0.17 | 13 | -50.52 |
| MPC + MCTS - MPC + ACS | 22 | -0.41 | 17 | 63.73 |
| MPC + ALNS - MPC + HGS | 29 | -0.72 | 18 | -115.24 |
| MPC + ALNS - MPC + ACS | 21 | -1.10 | 12 | 185.35 |
| MPC + HGS - MPC + ACS | 21 | -0.24 | 16 | 203.29 |
| MPC + Portfolio - MPC + MCTS | 17 | 0.18 | 11 | 92.97 |
| MPC + Portfolio - MPC + ALNS | 31 | 0.68 | 21 | 104.35 |
| MPC + Portfolio - MPC + HGS | 35 | 0.00 | 33 | -8.96 |
| MPC + Portfolio - MPC + ACS | 27 | -0.19 | 23 | 243.58 |

Negative conditional Delta favors the left method. Distance is compared only when service and EV count tie; NA means no eligible pair.
