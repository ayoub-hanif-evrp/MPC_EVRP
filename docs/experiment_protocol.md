# Final Experiment Protocol

Status: frozen Risk-Aware Fleet-Level MPC-MCTS final track. Earlier coordinator
and dynamic pilot results are historical tuning evidence, not final comparisons.
No source or configuration change is permitted after the development campaign
starts. A failed development gate blocks the holdout.

## Method and event budget

At each release/dispatch event, the controller observes only released customers
and immutable busy-vehicle commitments. MPC generates a feasible soft fleet
incumbent. Fleet-level MCTS searches customer assignment, sequence, and fleet
restructuring; charging stations and amounts are chosen by the deterministic
partial-charging decoder. Every retained candidate is exactly decoded and replay
validated. No LNS follows MCTS. The root is the best of the previous feasible
soft incumbent, due-order regret construction, and criticality-order regret
construction. Progressive widening remains active.

With uncovered released customers, final selection lexicographically minimizes
`(U, screened_Z0, screened_Z1, R_TW, R_BAT, R_CAP, D_normalized)`.
The zero/one option counts are cheap forward/backward screened insertion gaps,
not exact feasible-option counts. With full current coverage, it minimizes
`(R_FLEX, V, C_OP, D, R_STAB)`, where
`R_FLEX=(R_TW+R_BAT+R_CAP+R_TIME)/4` and `R_TIME` is the mean normalized
loss of safe remaining depot horizon among active vehicles. `C_OP` is the mean
of normalized distance, duration, charging, waiting, TW risk, battery risk,
and route imbalance. The bounded scalar reward guides MCTS only; it never
replaces lexicographic final selection. Full-service MCTS may use the remaining
event budget and includes flexibility relocate, swap, Or-opt, 2-opt, and route
compaction actions in addition to service-recovery insert/ejection actions.

Both `FLEET_MPC_MCTS` and `ROLLING_LNS` receive a five-second total wall-clock
budget per event. Fleet MCTS has an iteration ceiling of 256, depth four,
branch limit 24, and at most three candidate insertion positions. It reserves
approximately 50 ms for final route replay. The single event deadline includes
incumbent generation, criticality, search, rollout, decoding, and final replay.
On deadline expiry, use the last already validated incumbent. Record actual
iterations, expanded nodes, service/full-coverage search seconds, final replay
seconds, deadline fallbacks, event p95, and event maximum.

## Verification and source freeze

Before scientific runs, run focused method tests, the complete test suite once
with `results/verification/pytest.xml` refreshed, and all four Schneider
reference validations. Commit source, configuration, protocol, tests, and
verification evidence. Ensure the working tree is clean. Record that commit in
the final report and every run's provenance. Preserve SHA-256 manifests and
the independent trace audit. No experiments from uncommitted source.

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

The preregistered primary gate requires aggregate Fleet MPC-MCTS unserved no
more than Rolling-LNS, service wins at least losses, tie/improvement behavior
in more than one C/R/RC family, no severe individual service collapse, valid
physics/information audits, and latency within the event budget. Compare EV
count only at equal service; compare distance only at equal service and EV
count. Report operational-risk cost separately. Failure blocks the holdout;
do not retune seeds, fleet size, objectives, or instance-specific behavior.

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
