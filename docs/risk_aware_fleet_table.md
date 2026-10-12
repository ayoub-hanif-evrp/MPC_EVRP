# Risk-aware Fleet MPC-MCTS development

Generated from `risk_aware_fleet_manifest.json`; all listed raw records are
SHA-256 bound and independently trace-audited. Earlier attempts are retained
in the manifest. No holdout run was made.

| Stage | Instance | Seed | Algorithm | Served | EVs | Distance | Planning s | p95 s | Max s | Audit |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| static | c101_21 | 0 | FLEET_MPC_MCTS | 100 | 13 | 1449.38 | 32.64 | 0.65 | 4.95 | pass |
| static | c201_21 | 0 | FLEET_MPC_MCTS | 100 | 5 | 1147.32 | 89.31 | 0.87 | 4.95 | pass |
| static | r101_21 | 0 | FLEET_MPC_MCTS | 100 | 20 | 1919.86 | 16.94 | 0.33 | 2.39 | pass |
| static | r201_21 | 0 | FLEET_MPC_MCTS | 100 | 4 | 1762.68 | 135.45 | 4.95 | 4.95 | pass |
| static | rc101_21 | 0 | FLEET_MPC_MCTS | 100 | 21 | 2472.91 | 21.80 | 0.47 | 2.20 | pass |
| static | rc201_21 | 0 | FLEET_MPC_MCTS | 100 | 5 | 2139.52 | 128.80 | 4.95 | 4.96 | pass |
| DoD 0.5 | c101_21 | 0 | FLEET_MPC_MCTS | 98 | 13 | 1446.57 | 47.73 | 0.74 | 1.45 | pass |
| DoD 0.5 | c101_21 | 1 | FLEET_MPC_MCTS | 100 | 13 | 1323.53 | 36.73 | 0.48 | 1.42 | pass |
| DoD 0.5 | c101_21 | 0 | ROLLING_LNS | 100 | 13 | 1256.44 | 174.62 | 2.41 | 4.95 | pass |
| DoD 0.5 | c101_21 | 1 | ROLLING_LNS | 99 | 13 | 1401.42 | 203.81 | 2.40 | 4.95 | pass |
| DoD 0.5 | r101_21 | 1 | FLEET_MPC_MCTS | 94 | 20 | 2003.66 | 45.50 | 0.52 | 0.85 | pass |
| DoD 0.5 | r101_21 | 0 | FLEET_MPC_MCTS | 81 | 20 | 1812.26 | 24.52 | 0.24 | 0.94 | pass |
| DoD 0.5 | r101_21 | 1 | ROLLING_LNS | 97 | 20 | 1754.54 | 172.54 | 2.21 | 2.70 | pass |
| DoD 0.5 | r101_21 | 0 | ROLLING_LNS | 100 | 20 | 1778.89 | 107.02 | 1.25 | 1.92 | pass |

Static gate: PASS (600/600).
Dynamic gate: FAIL; 4/12 pairs run; Fleet 373 versus Rolling-LNS 396 customers served, 1 service wins and 3 losses.
