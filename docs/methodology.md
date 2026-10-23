# MPC Methodology

The active benchmark is Desaulniers et al. (2016) under the multiple-partial
(MP) charging policy. The original migration preserves the baseline methods;
this research branch also contains explicitly named development variants and
opt-in runtime corrections. These are not silently substituted into controls.

## Shared Controller

Each method starts with the same `K_ref` EVs from a physically validated
offline reference. At an observable release or vehicle event, the simulator
updates measured states, makes released requests visible, preserves executing
actions as noninterruptible, and replays feasible soft route suffixes. A
common constructor builds feasible candidates; Completion uses them without
further optimizer search, while MCTS, ALNS, HGS, and ACS search the same
released-state fleet problem. The controller executes only the first selected
action, retains soft continuations, and repeats at later observable events.
Hidden future requests and the offline reference routes are never input to
online optimizers. All methods use the same physical transition and
independent audit, and each optimization decision has a five-second budget.

## Objective

`evrp/optimizers/objective.py` remains the canonical service-first,
risk-aware lexicographic fleet evaluator. For uncovered released work it
orders the number unserved, zero/one screened insertion options, control
risk, time-window risk, battery risk, capacity risk, then normalized
distance. When all released work is covered, it retains the existing
control-risk, flexibility, activation, operational, distance, and route-
instability order. The Desaulniers migration does not change these terms,
their priorities, search strategies, or optimizer budgets.

Published static solution costs optimize a different study objective and
are not ranked against this dynamic MPC objective. A published feasible
route may be used offline to define `K_ref`, but does not supply online
actions.

## Physical Model

The shared plant uses the upward-rounded travel and time-equivalent energy
specified by format-2 published arcs. The source text supplies customer
windows, demand, service duration, depot/station hours, and vehicle
parameters. Station-to-station arcs are absent and therefore forbidden.
Service start must meet its hard window, load and battery cannot become
negative, partial recharge takes time proportional to energy added, and
every accepted action must retain a feasible return before depot closing.
See [dataset semantics](DESAULNIERS_MIGRATION.md) for the exact unit map.

## Dynamic Scenarios

For selected customers, `release_i <= min(ready_i,
reference_predecessor_departure_i)` preserves an offline full-service
schedule with advance knowledge. The online planner sees only currently
released requests. Exact-count DoD uses half-up customer counts; if the
reference yields too few eligible customers, that condition is rejected.
Target and realized DoD are both recorded. Scenarios, `K_ref`, controller
settings, and optimization limits are paired across methods.

## Evidence

The three-size C1 pilot and the 270-run development campaign are development
evidence only. The original Desaulniers final protocol stopped after ten
records due to an independent replay-audit timing defect. Those records and
failure evidence remain separate. An auditor-only erratum produced a new,
separately fingerprinted 270-run corrected final holdout over 54 matched
scenarios. Its raw traces have been independently replayed again in the
`validation/final_integrity.md` report. The old Schneider results remain in
Git history and are never relabeled as Desaulniers outcomes.

The corrected final study used one release seed. The prospective robustness-v2
preflight identified that its initial six instances were all ineligible at
DoD 0.75, before any method ran. The separately versioned robustness-v3
protocol uses the first unused, physically replayed, DoD-eligible instance
in each family-size slot and five new seeds. Its 450/450 method runs are
complete and independently audited, but remain a separate study from the
corrected final holdout. Paired uncertainty
resamples base instances, retaining their DoD and
seed scenarios together. Distance comparisons use only the same scenarios
where all methods serve every customer. A reference schedule proves offline
feasibility with advance knowledge, not online attainability or MP optimality.
