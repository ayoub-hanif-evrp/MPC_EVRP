# Final search-engine comparisons within MPC

| Comparison (left - right) | Mean Delta served | 95% bootstrap CI | W/T/L | Complete-rate difference |
| --- | --- | --- | --- | --- |
| MPC + MCTS - MPC + ALNS | -1.81 | [-2.61, -1.07] | 6/16/32 | -38.9 pp |
| MPC + MCTS - MPC + HGS | -1.19 | [-1.98, -0.30] | 6/18/30 | -35.2 pp |
| MPC + MCTS - MPC + ACS | -1.07 | [-1.74, -0.39] | 9/22/23 | -13.0 pp |
| MPC + ALNS - MPC + HGS | 0.63 | [-0.06, 1.35] | 15/29/10 | +3.7 pp |
| MPC + ALNS - MPC + ACS | 0.74 | [0.13, 1.41] | 25/21/8 | +25.9 pp |
| MPC + HGS - MPC + ACS | 0.11 | [-0.74, 0.83] | 22/21/11 | +22.2 pp |

Positive Delta favors the left method. All comparisons are paired across the same 54 scenarios.
