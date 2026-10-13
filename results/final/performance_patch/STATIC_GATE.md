# Final Performance Patch: Static Gate

Source SHA-256: `4cdead8ab9956362ba9921c0818b7bcc9690487ab11ba001d087abebe43176b6`.

The event-trigger policy, `J_A`/`J_B`, `K_ref`, charging physics, information
boundary, depth 4, branch limit 24, 256-iteration ceiling, and five-second
trigger budget are unchanged. The patch uses a cached parallel insertion root,
all-EV screening with selective exact decoding, a direct rollout, and the
bounded `EJECTION_CHAIN_2` tree action. No post-MCTS LNS is used.

## Targeted First Epoch

| Instance | Released | Constructor | Constructor ms | Screened insertions | Exact decodes | Zero-option after constructor | MCTS service improvements | Chains generated / feasible / selected | Final root | Final served |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| c201_21 | 100 | 89 | 1858.90 | 47139 | 96 | 0 | 6 | 0 / 0 / 0 | 100 | 100 |
| c101_21 | 100 | 97 | 2001.98 | 22624 | 125 | 0 | 1 | 5 / 1 / 1 | 98 | 100 |

Both targeted traces passed independent audit. C101's remaining first-epoch
work was served after later event-triggered replanning; the first root itself
did not claim complete coverage.

## Six-Static Gate

| Instance | Served | EVs | Distance | Wall s | p95 / max trigger s | Audit |
|---|---:|---:|---:|---:|---:|---|
| c101_21 | 100/100 | 13 | 1675.78 | 6.89 | 0.165 / 2.071 | PASS |
| c201_21 | 100/100 | 5 | 1011.99 | 7.09 | 3.078 / 4.613 | PASS |
| r101_21 | 100/100 | 20 | 2103.74 | 5.95 | 0.527 / 3.832 | PASS |
| r201_21 | 100/100 | 4 | 1829.60 | 33.57 | 4.750 / 4.750 | PASS |
| rc101_21 | 100/100 | 20 | 2418.76 | 7.36 | 0.370 / 4.608 | PASS |
| rc201_21 | 100/100 | 5 | 2777.78 | 28.61 | 4.685 / 4.719 | PASS |

**Gate: 600/600 served, all six audits passed, all optimization calls < 5 s.**
Distances are best-found outcomes of this run, not optimality claims or
published-value comparisons. Development and holdout are not represented here.

Full pytest: **307 passed**. Schneider small-case reference validation:
**4/4 passed**. The raw records are in `raw/targeted/` and `raw/static/`;
only current-source records belong to this gate. No PDF figures were made.
