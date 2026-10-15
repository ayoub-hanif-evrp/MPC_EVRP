# Complementarity gate: not yet evaluated

The current development manifest contains **one** paired scenario out of the
preregistered 66 inspected development scenarios. This is a feasibility pilot,
not a valid win matrix, SBS/VBS estimate, selector training set or inference
about optimizer complementarity.

| C101, DoD 0.5, seed 0 | Served | EVs | Distance | Max decision (s) |
| --- | ---: | ---: | ---: | ---: |
| MPC_COMPLETION | 92/100 | 13 | 1815.59 | 0.149 |
| MPC_MCTS_V1 | 99/100 | 13 | 1477.77 | 4.502 |
| MPC_ALNS | 100/100 | 13 | 1756.59 | 4.654 |
| MPC_HGS | 95/100 | 13 | 1832.40 | 4.658 |

The row with 100 served wins this single pilot on the primary metric.
Distances across unequal-service rows are **not** a quality comparison.
All four raw records and their SHA-256 digests are in
`development/manifest.json`. A complementarity matrix and SBS/VBS analysis
require the remaining paired scenarios and independent shadow snapshots.
No portfolio selector or new final holdout has been run.
