# Hybrid GPU/CPU acceleration and service-first development pilot

Status: worker_incomplete_preserved; 0/53 workers; 0/25 full-scenario pairs.
Frozen execution commit: `e4138be447ded5803626377bef83267190bd2612`. Source SHA-256: `37719466cd1594b712ede52a6fca40fe0db53abd0f027cc78497782316f56dce`.
These are previously generated development parents, not an independent final test. Historical paper results remain untouched.
All five MPC engines retain the same original physical simulator, fixed fleet, objective, and five-second decision cap. Enhancements are opt-in.

## Hardware and kernel screen

RTX A2000 12GB, NVIDIA driver 596.71, CUDA runtime 13.2; Windows, Python 3.12.10; isolated CuPy 14.2.0 and Numba 0.68 environment.
The GPU benchmark includes host/device transfer and synchronization; it does not beat compiled CPU at observed insertion-batch sizes. No GPU context is used in the full MPC runs: GPU processing time and workload utilization are 0/not applicable, not missing speedups.
The hybrid dispatcher therefore selects compiled CPU on this workstation. The original Python path remains the fallback if Numba is absent.
Standalone benchmark: `kernel_benchmark.json` (SHA-256 `8bd717dc51e6aa67018409f96458db0695f6510c5b4db35b93f4d5b87ab0e0a0`).

## Fixed-work checks

| Case | Screened gaps | Compiled batches | Proven late | Python s | Compiled s | Objective/options |
| --- | --- | --- | --- | --- | --- | --- |

## End-to-end paired results

Stage B compares original against opt-in compiled CPU plus the existing incremental screen/cache. Stage C independently compares original against opt-in quality/recovery; it does not combine Stage B and C.
Alternating pair order, fresh sequential workers, one numerical-library thread per worker. Timings are shared-machine observations.

| Stage | Method | Pairs | Original served | Enhanced served | Original complete | Enhanced complete | Original wall s | Enhanced wall s | Original CPU s | Enhanced CPU s | Equal-service pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### Every paired case

| Stage | Case | DoD | Method | Served O/E | Complete O/E | Wall s O/E | CPU s O/E | Distance O/E (only equal-service) | Equal served IDs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Full operational measurements

Travel energy is exact physical arc energy; charged energy is separately reported. Fleet workload balance is the standard deviation of customer service counts across active/known vehicles. Completion is the latest vehicle event time.
Distance, travel, energy, waiting, and charging comparisons are meaningful only when the served-customer identities match; see the paired table.

| Case | Method | Variant | Served | Distance | Travel time | Completion | Charge time | Charged energy | Travel energy | Wait time | EVs | Load SD | TW margin min/mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Computation, deadlines, and interventions

Route decode counts are per-problem distinct keys summed across decision problems, not globally unique routes. GPU time is zero in full workers.

| Case | Method | Variant | Wall s | CPU s | Optimizations | Latency mean/p95/max s | Route decodes | Route builds | Compiled batches/proven late | Quality eligible/accepted | Recovery eligible/accepted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Scientific interpretation

Across 0 matched pairs: 0 service gains, 0 service losses, 0 equal-served-set pairs, and 0 shorter-distance results among the latter.
A fixed-work compiled screen can match exact proposals yet change a deadline-limited search trajectory; end-to-end service and time, not micro speed, govern promotion.
The optional quality policy uses explicit risk tolerances and physical replay. It is a separate policy, not a rewrite of the historical lexicographic objective. Its intervention counts above establish whether it actually changed decisions.
Two structurally preselected Stage C development parents are too few to support a repeatable complete-service claim. No enhanced variant is promoted automatically; original remains default.
Every saved full scenario was independently replayed from disk against the original physical/information auditor and passed the five-second decision maximum.
Charged compute before report worker: 301.33/7200 s; 300 s setup charge and 120 s report reserve. Consult `budget.json` for the final report charge.
The stopped Reliability V2 evidence was not resumed; no new final holdout was opened.

## Reproduction

```powershell
.\.venv-accel\Scripts\python.exe -m pytest -q
.\.venv-accel\Scripts\python.exe -m scripts.run_hybrid_acceleration --freeze
.\.venv-accel\Scripts\python.exe -u -m scripts.run_hybrid_acceleration
.\.venv-accel\Scripts\python.exe -m scripts.report_hybrid_acceleration
```

Use the frozen source commit and the recorded environment. Completed raw files are hash-checked and never regenerated by the runner; failed jobs require an explicit revision, not a silent retry.
