# Desaulniers MP final holdout

Final holdout evidence. All included scenarios have five matched,
isolated, independently audited methods and the same five-second
decision budget. Ineligible target-DoD scenarios are excluded
before optimizer comparison and counted separately.

The original final protocol stopped after 10 records on a replay-audit
floating-point timing defect. Its evidence is preserved separately;
all records here were rerun under an auditor-only erratum with
unchanged optimizers, objective, controller, scenarios, and budget.

Planned method runs: 270; audited runs: 270; ineligible scenarios: 0.

Conditional EV and distance use only scenarios where every method
served all customers. Unconditional values must not be ranked when
service differs. Shared-machine load can affect runtime.

## Overall

| Group | Method | N | Served % | Complete % | EV mean | Charge visits mean | Mean decision s | Max decision s | Comparable N | EV conditional | Distance conditional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All | MPC_COMPLETION | 54 | 92.19 | 35.2 | 6.19 | 17.87 | 0.376 | 2.045 | 19 | 3.37 | 1011.35 |
| All | MPC_MCTS | 54 | 96.00 | 50.0 | 5.93 | 15.91 | 2.150 | 4.779 | 19 | 3.26 | 1081.46 |
| All | MPC_ALNS | 54 | 99.14 | 81.5 | 5.33 | 13.28 | 2.770 | 4.845 | 19 | 2.89 | 978.59 |
| All | MPC_HGS | 54 | 98.89 | 70.4 | 5.76 | 16.00 | 3.149 | 4.788 | 19 | 3.21 | 1088.23 |
| All | MPC_ACS | 54 | 98.19 | 66.7 | 6.02 | 13.85 | 2.609 | 4.871 | 19 | 3.37 | 852.15 |

## By size

| Group | Method | N | Served % | Complete % | EV mean | Charge visits mean | Mean decision s | Max decision s | Comparable N | EV conditional | Distance conditional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | MPC_COMPLETION | 18 | 90.44 | 44.4 | 2.94 | 8.28 | 0.150 | 2.004 | 8 | 1.88 | 711.12 |
| 25 | MPC_MCTS | 18 | 95.56 | 50.0 | 2.89 | 8.56 | 2.173 | 4.758 | 8 | 1.75 | 770.60 |
| 25 | MPC_ALNS | 18 | 97.33 | 77.8 | 2.89 | 8.28 | 1.693 | 4.759 | 8 | 1.75 | 711.16 |
| 25 | MPC_HGS | 18 | 98.44 | 77.8 | 2.94 | 7.89 | 2.654 | 4.765 | 8 | 1.88 | 701.39 |
| 25 | MPC_ACS | 18 | 96.00 | 61.1 | 2.94 | 6.78 | 1.544 | 4.770 | 8 | 1.88 | 565.64 |
| 50 | MPC_COMPLETION | 18 | 86.56 | 50.0 | 4.83 | 13.89 | 0.369 | 2.026 | 9 | 3.00 | 1068.48 |
| 50 | MPC_MCTS | 18 | 93.78 | 50.0 | 4.78 | 13.39 | 2.441 | 4.767 | 9 | 2.89 | 1173.73 |
| 50 | MPC_ALNS | 18 | 98.89 | 77.8 | 4.56 | 11.94 | 3.067 | 4.780 | 9 | 2.44 | 1043.87 |
| 50 | MPC_HGS | 18 | 97.67 | 61.1 | 4.78 | 14.94 | 3.270 | 4.773 | 9 | 2.89 | 1247.78 |
| 50 | MPC_ACS | 18 | 96.67 | 61.1 | 4.89 | 11.56 | 2.665 | 4.837 | 9 | 3.11 | 882.25 |
| 100 | MPC_COMPLETION | 18 | 95.44 | 11.1 | 10.78 | 31.44 | 0.610 | 2.045 | 2 | 11.00 | 1955.23 |
| 100 | MPC_MCTS | 18 | 97.22 | 50.0 | 10.11 | 25.78 | 1.836 | 4.779 | 2 | 11.00 | 1909.64 |
| 100 | MPC_ALNS | 18 | 99.72 | 88.9 | 8.56 | 19.61 | 3.550 | 4.845 | 2 | 9.50 | 1754.55 |
| 100 | MPC_HGS | 18 | 99.61 | 72.2 | 9.56 | 25.17 | 3.523 | 4.788 | 2 | 10.00 | 1917.69 |
| 100 | MPC_ACS | 18 | 99.50 | 77.8 | 10.22 | 23.22 | 3.618 | 4.871 | 2 | 10.50 | 1862.81 |

## By family

| Group | Method | N | Served % | Complete % | EV mean | Charge visits mean | Mean decision s | Max decision s | Comparable N | EV conditional | Distance conditional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | MPC_COMPLETION | 9 | 90.10 | 0.0 | 8.33 | 26.11 | 0.068 | 2.006 | 0 | NA | NA |
| C1 | MPC_MCTS | 9 | 96.95 | 33.3 | 8.22 | 21.78 | 1.479 | 4.649 | 0 | NA | NA |
| C1 | MPC_ALNS | 9 | 100.00 | 100.0 | 7.56 | 16.44 | 1.768 | 4.730 | 0 | NA | NA |
| C1 | MPC_HGS | 9 | 99.62 | 88.9 | 8.11 | 21.00 | 2.732 | 4.695 | 0 | NA | NA |
| C1 | MPC_ACS | 9 | 99.43 | 66.7 | 8.11 | 17.89 | 1.601 | 4.685 | 0 | NA | NA |
| C2 | MPC_COMPLETION | 9 | 97.52 | 55.6 | 3.67 | 22.11 | 0.210 | 2.016 | 5 | 3.20 | 1011.83 |
| C2 | MPC_MCTS | 9 | 96.57 | 55.6 | 3.56 | 21.22 | 2.339 | 4.758 | 5 | 3.00 | 1085.64 |
| C2 | MPC_ALNS | 9 | 99.24 | 88.9 | 3.22 | 14.67 | 3.164 | 4.785 | 5 | 2.60 | 858.93 |
| C2 | MPC_HGS | 9 | 99.62 | 77.8 | 3.56 | 19.22 | 3.506 | 4.756 | 5 | 3.00 | 971.92 |
| C2 | MPC_ACS | 9 | 98.86 | 77.8 | 3.67 | 14.44 | 3.137 | 4.829 | 5 | 3.20 | 750.38 |
| R1 | MPC_COMPLETION | 9 | 88.00 | 11.1 | 9.56 | 19.89 | 0.209 | 2.022 | 1 | 18.00 | 2057.23 |
| R1 | MPC_MCTS | 9 | 91.81 | 33.3 | 9.22 | 17.89 | 1.106 | 4.641 | 1 | 18.00 | 2020.79 |
| R1 | MPC_ALNS | 9 | 98.48 | 66.7 | 7.89 | 16.33 | 2.014 | 4.720 | 1 | 15.00 | 1590.21 |
| R1 | MPC_HGS | 9 | 97.33 | 55.6 | 8.44 | 17.78 | 2.562 | 4.683 | 1 | 16.00 | 1528.75 |
| R1 | MPC_ACS | 9 | 95.43 | 44.4 | 9.00 | 17.89 | 2.033 | 4.676 | 1 | 17.00 | 1821.14 |
| R2 | MPC_COMPLETION | 9 | 96.00 | 66.7 | 2.22 | 6.56 | 0.623 | 2.045 | 6 | 1.83 | 700.27 |
| R2 | MPC_MCTS | 9 | 96.95 | 66.7 | 2.11 | 6.11 | 3.543 | 4.779 | 6 | 1.67 | 784.21 |
| R2 | MPC_ALNS | 9 | 99.24 | 88.9 | 2.11 | 6.00 | 3.910 | 4.845 | 6 | 1.67 | 793.50 |
| R2 | MPC_HGS | 9 | 99.05 | 66.7 | 2.22 | 5.78 | 3.868 | 4.788 | 6 | 1.83 | 803.89 |
| R2 | MPC_ACS | 9 | 99.81 | 88.9 | 2.22 | 6.44 | 3.425 | 4.871 | 6 | 1.83 | 643.72 |
| RC1 | MPC_COMPLETION | 9 | 82.67 | 0.0 | 10.33 | 21.33 | 0.075 | 2.012 | 0 | NA | NA |
| RC1 | MPC_MCTS | 9 | 95.81 | 33.3 | 9.44 | 15.22 | 1.310 | 4.663 | 0 | NA | NA |
| RC1 | MPC_ALNS | 9 | 98.10 | 55.6 | 8.44 | 15.22 | 1.753 | 4.710 | 0 | NA | NA |
| RC1 | MPC_HGS | 9 | 97.71 | 33.3 | 9.22 | 18.11 | 2.094 | 4.713 | 0 | NA | NA |
| RC1 | MPC_ACS | 9 | 96.00 | 33.3 | 10.00 | 17.00 | 1.625 | 4.684 | 0 | NA | NA |
| RC2 | MPC_COMPLETION | 9 | 98.86 | 77.8 | 3.00 | 11.22 | 1.072 | 2.025 | 7 | 2.71 | 1128.24 |
| RC2 | MPC_MCTS | 9 | 97.90 | 77.8 | 3.00 | 13.22 | 3.122 | 4.755 | 7 | 2.71 | 1199.06 |
| RC2 | MPC_ALNS | 9 | 99.81 | 88.9 | 2.78 | 11.00 | 4.011 | 4.784 | 7 | 2.43 | 1135.34 |
| RC2 | MPC_HGS | 9 | 100.00 | 100.0 | 3.00 | 14.11 | 4.132 | 4.773 | 7 | 2.71 | 1352.11 |
| RC2 | MPC_ACS | 9 | 99.62 | 88.9 | 3.11 | 9.44 | 3.832 | 4.799 | 7 | 2.86 | 965.08 |

## By target DoD

| Group | Method | N | Served % | Complete % | EV mean | Charge visits mean | Mean decision s | Max decision s | Comparable N | EV conditional | Distance conditional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.25 | MPC_COMPLETION | 18 | 93.43 | 38.9 | 6.11 | 18.11 | 0.622 | 2.026 | 7 | 4.86 | 1243.38 |
| 0.25 | MPC_MCTS | 18 | 95.62 | 44.4 | 6.00 | 17.22 | 1.596 | 4.774 | 7 | 5.00 | 1310.27 |
| 0.25 | MPC_ALNS | 18 | 99.14 | 83.3 | 5.44 | 13.56 | 2.897 | 4.779 | 7 | 4.29 | 1179.18 |
| 0.25 | MPC_HGS | 18 | 98.76 | 61.1 | 5.89 | 16.44 | 2.979 | 4.776 | 7 | 4.71 | 1300.45 |
| 0.25 | MPC_ACS | 18 | 98.38 | 61.1 | 6.00 | 15.61 | 2.826 | 4.827 | 7 | 4.86 | 1107.67 |
| 0.5 | MPC_COMPLETION | 18 | 92.00 | 33.3 | 6.22 | 18.11 | 0.296 | 2.045 | 6 | 2.50 | 975.89 |
| 0.5 | MPC_MCTS | 18 | 96.19 | 50.0 | 6.00 | 15.83 | 2.263 | 4.765 | 6 | 2.50 | 1005.06 |
| 0.5 | MPC_ALNS | 18 | 99.05 | 77.8 | 5.28 | 12.94 | 2.908 | 4.785 | 6 | 2.17 | 871.22 |
| 0.5 | MPC_HGS | 18 | 98.86 | 72.2 | 5.78 | 16.28 | 3.237 | 4.783 | 6 | 2.33 | 909.08 |
| 0.5 | MPC_ACS | 18 | 97.62 | 61.1 | 6.06 | 13.33 | 2.635 | 4.850 | 6 | 2.50 | 661.21 |
| 0.75 | MPC_COMPLETION | 18 | 91.14 | 33.3 | 6.22 | 17.39 | 0.211 | 2.025 | 6 | 2.50 | 776.12 |
| 0.75 | MPC_MCTS | 18 | 96.19 | 55.6 | 5.78 | 14.67 | 2.592 | 4.779 | 6 | 2.00 | 890.90 |
| 0.75 | MPC_ALNS | 18 | 99.24 | 83.3 | 5.28 | 13.33 | 2.506 | 4.845 | 6 | 2.00 | 851.95 |
| 0.75 | MPC_HGS | 18 | 99.05 | 77.8 | 5.61 | 15.28 | 3.231 | 4.788 | 6 | 2.33 | 1019.80 |
| 0.75 | MPC_ACS | 18 | 98.57 | 77.8 | 6.00 | 12.61 | 2.366 | 4.871 | 6 | 2.50 | 745.00 |

## Paired service change vs Completion

| Method | N | Mean customers | Wins | Ties | Losses |
| --- | --- | --- | --- | --- | --- |
| MPC_MCTS | 54 | 2.22 | 25 | 26 | 3 |
| MPC_ALNS | 54 | 4.06 | 34 | 19 | 1 |
| MPC_HGS | 54 | 3.91 | 34 | 20 | 0 |
| MPC_ACS | 54 | 3.50 | 33 | 21 | 0 |

Reserved benchmark instances were fixed in the original protocol before final outcomes.


## Instance-clustered paired uncertainty

Bootstrap resamples benchmark instances, retaining their DoD scenarios together (10,000 draws, fixed seed). Intervals are descriptive 95% percentile intervals; no final-outcome tuning was performed.

| Method | Paired N | Mean gain vs Completion | 95% CI | Wins | Ties | Losses |
| --- | --- | --- | --- | --- | --- | --- |
| MPC_MCTS | 54 | 2.22 | [0.76, 3.98] | 25 | 26 | 3 |
| MPC_ALNS | 54 | 4.06 | [2.11, 6.31] | 34 | 19 | 1 |
| MPC_HGS | 54 | 3.91 | [2.17, 5.89] | 34 | 20 | 0 |
| MPC_ACS | 54 | 3.50 | [1.87, 5.35] | 33 | 21 | 0 |
