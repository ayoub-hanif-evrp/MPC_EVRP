# Fleet-MCTS static development attempts

Generated from `fleet_mcts_static_manifest.json`. Every JSON run in the static
campaign directory is included; each completed file is independently audited.
No dynamic or holdout cases were run.

| Source prefix | Instance | Status/audit | Served | EVs | Distance | Planning s | p95 s | Max s | Unserved |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `2ffba60318` | c101_21 | completed/pass | 100 | 13 | 1642.15 | 6.00 | 0.05 | 3.74 | - |
| `d1d348a4c0` | c101_21 | completed/pass | 99 | 13 | 1572.67 | 15.05 | 0.31 | 3.20 | C82 |
| `e34054ef30` | c101_21 | completed/pass | 100 | 13 | 1626.65 | 14.85 | 0.26 | 3.49 | - |
| `d1d348a4c0` | c201_21 | completed/pass | 100 | 5 | 1065.57 | 34.35 | 0.49 | 4.95 | - |
| `d1d348a4c0` | r101_21 | completed/pass | 100 | 20 | 1980.57 | 4.44 | 0.06 | 1.53 | - |
| `d1d348a4c0` | r201_21 | completed/pass | 100 | 4 | 1765.98 | 156.11 | 4.95 | 4.96 | - |
| `d1d348a4c0` | rc101_21 | completed/pass | 99 | 21 | 2460.41 | 15.80 | 0.27 | 1.88 | C27 |
| `2ffba60318` | rc101_21 | completed/pass | 99 | 21 | 2462.39 | 22.16 | 0.38 | 1.82 | C27 |
| `d1d348a4c0` | rc201_21 | completed/pass | 100 | 5 | 2691.92 | 83.85 | 4.95 | 4.96 | - |

Static six-instance gate: FAIL; no single source/configuration serves 100/100 on all six.
