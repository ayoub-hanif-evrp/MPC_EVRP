# Bounded performance-engineering development pilot

Starting project commit: ae7a3ae225ec51c649da254ec31341d561a8ae5e.
Work remains on the sole main branch. Reliability V2 stays stopped, and its
361 raw records, protocols, reference fleets, releases and STOP_REQUESTED.json
are immutable. This pilot is not a continuation of that campaign or a holdout.

## Exact engineering hypothesis

Repeated physical replay, charging-frontier prefixes and canonical objective
evaluation can reuse exact deterministic results within one immutable root.
No early stopping, changed event trigger, new objective, smaller horizon,
reduced iterations or reduced five-second decision limit is authorized here.

The new incremental_v1 policy is optional; original remains the default.
Greedy prefixes retain the complete original MPCState and action sequence.
Charging prefixes retain the exact original sorted and truncated label frontier;
that decoder's prefix transitions and target set do not depend on later route
customers. The station loop prunes only already-forbidden topology and time
windows that fail even assuming zero charging duration. Nearest-safe energy
is the same minimum, moved outside repeated label/station iterations.

Planning transition caches retain full immutable physical state/action and the
require-return flag. Frozen observations are held strongly for the root's
lifetime before identity keys are used. This is exact identity isolation, not
a projection that omits visible requests, commitments or infrastructure.
The plant/auditor still calls the unchanged original model.transition.

Objective memoization keys include sequences, exact actions, exact route costs
and the constructor ownership map. The original evaluator computes every
miss, with unchanged lexicographic order and floating-point reduction order.
Returned component dictionaries are copied so callers cannot corrupt a cache.
All caches have fixed finite bounds and close on normal or exceptional exit.
No cache stores a deadline failure as a physical infeasibility result.

## Correctness first

Require exact deterministic route/proposal/score checks before a pilot starts.
Cover partial/full charging, MP inter-station restrictions, epsilon time-window
boundaries, hidden/committed/served requests, payload/SOC/origin/observation
invalidation, ownership anchor changes, deadline-before-hit behavior and cache
caps. All five optimizers must match fixed-work outputs in regression tests.
Do not require bitwise-identical wall-clock-limited search trajectories.

The three original/root_v1/incremental fixed-work checksums must match before
unprofiled pilot admission. Every accepted micro route is physically replayed
outside the planning cache. Every finished simulation is independently audited
in its worker and again from disk before the consolidated report.

## Predeclared inputs and workloads

Use the exact archived targeted-development scenarios, not newly generated
release schedules: c101_21_25, DoD .25, seed0; c201_21_50, DoD .75, seed0;
r101_21_100, DoD .25, seed0. These were selected for size/family coverage before
new implementation timing outcomes. They are three previously seen development
parents. No untouched final parent is exposed. This sample is engineering
evidence, not independent paper superiority inference.

Microbenchmarks: the first observable optimization root; at most twelve
distinct neighboring customer sequences, with eight-service prefixes. Compare
original, prior root_v1 proposal memo, and incremental_v1. Report ordinary
construction separately from deliberately forced charging fallback and repeated
objective calls. Those isolated timings are not whole-scenario speedups.

Separate whole-Completion cProfile workers and fixed-root MCTS/ALNS/HGS/ACS
cProfile workers cover all three sizes and both implementations. cProfile
perturbs search; use call counts and own time for hotspots, never mix their
outcomes into unprofiled service/timing results. Separate tracemalloc workers
measure Python allocation during the fixed workload, not total process RSS.

Pilot: original versus incremental_v1 on all five methods and all three cases:
15 matched pairs, 30 full original-parameter simulations. Alternate pair order
by case/method index, use fresh sequential child processes, and set the same
native-thread environment to one for both sides. Other machine workloads are
left alone. No parallel-throughput or exclusive-machine claim is made.
Both variants have the same light operation counters and phase telemetry.

## Hard execution budget

Total authorized compute allowance: 7200 seconds, persistent across invocations.
Charge each child max(elapsed wall time, measured process CPU), including import,
simulation, auditing and serialization. Track orchestration elapsed time too.
Keep a final reporting reserve. Full design count and conservative cost upper
allowances are frozen before any worker; refuse an oversized design outright.

Per-simulation admission allowances use twice the previously recorded exact-
case worker cost plus 15 seconds, with a 45-second floor. These are engineering
admission bounds, not probabilistic runtime guarantees. Before starting either
side, require room for the complete remaining paired block plus report reserve.

The monitor polls actual worker CPU and elapsed time, with a safety margin, and
terminates only its own over-budget process. Simulation workers cannot launch
parallel agent children. Logs/command/elapsed/CPU and incomplete status remain
as interrupted evidence. Never convert interrupted work into a valid result.
No failed, timed-out, unfavorable or unmanifested job silently reruns. A verified
completed worker is reused byte-for-byte. Source/input drift fails closed.

No automatic holdout, multi-seed campaign or Reliability V2 restart follows.

## Decision and reporting

Report every method and case, including regressions, process CPU and wall time,
planning time, mean/p95/max decision latency, decoder calls, LRU and root-local
cache counts, distinct decode keys per problem, allocation, constructor-unchanged
counts, repeated exact root hashes and all independent audit results.
State which costs are nested (profile cumulative time) versus disjoint phases.
No event is skipped merely because ownership or a constructor stayed unchanged.

Aim for at least 2x demonstrated bottleneck improvement, without treating the
target as guaranteed or hiding non-improving phases. Distinguish fixed-work
CPU reduction from extra search completed within the same five-second limit.
The pilot does not prove general service noninferiority with only three seen
parents. Original remains the default if a broad performance/quality benefit
is not clear; no automatic default or research-method promotion occurs.

One consolidated FINAL_REPORT.md, Markdown tables and PNG figures at nominal
300 dpi only. Retain internal raw JSON, exact inputs, protocol, budget and logs.
