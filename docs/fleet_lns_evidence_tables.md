# Fleet-LNS evidence tables

Generated from `fleet_lns_evidence_manifest.json` by `scripts/fleet_lns_evidence.py`.
The ALNS algorithm IDs are historical labels; these methods use non-adaptive LNS.

## Static

| Instance | Served | EVs | Distance | Planning s | Max event s |
| --- | ---: | ---: | ---: | ---: | ---: |
| c101_21 | 100 | 12 | 1184.56 | 97.38 | 9.82 |
| c201_21 | 100 | 5 | 726.62 | 392.11 | 231.67 |
| r101_21 | 100 | 20 | 1744.03 | 62.66 | 4.32 |
| r201_21 | 100 | 4 | 1607.36 | 777.71 | 413.40 |
| rc101_21 | 100 | 19 | 1864.29 | 78.95 | 5.72 |
| rc201_21 | 100 | 5 | 1706.96 | 414.87 | 227.23 |

## Hybrid static check (partial)

The first three `MPC_MCTS_LNS` static runs completed. `r201_21` was interrupted
after a 30-minute wall-time cutoff; `rc101_21` and `rc201_21` were not started.
This is not a six-instance pass.

| Instance | Served | EVs | Distance | Planning s | Max event s |
| --- | ---: | ---: | ---: | ---: | ---: |
| c101_21 | 100 | 12 | 1154.03 | 109.06 | 15.65 |
| c201_21 | 100 | 5 | 691.49 | 780.25 | 407.21 |
| r101_21 | 100 | 20 | 1704.44 | 67.65 | 6.56 |

## Matched dynamic development (DoD 0.5, seeds 0)

Each cell is `served / EVs / distance / total planning seconds`.

| Instance | Rolling LNS | MPC-MCTS-LNS | Lexicographic winner |
| --- | --- | --- | --- |
| c101_21 | 100 / 13 / 1264.13 / 140.06 | 100 / 13 / 1227.53 / 146.60 | Hybrid: distance |
| c201_21 | 100 / 5 / 804.62 / 277.28 | 99 / 5 / 757.62 / 389.32 | Rolling: service |
| r101_21 | 100 / 20 / 1778.89 / 102.05 | 100 / 20 / 1784.12 / 109.59 | Rolling: distance |
| r201_21 | 100 / 4 / 1800.78 / 429.41 | 100 / 4 / 1536.71 / 766.08 | Hybrid: distance |
| rc101_21 | 99 / 21 / 1984.75 / 139.36 | 100 / 21 / 2054.64 / 144.39 | Hybrid: service |
| rc201_21 | 100 / 5 / 1996.14 / 342.78 | 98 / 5 / 1584.97 / 465.22 | Rolling: service |

Total service: Rolling LNS 599/600; MPC-MCTS-LNS 597/600.
