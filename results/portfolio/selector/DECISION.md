# Frozen state-aware selector decision

A depth-3 decision tree with minimum leaf size 15 uses nine observable MPC-state features.
Tied best-service labels prefer the frozen SBS, MPC + HGS. No final holdout state was used.

| Grouped validation | States | Planned service | SBS service | Gain | Wins/Ties/Losses |
| --- | ---: | ---: | ---: | ---: | --- |
| Held-out scenario | 396 | 10865 | 10832 | 33 | 17/375/4 |
| Held-out instance | 396 | 10867 | 10832 | 35 | 18/374/4 |

Portfolio deployment: **YES**.
The VBS remains analysis-only; grouped CV determines deployment without tuning the four engines.
