# MPC Methodology

The active benchmark is Desaulniers et al. (2016) under the multiple-partial
(MP) charging policy. This is a dataset migration, not a new algorithm.

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
orders the number unserved, zero/one feasible insertion options, control
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

The three-size C1 pilot is development evidence only. It tests migration
correctness and runtime, not optimizer superiority. The old Schneider
results remain available in Git history but are not relabeled as results
for this dataset. A future final evaluation must be preregistered on
untouched instances after development, with the fixed baselines rerun.
