# Fast, Service-Aware MPC: bounded development study

Status: **confirmation_not_promoted_pilot_service_regression**. Completed workers: 33 of 53. Source commit: `d369767429c9808620837d0f0286fa38dd29696b`. This is development evidence, not an independent final holdout.

The original policy remains the publication default unless separately confirmed. Enhanced runs use the optional fast screen/cache, adaptive stopping, and urgent service guard. MCTS additionally uses the separately identified skip-blocked rollout correction. Completion remains no-search. All retain the same five-second maximum decision cap, fleet, physics, visibility, objective, and archived scenario inputs.

## Matched five-method comparison

| Method | Paired cases | Original served | Enhanced served | Original complete | Enhanced complete | Original CPU s | Enhanced CPU s | Service losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MPC_COMPLETION | 3 | 166 | 166 | 2 | 2 | 3.41 | 2.59 | 0 |
| MPC_MCTS | 3 | 173 | 173 | 2 | 2 | 230.31 | 155.47 | 0 |
| MPC_ALNS | 3 | 174 | 174 | 2 | 2 | 180.31 | 120.41 | 0 |
| MPC_HGS | 3 | 175 | 174 | 3 | 2 | 326.11 | 251.25 | 1 |
| MPC_ACS | 3 | 171 | 171 | 2 | 2 | 326.62 | 280.47 | 0 |

Counts are over exactly matched completed pairs; CPU is fresh-worker process time. The five-case totals are not customer percentages across a representative population.

## Every paired outcome

| Case | Method | Served O -> E | Complete O -> E | CPU s O -> E | Mean latency s O -> E | Max latency s O -> E | Replans O -> E |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c101_21_25 DoD=0.25 seed=0 | MPC_COMPLETION | 25 -> 25 | 1 -> 1 | 0.16 -> 0.12 | 0.00 -> 0.00 | 0.04 -> 0.03 | 18 -> 18 |
| c101_21_25 DoD=0.25 seed=0 | MPC_MCTS | 25 -> 25 | 1 -> 1 | 8.16 -> 4.88 | 0.54 -> 0.32 | 2.15 -> 0.83 | 15 -> 15 |
| c101_21_25 DoD=0.25 seed=0 | MPC_ALNS | 25 -> 25 | 1 -> 1 | 2.33 -> 1.42 | 0.15 -> 0.09 | 0.82 -> 0.51 | 15 -> 15 |
| c101_21_25 DoD=0.25 seed=0 | MPC_HGS | 25 -> 25 | 1 -> 1 | 11.97 -> 7.62 | 0.67 -> 0.42 | 2.55 -> 1.67 | 18 -> 18 |
| c101_21_25 DoD=0.25 seed=0 | MPC_ACS | 25 -> 25 | 1 -> 1 | 2.30 -> 1.61 | 0.13 -> 0.09 | 0.72 -> 0.44 | 17 -> 17 |
| c201_21_50 DoD=0.75 seed=0 | MPC_COMPLETION | 50 -> 50 | 1 -> 1 | 0.92 -> 0.95 | 0.02 -> 0.02 | 0.15 -> 0.17 | 43 -> 43 |
| c201_21_50 DoD=0.75 seed=0 | MPC_MCTS | 50 -> 50 | 1 -> 1 | 190.58 -> 125.28 | 3.93 -> 2.55 | 4.71 -> 4.53 | 49 -> 50 |
| c201_21_50 DoD=0.75 seed=0 | MPC_ALNS | 50 -> 50 | 1 -> 1 | 142.72 -> 95.47 | 2.94 -> 1.97 | 4.75 -> 4.50 | 49 -> 49 |
| c201_21_50 DoD=0.75 seed=0 | MPC_HGS | 50 -> 50 | 1 -> 1 | 170.39 -> 128.52 | 3.83 -> 2.89 | 4.76 -> 4.55 | 45 -> 45 |
| c201_21_50 DoD=0.75 seed=0 | MPC_ACS | 50 -> 50 | 1 -> 1 | 70.81 -> 32.72 | 1.70 -> 0.79 | 4.73 -> 2.52 | 42 -> 42 |
| r101_21_100 DoD=0.25 seed=0 | MPC_COMPLETION | 91 -> 91 | 0 -> 0 | 2.33 -> 1.52 | 0.02 -> 0.01 | 0.33 -> 0.21 | 120 -> 120 |
| r101_21_100 DoD=0.25 seed=0 | MPC_MCTS | 98 -> 98 | 0 -> 0 | 31.58 -> 25.31 | 0.29 -> 0.23 | 2.46 -> 1.70 | 108 -> 108 |
| r101_21_100 DoD=0.25 seed=0 | MPC_ALNS | 99 -> 99 | 0 -> 0 | 35.27 -> 23.52 | 0.34 -> 0.22 | 2.84 -> 1.54 | 104 -> 104 |
| r101_21_100 DoD=0.25 seed=0 | MPC_HGS | 100 -> 99 | 1 -> 0 | 143.75 -> 115.11 | 1.79 -> 0.99 | 4.66 -> 4.48 | 81 -> 117 |
| r101_21_100 DoD=0.25 seed=0 | MPC_ACS | 96 -> 96 | 0 -> 0 | 253.52 -> 246.14 | 2.15 -> 2.09 | 4.67 -> 4.56 | 119 -> 119 |

## Regressions and interpretation

Observed paired service regressions: 1. r101_21_100 MPC_HGS 100->99
- MPC_COMPLETION: service delta +0, CPU ratio 0.76; development candidate only; requires independent confirmation.
- MPC_MCTS: service delta +0, CPU ratio 0.68; development candidate only; requires independent confirmation.
- MPC_ALNS: service delta +0, CPU ratio 0.67; development candidate only; requires independent confirmation.
- MPC_HGS: service delta -1, CPU ratio 0.77; reject shared combined enhancement on these development cases.
- MPC_ACS: service delta +0, CPU ratio 0.86; development candidate only; requires independent confirmation.

## Correctness and engineering observations

Fixed-work identical checksums on 3/3 seen roots; each accepted route independently replayed through the unchanged physical transition.
The optional fast screen removes calculations of two stored profile arrays that no screening caller consumes. Existing forward/backward time-window screening, capacity and safe-return checks, bounded charging labels, and exact transition reuse were already present; they were not redundantly reimplemented.
The MCTS skip-blocked rollout fixes a confirmed zero-option early exit in a synthetic root. It is method-specific and therefore cannot be attributed to the shared framework.
Prior HGS/ACS 100-customer divergences began in same-root, deadline-sensitive searches: HGS at decision 5 (same selected first actions but different future suffixes), ACS at decision 19 (different plan and first action). Their exact cause is not established by fixed-work equality; whole-scenario paired outcomes above are decisive.

## 100-customer case

- MPC_COMPLETION: 91 -> 91 served; 2.33 -> 1.52 CPU s.
- MPC_MCTS: 98 -> 98 served; 31.58 -> 25.31 CPU s.
- MPC_ALNS: 99 -> 99 served; 35.27 -> 23.52 CPU s.
- MPC_HGS: 100 -> 99 served; 143.75 -> 115.11 CPU s.
- MPC_ACS: 96 -> 96 served; 253.52 -> 246.14 CPU s.

## Limits and next study

Additional development parents completed: **0**. The preregistered gate skipped them after the HGS service regression. There are only three paired pilot scenarios from three benchmark parents; no confidence interval is defensible. The full test suite passed **393/393** with filesystem access to Windows temporary directories and multiprocessing pipes; the sandboxed attempt hit access denials. Focused new/optimizer tests passed 49/49.

For 30 paired scenarios across five methods and two variants (300 full workers), the observed-mean cost is approximately 5.28 worker hours; a conservative 2x allowance is 10.55 hours. This is an estimate, not an authorized run.
Conditional distance and fleet/charging outcomes are in `paired_summary.json`; distance is not compared as efficiency when customer sets differ.
The original publication package and Reliability V2 stop marker were not touched. Timings are sequential fresh-process measurements on a shared machine.

The separately frozen [fixed-seed HGS/ACS ablation](../ablation_1/REPORT.md) reproduced 100 to 99 served for HGS and 96 to 95 for ACS with fast evaluation alone. Adaptive-only and guard-only did not activate their intended mechanism on this 100-customer root; apparent service changes under those variants should not be attributed to successful early stopping or accepted recovery actions. Keep the original HGS/ACS configurations for publication.
