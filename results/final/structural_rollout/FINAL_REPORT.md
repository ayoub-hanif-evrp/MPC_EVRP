# Final-Method Correction: Static Gate Failed

**Status: stopped before scientific development.** This report covers the
structural-rollout Fleet MPC-MCTS correction, four required diagnostics, and
the first two six-instance static gate cases. It is not a matched Fleet-vs-LNS
paper result. No completion-only ablation grid or holdout was run.

## Method implemented

The same bounded screened regret-2 constructor now initializes
`FLEET_MPC_MCTS`, `ROLLING_LNS`, and `FLEET_MPC_COMPLETION_ONLY`. It retains
feasible soft suffixes, screens all physical EVs, exact-decodes shortlisted
insertions, preserves partial solutions on timeout, and uses at most 40% of
the five-second event budget. MCTS children remain states reached by one
structural tree action. Direct insertion completion evaluates each selected
node and is never installed as its tree state. A zero-option critical customer
stops the direct rollout; rescue/ejection is a tree action. Early-due requests
are represented in the tree action shortlist. No LNS follows MCTS.

The event-trigger policy, K_ref, information boundary, EV physics, objective
tuples `J_A`/`J_B`, and MCTS parameters were unchanged. The benchmark/scenario
objective version remains `service-activation-distance-v2`; planner version
is `risk-control-flex-service-v1`; search policy version is
`fleet-mcts-structural-rollout-v2`. Existing scenario hashes were reused.

## Four final-source diagnostics

All four completed, passed independent trace audits, avoided the engineering
watchdog, and had maximum optimization calls below five seconds. The C201
dynamic case lost one customer relative to the earlier 100/100 result; this
is reported rather than treated as a perfect stability result.

| Case | DoD | Seed | Served | Triggers | Constructor gain over retained, summed over calls | MCTS service gain over constructed root, summed over calls | Tree iterations / nodes | Max rollout residual | Wall s | p95 / max call s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| c101_21 | 0 | 0 | 100/100 | 22 | 99 | 1 | 5,441 / 1,427 | 1 | 10.25 | 2.223 / 4.614 |
| r101_21 | .5 | 0 | 99/100 | 145 | 95 | 4 | 37,120 / 30,291 | 3 | 70.88 | 1.624 / 2.866 |
| r201_21 | .5 | 1 | 100/100 | 79 | 73 | 27 | 1,205 / 701 | 33 | 354.43 | 4.807 / 4.840 |
| c201_21 | .5 | 0 | 99/100 | 113 | 93 | 6 | 17,202 / 14,092 | 28 | 292.24 | 4.751 / 4.754 |

MCTS made 24 service-improving incumbent updates and 327 equal-service
objective-improving updates across these diagnostics. These are within-run
search statistics, **not** a paired advantage over the completion-only
ablation. Mean rollouts inserted 0.0066, 0.0000, 0.0349, and 0.0002 customers
per simulation in table order; completed rollouts can retain zero-option
residuals. All-EV screening means were 13, 20, 4, and 5 EVs per screened
customer respectively. Exact decoded option totals were 3,357, 41,810,
6,222, and 41,864. Trigger reasons and per-epoch root-to-final outcomes are
retained in each audited raw record.

## Static gate and stop

| Instance | Served | Audit | Wall s | Maximum optimization call s |
|---|---:|---|---:|---:|
| c101_21 | 100/100 | PASS | 8.02 | 4.604 |
| c201_21 | 94/100 | PASS | 225.03 | 4.751 |

Six-static 600/600 prerequisite: **FAIL**. C201 left six customers unserved;
the first MPC epoch constructed 25/100 and MCTS did not improve that root
before execution. The runner stopped before `r101_21`, `r201_21`, `rc101_21`,
and `rc201_21` static cases. No parameter, objective, or instance-specific
change was made after this gate failure.

The 12 matched Fleet-vs-Rolling-LNS dynamic pairs, completion-only ablation
grid, Fleet service W/T/L, family comparisons, and holdout are **not available**.
No conditional EV or distance comparison, confidence interval, or positive
paper-performance claim is justified. The earlier intermediate diagnostics
(94/100 C101 static, 98/100 R101, 96/100 R201, 89/100 C201) are preserved
but excluded from the final-source table.

## Verification and provenance

Full pytest: **304 passed, 0 failed, 0 errors**;
[`pytest.xml`](../../verification/pytest.xml) was refreshed. Schneider
reference validation: **4/4 passed**. The final-source SHA-256 is
`c2debe712803f9241b4e25781de2983018dd6c9207fee085214c51351205a43a`.
The raw records identify their pre-correction base Git commit; this stopped
campaign was not frozen for a scientific development grid. The
[`SHA-256 manifest`](../../../docs/structural_rollout_manifest.json) lists all
ten audited raw records with final/intermediate roles. No PDF figures were made.
