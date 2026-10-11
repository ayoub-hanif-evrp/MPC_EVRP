# Fleet-LNS development gate (2026-10-11)

This is a **single-seed development comparison**, not final or holdout evidence.
The source fingerprint for every run below is
`f37b8ac6e7c332a5784a845ebad1870c7b87c1d8d608c601c68e67155485d6b7`.
Raw records are in `results/fleet_lns_static/runs/` and
`results/fleet_lns_development/runs/`. Each dynamic pair uses the same instance,
DoD 0.5, scenario seed 0, algorithm seed 0, and scenario hash. All listed runs
completed and passed the recorded no-future-information, safe-return,
trace-replay, and unique-service audits.

## Experimental method

`ROLLING_ALNS` starts from the rolling-horizon/regret fleet plan.
`MPC_MCTS_ALNS` also constructs short local MCTS proposals (12 iterations,
top-L 3) and selects the lexicographically best initial fleet plan before the
same fleet search. Both use fixed `K_ref`, horizon 5, partial charging, 100
fleet-LNS iterations or a cooperative 1.5-second limit per event, and a 10%
destroy fraction. The fleet search can remove and reassign released customers
across EVs using rescue, random, worst, and related removal followed by
regret-2/3 repair. Customer sequences are decoded with at most one charging
station between consecutive services and exact route replay. Executing actions
remain immutable. This is a minimal fleet LNS; relocate, swap, 2-opt*, and
route-pool MILP are **not** implemented in this study.

## Static prerequisite

All six known-demand runs used `ROLLING_ALNS` and served 100/100 customers.
The vehicle counts were within the reference fleet limits. Times are total
online planning CPU wall time in seconds; they are not isolated real-time
latency guarantees.

| Instance | Served | EVs | Distance | Planning s | Max event s |
| --- | ---: | ---: | ---: | ---: | ---: |
| c101_21 | 100 | 12 | 1184.56 | 97.38 | 9.82 |
| c201_21 | 100 | 5 | 726.62 | 392.11 | 231.67 |
| r101_21 | 100 | 20 | 1744.03 | 62.66 | 4.32 |
| r201_21 | 100 | 4 | 1607.36 | 777.71 | 413.40 |
| rc101_21 | 100 | 19 | 1864.29 | 78.95 | 5.72 |
| rc201_21 | 100 | 5 | 1706.96 | 414.87 | 227.23 |

## Matched dynamic development

Each cell is `served / EVs / distance / total planning seconds`. Compare
distance only after service and EV count are tied. These are individual
deterministic scenarios, not confidence intervals.

| Instance | Rolling ALNS | MPC-MCTS-ALNS | Lexicographic winner |
| --- | --- | --- | --- |
| c101_21 | 100 / 13 / 1264.13 / 140.06 | 100 / 13 / 1227.53 / 146.60 | Hybrid: distance |
| c201_21 | 100 / 5 / 804.62 / 277.28 | 99 / 5 / 757.62 / 389.32 | Rolling: service |
| r101_21 | 100 / 20 / 1778.89 / 102.05 | 100 / 20 / 1784.12 / 109.59 | Rolling: distance |
| r201_21 | 100 / 4 / 1800.78 / 429.41 | 100 / 4 / 1536.71 / 766.08 | Hybrid: distance |
| rc101_21 | 99 / 21 / 1984.75 / 139.36 | 100 / 21 / 2054.64 / 144.39 | Hybrid: service |
| rc201_21 | 100 / 5 / 1996.14 / 342.78 | 98 / 5 / 1584.97 / 465.22 | Rolling: service |

The hybrid wins three pairs and loses three. Its sole one-customer service
gain is outweighed by service losses of one and two customers elsewhere;
aggregate service is 599/600 for rolling and 597/600 for the hybrid. Hybrid
planning time is higher in all six pairs. In particular, its shorter routes
on `c201_21` and `rc201_21` do **not** compensate for lost service.

**Gate: do not launch the holdout.** The six cases do not establish a
meaningful service advantage or a majority matched-case advantage for MCTS
over fleet ALNS. This result does support fleet-wide repair as a viable
static constructor, but does not support claiming that MCTS improves it.
The unrun holdout remains untouched. The current 1.5-second LNS limit is
cooperative and excludes initial constructive repair; worst event times above
show that this implementation is not yet suitable for strict real-time claims.

## Verification and scope

The full local suite passed (`259 passed`), and all four Schneider C5
reference validations passed. Restricted charging-decoder regression tests
also replay the six static reference route sequences offline. No PDF figures
were produced. Further work should first address worst-case constructive
repair latency and evaluate multiple development seeds before reconsidering
the MCTS hybrid or opening a held-out comparison.
