# Fleet-Coordinated MPC-MCTS Development (2026-10-12)

**Status: static gate failed. No dynamic comparison or holdout was run.**

The new `FLEET_MPC_MCTS` algorithm searches complete fleet plans inside each
event-driven MPC decision. Its tree state contains released-customer sequences
for the fixed `K_ref` vehicles. Branches use bounded insert, rescue/ejection,
relocate, swap, and full-coverage route-compaction macro-actions. The existing
charging decoder maps sequences to replayed EV-feasible routes. A bounded
regret-2 construction supplies a feasible incumbent and rollout estimate;
there is **no LNS after MCTS**. Only the first physical actions are executed.
Busy actions are immutable, previous suffixes are soft incumbents, and online
planning sees only the current observation. `ROLLING_LNS` remains a separate
baseline and accepts the same total planning deadline.

The development configuration is [fleet_mcts.yaml](../configs/fleet_mcts.yaml):
64 iterations, depth 4, at most 12 macro-actions per expansion, three candidate
insertion positions, and a five-second total planning budget per event. The
cooperative deadline starts before incumbent construction and search, is checked
inside expensive insertion/decoder loops, and reserves a small final-validation
margin. Actual event latencies and overruns are recorded. It is not a hard
real-time guarantee.

## Static Gate

All nine static attempt files are preserved in the
[manifest](fleet_mcts_static_manifest.json), including failed-service runs.
The [table](fleet_mcts_static_table.md) is generated from that manifest.
`python -m scripts.fleet_mcts_evidence --verify` checks each file's SHA-256,
identity/config/source/scenario metadata, and reruns the independent disk-record
trace auditor; it does not trust the stored audit flags.

The first complete six-instance source (`d1d348a4c0...`) served **598/600**:
four instances reached 100/100, while `c101_21` missed `C82` and `rc101_21`
missed `C27`. All six passed physical and information audits. The longest
recorded planning event was 4.96 seconds; the highest per-instance p95 was
4.95 seconds, and total planning time across the six runs was 309.59 seconds.
The tree itself recorded improvements, but these did not close
the two service gaps.

One targeted correction changed candidate vehicle ranking to use planned-route
geometry and allowed two-customer ejection. Under the new source
(`2ffba60318...`), `c101_21` reached 100/100 but `rc101_21` still missed
`C27` at 99/100. The other four were not rerun under that source, because the
static gate already failed. An earlier one-instance prototype is also retained
in the manifest. These attempts must **not** be combined into a fictitious
six-instance pass.

## Development Decision

The required static condition, 100/100 on all six under one frozen method,
was not met. Therefore the DoD 0.5 scenario-seed 0/1 matched comparison of
`ROLLING_LNS` versus `FLEET_MPC_MCTS` was **not run**. Dynamic wins/ties/losses,
aggregate dynamic unserved requests, and comparative latency are not available.
No holdout instance was inspected or executed. This method is not ready for a
paper-performance or MCTS-superiority claim.

The full local test suite passed (**280 tests**), with JUnit evidence in
`results/verification/pytest.xml`. All four Schneider C5 reference validations
passed; the current CSV is in `results/fleet_mcts_validation/`. No PDF figures
were generated. The remaining problem is solution quality on tight clustered
static cases, not a trace-audit or measured deadline failure.
