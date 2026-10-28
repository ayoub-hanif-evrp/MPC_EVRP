# Methods and frozen protocol

## Common controller

All five modes use one event-triggered fleet MPC controller, the same Desaulniers MP charging physics, the same fixed offline-reference fleet, the same released-request observations, the same service-first lexicographic objective, and a five-second optimization-decision budget. Only the optimizer differs: Completion, MCTS, ALNS, HGS, or ACS. No optional compiled screen, altered first-action policy, quality policy, or recovery policy is enabled in the replication.

## Independent primary cohort

The previously frozen robustness v3 protocol selected six eligible underlying parents, DoD targets 0.25/0.50/0.75 and seeds 1-5. Each of the 90 scenarios was run once with each original method in an isolated sequential worker. Its protocol, manifest and 450 raw records remain under results/desaulniers/robustness_v3. Frozen source fingerprint: bb593ad57e9b0196ad3712d8c9d873addb5ed156c32ea7857e21471a1fe3f140.

## Prospective CPU replication

The new protocol selected the lexicographically first as-yet-unused published-reference parent in each family, with two each at sizes 25, 50, and 100. DoD 0.50 and seeds 6 and 7 were fixed before worker execution. The six files are c102_21_100, c202_21_50, r102_21_100, r202_21_25, rc102_21_25, rc202_21_50.
Reference and scenario input files are archived byte-for-byte in inputs/. Each method runs sequentially in a separate worker process; alternating method order within paired blocks limits simple order effects. Other pre-existing Python processes remained on the host, so CPU and wall measurements are shared-machine observations, not controlled single-load speed benchmarks. The wall allowance is 8 hours, worker CPU allowance 12 hours, with a per-worker watchdog and persistent checkpoint manifest. No failed worker is silently retried.

Frozen source commit: 7b7b7060c7a22225701f19aa57f54380b9b1c254. Frozen source fingerprint: 451039c10bdbb7e84edf19a761cda0eecaf999218afb5b5d37ac1bf9cee29a71. The protocol and raw manifest bind every scenario, method and result hash.

## Outcomes

Primary endpoints are customer-weighted service and the fraction of scenarios serving all customers. Secondary measures include matched complete-service distance, travel/completion/charging/waiting time, energy charged/consumed, active EVs, workload balance, time-window margin, minimum observed battery, worker wall/CPU time, replans, constructor telemetry, and decision latency. Historical child CPU time was not recorded and is NA, not inferred.

No algorithm was retuned to these prospective scenarios. The archived opt-in enhancement evidence includes service regressions; no enhanced promotion is justified and there is no enhanced-method independent final contrast.
