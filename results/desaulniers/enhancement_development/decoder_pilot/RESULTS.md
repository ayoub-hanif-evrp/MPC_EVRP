# Continuous charging decoder: development pilot

This is a small **selected-case development ablation**, not independent evaluation. Both variants used the same released requests, K_ref, common objective, original dispatch policy, and five-second decision limit. Every raw trace has a manifest SHA-256 and independent plant replay.

| Instance | DoD | Method | Original | LP fallback | Change | Worker time original / LP (s) | Max decision latency original / LP (s) |
| --- | ---: | --- | ---: | ---: | ---: | --- | --- |
| r101_21_100 | 0.75 | MPC_ALNS | 94/100 | 91/100 | -3 | 40.4 / 112.3 | 0.671 / 1.800 |
| r101_21_100 | 0.75 | MPC_COMPLETION | 82/100 | 82/100 | +0 | 2.4 / 7.3 | 0.042 / 0.154 |
| r101_21_50 | 0.5 | MPC_ALNS | 47/50 | 47/50 | +0 | 7.7 / 16.8 | 0.390 / 0.704 |
| r101_21_50 | 0.5 | MPC_COMPLETION | 48/50 | 48/50 | +0 | 0.8 / 1.0 | 0.037 / 0.066 |
| rc101_21_25 | 0.75 | MPC_ALNS | 22/25 | 22/25 | +0 | 1.9 / 7.8 | 0.102 / 0.476 |
| rc101_21_25 | 0.75 | MPC_COMPLETION | 23/25 | 23/25 | +0 | 0.3 / 0.5 | 0.011 / 0.044 |

## Decision

- MPC_COMPLETION: paired service changes +0, +0, +0; worker-time ratios 2.98x, 1.24x, 2.00x.
- MPC_ALNS: paired service changes -3, +0, +0; worker-time ratios 2.78x, 2.18x, 4.12x.

The LP fallback solves a synthetic fixed-charge-target miss, but the first-decision ALNS loss probe found no LP-only insertion witness on these development traces. This end-to-end pilot does not support adopting it as the default. A bounded decoder failure does not prove physical infeasibility. No new final holdout was opened.
