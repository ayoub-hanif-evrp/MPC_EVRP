# Paper Results Status

All tables are generated from audited raw records.
MPC and MCTS source remains frozen; Rolling-LNS remains historical/supplementary.

## Paired Service

- development:MCTS-minus-FLEET_MPC_COMPLETION_ONLY: n=12, mean=4.000, W/T/L=11/1/0, bootstrap 95% CI=(2.75, 5.166666666666667).
- development:MCTS-minus-RH_REGRET: n=12, mean=32.750, W/T/L=11/1/0, bootstrap 95% CI=(18.416666666666668, 47.33541666666664).
- holdout:MCTS-minus-FLEET_MPC_COMPLETION_ONLY: n=54, mean=2.833, W/T/L=34/16/4, bootstrap 95% CI=(1.5555555555555556, 4.037037037037037).
- holdout:MCTS-minus-RH_REGRET: n=54, mean=74.537, W/T/L=53/0/1, bootstrap 95% CI=(65.57407407407408, 82.70416666666667).

## Holdout Service

- FLEET_MPC_MCTS: 5295/5400 served; 34/54 complete.
- FLEET_MPC_COMPLETION_ONLY: 5142/5400 served; 7/54 complete.
- RH_REGRET: 1270/5400 served; 0/54 complete.
- MPC-MCTS run-level mean decision latency: 2.189s; largest recorded decision latency: 4.831s. Concurrent-family timings are not isolated-machine measurements.
- MCTS: 5792 calls, 182 service-improving, 42 EV-improving, 613 distance-improving, 1197 objective-improving.

## External Context

RoutingBlocks raw attempts: 180. Static quality columns require independent replay; strict budget success is reported separately. Nominal external budgets are not actual elapsed times. pyevrp 0.2.1 is excluded by the exact-physics gate.
The 5-second external whole-run budget is not equal to a five-second per-decision controller budget.
- RoutingBlocks nominal 5s: 41/60 replay-valid complete routes; 0 also met the strict elapsed-time cutoff.
- RoutingBlocks nominal 30s: 55/60 replay-valid complete routes; 0 also met the strict elapsed-time cutoff.
- RoutingBlocks nominal 300s: 59/60 replay-valid complete routes; 0 also met the strict elapsed-time cutoff.

The static external solver often uses fewer EVs and less distance. These are offline solution-quality results, not evidence that the online controller dominates ALNS. The four small reference checks pass, but the published charging model is not proven identical, so no optimality gap is claimed.

## Artifacts

Tables: `results/paper/tables/`; PNG figures: `results/paper/figures/`.
Figures generated: paired_service_scatter, per_instance_service_difference, complete_service_rate, decision_latency_distribution, mcts_root_to_final_gain, static_evs_distance, static_performance_profile.
