# Original five-method correctness pilot

Status: complete; 10/10 runs. Saved raw files independently replayed again.
Two preselected exposed development scenarios; target DoD .75, seed7301.
This pilot cannot establish population superiority.

| Instance | Method | Served | EVs | Wall s | CPU s | Max decision s | Deadline events | Audit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| c101_21_25 | MPC_COMPLETION | 24/25 | 7 | 0.25 | 0.30 | 0.018 | 0 | pass |
| c101_21_25 | MPC_MCTS | 25/25 | 6 | 5.03 | 5.00 | 0.424 | 0 | pass |
| c101_21_25 | MPC_ALNS | 25/25 | 6 | 0.95 | 1.00 | 0.094 | 0 | pass |
| c101_21_25 | MPC_HGS | 25/25 | 6 | 2.98 | 3.08 | 0.280 | 0 | pass |
| c101_21_25 | MPC_ACS | 25/25 | 7 | 0.90 | 1.06 | 0.078 | 0 | pass |
| r101_21_100 | MPC_ACS | 93/100 | 20 | 187.28 | 184.59 | 2.749 | 0 | pass |
| r101_21_100 | MPC_HGS | 97/100 | 20 | 235.60 | 232.83 | 2.943 | 0 | pass |
| r101_21_100 | MPC_ALNS | 98/100 | 20 | 61.80 | 60.81 | 1.097 | 0 | pass |
| r101_21_100 | MPC_MCTS | 87/100 | 20 | 11.65 | 11.50 | 0.784 | 0 | pass |
| r101_21_100 | MPC_COMPLETION | 89/100 | 20 | 2.70 | 2.83 | 0.041 | 0 | pass |

Highest total service here only: MPC_ALNS.

MCTS served 87/100 versus Completion's 89/100 on R101; this negative case is retained.

## Operating metrics

Rank operating costs only within identical served-set groups:

- Case 0: [['MPC_COMPLETION'], ['MPC_MCTS', 'MPC_ALNS', 'MPC_HGS', 'MPC_ACS']]
- Case 1: [['MPC_COMPLETION'], ['MPC_MCTS'], ['MPC_ALNS'], ['MPC_HGS'], ['MPC_ACS']]

| Instance | Method | Distance | Charge time | Charge visits | Charged energy | Travel energy |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| c101_21_25 | MPC_COMPLETION | 848.57 | 1157.15 | 15 | 1157.15 | 2876.03 |
| c101_21_25 | MPC_MCTS | 839.26 | 1377.37 | 17 | 1377.37 | 2844.53 |
| c101_21_25 | MPC_ALNS | 838.08 | 1473.14 | 12 | 1473.14 | 2840.54 |
| c101_21_25 | MPC_HGS | 788.99 | 1361.54 | 13 | 1361.54 | 2674.19 |
| c101_21_25 | MPC_ACS | 937.74 | 1356.86 | 17 | 1356.86 | 3178.35 |
| r101_21_100 | MPC_ACS | 1886.81 | 372.71 | 36 | 372.71 | 905.85 |
| r101_21_100 | MPC_HGS | 2062.35 | 514.24 | 47 | 514.24 | 990.21 |
| r101_21_100 | MPC_ALNS | 1959.70 | 444.60 | 41 | 444.60 | 940.88 |
| r101_21_100 | MPC_MCTS | 1858.11 | 330.93 | 30 | 330.93 | 892.11 |
| r101_21_100 | MPC_COMPLETION | 1939.64 | 360.06 | 35 | 360.06 | 931.22 |

## Limits and reporting correction

The original pilot runner's report attempted to read a legacy-only fallback metric.
That analysis failure is preserved separately. This analysis helper reads the saved schema
without changing the executed runner, protocol, raw bytes, or algorithms. Final-validation
fallback counts are null when not recorded; total deadline events, optimizer-deadline
decisions, initialization fallbacks, and worker failures are reported explicitly in JSON.
Original ALNS/HGS/ACS retain their documented initialization-timeout edge defect.
MPC_ALNS_SAFE_INIT_V1 was tested separately and not substituted into the original pilot.
Cooperative timing and external machine load limit real-time claims. The full future
270-run panel remains exposed and over budget; it was not launched.
