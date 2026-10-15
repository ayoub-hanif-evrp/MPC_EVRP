# MPC Optimizer Study Status

The current five methods are `MPC_COMPLETION`, `MPC_MCTS`, `MPC_ALNS`,
`MPC_HGS` and `MPC_ACS`. They use the same event-triggered MPC controller,
constructor, observable information, EV decoder and five-second decision
budget. Each campaign simulation runs in a fresh Python interpreter. The
active MCTS is a single method; the old paper tag and raw records remain
unchanged as historical evidence.

## Historical Development Pilot

The pre-final-MCTS isolated six-family pilot contains 30 audited simulations (one inspected
DoD 0.50, seed-0 scenario per family). Aggregate customers served out of 600:

| Method | Served | Complete scenarios | Maximum decision latency (s) |
| --- | ---: | ---: | ---: |
| Completion | 564 | 0/6 | 1.786 |
| MCTS | 592 | 3/6 | 4.789 |
| ALNS | 599 | 5/6 | 4.797 |
| HGS | 596 | 4/6 | 4.804 |
| ACS | 591 | 3/6 | 4.803 |

This is historical development evidence only. These six cases are part of the inspected
66-scenario grid, not a holdout. The earlier non-isolated pilot manifest is
preserved as `development/historical_nonisolated_manifest.json`; its raw
records were not modified. The 38-run stopped extension is preserved in
`development/historical_pre_mcts_final_manifest.json`; its raw files were
not modified. `development/analysis/` contains explicitly incomplete
pre-final-MCTS paired outputs and PNG figures until final-source analysis
replaces them.

## Gates

1. Complete all 330 isolated development runs and validate raw hashes,
   scenario pairing, audits and latency bounds.
2. Capture and freeze observable snapshots before running shadow optimizers.
3. Compute SBS and analysis-only VBS. Add a portfolio only if the
   preregistered complementarity gate passes.
4. Freeze methods and any justified selector, then preregister and commit a
   new unused-instance final holdout before running it.

No final holdout results or portfolio claims exist yet.
