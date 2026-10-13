# Paper Results Status

All tables are generated from audited raw records.
MPC and MCTS source remains frozen; Rolling-LNS remains historical/supplementary.

## Paired Service

- development:MCTS-minus-FLEET_MPC_COMPLETION_ONLY: n=12, mean=4.000, W/T/L=11/1/0, bootstrap 95% CI=(2.75, 5.166666666666667).
- development:MCTS-minus-RH_REGRET: n=12, mean=32.750, W/T/L=11/1/0, bootstrap 95% CI=(18.416666666666668, 47.33541666666664).
- Holdout not executed; no holdout inference is made.

## External Context

RoutingBlocks raw attempts: 0. Only budget-respecting, independently replayed complete routes enter static quality statistics. pyevrp 0.2.1 is excluded by the exact-physics gate.
The 5-second external whole-run budget is not equal to a five-second per-decision controller budget.

## Artifacts

Tables: `results/paper/tables/`; PNG figures: `results/paper/figures/`.
Figures generated: paired_service_scatter, per_instance_service_difference, complete_service_rate, decision_latency_distribution, mcts_root_to_final_gain.
