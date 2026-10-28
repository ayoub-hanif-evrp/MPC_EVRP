# Two-worker CPU throughput probe

Technical shared-machine observation only. Both modes used the original methods and the same fixed released-request scenarios, fleet, physics, objective and five-second MPC decision limit. Background host load was not controlled; these timings are not paper comparisons.

Sequential elapsed: 62.57 s; two-worker elapsed: 41.75 s; throughput ratio: 1.50x. Identical served counts: True.

| Mode | Instance | Method | Served | Worker CPU s | Peak observed working set MiB |
| --- | --- | --- | ---: | ---: | ---: |
| sequential | c101_21_25 | MPC_MCTS | 25 | 12.72 | 133.4 |
| sequential | r201_21_25 | MPC_HGS | 25 | 47.78 | 141.5 |
| two_workers | c101_21_25 | MPC_MCTS | 25 | 10.55 | 132.6 |
| two_workers | r201_21_25 | MPC_HGS | 25 | 40.39 | 141.5 |

Two workers are a supported technical option, but concurrent deadline-sensitive optimization must be evaluated as a separate execution methodology. The sequential original-method paper timings are not replaced by this probe.
