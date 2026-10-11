# Fleet-LNS development gate (2026-10-11)

This is a **single-seed development comparison**, not final or holdout evidence.
The source fingerprint for the original rolling-static and dynamic runs is
`f37b8ac6e7c332a5784a845ebad1870c7b87c1d8d608c601c68e67155485d6b7`.
Raw records are in `results/fleet_lns_static/runs/` and
`results/fleet_lns_development/runs/`. Each dynamic pair uses the same instance,
DoD 0.5, scenario seed 0, algorithm seed 0, and scenario hash. All listed runs
completed and passed the recorded no-future-information, safe-return,
trace-replay, and unique-service audits.
The exact selected result files, run IDs, configuration and scenario hashes, and file
SHA-256 values are frozen in [the evidence manifest](fleet_lns_evidence_manifest.json).
[The tables](fleet_lns_evidence_tables.md) are generated only from that manifest;
`python scripts/fleet_lns_evidence.py --verify` checks both against the raw files.

## Experimental method

`ROLLING_ALNS` starts from the rolling-horizon/regret fleet plan.
`MPC_MCTS_ALNS` also constructs short local MCTS proposals (12 iterations,
top-L 3) and selects the lexicographically best initial fleet plan before the
same fleet search. Both use fixed `K_ref`, horizon 5, partial charging, 100
fleet-LNS iterations or a cooperative 1.5-second limit per event. The configured
10% destroy fraction is a target before a hard cap: each iteration removes
`min(owned, 4, max(1, round(0.1 * owned)))` customers; rescue removes at most
two. The fleet search can remove and reassign released customers
across EVs using rescue, random, worst, and related removal followed by
regret-2/3 repair. Customer sequences are decoded with at most one charging
station between consecutive services and exact route replay. Executing actions
remain immutable. This is a minimal fleet LNS; relocate, swap, 2-opt*, and
route-pool MILP are **not** implemented in this study.
Operator choice cycles deterministically; there is no adaptive weighting.
The `*_ALNS` IDs in the frozen result files are historical misnomers. New runs
use `ROLLING_LNS` and `MPC_MCTS_LNS`; the old IDs remain accepted solely to
reproduce the committed runs.

## Static prerequisite

All six original known-demand runs used the historical `ROLLING_ALNS` ID and
served 100/100 customers.
The vehicle counts were within the reference fleet limits. Times are total
recorded online planning wall time in seconds; they are not isolated real-time
latency guarantees.
The exact static values are in the [generated table](fleet_lns_evidence_tables.md#static).
The six selected files exclude earlier failed/prototype attempts, which remain
preserved in the repository.

## Hybrid static check

A later `MPC_MCTS_LNS` static check used one unchanged newer source fingerprint,
`0ef7219ac6c578bdd8134809cfbdfb9d65958464b7cae4170c7af4d879336c5d`.
`c101_21`, `c201_21`, and `r101_21` each served 100/100 and passed all recorded
audits; exact values and file hashes are in the
[partial static table](fleet_lns_evidence_tables.md#hybrid-static-check-partial)
and manifest. `r201_21` was interrupted after a 30-minute wall-time cutoff
without a result; `rc101_21` and `rc201_21` were not started. Thus the proposed
hybrid has **not** passed a six-instance static gate. The completed `c201_21`
run alone recorded 780.25 seconds total planning time and a 407.21-second
maximum event, reinforcing the latency concern. These newer runs are not mixed
into the original dynamic comparison.

## Matched dynamic development

Compare distance only after service and EV count are tied. These are individual
deterministic scenarios, not confidence intervals. See the
[generated matched table](fleet_lns_evidence_tables.md#matched-dynamic-development-dod-05-seeds-0).

The hybrid wins three pairs and loses three. Its sole one-customer service
gain is outweighed by service losses of one and two customers elsewhere;
aggregate service is 599/600 for rolling and 597/600 for the hybrid. Hybrid
planning time is higher in all six pairs. In particular, its shorter routes
on `c201_21` and `rc201_21` do **not** compensate for lost service.

**Gate: do not launch the holdout.** The six cases do not establish a
meaningful service advantage or a majority matched-case advantage for MCTS
over fleet LNS. This result does support fleet-wide repair as a viable
static constructor, but does not support claiming that MCTS improves it.
The unrun holdout remains untouched. The current 1.5-second LNS limit is
cooperative and excludes initial constructive repair; worst event times in the
generated tables show that this implementation is not yet suitable for strict
real-time claims.
The hybrid also receives MCTS computation on top of the same LNS budget, so the
pair is not equal-total-compute. Any future superiority claim would require a
matched total planning budget.

## Verification and scope

The full local suite passed (`271 passed`), with JUnit evidence at
`results/verification/pytest.xml`; all four Schneider C5 reference validations
passed. Restricted charging-decoder regression tests
also replay the six static reference route sequences offline. No PDF figures
were produced. Further work should first address worst-case constructive
repair latency and evaluate multiple development seeds before reconsidering
the MCTS hybrid or opening a held-out comparison.
