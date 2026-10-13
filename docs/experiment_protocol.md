# Final Experiment Protocol

Status: structural-rollout correction stopped at the static gate after
`c101_21` served 100/100 and `c201_21` served 94/100. The other four static
cases, 12-pair development grid, completion-only ablation, and holdout were
not run. The four required diagnostics were completed and audited.
The `6a1ab7e` campaign and earlier coordinator/dynamic pilots are historical
development evidence, not results of this corrected method.
No source or configuration change is permitted after the development campaign
starts. A failed development gate blocks the holdout.

## Method and trigger budget

At each physical event, the controller observes only released customers and
immutable busy-vehicle commitments. It exactly replays retained soft suffixes.
MPC optimization triggers at the initial epoch, new customer releases, a ready
vehicle with no valid continuation, an infeasible retained suffix, or a
customer-service completion while released uncommitted work remains.
Uncovered work alone is not a trigger. Charge and wait completions with a valid
suffix dispatch the next validated action without a new global search.
Only executing actions are hard; future assignments remain soft at the next
trigger. A deterministic fingerprint of released information, post-commitment
vehicle states, commitments, and retained customer sequences prevents repeated
MCTS calls on an unchanged root. Fleet-level MCTS searches customer assignment, sequence, and fleet
restructuring; charging stations and amounts are chosen by the deterministic
partial-charging decoder. Every retained candidate is exactly decoded and replay
validated. No LNS follows MCTS. Fleet MCTS, Rolling-LNS, and
`FLEET_MPC_COMPLETION_ONLY` start from the same retained feasible soft plan and
the same screened, anytime regret-2 constructor over all released residual
customers. It uses at most 40% of the event budget and five screened positions
per EV. Unused constructor time flows immediately to the improvement search.
MCTS tree children represent only explicit structural actions. A separate
direct-insertion default policy completes the residual plan for scoring and
backpropagation; it never replaces the structural tree node. A zero-option
critical customer stops direct rollout insertion, leaving rescue/ejection to
tree actions. Service screening considers every physical EV before shortlisting
exact charging-aware decodes. Progressive widening remains active.

`OBJECTIVE_VERSION=service-activation-distance-v2` continues to identify the
external scenario/evaluation dependency. The planner and search versions are
`risk-control-flex-service-v1` and `fleet-mcts-structural-rollout-v2` and
appear separately in new run identities, provenance, and the final report.

With uncovered released customers, final selection lexicographically minimizes
`J_A=(U, screened_Z0, screened_Z1, R_CTRL, R_TW, R_BAT, R_CAP, D_normalized)`.
The zero/one option counts are cheap forward/backward screened insertion gaps,
not exact feasible-option counts. With full current coverage, it minimizes
`J_B=(R_CTRL, R_FLEX, V, C_OP, D, R_STAB)`, where
`R_FLEX=(R_TW+R_BAT+R_CAP+R_TIME)/4` and `R_TIME` is the mean normalized
loss of safe remaining depot horizon among active vehicles. `C_OP` is the mean
of normalized distance, duration, charging, waiting, TW risk, battery risk,
and route imbalance. `R_CTRL` is the fleet mean of four risks at each EV's
state immediately after the next control action: first-served-customer window
slack divided by its window width, battery reserve above direct reachable-safe
energy divided by battery capacity, residual payload divided by vehicle
capacity, and remaining depot-horizon reserve divided by the horizon left at
the current event. Each risk is one minus its clipped reserve; the TW risk is
zero when the first action does not serve. Busy EVs use their immutable
committed-action after-state; unused ready depot EVs remain available reserves
at the current event time rather than receiving a horizon-long WAIT risk.
`R_FLEX` remains predicted suffix robustness. The bounded scalar
reward guides MCTS only; it never replaces lexicographic final selection.
Full-service MCTS adds CONTROL-RELOCATE and CONTROL-SWAP at route heads to
the existing relocate, swap, Or-opt, 2-opt, and compaction moves.

`FLEET_MPC_MCTS`, `ROLLING_LNS`, and `FLEET_MPC_COMPLETION_ONLY` receive a five-second total wall-clock
ceiling per actual optimization trigger, with a common 250 ms internal guard for cooperative stop
overhead. Fleet MCTS has an iteration ceiling of 256, depth four,
branch limit 24, and at most three candidate insertion positions. It reserves
another 150 ms before that guard for final replay and bookkeeping. The single trigger deadline includes
incumbent generation, criticality, search, rollout, decoding, and final replay.
Each method gives the shared constructor at most 40% of the event budget.
Rolling-LNS uses the remaining budget for its unchanged LNS operators; Fleet
MCTS uses it for structural tree search. The completion-only ablation executes
the constructor with no tree search. All methods
retain their last validated incumbent on deadline expiry. Record actual
iterations, expanded nodes, service/full-coverage search seconds, final replay
seconds, deadline fallbacks, simulation events, trigger counts, MCTS calls,
complete-instance runtime, and optimization mean/p95/maximum latency. A
15-minute engineering watchdog and repeated-state detector fail a stuck
100-customer development run with diagnostic state.

## Verification and source freeze

Before dynamic scientific runs, pass the four diagnostics and all six static
cases at 600/600, focused method tests, the complete test suite once
with `results/verification/pytest.xml` refreshed, and all four Schneider
reference validations. Commit source, configuration, protocol, tests, and
verification evidence. Ensure the tracked working tree is clean. Static sanity
may have a pre-freeze Git commit but must share the exact frozen source hash;
all dynamic development runs must use one frozen commit. Record that commit in
the final report and every run's provenance. Preserve SHA-256 manifests and
the independent trace audit. No scientific grid from uncommitted source.

## Static validation and development

Validate the corrected method statically on the six development instances
`c101_21`, `c201_21`, `r101_21`, `r201_21`, `rc101_21`, `rc201_21` using the
fixed reference fleet. The historical 600/600 result is context; the final
report must distinguish it from validation under the frozen new commit.

Run the full 12 matched dynamic pairs: those six instances at target DoD 0.5,
scenario seeds 0 and 1, algorithm seed 0, comparing `FLEET_MPC_MCTS` and
`ROLLING_LNS`. Share each scenario, K_ref, physics, release boundary, and
five-second event budget. Do not stop after early wins or losses. Audit every
record and report target versus realized DoD and technical failures.

The development verdict requires the complete 12-pair grid, static 600/600,
zero technical failures, no catastrophic Fleet collapse, competitive aggregate
and family-level service against Rolling-LNS, credible wins/ties across C/R/RC,
and meaningful paired improvement over the completion-only ablation. Every
measured optimization call must be at or below five seconds, with all independent
audits passing. Compare EV count only at equal service; compare distance only
at equal service and EV count. Report `R_CTRL`, `R_FLEX`, and compute effort
separately. A failed gate blocks holdout; do not retune seeds, fleet size,
objectives, or instance-specific behavior.

## Conditional holdout

Only after a development PASS, keep source/configuration frozen and run the
untouched holdout instances `c109_21`, `c208_21`, `r112_21`, `r211_21`,
`rc108_21`, `rc208_21` at DoD 0.25, 0.50, 0.75; scenario seeds 0, 1, 2;
algorithm seed 0. Main methods are `RH_REGRET`, `ROLLING_LNS`, and
`FLEET_MPC_MCTS`; the old coordinator is an optional ablation only. Report all
conditions, including unrealized DoD and technical failures. Do not inspect
holdout records if development fails.

## Reporting

Archive raw records/manifests, audited summaries, CSV/LaTeX tables, source
CSVs and PNG-only figures, and `results/final/FINAL_REPORT.md`. Report service,
full-service rate, wins/ties/losses, conditional EV and distance comparisons,
operational-risk objective, planning latency, MCTS iterations/nodes, failures,
limitations, and whether the paper hypothesis is supported. Large raw traces
may remain compressed/ignored locally, but final summaries, manifest, tables,
figures, and report must be preserved under `results/final/`.
