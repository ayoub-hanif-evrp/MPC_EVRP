# Common event-triggered MPC architecture

| Method | MPC controller | Search engine | Common constructor | Released-only information | Exact EV decoder | Decision budget |
| --- | --- | --- | --- | --- | --- | --- |
| MPC + Completion | Event-triggered | None | Yes | Yes; audited | Yes; audited | 5 s |
| MPC + MCTS | Event-triggered | MCTS | Yes | Yes; audited | Yes; audited | 5 s |
| MPC + ALNS | Event-triggered | ALNS | Yes | Yes; audited | Yes; audited | 5 s |
| MPC + HGS | Event-triggered | HGS | Yes | Yes; audited | Yes; audited | 5 s |
| MPC + ACS | Event-triggered | ACS | Yes | Yes; audited | Yes; audited | 5 s |
| MPC + Portfolio | Event-triggered | State-aware selector | Yes | Yes; audited | Yes; audited | 5 s |

All rows use the frozen common controller and the same 100-customer final scenarios.
