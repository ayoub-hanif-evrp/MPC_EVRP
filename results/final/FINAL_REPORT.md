# Event-Triggered Risk-Aware Fleet MPC-MCTS: Final Development Report

Frozen development commit: `2b670e435fb2f43539049a341c8329463a2bc4b7`. Source SHA-256: `51d9d72bb1fef24065db805f3b5bf27005b7edfbe81d727291bc830979c1bd22`. Configuration SHA-256: `289353c22239fbd81a66d7ece03b7e69a0c670a7e011378ba3141c3dfc15436a`.

## Validation

Static Fleet service: 600/600 across 6 completed cases. Full pytest: 296 passed. Schneider reference validation: 4/4 passed.

## Matched Development

All 24 prescribed dynamic attempts were launched. Six Fleet attempts ended at
the 15-minute engineering watchdog and have no valid final service result.
`watchdog` below denotes technical failure, not zero customers served.

| Instance | Seed | Fleet | Rolling-LNS | Difference | Fleet calls | Fleet wall s | LNS wall s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| c101_21 | 0 | 92 | 100 | -8 | 139 | 107.84111779998057 | 147.52700150001328 |
| c101_21 | 1 | 99 | 100 | -1 | 148 | 132.8944487000117 | 176.25581449997844 |
| c201_21 | 0 | watchdog | 100 | n/a | n/a | >900 | 229.13 |
| c201_21 | 1 | watchdog | 99 | n/a | n/a | >900 | 442.21 |
| r101_21 | 0 | watchdog | 98 | n/a | n/a | >900 | 152.61 |
| r101_21 | 1 | 93 | 98 | -5 | 181 | 159.07881570002064 | 168.51019130001077 |
| r201_21 | 0 | watchdog | 98 | n/a | n/a | >900 | 606.38 |
| r201_21 | 1 | 62 | 100 | -38 | 136 | 447.8060024000006 | 235.38978599995608 |
| rc101_21 | 0 | 85 | 100 | -15 | 169 | 105.45386739994865 | 104.80062920000637 |
| rc101_21 | 1 | 100 | 100 | 0 | 80 | 65.53347680001752 | 103.1006228000042 |
| rc201_21 | 0 | watchdog | 100 | n/a | n/a | >900 | 229.70 |
| rc201_21 | 1 | watchdog | 99 | n/a | n/a | >900 | 580.95 |

Among the **six completed matched pairs only**, aggregate service was Fleet 531
versus Rolling-LNS 598; wins/ties/losses were 0/1/5. Across all twelve baseline
runs, Rolling-LNS served 1192/1200. A twelve-pair Fleet aggregate is undefined
because six Fleet runs lack completed traces. Two completed Fleet runs also fell
below 90/100 (62 on R2 seed 1 and 85 on RC1 seed 0).

## Gate

- complete_grid: FAIL
- static_600: PASS
- aggregate_service: FAIL
- wins_at_least_losses: FAIL
- minimum_90: FAIL
- no_family_collapse: FAIL
- all_audits: FAIL (six technical failures have no complete trace; all 24 completed traces passed)
- all_events_within_five: PASS
- passed: FAIL

## Runtime and Triggers

- Fleet, six completed dynamic runs: 1075 simulation events, 853 optimization triggers, 853 MCTS calls (0.793 calls/event), 1018.61 total wall seconds, 447.81 maximum instance wall seconds, 4.800 maximum call seconds.
- Rolling-LNS, all twelve completed dynamic runs: 2088 simulation events, 1236 optimization triggers, 3176.57 total wall seconds, 606.38 maximum instance wall seconds, 4.825 maximum call seconds.
- Static Fleet, six completed runs: 813 simulation events, 145 triggers/MCTS calls (0.178 calls/event), 196.13 total wall seconds, 4.799 maximum call seconds.
- Failed Fleet runs: each stopped after more than 900 seconds; their watchdog states recorded 2275 additional MCTS calls (192 to 1114 per run), repeatedly triggered by uncovered released work. Across all dynamic Fleet attempts, at least 3128 calls were made. The failed runs have no complete latency trace and are not represented by the maxima above.

## Evidence

Raw SHA-256 manifest: `control_horizon/summaries/raw_sha256_manifest.json`. Audit, matched service, family, eligible EV/distance, runtime, and trigger CSVs are in `control_horizon/tables/`. `runtime_all_attempts.csv` includes all 24 dynamic attempts and their technical failures. Figures are PNG with source CSVs in `control_horizon/figures/`.

**Conclusion:** The event-triggered execution fix solved the static runtime problem,
but the frozen method failed dynamic service and practical-runtime criteria against
Rolling-LNS. This is a negative development result, not evidence for the proposed
paper performance claim. No holdout was run or inspected.

Technical failures:
- C:\Users\AYOUB\OneDrive - EMSI\Bureau\PHD_WORK\MPC_MCTS_Multi_agents_EVRP\results\final\control_horizon\raw\development\c201_21_FLEET_MPC_MCTS_0a79ff3e0ff7be9e7766.json: ["Engineering watchdog: time=388.2146181935195 loops=315 epochs=315 triggers=311 served=12 committed=4 busy=5 idle=0 mcts_calls=311 last_triggers=['uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work']"]
- C:\Users\AYOUB\OneDrive - EMSI\Bureau\PHD_WORK\MPC_MCTS_Multi_agents_EVRP\results\final\control_horizon\raw\development\c201_21_FLEET_MPC_MCTS_e38197e55d52ca944d8c.json: ["Engineering watchdog: time=1063.4337258732337 loops=281 epochs=281 triggers=250 served=39 committed=3 busy=5 idle=0 mcts_calls=250 last_triggers=['uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work']"]
- C:\Users\AYOUB\OneDrive - EMSI\Bureau\PHD_WORK\MPC_MCTS_Multi_agents_EVRP\results\final\control_horizon\raw\development\r101_21_FLEET_MPC_MCTS_b87e5d9d25f9ac662965.json: ["Engineering watchdog: time=53.42165336062197 loops=1129 epochs=1129 triggers=1114 served=13 committed=18 busy=20 idle=0 mcts_calls=1114 last_triggers=['uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work']"]
- C:\Users\AYOUB\OneDrive - EMSI\Bureau\PHD_WORK\MPC_MCTS_Multi_agents_EVRP\results\final\control_horizon\raw\development\r201_21_FLEET_MPC_MCTS_3f7fc8243802c13b1bad.json: ["Engineering watchdog: time=188.46753368903111 loops=204 epochs=204 triggers=192 served=21 committed=2 busy=4 idle=0 mcts_calls=192 last_triggers=['uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work']"]
- C:\Users\AYOUB\OneDrive - EMSI\Bureau\PHD_WORK\MPC_MCTS_Multi_agents_EVRP\results\final\control_horizon\raw\development\rc201_21_FLEET_MPC_MCTS_e88a6b8d143ba940d0d6.json: ["Engineering watchdog: time=148.05658886176343 loops=195 epochs=195 triggers=194 served=10 committed=4 busy=5 idle=0 mcts_calls=194 last_triggers=['uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work']"]
- C:\Users\AYOUB\OneDrive - EMSI\Bureau\PHD_WORK\MPC_MCTS_Multi_agents_EVRP\results\final\control_horizon\raw\development\rc201_21_FLEET_MPC_MCTS_eb56c0f5cb3a594c5d7d.json: ["Engineering watchdog: time=497.9386487968374 loops=256 epochs=256 triggers=214 served=52 committed=3 busy=5 idle=0 mcts_calls=214 last_triggers=['uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work', 'uncovered_work']"]
