# Bounded depot-reserve development pilot

This is a **loss-selected development pilot**, not independent evaluation.
Original and reserve variants used identical scenarios, fixed K_ref,
original optimizer and decoder, unchanged service-first objective, and
five-second decision limit. All 12 raw traces passed SHA-256 verification
and independent physical/information-boundary replay.

| Instance | Method | Original service | Reserve service | Change | Complete old / reserve | Worker s old / reserve | Triggers old / reserve | Max decision s old / reserve |
| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| r101_21_25, DoD 0.75 | MPC_COMPLETION | 24 | 23 | -1 | 0 / 0 | 0.3 / 0.3 | 49 / 48 | 0.013 / 0.012 |
| r101_21_25, DoD 0.75 | MPC_ALNS | 23 | 24 | +1 | 0 / 0 | 1.1 / 1.2 | 47 / 50 | 0.051 / 0.057 |
| rc101_21_50, DoD 0.75 | MPC_COMPLETION | 42 | 42 | +0 | 0 / 0 | 0.8 / 0.8 | 87 / 87 | 0.033 / 0.035 |
| rc101_21_50, DoD 0.75 | MPC_ALNS | 49 | 46 | -3 | 0 / 0 | 5.7 / 6.5 | 83 / 80 | 0.272 / 0.256 |
| r101_21_100, DoD 0.75 | MPC_COMPLETION | 82 | 82 | +0 | 0 / 0 | 2.5 / 2.5 | 164 / 163 | 0.042 / 0.044 |
| r101_21_100, DoD 0.75 | MPC_ALNS | 94 | 92 | -2 | 0 / 0 | 40.0 / 42.2 | 174 / 176 | 0.686 / 0.642 |

## Decision

- MPC_COMPLETION: paired changes -1, +0, +0; total -1, median +0.0 customers.
- MPC_ALNS: paired changes +1, -3, -2; total -4, median -2.0 customers.

The reserve policy is **not promoted**. Its negative and mixed service
results do not justify a new final holdout. These selected cases do
not estimate generalization; no old final/robustness data were used
to select the policy or its pilot cases.
