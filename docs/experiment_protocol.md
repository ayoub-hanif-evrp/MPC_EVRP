# Final Experiment Protocol

Status: preregistered control-horizon correction of Risk-Aware Fleet-Level
MPC-MCTS. The `6a1ab7e` campaign and earlier coordinator/dynamic pilots are
historical development evidence, not results of this corrected method.
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
committed-action after-state; idle EVs use the validated fallback action's
after-state. `R_FLEX` remains predicted suffix robustness. The bounded scalar
reward guides MCTS only; it never replaces lexicographic final selection.
Full-service MCTS adds CONTROL-RELOCATE and CONTROL-SWAP at route heads to
the existing relocate, swap, Or-opt, 2-opt, and compaction moves.

Both `FLEET_MPC_MCTS` and `ROLLING_LNS` receive a five-second total wall-clock
ceiling per event, with a common 150 ms internal guard for cooperative stop
overhead. Fleet MCTS has an iteration ceiling of 256, depth four,
branch limit 24, and at most three candidate insertion positions. It reserves
another 150 ms before that guard for final replay and bookkeeping. The single event deadline includes
incumbent generation, criticality, search, rollout, decoding, and final replay.
Rolling-LNS receives at most 40% of the event budget for initial regret repair
and can use the remaining budget for its unchanged LNS operators. Both methods
retain their last validated incumbent on deadline expiry. Record actual
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

The preregistered development PASS requires every one of the 12 matched pairs
to complete; static Fleet service 600/600; aggregate Fleet service at least
Rolling-LNS service; Fleet service wins at least losses; Fleet service at least
90/100 in **every** dynamic run; no C/R/RC family-wide severe Fleet collapse;
all independent physics/information audits pass; and **every measured event**
for both methods at or below 5.0 seconds. Any failure blocks holdout. Compare EV
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
