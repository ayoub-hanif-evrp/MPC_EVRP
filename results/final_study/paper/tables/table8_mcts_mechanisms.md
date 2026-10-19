# MCTS mechanism diagnostics on final holdout

| Metric | Total |
| --- | --- |
| MCTS calls | 4922 |
| Iterations | 1030391 |
| Nodes Expanded | 142087 |
| Service Improvements | 218 |
| Objective Only Improvements | 3202 |
| Service Gain Over Constructor | 348 |
| Exact Decoded Options | 931056 |
| Ejection Chains Generated | 16519 |
| Ejection Chains Selected | 399 |
| KEEP_CONSTRUCTOR selections | 4528 |
| Alternative-root-control selections | 394 |
| Critical Regret rollout usage | 342724 |
| Earliest Deadline rollout usage | 343150 |
| Reserve Preserving rollout usage | 344517 |
| Critical Regret rollout improvements | 1171 |
| Earliest Deadline rollout improvements | 1114 |
| Reserve Preserving rollout improvements | 1135 |

Counts are summed over instrumented MCTS optimizer calls. Policy-specific rollout improvements include service and objective-only gains; the frozen trace does not split these by policy. Service gain is over the common constructor.
