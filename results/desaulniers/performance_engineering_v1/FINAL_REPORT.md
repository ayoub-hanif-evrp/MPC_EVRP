# Performance engineering: consolidated technical report

Status: complete; 75/75 diagnostic/pilot workers saved; 15/15 complete unprofiled pairs.
Execution source: `d9cc8cb9520c3cf2558466ba17b6b4635960b016`. Shared machine, fresh sequential processes, one native thread per worker.
This is a three-parent development engineering pilot, not a new independent final study. The original policy remains the default.

## Executive Result

For the tested paired workload, aggregate unprofiled process time was 1058.552 s original versus 887.845 s incremental (1.19x), with 1039.625 versus 872.109 process CPU seconds (1.19x).
Service/complete-service regressions occurred in 2 of 15 pairs. Every case is listed below, including losses.
These totals summarize this engineering workload, not a universal five-engine speedup. Keep the original default; the new evaluator is an explicit optional policy.

Observed service regression: r101_21_100, MPC_HGS: 100 to 98 served; 81 to 122 optimization triggers. Exact fixed-work equivalence does not establish closed-loop service noninferiority, and this pilot does not isolate the causal source of trajectory differences.

Observed service regression: r101_21_100, MPC_ACS: 96 to 95 served; 119 to 122 optimization triggers. Exact fixed-work equivalence does not establish closed-loop service noninferiority, and this pilot does not isolate the causal source of trajectory differences.

## 1. Why the earlier study was expensive

The stopped Reliability V2 study performed 28,843 optimization calls: 13.567 of 13.692 worker hours were planning (99.09%).
Its 1,116-run grid multiplied full scenarios by five engines and multiple variants before effectiveness was established.
Five seconds bounds one MPC decision, not a full scenario. Its prior 12-hour control was a soft scenario-boundary pause.
All 361 Reliability V2 raws were byte-hash verified against their saved manifest, and the stopped_by_user marker was verified. Protocols and historical primary results are preserved; that campaign was not resumed.

## 2. Exact implementation changes

- Optional `proposal_cache_policy=incremental_v1`; original and prior cache-only (`root_v1`) implementations remain runnable.
- Reuse exact greedy MPC prefix states and the original bounded charging decoder's complete prefix frontiers. Prefix choices do not depend on later customers.
- Precompute each current customer's nearest-safe energy once per decoder stage. Prune only prohibited inter-station arcs or station paths that violate time windows even with zero charging time.
- Cache exact planning transitions, including failure reason/message, under complete physical state/action/require-return keys.
  Frozen observations are held strongly by decision-local identity, preventing recycled IDs or cross-observation reuse without repeatedly hashing all visible customers.
- Cache the unchanged evaluator's entire score/component result for identical sequences/actions/costs and constructor ownership anchors.
  No floating-point summation order or lexicographic priority changes. Existing route/criticality/screen caches already handle unchanged route contributions.
- Every cache is bounded and closed at a decision boundary or exception. Deadlines precede planning cache hits. No event is suppressed and no optimizer strategy or iteration count is reduced.
- The independent plant/auditor in evrp/model.py and canonical evrp/optimizers/objective.py are unchanged.

## 3. Tests and fixed-work equivalence

Test suite evidence: 389 tests, 0 failures, 0 errors, 0 skipped (48.274 s).
Independently replayed saved profile/pilot trajectories: 36. All accepted route microbenchmarks are also replayed by the uncached original transition.
Tests cover randomized and boundary charging routes, MP topology, complete observation/config invalidation, exact fixed-work optimizer results for all five engines, deadlines and finite cache caps.
Original/cache-only/incremental microchecksums must agree before pilot admission. Wall-clock-limited search need not produce identical trajectories.

### Fixed-work measurements

One first-observation root per size, at most 12 unique candidates and eight-service prefixes. Forced fallback and repeated-score phases deliberately isolate bottlenecks; they do not establish a general scenario speedup.
These short microtimings are single trials, some below Windows process-CPU clock granularity. Wall times and call reuse are descriptive; full-scenario CPU is the more stable end-to-end measure.

| Instance | Phase | Variant | Wall s | CPU s | Wall speedup vs original |
| --- | --- | --- | --- | --- | --- |
| c101_21_25 | route_construction | incremental_v1 | 0.005384 | 0.015625 | 1.58 |
| c101_21_25 | forced_charging_fallback | incremental_v1 | 0.001824 | 0.000000 | 4.78 |
| c101_21_25 | repeated_exact_objective | incremental_v1 | 0.001815 | 0.000000 | 1.99 |
| c101_21_25 | route_construction | original | 0.008529 | 0.015625 | 1.00 |
| c101_21_25 | forced_charging_fallback | original | 0.008725 | 0.000000 | 1.00 |
| c101_21_25 | repeated_exact_objective | original | 0.003622 | 0.000000 | 1.00 |
| c101_21_25 | route_construction | root_v1 | 0.008705 | 0.015625 | 0.98 |
| c101_21_25 | forced_charging_fallback | root_v1 | 0.008544 | 0.000000 | 1.02 |
| c101_21_25 | repeated_exact_objective | root_v1 | 0.003657 | 0.000000 | 0.99 |
| c201_21_50 | route_construction | incremental_v1 | 0.001164 | 0.000000 | 1.43 |
| c201_21_50 | forced_charging_fallback | incremental_v1 | 0.013062 | 0.015625 | 1.65 |
| c201_21_50 | repeated_exact_objective | incremental_v1 | 0.000979 | 0.000000 | 2.59 |
| c201_21_50 | route_construction | original | 0.001662 | 0.000000 | 1.00 |
| c201_21_50 | forced_charging_fallback | original | 0.021611 | 0.031250 | 1.00 |
| c201_21_50 | repeated_exact_objective | original | 0.002531 | 0.000000 | 1.00 |
| c201_21_50 | route_construction | root_v1 | 0.001333 | 0.000000 | 1.25 |
| c201_21_50 | forced_charging_fallback | root_v1 | 0.020744 | 0.031250 | 1.04 |
| c201_21_50 | repeated_exact_objective | root_v1 | 0.002202 | 0.000000 | 1.15 |
| r101_21_100 | route_construction | incremental_v1 | 0.002043 | 0.000000 | 1.00 |
| r101_21_100 | forced_charging_fallback | incremental_v1 | 0.001049 | 0.000000 | 9.07 |
| r101_21_100 | repeated_exact_objective | incremental_v1 | 0.007248 | 0.000000 | 1.74 |
| r101_21_100 | route_construction | original | 0.002039 | 0.000000 | 1.00 |
| r101_21_100 | forced_charging_fallback | original | 0.009521 | 0.015625 | 1.00 |
| r101_21_100 | repeated_exact_objective | original | 0.012636 | 0.015625 | 1.00 |
| r101_21_100 | route_construction | root_v1 | 0.002420 | 0.000000 | 0.84 |
| r101_21_100 | forced_charging_fallback | root_v1 | 0.009183 | 0.015625 | 1.04 |
| r101_21_100 | repeated_exact_objective | root_v1 | 0.013687 | 0.015625 | 0.92 |

### Python allocation probes (separate from timing runs)

| Instance | Variant | Current bytes | Peak bytes |
| --- | --- | --- | --- |
| c101_21_25 | original | 1195210 | 3452832 |
| c101_21_25 | incremental_v1 | 1203370 | 3452832 |
| c201_21_50 | original | 2460685 | 6424321 |
| c201_21_50 | incremental_v1 | 2503553 | 6424601 |
| r101_21_100 | original | 6160427 | 17953376 |
| r101_21_100 | incremental_v1 | 6140515 | 17953376 |

Allocation probes include input preparation, whose peak can dominate cache allocation. Equal peaks do not prove that caches use no memory.

## 4. Unprofiled original versus optimized scenarios

Three prespecified previously seen eligible cases: 25, 50 and 100 customers. Identical archived scenario/ref/fleet and full original parameters; matched pair order alternates.
The reference is original evaluator mode in the same frozen build, with common telemetry/dispatch wrappers on both sides, not a separate timing checkout of the historical primary executable.
Both sides retain the existing validated_incumbent_v1 initialization and forced_retained_v1 coordination policies; first-action, constructor and route-decoder policies are original. The only paired configuration difference is proposal_cache_policy.
Both variants use the same lightweight operation counters. cProfile and tracemalloc run in different workers and are never pooled into pilot runtimes.

| Method | Pairs | Original process s | Optimized process s | Wall ratio | Original CPU s | Optimized CPU s | CPU ratio | Original service % | Optimized service % | Original complete % | Optimized complete % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MPC_COMPLETION | 3 | 6.775 | 5.816 | 1.165 | 6.016 | 4.969 | 1.211 | 94.857 | 94.857 | 66.667 | 66.667 |
| MPC_MCTS | 3 | 208.921 | 168.511 | 1.240 | 205.578 | 164.766 | 1.248 | 98.857 | 98.857 | 66.667 | 66.667 |
| MPC_ALNS | 3 | 181.604 | 155.819 | 1.165 | 179.062 | 152.906 | 1.171 | 99.429 | 99.429 | 66.667 | 66.667 |
| MPC_HGS | 3 | 332.633 | 291.496 | 1.141 | 325.438 | 287.703 | 1.131 | 100.000 | 98.857 | 100.000 | 66.667 |
| MPC_ACS | 3 | 328.619 | 266.204 | 1.234 | 323.531 | 261.766 | 1.236 | 97.714 | 97.143 | 66.667 | 66.667 |

### Every matched case, including regressions

| Instance | Method | Original / optimized served | Original / optimized complete | Original / optimized process s |
| --- | --- | --- | --- | --- |
| c101_21_25 | MPC_COMPLETION | 25 / 25 | True / True | 1.269 / 1.215 |
| c101_21_25 | MPC_MCTS | 25 / 25 | True / True | 8.274 / 5.548 |
| c101_21_25 | MPC_ALNS | 25 / 25 | True / True | 3.380 / 2.474 |
| c101_21_25 | MPC_HGS | 25 / 25 | True / True | 12.358 / 7.970 |
| c101_21_25 | MPC_ACS | 25 / 25 | True / True | 3.333 / 2.626 |
| c201_21_50 | MPC_COMPLETION | 50 / 50 | True / True | 2.023 / 1.977 |
| c201_21_50 | MPC_MCTS | 50 / 50 | True / True | 168.266 / 136.880 |
| c201_21_50 | MPC_ALNS | 50 / 50 | True / True | 141.669 / 129.290 |
| c201_21_50 | MPC_HGS | 50 / 50 | True / True | 175.789 / 159.516 |
| c201_21_50 | MPC_ACS | 50 / 50 | True / True | 72.347 / 34.655 |
| r101_21_100 | MPC_COMPLETION | 91 / 91 | False / False | 3.484 / 2.624 |
| r101_21_100 | MPC_MCTS | 98 / 98 | False / False | 32.381 / 26.082 |
| r101_21_100 | MPC_ALNS | 99 / 99 | False / False | 36.555 / 24.056 |
| r101_21_100 | MPC_HGS | 100 / 98 | True / False | 144.487 / 124.010 |
| r101_21_100 | MPC_ACS | 96 / 95 | False / False | 252.939 / 228.922 |

### Decision latency, not whole-scenario cost

| Case / method / variant | Decisions | Mean s | p95 s | Max s | Planning s | Process CPU / wall % |
| --- | --- | --- | --- | --- | --- | --- |
| c101_21_25 / MPC_ACS / incremental_v1 | 17 | 0.089754 | 0.309950 | 0.429241 | 1.5258 | 91.62 |
| c101_21_25 / MPC_ACS / original | 17 | 0.126044 | 0.450177 | 0.706448 | 2.1427 | 91.42 |
| c101_21_25 / MPC_ALNS / incremental_v1 | 15 | 0.091061 | 0.375989 | 0.514247 | 1.3659 | 89.69 |
| c101_21_25 / MPC_ALNS / original | 15 | 0.148946 | 0.598894 | 0.824492 | 2.2342 | 89.67 |
| c101_21_25 / MPC_COMPLETION / incremental_v1 | 18 | 0.003196 | 0.010328 | 0.026783 | 0.0575 | 73.32 |
| c101_21_25 / MPC_COMPLETION / original | 18 | 0.004738 | 0.014327 | 0.038395 | 0.0853 | 77.60 |
| c101_21_25 / MPC_HGS / incremental_v1 | 18 | 0.375810 | 1.099142 | 1.517315 | 6.7646 | 94.69 |
| c101_21_25 / MPC_HGS / original | 18 | 0.617456 | 1.935939 | 2.341355 | 11.1142 | 96.22 |
| c101_21_25 / MPC_MCTS / incremental_v1 | 15 | 0.290673 | 0.811129 | 0.849358 | 4.3601 | 92.66 |
| c101_21_25 / MPC_MCTS / original | 15 | 0.473912 | 1.433022 | 1.682405 | 7.1087 | 93.86 |
| c201_21_50 / MPC_ACS / incremental_v1 | 42 | 0.791138 | 1.824284 | 2.185394 | 33.2278 | 97.98 |
| c201_21_50 / MPC_ACS / original | 42 | 1.689909 | 4.678979 | 4.736919 | 70.9762 | 97.84 |
| c201_21_50 / MPC_ALNS / incremental_v1 | 52 | 2.459541 | 4.694614 | 4.750929 | 127.8962 | 98.31 |
| c201_21_50 / MPC_ALNS / original | 48 | 2.922095 | 4.713316 | 4.750627 | 140.2606 | 98.72 |
| c201_21_50 / MPC_COMPLETION / incremental_v1 | 43 | 0.018594 | 0.129352 | 0.169148 | 0.7995 | 88.50 |
| c201_21_50 / MPC_COMPLETION / original | 43 | 0.018433 | 0.100969 | 0.147002 | 0.7926 | 90.38 |
| c201_21_50 / MPC_HGS / incremental_v1 | 45 | 3.509257 | 4.716435 | 4.806911 | 157.9166 | 98.89 |
| c201_21_50 / MPC_HGS / original | 49 | 3.557671 | 4.741271 | 4.751817 | 174.3259 | 97.84 |
| c201_21_50 / MPC_MCTS / incremental_v1 | 48 | 2.821419 | 4.651314 | 4.695039 | 135.4281 | 98.16 |
| c201_21_50 / MPC_MCTS / original | 50 | 3.336623 | 4.751610 | 4.757170 | 166.8312 | 98.78 |
| r101_21_100 / MPC_ACS / incremental_v1 | 122 | 1.860369 | 4.653746 | 4.664348 | 226.9650 | 98.46 |
| r101_21_100 / MPC_ACS / original | 119 | 2.108952 | 4.653154 | 4.657691 | 250.9653 | 98.72 |
| r101_21_100 / MPC_ALNS / incremental_v1 | 104 | 0.212832 | 0.762839 | 1.517672 | 22.1345 | 98.01 |
| r101_21_100 / MPC_ALNS / original | 104 | 0.333125 | 1.266974 | 2.695287 | 34.6450 | 98.95 |
| r101_21_100 / MPC_COMPLETION / incremental_v1 | 120 | 0.008511 | 0.011171 | 0.206078 | 1.0213 | 88.72 |
| r101_21_100 / MPC_COMPLETION / original | 120 | 0.015334 | 0.022382 | 0.328111 | 1.8401 | 91.94 |
| r101_21_100 / MPC_HGS / incremental_v1 | 122 | 0.999179 | 4.654775 | 4.661343 | 121.8998 | 98.71 |
| r101_21_100 / MPC_HGS / original | 81 | 1.759079 | 4.652077 | 4.658160 | 142.4854 | 97.97 |
| r101_21_100 / MPC_MCTS / incremental_v1 | 108 | 0.224534 | 1.436872 | 1.661266 | 24.2497 | 96.87 |
| r101_21_100 / MPC_MCTS / original | 108 | 0.281704 | 1.758913 | 2.426297 | 30.4240 | 97.57 |

## 5. Where CPU work is reused

Repeated ownership alone does not define an identical physical/observable root and is never used to skip a meaningful event.
Returning the constructor unchanged does not prove another search was useless or that early stopping is harmless.

| Case / method / variant | Repeated root hashes | Empty service sets | Constructor unchanged | Replay hits | Replay misses | Transition hits | Transition misses | Greedy customers reused | Label customers reused | Objective hits | Replay hit % | Transition hit % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c101_21_25 / MPC_ACS / incremental_v1 | 0 | 7 | 10 | 388 | 1000 | 14788 | 39086 | 1397 | 366 | 6160 | 27.95 | 27.45 |
| c101_21_25 / MPC_ACS / original | 0 | 7 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| c101_21_25 / MPC_ALNS / incremental_v1 | 0 | 6 | 8 | 416 | 859 | 15339 | 91877 | 1341 | 497 | 4321 | 32.63 | 14.31 |
| c101_21_25 / MPC_ALNS / original | 0 | 6 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| c101_21_25 / MPC_COMPLETION / incremental_v1 | 0 | 7 | 18 | 212 | 61 | 810 | 2346 | 34 | 7 | 11 | 77.66 | 25.67 |
| c101_21_25 / MPC_COMPLETION / original | 0 | 7 | 18 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| c101_21_25 / MPC_HGS / incremental_v1 | 0 | 5 | 8 | 1108 | 3048 | 57839 | 386473 | 5543 | 2391 | 1074 | 26.66 | 13.02 |
| c101_21_25 / MPC_HGS / original | 0 | 5 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| c101_21_25 / MPC_MCTS / incremental_v1 | 0 | 5 | 9 | 692 | 2164 | 53064 | 183671 | 3214 | 1048 | 13978 | 24.23 | 22.41 |
| c101_21_25 / MPC_MCTS / original | 0 | 5 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| c201_21_50 / MPC_ACS / incremental_v1 | 0 | 0 | 29 | 1930 | 8968 | 143296 | 1922658 | 28625 | 5841 | 43726 | 17.71 | 6.94 |
| c201_21_50 / MPC_ACS / original | 0 | 0 | 29 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| c201_21_50 / MPC_ALNS / incremental_v1 | 0 | 4 | 15 | 3372 | 6904 | 152849 | 10141541 | 22169 | 12382 | 18961 | 32.81 | 1.48 |
| c201_21_50 / MPC_ALNS / original | 0 | 4 | 17 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| c201_21_50 / MPC_COMPLETION / incremental_v1 | 0 | 1 | 43 | 566 | 158 | 5044 | 61160 | 33 | 0 | 4 | 78.18 | 7.62 |
| c201_21_50 / MPC_COMPLETION / original | 0 | 1 | 43 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| c201_21_50 / MPC_HGS / incremental_v1 | 0 | 3 | 17 | 4520 | 13137 | 205070 | 12223583 | 44635 | 19098 | 3715 | 25.60 | 1.65 |
| c201_21_50 / MPC_HGS / original | 0 | 4 | 18 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| c201_21_50 / MPC_MCTS / incremental_v1 | 0 | 2 | 16 | 4331 | 14460 | 245698 | 10592606 | 41245 | 18340 | 70170 | 23.05 | 2.27 |
| c201_21_50 / MPC_MCTS / original | 0 | 3 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| r101_21_100 / MPC_ACS / incremental_v1 | 0 | 0 | 95 | 15157 | 23619 | 265418 | 339780 | 31773 | 6845 | 117225 | 39.09 | 43.86 |
| r101_21_100 / MPC_ACS / original | 0 | 0 | 98 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| r101_21_100 / MPC_ALNS / incremental_v1 | 0 | 0 | 50 | 11476 | 13067 | 173339 | 480977 | 17014 | 4906 | 33187 | 46.76 | 26.49 |
| r101_21_100 / MPC_ALNS / original | 0 | 0 | 50 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| r101_21_100 / MPC_COMPLETION / incremental_v1 | 0 | 0 | 120 | 11419 | 1829 | 15139 | 16237 | 184 | 115 | 214 | 86.19 | 48.25 |
| r101_21_100 / MPC_COMPLETION / original | 0 | 0 | 120 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| r101_21_100 / MPC_HGS / incremental_v1 | 0 | 0 | 62 | 21271 | 55975 | 486142 | 2200187 | 60858 | 12258 | 3420 | 27.54 | 18.10 |
| r101_21_100 / MPC_HGS / original | 0 | 14 | 39 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |
| r101_21_100 / MPC_MCTS / incremental_v1 | 0 | 0 | 93 | 11733 | 6178 | 99154 | 172089 | 6671 | 1557 | 29838 | 65.51 | 36.56 |
| r101_21_100 / MPC_MCTS / original | 0 | 0 | 93 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | not enabled | not enabled |

### Route and objective call counts

Distinct route decodes are distinct keys within each immutable fleet problem; counts summed across problems may repeat equivalent roots. Global LRU misses are not claimed as globally unique routes.

| Case / method / variant | Build requests | Charging fallbacks | Fleet decode requests | Distinct problem decodes | Score requests | Score computations | Global route LRU hits | Global route LRU misses |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c101_21_25 / MPC_ACS / incremental_v1 | 1115 | 242 | 12202 | 1163 | 10688 | 4528 | 12 | 1103 |
| c101_21_25 / MPC_ACS / original | 1115 | 242 | 12202 | 1163 | 10688 | 10688 | 12 | 1103 |
| c101_21_25 / MPC_ALNS / incremental_v1 | 1071 | 396 | 7885 | 1088 | 6419 | 2098 | 5 | 1066 |
| c101_21_25 / MPC_ALNS / original | 1071 | 396 | 7885 | 1088 | 6419 | 6419 | 5 | 1066 |
| c101_21_25 / MPC_COMPLETION / incremental_v1 | 30 | 10 | 30 | 30 | 54 | 43 | 0 | 30 |
| c101_21_25 / MPC_COMPLETION / original | 30 | 10 | 30 | 30 | 54 | 54 | 0 | 30 |
| c101_21_25 / MPC_HGS / incremental_v1 | 5276 | 1793 | 16551 | 5325 | 9276 | 8202 | 15 | 5261 |
| c101_21_25 / MPC_HGS / original | 5276 | 1793 | 16551 | 5325 | 9276 | 9276 | 15 | 5261 |
| c101_21_25 / MPC_MCTS / incremental_v1 | 5853 | 869 | 86676 | 5883 | 19604 | 5626 | 11 | 5842 |
| c101_21_25 / MPC_MCTS / original | 5853 | 869 | 86676 | 5883 | 19604 | 19604 | 11 | 5842 |
| c201_21_50 / MPC_ACS / incremental_v1 | 9161 | 1475 | 74618 | 9286 | 72403 | 28677 | 3 | 9158 |
| c201_21_50 / MPC_ACS / original | 9011 | 1443 | 71807 | 9136 | 69691 | 69691 | 3 | 9008 |
| c201_21_50 / MPC_ALNS / incremental_v1 | 7545 | 3303 | 32608 | 7589 | 30200 | 11239 | 2 | 7543 |
| c201_21_50 / MPC_ALNS / original | 6004 | 2276 | 26011 | 6032 | 24601 | 24601 | 3 | 6001 |
| c201_21_50 / MPC_COMPLETION / incremental_v1 | 53 | 11 | 53 | 53 | 129 | 125 | 0 | 53 |
| c201_21_50 / MPC_COMPLETION / original | 53 | 11 | 53 | 53 | 129 | 129 | 0 | 53 |
| c201_21_50 / MPC_HGS / incremental_v1 | 19672 | 5354 | 38671 | 19775 | 25971 | 22256 | 5 | 19667 |
| c201_21_50 / MPC_HGS / original | 15954 | 3840 | 30493 | 16073 | 19703 | 19703 | 6 | 15948 |
| c201_21_50 / MPC_MCTS / incremental_v1 | 57937 | 5631 | 471365 | 58001 | 95703 | 25533 | 10 | 57927 |
| c201_21_50 / MPC_MCTS / original | 45389 | 4203 | 351896 | 45449 | 65878 | 65878 | 9 | 45380 |
| r101_21_100 / MPC_ACS / incremental_v1 | 25752 | 6035 | 417965 | 27403 | 321696 | 204471 | 262 | 25490 |
| r101_21_100 / MPC_ACS / original | 26751 | 5938 | 367885 | 28402 | 314014 | 314014 | 70 | 26681 |
| r101_21_100 / MPC_ALNS / incremental_v1 | 14669 | 4998 | 91896 | 15414 | 69300 | 36113 | 94 | 14575 |
| r101_21_100 / MPC_ALNS / original | 14669 | 4998 | 91896 | 15414 | 69300 | 69300 | 94 | 14575 |
| r101_21_100 / MPC_COMPLETION / incremental_v1 | 500 | 240 | 516 | 500 | 472 | 258 | 196 | 304 |
| r101_21_100 / MPC_COMPLETION / original | 500 | 240 | 516 | 500 | 472 | 472 | 196 | 304 |
| r101_21_100 / MPC_HGS / incremental_v1 | 84112 | 19990 | 219090 | 85355 | 114329 | 110909 | 67 | 84045 |
| r101_21_100 / MPC_HGS / original | 71110 | 17583 | 165464 | 71989 | 93001 | 93001 | 102 | 71008 |
| r101_21_100 / MPC_MCTS / incremental_v1 | 20249 | 1565 | 600768 | 20293 | 44979 | 15141 | 101 | 20148 |
| r101_21_100 / MPC_MCTS / original | 20249 | 1565 | 600768 | 20293 | 44979 | 44979 | 101 | 20148 |

## 6. Phase costs

Disjoint high-level measurements: input preparation, constructor, optimizer, final replay, other planning overhead, nonplanning simulation, independent audit, serialization and startup/polling residual.
Nonplanning simulation includes event processing, state hashing and physical dispatch. The startup residual also includes process teardown and monitor granularity.
Nested cProfile cumulative times below overlap; they must not be added as a time partition.

| Case / method / variant | Prepare s | Constructor s | Optimizer s | Final validation s | Other planning s | Nonplanning simulation s | Audit s | Serialize s | Startup/residual s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c101_21_25 / MPC_ACS / incremental_v1 | 0.0078 | 0.0417 | 1.4421 | 0.0005 | 0.0415 | 0.0491 | 0.0022 | 0.0315 | 0.9997 |
| c101_21_25 / MPC_ACS / original | 0.0081 | 0.0611 | 2.0628 | 0.0025 | 0.0164 | 0.0581 | 0.0024 | 0.0375 | 1.0696 |
| c101_21_25 / MPC_ALNS / incremental_v1 | 0.0078 | 0.0441 | 1.3068 | 0.0002 | 0.0147 | 0.0485 | 0.0019 | 0.0298 | 1.0097 |
| c101_21_25 / MPC_ALNS / original | 0.0078 | 0.0699 | 2.1481 | 0.0028 | 0.0134 | 0.0559 | 0.0019 | 0.0336 | 1.0371 |
| c101_21_25 / MPC_COMPLETION / incremental_v1 | 0.0082 | 0.0439 | 0.0043 | 0.0002 | 0.0091 | 0.0450 | 0.0018 | 0.0288 | 1.0634 |
| c101_21_25 / MPC_COMPLETION / original | 0.0085 | 0.0629 | 0.0079 | 0.0025 | 0.0120 | 0.0447 | 0.0018 | 0.0284 | 1.0904 |
| c101_21_25 / MPC_HGS / incremental_v1 | 0.0076 | 0.0529 | 6.6742 | 0.0004 | 0.0370 | 0.0714 | 0.0034 | 0.0395 | 1.0633 |
| c101_21_25 / MPC_HGS / original | 0.0083 | 0.0711 | 11.0135 | 0.0051 | 0.0245 | 0.0621 | 0.0024 | 0.0443 | 1.0992 |
| c101_21_25 / MPC_MCTS / incremental_v1 | 0.0080 | 0.0452 | 4.2929 | 0.0003 | 0.0217 | 0.0479 | 0.0020 | 0.0385 | 1.0688 |
| c101_21_25 / MPC_MCTS / original | 0.0082 | 0.0630 | 7.0281 | 0.0031 | 0.0145 | 0.0520 | 0.0025 | 0.0475 | 1.0367 |
| c201_21_50 / MPC_ACS / incremental_v1 | 0.0173 | 1.1538 | 31.8642 | 0.0011 | 0.2087 | 0.1000 | 0.0035 | 0.0437 | 1.2488 |
| c201_21_50 / MPC_ACS / original | 0.0175 | 1.0405 | 69.8027 | 0.0170 | 0.1159 | 0.1073 | 0.0030 | 0.0652 | 1.1630 |
| c201_21_50 / MPC_ALNS / incremental_v1 | 0.0171 | 1.8334 | 116.5159 | 0.0012 | 9.5456 | 0.1118 | 0.0047 | 0.0394 | 1.2061 |
| c201_21_50 / MPC_ALNS / original | 0.0172 | 1.4860 | 133.9392 | 0.0157 | 4.8197 | 0.1064 | 0.0032 | 0.0492 | 1.2140 |
| c201_21_50 / MPC_COMPLETION / incremental_v1 | 0.0173 | 0.7530 | 0.0167 | 0.0007 | 0.0291 | 0.1013 | 0.0029 | 0.0335 | 1.0099 |
| c201_21_50 / MPC_COMPLETION / original | 0.0177 | 0.6964 | 0.0348 | 0.0138 | 0.0476 | 0.0993 | 0.0030 | 0.0410 | 1.0558 |
| c201_21_50 / MPC_HGS / incremental_v1 | 0.0174 | 1.9885 | 146.3800 | 0.0012 | 9.5469 | 0.1296 | 0.0044 | 0.0689 | 1.3591 |
| c201_21_50 / MPC_HGS / original | 0.0172 | 2.0846 | 162.7288 | 0.0193 | 9.4931 | 0.1294 | 0.0036 | 0.0466 | 1.2524 |
| c201_21_50 / MPC_MCTS / incremental_v1 | 0.0174 | 1.4720 | 133.7381 | 0.0011 | 0.2170 | 0.1142 | 0.0033 | 0.0795 | 1.2202 |
| c201_21_50 / MPC_MCTS / original | 0.0172 | 1.1432 | 146.7390 | 0.0153 | 18.9337 | 0.1145 | 0.0057 | 0.0755 | 1.1868 |
| r101_21_100 / MPC_ACS / incremental_v1 | 0.0486 | 0.6237 | 224.8205 | 0.0101 | 1.5107 | 0.4668 | 0.0117 | 0.1177 | 1.2094 |
| r101_21_100 / MPC_ACS / original | 0.0485 | 1.0107 | 248.6536 | 0.1205 | 1.1804 | 0.4405 | 0.0172 | 0.1375 | 1.2305 |
| r101_21_100 / MPC_ALNS / incremental_v1 | 0.0478 | 0.4799 | 21.2980 | 0.0065 | 0.3501 | 0.5116 | 0.0093 | 0.1282 | 1.1877 |
| r101_21_100 / MPC_ALNS / original | 0.0473 | 0.8271 | 33.4615 | 0.0720 | 0.2844 | 0.5036 | 0.0124 | 0.1059 | 1.2039 |
| r101_21_100 / MPC_COMPLETION / incremental_v1 | 0.0489 | 0.6771 | 0.1903 | 0.0056 | 0.1482 | 0.3709 | 0.0091 | 0.1014 | 1.0450 |
| r101_21_100 / MPC_COMPLETION / original | 0.0476 | 1.1709 | 0.2991 | 0.0869 | 0.2832 | 0.3765 | 0.0091 | 0.1113 | 1.0713 |
| r101_21_100 / MPC_HGS / incremental_v1 | 0.0473 | 0.5342 | 120.3089 | 0.0095 | 1.0472 | 0.4931 | 0.0125 | 0.1348 | 1.2837 |
| r101_21_100 / MPC_HGS / original | 0.0483 | 0.7516 | 140.9806 | 0.0800 | 0.6733 | 0.5186 | 0.0094 | 0.1162 | 1.2799 |
| r101_21_100 / MPC_MCTS / incremental_v1 | 0.0501 | 0.5001 | 23.5393 | 0.0061 | 0.2042 | 0.4608 | 0.0158 | 0.1644 | 1.1028 |
| r101_21_100 / MPC_MCTS / original | 0.0482 | 0.9285 | 29.0707 | 0.1028 | 0.3221 | 0.5446 | 0.0124 | 0.1608 | 1.1567 |

### Size- and method-specific hotspot ranking

Sorted by own time within bounded separate profiles. Completion uses full scenarios; other engines use one saved root and the unchanged iteration settings with the usual 4.75-second inner allowance. Profiling perturbs search.

| Instance | Engine | Variant | Function | Calls | Own s | Cumulative s |
| --- | --- | --- | --- | --- | --- | --- |
| r101_21_100 | MPC_ACS | incremental_v1 | fleet_mcts.py:_option_rank | 558995 | 0.971108 | 2.529373 |
| r101_21_100 | MPC_ACS | original | fleet_mcts.py:_option_rank | 544345 | 0.938990 | 2.439916 |
| c201_21_50 | MPC_MCTS | original | model.py:transition | 191805 | 0.730218 | 2.987643 |
| c201_21_50 | MPC_HGS | original | model.py:transition | 181252 | 0.706103 | 2.902337 |
| r101_21_100 | MPC_ACS | original | instance.py:energy | 1939523 | 0.702485 | 1.219005 |
| r101_21_100 | MPC_ACS | incremental_v1 | instance.py:energy | 1923361 | 0.702321 | 1.219144 |
| r101_21_100 | MPC_ALNS | original | model.py:transition | 187993 | 0.664703 | 2.609216 |
| c201_21_50 | MPC_ALNS | original | model.py:transition | 158533 | 0.607837 | 2.461675 |
| c201_21_50 | MPC_MCTS | incremental_v1 | model.py:transition | 143672 | 0.593137 | 2.535749 |
| c101_21_25 | MPC_MCTS | original | model.py:transition | 163047 | 0.562017 | 2.192461 |
| c101_21_25 | MPC_HGS | original | model.py:transition | 158777 | 0.560238 | 2.177276 |
| r101_21_100 | MPC_COMPLETION | original | model.py:transition | 137863 | 0.556664 | 2.149042 |
| c101_21_25 | MPC_ALNS | original | model.py:transition | 148087 | 0.520129 | 2.022252 |
| r101_21_100 | MPC_MCTS | incremental_v1 | instance.py:distance | 1160380 | 0.499666 | 0.819033 |
| r101_21_100 | MPC_COMPLETION | original | instance.py:energy | 1366378 | 0.493581 | 0.844163 |
| c201_21_50 | MPC_HGS | incremental_v1 | model.py:transition | 120005 | 0.484131 | 2.078227 |
| r101_21_100 | MPC_HGS | original | instance.py:energy | 1223136 | 0.445187 | 0.773201 |
| r101_21_100 | MPC_HGS | incremental_v1 | instance.py:energy | 1114926 | 0.416973 | 0.725255 |
| r101_21_100 | MPC_HGS | original | model.py:transition | 116267 | 0.410929 | 1.648268 |
| r101_21_100 | MPC_ACS | incremental_v1 | fleet_mcts.py:screened_options | 32686 | 0.404575 | 3.879118 |
| r101_21_100 | MPC_ACS | original | instance.py:_rounded_up | 2071270 | 0.395240 | 0.555886 |
| r101_21_100 | MPC_ACS | incremental_v1 | instance.py:_rounded_up | 2033425 | 0.388788 | 0.548162 |
| r101_21_100 | MPC_ACS | original | fleet_mcts.py:screened_options | 31628 | 0.388244 | 3.688014 |
| r101_21_100 | MPC_HGS | incremental_v1 | fleet_mcts.py:_option_rank | 209229 | 0.385553 | 0.997045 |
| r101_21_100 | MPC_MCTS | original | instance.py:distance | 888608 | 0.382105 | 0.622323 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | instance.py:energy | 1111210 | 0.380190 | 0.650803 |
| r101_21_100 | MPC_ALNS | incremental_v1 | model.py:transition | 106215 | 0.379588 | 1.669934 |
| r101_21_100 | MPC_COMPLETION | original | instance.py:_rounded_up | 1889264 | 0.363225 | 0.506374 |
| r101_21_100 | MPC_ALNS | original | instance.py:energy | 969745 | 0.347524 | 0.604013 |
| r101_21_100 | MPC_MCTS | original | model.py:transition | 101554 | 0.333605 | 1.356062 |
| r101_21_100 | MPC_HGS | incremental_v1 | fleet_mcts.py:screened_options | 22436 | 0.330814 | 2.276136 |
| c201_21_50 | MPC_HGS | original | instance.py:energy | 899815 | 0.320263 | 0.562354 |
| c201_21_50 | MPC_MCTS | original | instance.py:energy | 921982 | 0.317568 | 0.558096 |
| c101_21_25 | MPC_HGS | original | instance.py:energy | 902801 | 0.315831 | 0.553033 |
| c201_21_50 | MPC_COMPLETION | original | model.py:transition | 84355 | 0.312217 | 1.363024 |
| r101_21_100 | MPC_HGS | original | instance.py:_rounded_up | 1578581 | 0.307274 | 0.432781 |
| c201_21_50 | MPC_MCTS | original | dataclasses.py:replace | 150869 | 0.288630 | 0.655062 |
| r101_21_100 | MPC_MCTS | incremental_v1 | instance.py:_rounded_up | 1464516 | 0.286653 | 0.397515 |
| r101_21_100 | MPC_HGS | incremental_v1 | instance.py:_rounded_up | 1426035 | 0.284112 | 0.400593 |
| r101_21_100 | MPC_MCTS | incremental_v1 | fleet_mcts.py:<genexpr> | 1754550 | 0.283832 | 0.906440 |
| c201_21_50 | MPC_MCTS | incremental_v1 | evaluation_cache.py:transition | 144814 | 0.283335 | 3.242757 |
| r101_21_100 | MPC_ACS | incremental_v1 | ~:<built-in method builtins.max> | 2298975 | 0.282035 | 0.282447 |
| c201_21_50 | MPC_HGS | original | dataclasses.py:replace | 142370 | 0.279768 | 0.635958 |
| r101_21_100 | MPC_ALNS | original | instance.py:_rounded_up | 1414765 | 0.277808 | 0.389515 |
| r101_21_100 | MPC_ACS | original | ~:<built-in method builtins.max> | 2280633 | 0.277185 | 0.277552 |
| r101_21_100 | MPC_MCTS | original | instance.py:_rounded_up | 1480161 | 0.276474 | 0.386063 |
| c101_21_25 | MPC_MCTS | original | instance.py:energy | 791627 | 0.269998 | 0.472872 |
| r101_21_100 | MPC_HGS | original | fleet_mcts.py:_option_rank | 149698 | 0.264418 | 0.690335 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | instance.py:_rounded_up | 1474958 | 0.263161 | 0.372136 |
| c201_21_50 | MPC_MCTS | original | instance.py:_rounded_up | 1361346 | 0.263040 | 0.370154 |
| r101_21_100 | MPC_COMPLETION | original | dataclasses.py:_asdict_inner | 489550 | 0.261460 | 0.446978 |
| c201_21_50 | MPC_HGS | original | instance.py:_rounded_up | 1312706 | 0.260895 | 0.366895 |
| c201_21_50 | MPC_ACS | original | model.py:transition | 73044 | 0.257887 | 1.108806 |
| c201_21_50 | MPC_ALNS | original | instance.py:energy | 744295 | 0.257532 | 0.454313 |
| r101_21_100 | MPC_ALNS | incremental_v1 | ~:<built-in method builtins.hash> | 1940380 | 0.255457 | 0.315644 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | model.py:transition | 66390 | 0.255211 | 1.145655 |
| c201_21_50 | MPC_MCTS | incremental_v1 | dataclasses.py:replace | 126997 | 0.253519 | 0.572091 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | dataclasses.py:_asdict_inner | 489550 | 0.250196 | 0.434407 |
| c201_21_50 | MPC_ALNS | incremental_v1 | model.py:transition | 67361 | 0.246214 | 1.087442 |
| c101_21_25 | MPC_ALNS | original | instance.py:energy | 718638 | 0.244313 | 0.428571 |
| c101_21_25 | MPC_HGS | original | instance.py:_rounded_up | 1261936 | 0.244015 | 0.343205 |
| r101_21_100 | MPC_COMPLETION | original | instance.py:distance | 522885 | 0.243695 | 0.406228 |
| c201_21_50 | MPC_MCTS | original | repair.py:_decode_one_station | 38 | 0.239481 | 4.250899 |
| c101_21_25 | MPC_MCTS | original | instance.py:_rounded_up | 1233609 | 0.237687 | 0.333400 |
| c201_21_50 | MPC_HGS | original | repair.py:_decode_one_station | 40 | 0.234567 | 4.152330 |
| c101_21_25 | MPC_HGS | incremental_v1 | model.py:transition | 69660 | 0.233849 | 0.938594 |
| c201_21_50 | MPC_ALNS | original | dataclasses.py:replace | 119946 | 0.232953 | 0.533438 |
| r101_21_100 | MPC_MCTS | incremental_v1 | fleet_mcts.py:proximity | 167100 | 0.230314 | 1.280801 |
| r101_21_100 | MPC_ALNS | original | repair.py:_decode_one_station | 222 | 0.229730 | 3.367950 |
| r101_21_100 | MPC_COMPLETION | original | dataclasses.py:replace | 100395 | 0.228533 | 0.500144 |
| c201_21_50 | MPC_HGS | incremental_v1 | evaluation_cache.py:transition | 120441 | 0.227297 | 2.652068 |
| r101_21_100 | MPC_HGS | original | fleet_mcts.py:screened_options | 15634 | 0.225557 | 1.567819 |
| c201_21_50 | MPC_MCTS | incremental_v1 | repair.py:_decode_one_station | 68 | 0.222214 | 3.933831 |
| c101_21_25 | MPC_ALNS | incremental_v1 | model.py:transition | 68818 | 0.221593 | 0.903002 |
| c101_21_25 | MPC_MCTS | incremental_v1 | model.py:transition | 68986 | 0.220138 | 0.892539 |
| r101_21_100 | MPC_COMPLETION | original | ~:<built-in method builtins.hash> | 900576 | 0.217828 | 0.319616 |
| r101_21_100 | MPC_ALNS | original | dataclasses.py:replace | 104430 | 0.211989 | 0.477550 |
| c201_21_50 | MPC_ALNS | original | instance.py:_rounded_up | 1092876 | 0.211919 | 0.299763 |
| c101_21_25 | MPC_ACS | original | model.py:transition | 65622 | 0.207181 | 0.821227 |
| c201_21_50 | MPC_HGS | incremental_v1 | dataclasses.py:replace | 106222 | 0.206670 | 0.466940 |
| c201_21_50 | MPC_ALNS | original | repair.py:_decode_one_station | 29 | 0.202643 | 3.560952 |
| r101_21_100 | MPC_ALNS | incremental_v1 | instance.py:distance | 473953 | 0.201427 | 0.340131 |
| r101_21_100 | MPC_MCTS | original | instance.py:energy | 591553 | 0.200892 | 0.346738 |
| r101_21_100 | MPC_ACS | incremental_v1 | ~:<built-in method builtins.sorted> | 66532 | 0.200736 | 2.907599 |
| r101_21_100 | MPC_MCTS | incremental_v1 | ~:<built-in method builtins.hash> | 1779520 | 0.199642 | 0.238863 |
| c101_21_25 | MPC_ALNS | original | instance.py:_rounded_up | 1045853 | 0.197231 | 0.278291 |
| r101_21_100 | MPC_ALNS | incremental_v1 | instance.py:_rounded_up | 991991 | 0.196948 | 0.278203 |
| c101_21_25 | MPC_HGS | original | dataclasses.py:replace | 98428 | 0.196837 | 0.437032 |
| r101_21_100 | MPC_ALNS | incremental_v1 | instance.py:energy | 518038 | 0.193757 | 0.333256 |
| c201_21_50 | MPC_MCTS | original | model.py:escape | 151916 | 0.193625 | 0.488156 |
| c101_21_25 | MPC_MCTS | original | dataclasses.py:replace | 101116 | 0.193465 | 0.444412 |
| r101_21_100 | MPC_ALNS | original | instance.py:distance | 445020 | 0.190130 | 0.323156 |
| c201_21_50 | MPC_HGS | original | model.py:escape | 143416 | 0.188496 | 0.461401 |
| r101_21_100 | MPC_ALNS | incremental_v1 | evaluation_cache.py:transition | 86344 | 0.186625 | 2.005076 |
| c201_21_50 | MPC_HGS | incremental_v1 | repair.py:_decode_one_station | 60 | 0.185523 | 3.288104 |
| r101_21_100 | MPC_ACS | original | ~:<built-in method builtins.sorted> | 65724 | 0.182886 | 2.791856 |
| c201_21_50 | MPC_ACS | incremental_v1 | model.py:transition | 47917 | 0.180937 | 0.806711 |
| c201_21_50 | MPC_HGS | original | model.py:<genexpr> | 1087512 | 0.179729 | 0.244618 |
| c101_21_25 | MPC_MCTS | original | instance.py:distance | 441982 | 0.178851 | 0.309377 |
| c101_21_25 | MPC_ALNS | original | dataclasses.py:replace | 92193 | 0.178606 | 0.409242 |
| r101_21_100 | MPC_COMPLETION | original | fleet_mcts.py:_screen_gap_detail_untraced | 116870 | 0.177878 | 0.946243 |
| c201_21_50 | MPC_MCTS | original | instance.py:distance | 439364 | 0.175827 | 0.305452 |
| c101_21_25 | MPC_HGS | original | repair.py:_decode_one_station | 168 | 0.175068 | 2.827089 |
| c201_21_50 | MPC_MCTS | incremental_v1 | instance.py:distance | 426411 | 0.173572 | 0.303116 |
| r101_21_100 | MPC_COMPLETION | original | model.py:escape | 123430 | 0.172381 | 0.359183 |
| r101_21_100 | MPC_MCTS | incremental_v1 | fleet_mcts.py:_screen_gap_detail_untraced | 100637 | 0.171502 | 0.498860 |
| r101_21_100 | MPC_ALNS | incremental_v1 | repair.py:_decode_one_station | 410 | 0.170983 | 2.152913 |
| c201_21_50 | MPC_MCTS | incremental_v1 | model.py:escape | 128427 | 0.169832 | 0.474166 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | fleet_mcts.py:_screen_gap_detail_untraced | 116870 | 0.169336 | 0.900333 |
| c201_21_50 | MPC_HGS | original | instance.py:distance | 412891 | 0.169246 | 0.294050 |
| r101_21_100 | MPC_COMPLETION | original | mpc.py:initial | 34865 | 0.167398 | 0.287403 |
| c101_21_25 | MPC_MCTS | original | repair.py:_decode_one_station | 164 | 0.166367 | 2.749086 |
| r101_21_100 | MPC_MCTS | original | ~:<built-in method builtins.hash> | 1621070 | 0.165687 | 0.188924 |
| c201_21_50 | MPC_MCTS | incremental_v1 | ~:<built-in method builtins.hash> | 779497 | 0.165668 | 0.217657 |
| c201_21_50 | MPC_MCTS | original | model.py:<genexpr> | 1150830 | 0.164158 | 0.231587 |
| c201_21_50 | MPC_COMPLETION | original | instance.py:energy | 507894 | 0.163844 | 0.283756 |
| c101_21_25 | MPC_ACS | original | instance.py:energy | 516968 | 0.163404 | 0.286901 |
| r101_21_100 | MPC_HGS | incremental_v1 | ~:<built-in method builtins.hash> | 1256144 | 0.163093 | 0.201331 |
| c201_21_50 | MPC_MCTS | incremental_v1 | instance.py:_rounded_up | 789597 | 0.162413 | 0.229579 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | instance.py:distance | 363747 | 0.161604 | 0.270003 |
| r101_21_100 | MPC_ACS | original | ~:<built-in method math.ceil> | 2071270 | 0.160646 | 0.160646 |
| r101_21_100 | MPC_ACS | incremental_v1 | ~:<built-in method math.ceil> | 2033425 | 0.159374 | 0.159374 |
| r101_21_100 | MPC_ALNS | original | model.py:<genexpr> | 1127958 | 0.158814 | 0.225427 |
| c201_21_50 | MPC_HGS | incremental_v1 | repair.py:<genexpr> | 512345 | 0.158725 | 0.205477 |
| c101_21_25 | MPC_ALNS | original | repair.py:_decode_one_station | 147 | 0.158015 | 2.602343 |
| c201_21_50 | MPC_MCTS | incremental_v1 | model.py:<genexpr> | 862032 | 0.157812 | 0.210112 |
| r101_21_100 | MPC_HGS | incremental_v1 | model.py:transition | 43153 | 0.157365 | 0.699202 |
| c201_21_50 | MPC_ALNS | original | model.py:<genexpr> | 951198 | 0.157187 | 0.212782 |
| c201_21_50 | MPC_MCTS | incremental_v1 | repair.py:<genexpr> | 570686 | 0.157083 | 0.210988 |
| r101_21_100 | MPC_HGS | original | instance.py:distance | 355445 | 0.155565 | 0.260331 |
| c201_21_50 | MPC_ALNS | original | model.py:escape | 120435 | 0.154914 | 0.379474 |
| r101_21_100 | MPC_HGS | incremental_v1 | ~:<built-in method builtins.max> | 1104691 | 0.151547 | 0.151560 |
| r101_21_100 | MPC_MCTS | incremental_v1 | ~:<built-in method builtins.min> | 229639 | 0.150557 | 1.066616 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | ~:<built-in method builtins.hash> | 765082 | 0.149252 | 0.206266 |
| r101_21_100 | MPC_MCTS | original | fleet_mcts.py:proximity | 108460 | 0.149220 | 0.826603 |
| c201_21_50 | MPC_ACS | original | instance.py:energy | 471533 | 0.147541 | 0.260771 |
| c101_21_25 | MPC_HGS | original | instance.py:distance | 359135 | 0.145777 | 0.251781 |
| r101_21_100 | MPC_ALNS | original | model.py:escape | 105504 | 0.145495 | 0.435544 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | model.py:transition | 41201 | 0.142835 | 0.571672 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | evaluation_cache.py:transition | 70586 | 0.142686 | 1.523354 |
| c201_21_50 | MPC_HGS | incremental_v1 | instance.py:distance | 356777 | 0.142359 | 0.248864 |
| r101_21_100 | MPC_HGS | incremental_v1 | instance.py:distance | 311109 | 0.142025 | 0.234336 |
| c201_21_50 | MPC_ALNS | original | instance.py:distance | 348581 | 0.140448 | 0.243430 |
| c201_21_50 | MPC_HGS | incremental_v1 | model.py:escape | 107342 | 0.139496 | 0.391438 |
| c201_21_50 | MPC_HGS | incremental_v1 | instance.py:_rounded_up | 694271 | 0.139097 | 0.196320 |
| r101_21_100 | MPC_HGS | original | ~:<built-in method builtins.max> | 1017689 | 0.137904 | 0.137917 |
| r101_21_100 | MPC_HGS | incremental_v1 | fleet_mcts.py:_screen_gap_detail_untraced | 56498 | 0.137786 | 0.567735 |
| r101_21_100 | MPC_MCTS | original | ~:<built-in method builtins.min> | 255751 | 0.137071 | 0.923565 |
| c201_21_50 | MPC_MCTS | original | repair.py:<genexpr> | 473203 | 0.134738 | 0.175564 |
| c201_21_50 | MPC_HGS | original | repair.py:<genexpr> | 520882 | 0.134058 | 0.185017 |
| r101_21_100 | MPC_ACS | incremental_v1 | fleet_mcts.py:<lambda> | 558995 | 0.133989 | 2.663362 |
| c101_21_25 | MPC_MCTS | original | model.py:<genexpr> | 978282 | 0.132735 | 0.188479 |
| c201_21_50 | MPC_COMPLETION | original | instance.py:_rounded_up | 765648 | 0.132678 | 0.185514 |
| r101_21_100 | MPC_MCTS | original | fleet_mcts.py:_screen_gap_detail_untraced | 65234 | 0.132575 | 0.346173 |
| r101_21_100 | MPC_HGS | original | dataclasses.py:replace | 64064 | 0.132470 | 0.297210 |
| c101_21_25 | MPC_HGS | original | model.py:<genexpr> | 952662 | 0.132468 | 0.187844 |
| r101_21_100 | MPC_ALNS | incremental_v1 | dataclasses.py:replace | 60528 | 0.131534 | 0.294271 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | fleet_mcts.py:screened_options | 6339 | 0.131472 | 1.442394 |
| c201_21_50 | MPC_HGS | incremental_v1 | ~:<built-in method builtins.hash> | 610509 | 0.131422 | 0.170463 |
| c101_21_25 | MPC_MCTS | original | model.py:escape | 101830 | 0.129558 | 0.319941 |
| c101_21_25 | MPC_ALNS | original | instance.py:distance | 327215 | 0.129517 | 0.223550 |
| r101_21_100 | MPC_ALNS | original | ~:<built-in method builtins.all> | 194543 | 0.129291 | 0.359044 |
| c201_21_50 | MPC_MCTS | original | ~:<built-in method builtins.all> | 195946 | 0.128509 | 0.362618 |
| c201_21_50 | MPC_HGS | incremental_v1 | model.py:<genexpr> | 720030 | 0.128054 | 0.170816 |
| c101_21_25 | MPC_HGS | original | model.py:escape | 98138 | 0.127512 | 0.308052 |
| r101_21_100 | MPC_ACS | original | fleet_mcts.py:<lambda> | 544345 | 0.126210 | 2.566126 |
| c101_21_25 | MPC_HGS | incremental_v1 | evaluation_cache.py:transition | 65415 | 0.125741 | 1.217803 |
| r101_21_100 | MPC_HGS | original | ~:<built-in method math.ceil> | 1578581 | 0.125507 | 0.125507 |
| c201_21_50 | MPC_HGS | original | ~:<built-in method builtins.all> | 184158 | 0.123891 | 0.370520 |
| c101_21_25 | MPC_HGS | incremental_v1 | instance.py:energy | 370634 | 0.123808 | 0.217538 |
| r101_21_100 | MPC_HGS | original | model.py:<genexpr> | 697602 | 0.123707 | 0.165233 |
| c201_21_50 | MPC_COMPLETION | original | dataclasses.py:replace | 68329 | 0.122449 | 0.278447 |
| c101_21_25 | MPC_ALNS | original | model.py:<genexpr> | 888522 | 0.121057 | 0.171687 |
| c101_21_25 | MPC_MCTS | incremental_v1 | evaluation_cache.py:transition | 64354 | 0.120843 | 1.152706 |
| r101_21_100 | MPC_MCTS | incremental_v1 | model.py:transition | 34882 | 0.119699 | 0.582171 |
| c101_21_25 | MPC_ACS | original | instance.py:_rounded_up | 685804 | 0.119419 | 0.167440 |
| c201_21_50 | MPC_ALNS | incremental_v1 | evaluation_cache.py:transition | 68226 | 0.118969 | 1.393050 |
| c101_21_25 | MPC_ALNS | original | model.py:escape | 92053 | 0.118353 | 0.302857 |
| c201_21_50 | MPC_ACS | original | instance.py:_rounded_up | 672801 | 0.117634 | 0.165679 |
| r101_21_100 | MPC_HGS | incremental_v1 | ~:<built-in method math.ceil> | 1426035 | 0.116480 | 0.116480 |
| c101_21_25 | MPC_ALNS | incremental_v1 | evaluation_cache.py:transition | 62496 | 0.115336 | 1.155638 |
| r101_21_100 | MPC_MCTS | incremental_v1 | instance.py:energy | 304136 | 0.113237 | 0.191384 |
| c101_21_25 | MPC_HGS | incremental_v1 | instance.py:_rounded_up | 603726 | 0.112612 | 0.158326 |
| r101_21_100 | MPC_MCTS | original | dataclasses.py:replace | 58825 | 0.112262 | 0.251218 |
| r101_21_100 | MPC_ALNS | original | ~:<built-in method math.ceil> | 1414765 | 0.111707 | 0.111707 |
| r101_21_100 | MPC_ACS | incremental_v1 | fleet_mcts.py:_check_search_time | 714610 | 0.110204 | 0.173940 |
| r101_21_100 | MPC_MCTS | original | ~:<built-in method math.ceil> | 1480161 | 0.109589 | 0.109589 |
| c101_21_25 | MPC_MCTS | original | ~:<built-in method builtins.all> | 174967 | 0.109246 | 0.303935 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | ~:<built-in method math.ceil> | 1474958 | 0.108974 | 0.108974 |
| c101_21_25 | MPC_MCTS | incremental_v1 | instance.py:distance | 298737 | 0.108708 | 0.188879 |
| r101_21_100 | MPC_COMPLETION | incremental_v1 | ~:<built-in method builtins.min> | 134263 | 0.108233 | 0.766070 |
| c101_21_25 | MPC_HGS | original | ~:<built-in method builtins.all> | 164678 | 0.106771 | 0.298390 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | ~:<built-in method builtins.hash> | 538065 | 0.106544 | 0.143135 |
| c201_21_50 | MPC_ACS | original | dataclasses.py:replace | 61365 | 0.106543 | 0.242492 |
| c201_21_50 | MPC_ALNS | original | ~:<built-in method builtins.all> | 159767 | 0.105485 | 0.319113 |
| r101_21_100 | MPC_ACS | original | fleet_mcts.py:_check_search_time | 691710 | 0.103727 | 0.163931 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | dataclasses.py:replace | 54758 | 0.103348 | 0.230142 |
| c201_21_50 | MPC_ALNS | incremental_v1 | dataclasses.py:replace | 59016 | 0.102911 | 0.234764 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | repair.py:<genexpr> | 226745 | 0.102568 | 0.121203 |
| c101_21_25 | MPC_MCTS | incremental_v1 | instance.py:_rounded_up | 557030 | 0.101795 | 0.142924 |
| c101_21_25 | MPC_HGS | original | ~:<built-in method math.ceil> | 1261936 | 0.099190 | 0.099190 |
| c201_21_50 | MPC_ALNS | incremental_v1 | repair.py:_decode_one_station | 29 | 0.098988 | 1.733715 |
| r101_21_100 | MPC_ALNS | incremental_v1 | model.py:escape | 64036 | 0.098277 | 0.430319 |
| r101_21_100 | MPC_ACS | incremental_v1 | ~:<method 'index' of 'tuple' objects> | 560651 | 0.097884 | 0.097884 |
| c101_21_25 | MPC_ALNS | original | ~:<built-in method builtins.all> | 153394 | 0.097570 | 0.272519 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | instance.py:_rounded_up | 540598 | 0.096465 | 0.135158 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | instance.py:energy | 291644 | 0.096151 | 0.166682 |
| c101_21_25 | MPC_MCTS | incremental_v1 | ~:<built-in method builtins.hash> | 565216 | 0.096140 | 0.128278 |
| c101_21_25 | MPC_MCTS | original | ~:<built-in method math.ceil> | 1233609 | 0.095713 | 0.095713 |
| c101_21_25 | MPC_HGS | incremental_v1 | ~:<built-in method builtins.hash> | 575585 | 0.095250 | 0.124212 |
| c201_21_50 | MPC_COMPLETION | original | instance.py:distance | 257753 | 0.094857 | 0.162772 |
| c101_21_25 | MPC_HGS | incremental_v1 | repair.py:_decode_one_station | 168 | 0.094767 | 1.363366 |
| r101_21_100 | MPC_ACS | original | ~:<method 'index' of 'tuple' objects> | 545875 | 0.093857 | 0.093857 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | instance.py:distance | 248953 | 0.091782 | 0.158716 |
| r101_21_100 | MPC_ALNS | incremental_v1 | model.py:<genexpr> | 637290 | 0.091682 | 0.129442 |
| c101_21_25 | MPC_ACS | incremental_v1 | instance.py:energy | 284026 | 0.091403 | 0.160504 |
| c201_21_50 | MPC_ACS | incremental_v1 | evaluation_cache.py:transition | 49233 | 0.089268 | 1.034928 |
| c201_21_50 | MPC_ALNS | original | repair.py:<genexpr> | 478975 | 0.088069 | 0.357842 |
| c101_21_25 | MPC_HGS | incremental_v1 | instance.py:distance | 233092 | 0.087315 | 0.151911 |
| c101_21_25 | MPC_ALNS | incremental_v1 | ~:<built-in method builtins.hash> | 519886 | 0.085457 | 0.112622 |
| c201_21_50 | MPC_COMPLETION | original | model.py:escape | 70199 | 0.085176 | 0.322169 |
| c101_21_25 | MPC_MCTS | incremental_v1 | instance.py:energy | 258293 | 0.085015 | 0.147768 |
| c101_21_25 | MPC_ALNS | incremental_v1 | repair.py:_decode_one_station | 147 | 0.082802 | 1.241883 |
| c101_21_25 | MPC_HGS | incremental_v1 | dataclasses.py:replace | 42517 | 0.082038 | 0.182459 |
| c101_21_25 | MPC_ALNS | incremental_v1 | instance.py:_rounded_up | 451525 | 0.081540 | 0.114754 |
| c101_21_25 | MPC_MCTS | incremental_v1 | repair.py:_decode_one_station | 164 | 0.081313 | 1.248356 |
| c101_21_25 | MPC_ACS | incremental_v1 | fleet_mcts.py:_option_rank | 49940 | 0.081177 | 0.206969 |
| c101_21_25 | MPC_ALNS | original | ~:<built-in method math.ceil> | 1045853 | 0.081060 | 0.081060 |
| c101_21_25 | MPC_ACS | original | fleet_mcts.py:_option_rank | 49940 | 0.081037 | 0.207187 |
| c201_21_50 | MPC_ACS | original | repair.py:_decode_one_station | 18 | 0.080788 | 1.472625 |
| c201_21_50 | MPC_COMPLETION | original | repair.py:_decode_one_station | 11 | 0.079674 | 1.531889 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | repair.py:_decode_one_station | 11 | 0.079533 | 1.702676 |
| c201_21_50 | MPC_ACS | incremental_v1 | instance.py:energy | 241418 | 0.078782 | 0.138044 |
| c101_21_25 | MPC_ALNS | incremental_v1 | instance.py:distance | 218272 | 0.078467 | 0.136228 |
| c201_21_50 | MPC_ACS | incremental_v1 | dataclasses.py:replace | 43392 | 0.078099 | 0.175833 |
| c201_21_50 | MPC_ALNS | incremental_v1 | model.py:<genexpr> | 404166 | 0.077823 | 0.099760 |
| c101_21_25 | MPC_MCTS | incremental_v1 | dataclasses.py:replace | 40690 | 0.077059 | 0.169451 |
| c101_21_25 | MPC_ALNS | incremental_v1 | dataclasses.py:replace | 41424 | 0.076078 | 0.169622 |
| c101_21_25 | MPC_ALNS | incremental_v1 | instance.py:energy | 233253 | 0.076042 | 0.133036 |
| c201_21_50 | MPC_ACS | incremental_v1 | instance.py:_rounded_up | 408113 | 0.074720 | 0.104606 |
| c201_21_50 | MPC_ALNS | incremental_v1 | instance.py:distance | 205629 | 0.073976 | 0.129978 |
| c201_21_50 | MPC_ACS | original | model.py:escape | 62509 | 0.073445 | 0.224199 |
| c101_21_25 | MPC_ACS | original | dataclasses.py:replace | 40454 | 0.072330 | 0.162187 |
| c201_21_50 | MPC_ACS | original | instance.py:distance | 201268 | 0.072214 | 0.124662 |
| c201_21_50 | MPC_COMPLETION | incremental_v1 | model.py:escape | 56053 | 0.070148 | 0.294033 |
| c201_21_50 | MPC_ALNS | incremental_v1 | model.py:escape | 59436 | 0.069874 | 0.217449 |
| c201_21_50 | MPC_ALNS | incremental_v1 | instance.py:_rounded_up | 372559 | 0.069428 | 0.097450 |
| c201_21_50 | MPC_ACS | original | repair.py:<genexpr> | 207731 | 0.068887 | 0.084779 |
| c201_21_50 | MPC_ACS | incremental_v1 | repair.py:<genexpr> | 188716 | 0.068576 | 0.083006 |
| c201_21_50 | MPC_ALNS | incremental_v1 | ~:<built-in method builtins.hash> | 352622 | 0.067300 | 0.087032 |
| c201_21_50 | MPC_COMPLETION | original | model.py:<genexpr> | 506130 | 0.067233 | 0.094464 |
| c101_21_25 | MPC_ACS | incremental_v1 | instance.py:_rounded_up | 368466 | 0.064675 | 0.090684 |
| c101_21_25 | MPC_HGS | incremental_v1 | fleet_mcts.py:_option_rank | 36728 | 0.064033 | 0.161579 |
| c201_21_50 | MPC_ACS | incremental_v1 | repair.py:_decode_one_station | 18 | 0.062779 | 1.201177 |
| c201_21_50 | MPC_ALNS | incremental_v1 | repair.py:<genexpr> | 296214 | 0.062320 | 0.085251 |
| c101_21_25 | MPC_ACS | original | instance.py:distance | 168836 | 0.061355 | 0.105298 |
| c101_21_25 | MPC_ACS | original | repair.py:_decode_one_station | 66 | 0.060871 | 1.009421 |
| c201_21_50 | MPC_ACS | incremental_v1 | instance.py:distance | 166695 | 0.060495 | 0.105840 |
| c101_21_25 | MPC_HGS | incremental_v1 | ~:<built-in method builtins.max> | 441815 | 0.059991 | 0.060004 |
| c201_21_50 | MPC_ACS | incremental_v1 | ~:<built-in method builtins.hash> | 308422 | 0.059434 | 0.078297 |
| c201_21_50 | MPC_ACS | original | model.py:<genexpr> | 438264 | 0.057203 | 0.080538 |
| c101_21_25 | MPC_ACS | original | ~:<built-in method builtins.max> | 440095 | 0.055332 | 0.056102 |
| c201_21_50 | MPC_COMPLETION | original | model.py:_escape_geometry | 4783 | 0.053951 | 0.162204 |
| c201_21_50 | MPC_COMPLETION | original | ~:<built-in method builtins.all> | 87157 | 0.053849 | 0.151023 |
| c101_21_25 | MPC_MCTS | incremental_v1 | model.py:<genexpr> | 413916 | 0.053778 | 0.076053 |
| c101_21_25 | MPC_ALNS | incremental_v1 | model.py:<genexpr> | 412908 | 0.053592 | 0.075636 |
| c101_21_25 | MPC_ALNS | incremental_v1 | model.py:escape | 42778 | 0.053350 | 0.178089 |
| c201_21_50 | MPC_ACS | incremental_v1 | model.py:escape | 44422 | 0.053307 | 0.188313 |
| c101_21_25 | MPC_ACS | incremental_v1 | model.py:transition | 16970 | 0.053013 | 0.233634 |
| c101_21_25 | MPC_MCTS | incremental_v1 | model.py:escape | 42167 | 0.052667 | 0.172806 |
| c101_21_25 | MPC_ACS | original | model.py:<genexpr> | 393732 | 0.049242 | 0.070279 |
| c201_21_50 | MPC_ACS | original | ~:<built-in method math.ceil> | 672801 | 0.048045 | 0.048045 |
| c101_21_25 | MPC_ACS | original | ~:<built-in method math.ceil> | 685804 | 0.048021 | 0.048021 |
| c101_21_25 | MPC_ACS | incremental_v1 | fleet_mcts.py:screened_options | 8549 | 0.043649 | 0.410527 |
| c101_21_25 | MPC_ACS | incremental_v1 | ~:<built-in method builtins.hash> | 268486 | 0.039607 | 0.051546 |
| c101_21_25 | MPC_ACS | incremental_v1 | evaluation_cache.py:transition | 17946 | 0.037529 | 0.318467 |
| c101_21_25 | MPC_ACS | incremental_v1 | ~:<built-in method builtins.max> | 290995 | 0.035716 | 0.036468 |
| c101_21_25 | MPC_ACS | incremental_v1 | fleet_mcts.py:_screen_gap_detail_untraced | 7446 | 0.034669 | 0.102880 |
| c101_21_25 | MPC_COMPLETION | original | model.py:transition | 9013 | 0.031675 | 0.131443 |
| c101_21_25 | MPC_ACS | incremental_v1 | instance.py:distance | 84440 | 0.030293 | 0.051876 |
| c101_21_25 | MPC_COMPLETION | original | dataclasses.py:_asdict_inner | 54430 | 0.022760 | 0.040624 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | dataclasses.py:_asdict_inner | 54430 | 0.022505 | 0.040608 |
| c101_21_25 | MPC_COMPLETION | original | instance.py:energy | 65169 | 0.021040 | 0.036816 |
| c101_21_25 | MPC_COMPLETION | original | instance.py:_rounded_up | 98219 | 0.016745 | 0.023797 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | model.py:transition | 4117 | 0.014948 | 0.067054 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | instance.py:energy | 44870 | 0.014549 | 0.025129 |
| c101_21_25 | MPC_COMPLETION | original | dataclasses.py:replace | 6706 | 0.014133 | 0.031339 |
| c101_21_25 | MPC_COMPLETION | original | instance.py:distance | 33049 | 0.012352 | 0.021415 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | instance.py:_rounded_up | 70417 | 0.011778 | 0.016384 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | ~:<built-in method builtins.hash> | 49495 | 0.009759 | 0.013718 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | instance.py:distance | 25546 | 0.009539 | 0.016372 |
| c101_21_25 | MPC_COMPLETION | original | model.py:escape | 7790 | 0.009368 | 0.027949 |
| c101_21_25 | MPC_COMPLETION | original | encoder.py:iterencode | 112 | 0.008814 | 0.008814 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | encoder.py:iterencode | 112 | 0.008598 | 0.008598 |
| c101_21_25 | MPC_COMPLETION | original | ~:<built-in method builtins.hash> | 39092 | 0.008246 | 0.012089 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | evaluation_cache.py:transition | 4184 | 0.007772 | 0.080736 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | dataclasses.py:replace | 3299 | 0.007662 | 0.016853 |
| c101_21_25 | MPC_COMPLETION | original | ~:<built-in method math.ceil> | 98219 | 0.007052 | 0.007052 |
| c101_21_25 | MPC_COMPLETION | incremental_v1 | dataclasses.py:fields | 4362 | 0.006040 | 0.009880 |

## 7. Hard budget and affordable future design

Planned conservative upper allowances plus reporting: 6748.5/7200 s; jobs: 75; full unprofiled simulations: 30.
Worker max(elapsed,CPU) charged before this reporting worker: 2111.936 s. Final accounting, including this report, is in budget.json.
A complete paired block is admitted only when its full remaining upper allowance plus a reporting reserve fits.
The monitor checks elapsed and actual worker CPU, kills only its owned timed-out worker, and records incomplete evidence/logs. Failed, interrupted or unmanifested jobs never silently rerun.
Historical exact-case cost estimates are doubled plus startup margin and a worker floor; these are conservative estimates, not guarantees. Actual watchdogs enforce the hard limit.
Keep future work staged: fixed-work correctness and profiling first, then a prespecified small matched pilot, then explicit review. No automatic holdout or five-engine multi-seed expansion.
Observed mean paired-method process cost: 129.8 s. A future 6-files-per-size x 3-sizes x 2-DoD x 2-seeds x 5-engines paired study would have 360 paired blocks (720 simulations),
projecting about 13.0 shared-machine process hours at this pilot's mix. This is a scenario-mix extrapolation, not a reliable forecast; preflight must use size/method-specific bounds.
A smaller next step, only after explicit authorization, is three other structurally selected seen-development parents (one per size), one prespecified seed/DoD each, all five engines and both evaluators: 15 pairs, 30 simulations. This retains balanced method coverage rather than dropping slow or unfavorable engines.
At this pilot's mix that projects 32.4 process minutes before profiling, audit and safety margins. This is illustrative, not an admitted budget.
Select parents without their service outcomes, retain full search settings, and refuse the entire plan unless case/method-specific conservative upper bounds plus reporting fit its separately authorized allowance. Review paired regressions before any broader rollout.

## 8. Recommendation and limitations

Original policy stays the default. Exact evaluator speedups demonstrate less work for a fixed workload, but time-limited optimizers can spend the same five seconds exploring more candidates.
Consequently faster kernels do not guarantee shorter scenario time, better closed-loop service or fewer planning calls. Inspect every regression above before any method-wide rollout.
Only three previously seen parents and one seed/DoD per file were tested. Shared-machine load, profiler perturbation, fresh-process startup and bounded Python caches limit generalization.
The runner requests one native thread through the same thread-count environment variables for both variants; measured CPU/wall ratios record actual process utilization. PYTHONHASHSEED is inherited rather than separately pinned, and wall-clock-limited trajectories are not promised bitwise reproducible.
The prior root-v1 cache is explicitly benchmarked; a larger cache is not automatically faster. No statistically independent new paper superiority claim or final holdout is made.
No adaptive early stop, fewer events, reduced search or objective approximation was introduced. Such policies would require separate names and new evaluation.

## 9. Reproduction

```powershell
python -m pytest -q
python -m scripts.run_performance_engineering --freeze
python -u -m scripts.run_performance_engineering
python -m scripts.report_performance_engineering
```

Use the recorded execution source. Completed hash-verified outputs are reused; the persistent 7200-second allowance cannot be extended by rerunning the command.
The standalone report command is read-only scientific analysis, not a new optimization campaign. Keep Reliability V2 STOP_REQUESTED.json intact.
