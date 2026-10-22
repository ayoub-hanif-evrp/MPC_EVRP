# Engineering pilot

Protocol: `71566312c803ed14e7dbd31bb0a1949523cd47ec0df938ae31c4b290ed375759`; audited raw runs: 5/5; predeclared ineligible scenarios: 0; status: complete.

All existing raw files passed SHA-256, identity, five-second budget, and independent trace replay checks.

Engineering validation only: one development scenario is not a generalizable optimizer comparison. Offline reference coverage validation shared the machine during this pilot, so worker times are engineering observations, not isolated runtime comparisons.

| Method | Served | Complete | Worker s |
| --- | --- | --- | --- |
| MPC_COMPLETION | 25 | True | 2.0 |
| MPC_MCTS | 25 | True | 27.9 |
| MPC_ALNS | 25 | True | 25.2 |
| MPC_HGS | 25 | True | 28.5 |
| MPC_ACS | 25 | True | 22.1 |
