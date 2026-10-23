# Desaulniers MP reference coverage

Every format-1 file is paired with and checked against all format-2 arcs. Published full-charge routes are replayed under MP. Constructed references are offline preprocessing, not online MPC runs.

Fallback uses the unchanged offline `ReferenceConfig` defaults (3 multistarts, 1 improvement pass, seed 0, 24 labels) in an isolated process with a 120-second per-instance limit. Validation time includes parsing and replay overhead.

Dataset fingerprint: `02011e3273fef190bd61cc223b4504d8265ca5be30ccf02a34f674f27d58741e` (matches corrected final protocol).

Inspected: 168/168; parsed/arcs consistent: 168; published MP references: 120; constructed/cached: 24; unresolved: 24.

A search failure or timeout is not proof of infeasibility. Full per-instance evidence and reasons are in `coverage.csv`.

`available_solutions` lists SF/MF/SP/MP files; only physically replayed SF/MF routes are used to define offline reference fleets. SP/MP route-order witnesses are reported separately and never substituted into the frozen final or robustness reference policy. `arcs_consistent` validates every cost, travel-time, and energy arc against the coordinate source. The information-model check records complete reference predecessor-departure bounds; online no-future-leakage is separately tested and audited in experiment traces.

| Size | Instances | SF/MF MP references | Fallback validated | Unresolved |
| ---: | ---: | ---: | ---: | ---: |
| 25 | 56 | 56 | 0 | 0 |
| 50 | 56 | 48 | 2 | 6 |
| 100 | 56 | 16 | 22 | 18 |

Published SP/MP route-order witnesses on instances lacking SF/MF: 13 distinct instances. See `PARTIAL_SOLUTIONS.md` for the LP-witness limitation.
Of the unresolved reference cases, 6 already have a physically witnessable published partial route order; their unresolved status is a limitation of the frozen reference path, not evidence of MP infeasibility.

- c202_21_100: timeout; Reference search exceeded 120s
- c203_21_100: timeout; Reference search exceeded 120s
- c204_21_100: timeout; Reference search exceeded 120s
- c207_21_100: timeout; Reference search exceeded 120s
- r202_21_100: timeout; Reference search exceeded 120s
- r203_21_100: timeout; Reference search exceeded 120s
- r204_21_100: timeout; Reference search exceeded 120s
- r204_21_50: timeout; Reference search exceeded 120s
- r205_21_100: timeout; Reference search exceeded 120s
- r206_21_100: timeout; Reference search exceeded 120s
- r206_21_50: timeout; Reference search exceeded 120s
- r207_21_100: timeout; Reference search exceeded 120s
- r207_21_50: timeout; Reference search exceeded 120s
- r208_21_100: timeout; Reference search exceeded 120s
- r208_21_50: timeout; Reference search exceeded 120s
- r209_21_100: timeout; Reference search exceeded 120s
- r209_21_50: timeout; Reference search exceeded 120s
- r210_21_100: timeout; Reference search exceeded 120s
- r210_21_50: timeout; Reference search exceeded 120s
- rc202_21_100: timeout; Reference search exceeded 120s
- rc203_21_100: timeout; Reference search exceeded 120s
- rc204_21_100: timeout; Reference search exceeded 120s
- rc206_21_100: timeout; Reference search exceeded 120s
- rc207_21_100: timeout; Reference search exceeded 120s
