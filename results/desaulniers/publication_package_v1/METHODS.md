# Framework and unchanged mathematical problem

The static input is the Desaulniers et al. (2016) dataset with multiple partial
recharging (MP). The loader validates all format-2 arc costs, travel times and
energy against format-1 input. Existing distance, time, energy conversion and
rounding functions are used throughout. The plant enforces battery bounds,
remaining payload, service-start time windows, safe depot return, one route per
fixed-fleet EV, and the published station-to-station restriction. Linear charging
adds time in proportion to energy. No fleet enlargement, window relaxation or
nonlinear charging is used in online comparisons.

Dynamic requests become visible only on release. The common event-triggered
controller plans from measured idle-vehicle states and the after-states of
immutable busy actions. It coordinates unique customer ownership, constructs
feasible suffixes, runs the selected optimizer, independently replays the chosen
routes, and executes the next physical action. Five seconds is the shared
decision budget, including construction, search and final validation.

## Canonical objective

The implementation uses lexicographic minimization. With uncovered observable
customers, its tuple is `(unserved, zero_options, one_option, control_risk,
time_window_risk, battery_risk, capacity_risk, normalized_distance)`.
`zero_options` and `one_option` count screened insertion options; they are
heuristic opportunity indicators, not certificates of physical infeasibility.

With complete currently observable coverage, the tuple is `(0, control_risk,
flexibility_risk, activated_vehicles, operational_cost, distance,
route_instability)`. Flexibility averages time-window, battery, payload and
time-reserve risk. Operational cost averages the original seven normalized
distance, duration, charge, waiting, time-window, battery and balance measures.
The definitions in `evrp/optimizers/objective.py` are unchanged across methods.

## Algorithms and explicit development variants

Completion retains the common feasible constructor; MCTS, ALNS, HGS and ACS
search the same observable fleet problem with the common objective and plant.
Original implementations and historical source commits remain available.

These are repository implementations of optimization paradigms, not claimed
bit-for-bit reproductions of external published solver packages. Exact
per-run parameter values are retained in every raw `effective_config`.

Completion returns the independently checked common fleet constructor without
additional search. The constructor compares retained, parallel-insertion and
regret-insertion candidates using the same canonical objective.

MCTS searches structural fleet-route edits with progressive widening, a
prior-weighted exploration rule and bounded completion rollouts. Rollout
evidence is grouped by executable first-control signature. Root selection
first rejects alternatives worse than the constructor, then orders eligible
controls by planned unserved count, visit support, mean search value and
canonical best-plan score. It therefore need not return the globally best
lexicographic plan ever sampled when equal-service controls have different
visit support. This is the preserved original control policy, not a new fix.

ALNS adaptively samples random, distance-related, related-customer,
time-window, battery-risk and route-risk removal with regret-2/regret-3,
criticality-first and reserve-preserving repair. Original removal is capped
at four customers. Operator rewards update segment weights. Diversification
may accept worse lower-priority components at equal service, while the best
incumbent uses the canonical lexicographic score. More-unserved moves are
not accepted as the current solution.

HGS uses a small population, service-first objective/diversity ranking,
route inheritance, missing-customer insertion, and bounded relocation,
swap, 2-opt and Or-opt education. Its best feasible elite is retained.
ACS constructs fresh ant plans with pheromone and urgency/slack/distance
heuristics, local pheromone updates, evaporation and reinforcement of the
best plan. The original constructor remains a separate incumbent.

Every accepted route uses the common decoder and physical replay. Iteration,
population and ant limits can terminate before the common five-second
deadline; they do not enlarge it. No new search parameters were tuned on the
completed final holdout.

ALNS Stable V3 restricts best-incumbent replacement during equal-service moves
to plans covering the same customer set. It allows route reassignment and
strict coverage increases, and scores candidates with the canonical objective.
This is an explicit search-policy change. It does not guarantee improved
closed-loop service and is governed by the frozen development selection rule.

Other evaluated variants are depot-window waiting, generic continuous-charge
fallback, ALNS Recovery V2, and bounded one-EV depot reserve. They remain
experimental because measured gains were mixed, negligible or negative.
