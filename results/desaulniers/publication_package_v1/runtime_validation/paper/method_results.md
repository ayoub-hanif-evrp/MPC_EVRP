# Matched runtime implementation validation

All 30/30 separate-worker runs passed raw SHA-256 verification, exact scenario/fleet
matching, independent physical replay, duplicate/future-information checks
and the five-second decision limit. These are three development size
variants of one parent case; results are descriptive implementation
checks and carry no independent-instance generalization claim.

The guarded variant enables validated-incumbent initialization fallback
and exact forced retained-route coordination. Core search strategies,
canonical objective, physics, fleets, releases and configured budgets match.

Machine-load policy: One campaign worker at a time; unrelated system workloads may run; no machine-exclusive timing claim.
Process isolation does not imply an otherwise idle computer. Runtime
ratios are descriptive shared-machine observations, not hardware benchmarks.

| Method | Original service % | Guarded service % | Original complete % | Guarded complete % | Customer change |
| --- | ---: | ---: | ---: | ---: | ---: |
| MPC_COMPLETION | 86.86 | 86.86 | 0.00 | 0.00 | +0 |
| MPC_MCTS | 89.71 | 89.71 | 0.00 | 0.00 | +0 |
| MPC_ALNS | 93.71 | 93.71 | 0.00 | 0.00 | +0 |
| MPC_HGS | 94.86 | 94.86 | 0.00 | 0.00 | +0 |
| MPC_ACS | 92.00 | 92.00 | 0.00 | 0.00 | +0 |

| Method | Mean decision s old / guarded | p95 s old / guarded | Max s old / guarded | Timed-section median ratio |
| --- | --- | --- | --- | ---: |
| MPC_COMPLETION | 0.0174 / 0.0128 | 0.0357 / 0.0286 | 0.0619 / 0.0700 | 0.77x |
| MPC_MCTS | 0.0965 / 0.0877 | 0.4676 / 0.5015 | 1.6199 / 1.5314 | 0.90x |
| MPC_ALNS | 0.3419 / 0.3351 | 1.1682 / 1.1556 | 1.7684 / 1.7103 | 1.05x |
| MPC_HGS | 1.2990 / 1.3589 | 3.9525 / 4.2104 | 4.6498 / 4.6511 | 0.98x |
| MPC_ACS | 0.8933 / 0.8806 | 3.2356 / 3.1300 | 4.4249 / 4.1812 | 0.91x |

| Method | Coordination solver calls old / guarded | Forced choices | Initialization fallbacks |
| --- | --- | ---: | ---: |
| MPC_COMPLETION | 822 / 0 | 274 | 0 |
| MPC_MCTS | 840 / 0 | 280 | 0 |
| MPC_ALNS | 831 / 0 | 277 | 0 |
| MPC_HGS | 813 / 0 | 271 | 0 |
| MPC_ACS | 783 / 0 | 261 | 0 |

Search may execute a different number of iterations under the same
wall-clock limit when coordination overhead changes. Consequently this
small sample does not establish a general service improvement or
noninferiority claim. Synthetic deadline tests separately exercise the
initialization fallback even when it is not triggered in these runs.

`worker_wall_seconds` measures simulation plus independent audit inside
the worker; the separate parent process timer includes startup and
preparation. Neither is an optimization-decision latency.

