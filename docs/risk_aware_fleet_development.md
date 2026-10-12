# Risk-Aware Fleet-Level MPC-MCTS Development

**Decision: static gate passed; dynamic development gate failed. No holdout was run.**

The final source revision for these experiments is commit
`5d6600e02d4cd15341c45a9c16a0ad4407089345`, with fleet source fingerprint
`efbbcdfcb7303cc4e59e089c6dc15c4e6d419b65ce22b2a517e7f1c7342699fe`.
The six static records share one requested-configuration hash
`b6e13623bd42e85b162aea14280473610a77d72cb0f803da67fa6664d82ecd55`.
The [manifest](risk_aware_fleet_manifest.json) binds every new development
attempt to its commit, source, scenario, config, run ID, and file SHA-256.
`python -m scripts.risk_aware_fleet_evidence --verify` independently replays
the disk-record trace auditor and checks that no attempt is omitted. The
[table](risk_aware_fleet_table.md) is generated from that manifest. The earlier
nine static attempts remain in the [historical manifest](fleet_mcts_static_manifest.json).

## Method

At each event-driven MPC epoch, the method sees only measured EV states and
released customers. Executing actions remain immutable; all later suffixes are
soft. Fleet MCTS searches customer assignment and sequence macro-actions, the
charging-aware decoder turns sequences into executable EV routes, and only the
first physical controls are dispatched. The MPC planning horizon is the
currently observable residual routing horizon, not the legacy local
`prediction_horizon=5`; the control horizon is one action. The fleet is fixed
at `K_ref`, and reference routes are never exposed to online planning.

The service phase compares plans lexicographically by uncovered customers,
estimated zero/one insertion-option counts, time-window risk, battery risk,
capacity risk, and normalized distance. The full-service phase compares
activated EVs, a normalized seven-component operational cost, distance, then
route instability. Secondary scalar MCTS reward terms sum to 0.90, so one more
covered customer dominates them. Progressive widening, rank priors, critical
customer ranking, adjacent-gap ejection, regret-2/3 rollouts, and bounded
full-service relocate, swap, Or-opt, 2-opt, and route-compaction actions remain
inside MCTS. There is no post-MCTS LNS. `ROLLING_LNS` is a separate baseline.

The insertion-option counts are **optimistic geometric estimates**, not exact
feasible-gap counts. This is a methodological limitation against the requested
exact `zero_option_customers` definition; every *selected* route is still
exactly decoded and replay-validated. Decoder prechecks cover demand and
earliest-arrival time windows, but do not implement a separate rigorous energy
lower-bound screen. These distinctions must not be hidden in a paper claim.

The configuration permits five seconds total per event, reserving 50 ms for
final validation and returning a previously validated incumbent if that
validation reaches the deadline. Full-coverage search has an additional
0.75-second cap to prevent repeated phase-B search from consuming the full
five seconds. The cap is a ceiling, not a promise of constant runtime.

## Static Gate

The six DoD 0 development instances served **600/600** from one clean source
revision, with all independent physical and information audits passing.
Activated EVs were 13, 5, 20, 4, 21, and 5 for C1, C2, R1, R2, RC1, and RC2.
Maximum recorded decision latency was 4.96 seconds. All failed and superseded
pilots were retained, including the 73/100 and 85/100 `c101_21` attempts.

## Dynamic Gate

DoD 0.5 comparisons used identical scenarios, seeds 0 and 1, and the same
five-second **per-event cap** for both algorithms. Actual compute differed:
Rolling-LNS often used much more of that allowance. Four matched pairs were
completed before the clear service loss stopped the campaign:

| Instance | Seed | Fleet served | Rolling-LNS served |
| --- | ---: | ---: | ---: |
| c101_21 | 0 | 98 | 100 |
| c101_21 | 1 | 100 | 99 |
| r101_21 | 0 | 81 | 100 |
| r101_21 | 1 | 94 | 97 |

Fleet served **373** versus Rolling-LNS **396**, with one service win and
three losses. All eight runs passed independent audits. The proposed method
therefore does **not** satisfy the required no-worse aggregate service, nor
the cross-family win condition. The other eight planned pairs were not run;
their results are unknown. The holdout was not inspected or executed. These
data do not support a dynamic superiority or final-paper performance claim.

The research record supports a narrower conclusion: risk-aware fleet MPC-MCTS
can achieve the complete six-instance static service prerequisite under a
bounded event budget, but this revision does not match Rolling-LNS on the
observed dynamic development cases. No PDF figures were generated.
