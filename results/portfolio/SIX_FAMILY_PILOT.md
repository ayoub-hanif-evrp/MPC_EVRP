# Historical Non-Isolated Six-Family Pilot

This file preserves the earlier four-method pilot, including its original
labels and measurements, for reproducibility. It is **not** the active
five-method isolated pilot. The current pilot is summarized in `README.md`;
its audited raw records and manifest are under `development/`.

This is a **development pilot**, not the 66-scenario development study or a
new final holdout. It uses one already-inspected DoD 0.5, seed-0 scenario from
each C1/C2/R1/R2/RC1/RC2 family. The four methods share the five-second MPC
decision limit and a common scenario within each family. The current
`development/historical_nonisolated_manifest.json` preserves all 24 original
records and their raw SHA-256 hashes.
The recursive optimizer-source fingerprint is
`f133ce3431c8df75fb0318242cc133955080fbb19538cfc09338a5ec15fce110`.

## Primary Service Result

| Instance | Completion | MCTS V1 | ALNS | HGS |
| --- | ---: | ---: | ---: | ---: |
| c101_21 | 92 | 99 | 100 | 99 |
| c201_21 | 93 | 100 | 100 | 98 |
| r101_21 | 92 | 97 | 99 | 99 |
| r201_21 | 99 | 98 | 100 | 100 |
| rc101_21 | 89 | 96 | 100 | 100 |
| rc201_21 | 99 | 100 | 100 | 99 |
| **Total / 600** | **564** | **590** | **599** | **595** |

Pairwise service wins/ties/losses over the six **trajectories**:

| First method vs second | Win | Tie | Loss |
| --- | ---: | ---: | ---: |
| MCTS V1 vs ALNS | 0 | 2 | 4 |
| MCTS V1 vs HGS | 2 | 1 | 3 |
| ALNS vs HGS | 3 | 3 | 0 |

ALNS was never worse in service in this small pilot. This does **not** show a
service-complementarity gap or justify an optimizer selector. Equal-service
secondary differences exist: on C2, MCTS and ALNS both served 100 with five
EVs, and MCTS traveled 1261.52 versus ALNS's 1309.55. On RC1, ALNS and HGS
both served 100, but ALNS used 20 EVs versus HGS's 21. Distance is not ranked
across unequal-service or unequal-EV outcomes.

## Mechanism And Runtime

The corrected HGS produced a final route with greater released-customer
coverage than its constructor root at 36 of its 631 optimization calls across
the pilot. Its diagnostics recorded 278 exact-feasible offspring recovery
insertions and zero direct root insertions. These are search-event counts, not
independent trajectory wins or proof that every insertion was later executed.
All 24 raw records include optimizer-specific diagnostics. All 24 runs passed
physical replay and information-boundary audits before being saved. The
largest recorded maximum decision latency was 4.841 seconds, below the
five-second limit; these measurements were taken with methods run sequentially.

The initial one-case pilot at source `6cdba9bf63b419e47cb0498f244de15cc211d3f3907e995234439b7c103cb081`
remains as historical compressed development evidence. Its records are not
mixed into the current-source manifest.

**Next gate:** the other 60 development scenarios and independent common-state
shadow snapshots are still needed for complementarity and SBS/VBS analysis.
No selector, new final holdout or portfolio result exists yet.
