# Terminal-Completion Paper Track: Failed Static Gate

This is a stopped implementation/diagnostic campaign, not a frozen scientific
development result. No dynamic matched pairs or holdout runs were made.

## Correction and provenance

The independent `uncovered_work` optimization trigger was removed for both
Fleet MPC-MCTS and Rolling-LNS. Optimization now triggers initially, on a new
release, invalid retained suffix, ready EV without continuation, or a customer
service completion with released uncovered work. Valid charge/wait continuations
replay without global optimization. Fleet MCTS now builds two bounded
residual-completion roots from the retained soft plan (criticality and due
order), and completes expanded service-phase tree children before scoring and
backpropagation. The tree still chooses structural fleet actions. The current
lexicographic objectives, bounded tree reward, EV physics, K_ref, depth 4,
branch 24, and 256-iteration ceiling were not changed. No LNS follows MCTS.

Evaluation/scenario objective version: `service-activation-distance-v2`.
Planner objective version: `risk-control-flex-service-v1`.
Search policy version: `fleet-mcts-terminal-completion-v1`.
The five records share source SHA-256
`b16fb07badf111f00dfbc70fe2c4818db8c8a85c86dfac26b62a81e8b2a0149c`.
Their recorded base commit is `e89cd34fde6dc68a725e1fa3ed9d1141c2c17636`;
the corrected source was **not frozen or committed**, because the static gate
failed. Raw-record paths, scenario hashes, and SHA-256 values are in
[`docs/terminal_completion_manifest.json`](../../../docs/terminal_completion_manifest.json).

## Three required diagnostics

All three completed, independently audited, and stayed below the five-second
optimization ceiling. `R101` still had significant uncovered work; its maximum
rollout residual was 17, so near-terminal behavior is not established there.
Counts below aggregate root/rollout statistics over all MCTS calls in each run.

| Instance | Seed | Served/released | MCTS calls | Trigger reasons (initial/release/service/no continuation) | Root uncovered -> completed root -> final | Service gain over root | Simulations | Mean customers completed/rollout | Max rollout residual | Wall s | p95/max call s |
|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| r101_21 | 0 | 85/100 | 137 | 1/51/78/24 | 1733 -> 1678 -> 1648 | 30 | 35072 | 0.0022 | 17 | 73.55 | 0.965/1.280 |
| c201_21 | 0 | 100/100 | 63 | 1/51/0/12 | 100 -> 0 -> 0 | 0 | 4513 | 0 | 0 | 240.38 | 4.750/4.814 |
| r201_21 | 1 | 99/100 | 150 | 1/51/99/1 | 284 -> 185 -> 185 | 0 | 14565 | 0 | 1 | 532.83 | 4.752/4.858 |

Trigger-reason counts can overlap at one call. Root and final uncovered values
are sums over calls, not final unserved customers. There were no watchdog
failures and no standalone `uncovered_work` triggers.

## Static regression and stop

| Instance | Served | Audit | Wall s | Maximum optimization call s |
|---|---:|---|---:|---:|
| c101_21 | 96/100 | PASS | 50.55 | 4.606 |
| c201_21 | 100/100 | PASS | 20.00 | 4.750 |

The first case made 600/600 impossible. The static runner was stopped after
two records, before four remaining cases. Static gate: **FAIL**. The full
12-pair dynamic development grid, Fleet-vs-Rolling-LNS W/T/L, family totals,
and holdout are **not available** and must not be inferred from historical
campaigns. This correction does not support a positive final paper claim.

Full pytest passed **298/298** when run outside the Windows sandbox so pytest
temporary directories and process named pipes were accessible. Schneider
reference validation passed **4/4**. The earlier sandboxed pytest attempts
failed on environment permissions, not assertions. No PDF figures were made.
