# MPC-ALNS reliability and fair five-method milestone

## Scope and source preservation

This milestone audits the existing event-triggered MPC pipeline, exposes a versioned initialization-timeout correction, and runs only a preselected ten-execution development pilot. Original Completion, MCTS, ALNS, HGS and ACS search implementations, the shared objective, physical model, dataset and historical result bytes are preserved. The historical source remains available at `b44f2636adcd5fbab38027a45b5c84e23e790c25` and earlier frozen execution commits. Exact current scientific source bytes are fingerprinted in the new protocol, including uncommitted source; a Git commit alone is not substituted for those fingerprints.

The new evidence directory is [mpc_reliability_v1](../results/research_v2/mpc_reliability_v1/). The [supervisor](../scripts/experiments/run_mpc_reliability_pilot.py) has a ten-job execution path and a separate, non-executable future-study plan. Historical launchers are not changed.

## Pipeline audit

1. `scenario.generate` creates releases from a full-service physical reference. Online observations contain only released requests. The reference and unreleased customers are not provided as optimizer features.
2. `EventDrivenSimulator.run` reacts to releases, invalid suffixes, uncovered work after service, and missing continuations. A dispatched physical action is noninterruptible. A busy vehicle's planning origin is its measured post-action state; its future suffix can change.
3. The common constructor retains/replays available suffixes and builds a fleet incumbent. Every optimizer receives the same visible state, fixed K_ref, constructor, resource limits and canonical objective.
4. `ALNSOptimizer` adaptively selects its existing destroy/repair operators, decodes changed customer sequences through the shared charging-aware route builder, and retains its best canonical objective. No new recovery/stability heuristic is added.
5. `route_proposal` and `model.transition` replay battery, payload, hard service-start windows, service durations, permitted charging arcs, partial charge targets/durations and a feasible depot return. The bounded route decoder is not a complete feasibility oracle.
6. `evaluated_result` independently replays chosen suffixes, rejects duplicate or unavailable service, and checks objective/coverage consistency. The simulator reconciles routes and dispatches only ready vehicles; busy continuations remain future plans.
7. Planning uses cooperative deadlines with a final validation reserve and a previously validated constructor/fleet incumbent. A wall-clock deadline may truncate search, so fixed seeds guarantee repeatable random choices under the same work limit, not identical routes under arbitrary machine load. Recorded optimization latency is the simulator's planning timer, not hard real-time certification of all event bookkeeping.

## Reproduced defect and explicit correction

An expired deadline during initial fleet-plan construction reaches ALNS's exception handler before local `best` is assigned. Original `MPC_ALNS` then raises `UnboundLocalError`; original ACS has the same unset-incumbent issue, while original HGS accesses an absent plan and raises `AttributeError`. These are reproducible timeout-handling defects, not EV infeasibility or proof of weak routing search. An ordinary post-initialization search timeout retains a valid incumbent.

The repository already contains an optional `validated_incumbent_v1` initialization policy which raises `OptimizerInitializationDeadline` for the simulator to retain its validated constructor. The new **`MPC_ALNS_SAFE_INIT_V1`** identity exposes precisely that existing correction by subclassing ALNS with its initialization fallback enabled. It changes no operators, objective terms, charging rules, information, fleet, or search allowance. Successful initialization follows identical seeded search and returns identical routes/objectives/counters in the regression fixture. Elapsed-time diagnostics are compared separately from deterministic behavior.

The original `MPC_ALNS` registry entry and its initialization defaults remain unchanged. HGS/ACS also retain their historical defaults and their documented expired-initialization defects. For operational use, an explicitly versioned common configuration can enable the existing initialization policy for all methods; it must not be mixed with frozen-original results. The ten-run comparison below uses **all five original settings**, and does not substitute the corrected ALNS variant into the comparison.

Focused regressions cover depleted battery, impossible capacity/time windows, no charging opportunity, empty neighborhoods, two partial charges and exact charging durations, safe return, dynamic revelation during a noninterruptible action, adjustable busy suffixes, duplicate/hidden service, deterministic seeded work, expired initialization, and timeout after a valid incumbent exists. The corrected simulator path must retain the constructor and pass independent physical/information replay. No test is weakened to permit a physically invalid result.

## Preselected fair pilot

| Case | Role | Target DoD | Scenario seed | Methods |
| --- | --- | ---: | ---: | --- |
| c101_21_25 | First C1 development parent at 25 customers | 0.75 | 7301 | Completion, MCTS, ALNS, HGS, ACS |
| r101_21_100 | First R1 parent, 100 customers with tight windows | 0.75 | 7301 | Same five originals |

These two exposed development cases were fixed before opening new outcomes. They were selected by size/family and lexical parent order, not a known ALNS ranking. This is a correctness pilot, not untouched evaluation or tuning. The original exact-count generator's discrete realized dynamicity is retained. Algorithm seed remains 0.

All five configurations derive from `paper_controller.yaml`; only optimizer identity differs. Constructor/initialization/coordination/dispatch/first-action/cache/recovery policies and decoder are `original`; partial charging, original event triggers, one-action control horizon and five-second total planning limit are common. Each case's benchmark/reference hashes, canonical release schedule ID, K_ref, full effective configs, complete planned order and source hashes are frozen before any worker starts.

Workers run sequentially in separate processes, Python hash seed 0, with numerical-library thread counts 1. The first case uses the listed method order and the second reverses it. An exclusive supervisor lock prevents duplicate supervisors. External machine load is not certified; timings are labelled accordingly.

## Compute admission and failures

The timing model SHA-checks the 450 primary and 60 CPU-replication raw files and uses original workers labelled isolated. For each size/method, the cap is `ceil(max(60, 2*largest wall + 60, 2*largest measured child CPU + 60))`. Missing primary CPU measurements are not inferred from wall time. There is no clipping to force admission.

The ten pilot jobs plus 300 seconds setup, 600 seconds validation reserve and two seconds supervision per job require **4,435 seconds (73.92 minutes)** conservatively. This fits a **7,200-second wall and worker-CPU limit**. Estimated storage is **21,788,740 bytes**, within 256 MiB. These caps bound spending rather than guarantee successful completion.

The existing `HardBudget` charges the greater of worker elapsed and measured child CPU. Each complete five-method case block must fit the remaining allowance plus reserve before admission. Raw files are never overwritten; recorded completed jobs are hash-verified and reused. Unmanifested raw evidence, worker errors or watchdog exhaustion stop the pilot, retain the complete failure/log record and prevent automatic retries. Outcome quality never decides whether to rerun. A completed raw file contains full simulator results, effective configuration identity, source/protocol IDs, measured wall/CPU and independent replay outcomes.

## Full future benchmark design and obstacles

The frozen design also lists an **exploratory**, exposed-parent candidate panel: three lexicographically first parents per family with all three sizes and reference-derived DoD 0.75 eligibility. It is not launched by this milestone.

| Family | Candidate parents |
| --- | --- |
| C1 | c101, c105, c106 |
| C2 | c201, c205, c206 |
| R1 | r101, r105, r109 |
| R2 | r201, r205, r209 |
| RC1 | rc101, rc105, rc106 |
| RC2 | rc201, rc205, rc206 |

These are 18 independent parent identifiers, 54 files/scenarios, and **270 executions** for all five methods. They are all previously exposed, as documented in [the exposure audit](BALANCED_BENCHMARK_PROTOCOL.md). Different sizes/seeds do not make their geometry untouched. Thus the panel cannot be called confirmatory. Its conservative allowance is **103,410 seconds (28.73 hours)** with **138,934,756 bytes** estimated storage; it fails a provisional 12-hour wall/CPU admission gate. Neither the pilot nor its results authorize that campaign. A new prompt must approve an explicitly exploratory study with a credible larger budget, or provide genuinely new benchmark parents.

For any later full comparison, aggregate each method difference equally across the three sizes within parent, then equally across parents. Use 20,000 family-stratified parent-bootstrap draws, seed7302, carrying all sizes together. Report paired effect sizes and descriptive 95% intervals, complete-service differences, family/size and 100-customer subsets, and wins/ties/losses. Main contrasts include each search method versus Completion and ALNS versus HGS; other contrasts/subgroups are exploratory with multiplicity disclosed. Parent groups, not epochs or repeated seeds, are the sampling units. Small within-family samples and prior exposure limit inference. An interval containing zero is not equivalence.

## Audits, pilot results and reproduction

The full suite passed **524 tests, with 4 skipped**, before pilot freeze; [JUnit evidence](../results/research_v2/mpc_reliability_v1/validation/tests.xml) is retained. The [historical replay](../results/research_v2/mpc_reliability_v1/validation/historical_replay.json) passed **510/510** exact-hash primary/replication records. The [implementation audit](../results/research_v2/mpc_reliability_v1/validation/implementation_audit.json) records the timeout reproducer and verifies 13 original optimizer/objective/physical/decoder files byte-for-byte against the reviewed commit.

**All 10 pilot executions completed and passed both worker-time and saved-file independent physical/information replay.** Maximum recorded planning latency was **2.943 seconds**, below five seconds. There were zero reported deadline events, optimizer-deadline decisions, initialization fallbacks, worker failures, or physical/information violations. The supervisor charged **819.915 seconds** including its setup allowance, against 7,200 seconds; measured worker CPU totalled **503.0 seconds**. The [pilot report](../results/research_v2/mpc_reliability_v1/validation/RESULTS.md) and [structured metrics](../results/research_v2/mpc_reliability_v1/validation/pilot_results.json) retain every outcome.

| Original method | C101 / 25 served | R101 / 100 served | Customer-weighted service across these two cases | Complete scenarios |
| --- | ---: | ---: | ---: | ---: |
| Completion | 24 | 89 | 113/125 = 90.4% | 0/2 |
| MCTS | 25 | 87 | 112/125 = 89.6% | 1/2 |
| ALNS | 25 | 98 | 123/125 = 98.4% | 1/2 |
| HGS | 25 | 97 | 122/125 = 97.6% | 1/2 |
| ACS | 25 | 93 | 118/125 = 94.4% | 1/2 |

ALNS has the largest observed service count here only. MCTS underperformed Completion on R101 and in the pooled two-case count. On the jointly complete 25-customer case, HGS had shorter distance than ALNS (788.99 versus 838.08 benchmark distance units). On R101 every method served a different customer set, so those operating costs do not support an efficiency ranking. These two exposed scenarios do not establish population superiority or a confidence interval across independent benchmark parents.

The executed runner's initial reporting routine attempted to access `deadline_fallback_count`, which the frozen simulator records only for the older `FLEET_MPC_MCTS` identity. That [analysis failure](../results/research_v2/mpc_reliability_v1/validation/analysis_failure.json) is preserved. A separate [analysis helper](../scripts/experiments/analyze_mpc_reliability_pilot.py) fixes the schema assumption without altering executed source, protocol or raw outcomes. It reports this unavailable final-validation fallback counter as null, rather than inventing zero. Total deadline events and the separately recorded optimizer/initialization flags remain available. Two schema regression tests cover absent and explicit-zero counters and unchanged input records. The final full suite passed **526 tests, with 4 skipped**; [post-analysis JUnit evidence](../results/research_v2/mpc_reliability_v1/validation/tests_analysis.xml) is retained separately from the pre-pilot gate.

The validation artifacts record the actual full-suite outcome, 510 historical physical/information replays, and the pilot's independent replay, latency, timeout, fallback, charge/energy and operating metrics. A passing pilot is evidence for these cases and constraints, not proof that the methods are defect-free. Original initialization-timeout defects, bounded decoder incompleteness, wall-clock truncation and prior benchmark exposure remain material limitations.

Pilot operating costs are compared only for identical actual served customer sets within the same scenario. Individual measurements on different served sets are descriptive and cannot rank routing efficiency. The highest observed service in two cases is not a superiority claim. Worker failures and timeouts stay in the manifest/failure ledger; no fabricated complete outcome is substituted.

```powershell
# Read-only design and conservative admission preview.
python -m scripts.experiments.run_mpc_reliability_pilot

# These explicit evidence steps each create new files; do not overwrite or restart a frozen study.
python -m scripts.experiments.run_mpc_reliability_pilot --audit-history
python -m pytest -q --junitxml=results/research_v2/mpc_reliability_v1/validation/tests.xml
python -m scripts.experiments.run_mpc_reliability_pilot --freeze
python -u -m scripts.experiments.run_mpc_reliability_pilot --run-pilot
python -m scripts.experiments.analyze_mpc_reliability_pilot
```

After completion, use the saved protocol/manifest/validation reports directly. The runner checks exact current source bytes and refuses source drift. Replaying a historical campaign requires its recorded source, not a rewritten fingerprint. No large benchmark execution command is provided here.
