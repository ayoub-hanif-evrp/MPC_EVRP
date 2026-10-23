# ALNS recovery v2: balanced development screen

This 18-instance screen is **development data**, not an independent final holdout. It crosses six Desaulniers families and sizes 25/50/100 at DoD 0.75, seed 0. Original and recovery ALNS use identical scenario hashes, fixed K_ref, original decoder/dispatch, common objective, and five-second decisions. All 36 isolated raw runs passed independent replay and SHA-256 checks.

Customer-weighted service: 1033/1050 (98.38%) original versus 1034/1050 (98.48%) recovery; paired change +0.10 percentage points, instance-bootstrap 95% interval [-0.23, +0.43].

Complete scenarios: 12/18 original versus 12/18 recovery; paired change +0.0 percentage points, instance-bootstrap 95% interval [+0.0, +0.0].

Worker-time median ratio: 1.00x; total 1742.9s original versus 1822.3s recovery. These are isolated whole-run times, not a change to the five-second per-decision budget.

## Paired instances

| Instance | Family | Size | Original | Recovery v2 | Change | Whole-run time old / v2 (s) | Max decision latency old / v2 (s) |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| c101_21_100 | C1 | 100 | 98 | 98 | +0 | 67.9 / 68.1 | 1.764 / 1.779 |
| c101_21_25 | C1 | 25 | 25 | 25 | +0 | 1.2 / 1.2 | 0.066 / 0.064 |
| c101_21_50 | C1 | 50 | 50 | 50 | +0 | 14.4 / 14.4 | 0.867 / 0.861 |
| c201_21_100 | C2 | 100 | 100 | 100 | +0 | 342.6 / 340.2 | 4.729 / 4.776 |
| c201_21_25 | C2 | 25 | 25 | 25 | +0 | 1.2 / 1.2 | 0.139 / 0.141 |
| c201_21_50 | C2 | 50 | 50 | 50 | +0 | 149.1 / 148.4 | 4.750 / 4.740 |
| r101_21_100 | R1 | 100 | 94 | 95 | +1 | 51.8 / 125.1 | 0.864 / 2.064 |
| r101_21_25 | R1 | 25 | 23 | 24 | +1 | 1.1 / 2.7 | 0.051 / 0.166 |
| r101_21_50 | R1 | 50 | 47 | 47 | +0 | 6.7 / 22.8 | 0.294 / 0.746 |
| r201_21_100 | R2 | 100 | 100 | 100 | +0 | 357.5 / 356.1 | 4.794 / 4.801 |
| r201_21_25 | R2 | 25 | 25 | 25 | +0 | 15.9 / 16.5 | 3.500 / 3.572 |
| r201_21_50 | R2 | 50 | 50 | 50 | +0 | 146.3 / 142.9 | 4.752 / 4.763 |
| rc101_21_100 | RC1 | 100 | 100 | 100 | +0 | 43.5 / 44.3 | 1.136 / 1.245 |
| rc101_21_25 | RC1 | 25 | 22 | 21 | -1 | 1.8 / 3.7 | 0.093 / 0.320 |
| rc101_21_50 | RC1 | 50 | 49 | 49 | +0 | 6.0 / 7.8 | 0.330 / 0.345 |
| rc201_21_100 | RC2 | 100 | 100 | 100 | +0 | 350.8 / 347.8 | 4.770 / 4.751 |
| rc201_21_25 | RC2 | 25 | 25 | 25 | +0 | 25.7 / 25.9 | 4.633 / 4.644 |
| rc201_21_50 | RC2 | 50 | 50 | 50 | +0 | 159.2 / 152.9 | 4.751 / 4.750 |

## By size

| Size | Scenarios | Original service | Recovery service | Paired change | Complete old / v2 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 25 | 6 | 145 | 145 | +0 | 4 / 4 |
| 50 | 6 | 296 | 296 | +0 | 4 / 4 |
| 100 | 6 | 592 | 593 | +1 | 4 / 4 |

## By family

| Family | Scenarios | Paired customers gained |
| --- | ---: | ---: |
| C1 | 3 | +0 |
| C2 | 3 | +0 |
| R1 | 3 | +2 |
| R2 | 3 | +0 |
| RC1 | 3 | -1 |
| RC2 | 3 | +0 |

The bootstrap resamples **base instances**, not decisions or customers. Intervals are exploratory: one seed and one DoD per instance, with no multiplicity-adjusted confirmatory claim. Neither this screen nor the selected pilot may be used to tune on historical holdouts.
