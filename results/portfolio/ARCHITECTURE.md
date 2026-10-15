# MPC optimizer architecture

All internal optimizers act only at a common event-triggered MPC decision
epoch. They receive the measured fleet origins, released-customer observation,
immutable busy actions, soft suffixes, fixed `K_ref`, deterministic seed,
common constructor root, and shared decision deadline through
`OptimizationContext`. The constructor is `construct_fleet_root`; no optimizer
gets future releases or a private constructor. The first action of an
independently replayed fleet route is executed, then the controller observes
the next physical event.

`MPC_COMPLETION` retains the constructor. `MPC_MCTS_V1` wraps frozen fleet
MCTS; `MPC_ALNS` uses six destroy/four repair operators with adaptive weights;
`MPC_HGS` uses a population, route crossover, local education and survivor
selection. Its population and offspring also attempt exact insertion of
currently uncovered released customers. All candidate route changes use the
canonical EV charging decoder.
The accepted winner in each method uses the same lexicographic `J_A/J_B`
objective. RoutingBlocks is external offline context, not MPC-ALNS.

V1 paper evidence is immutable under `results/paper/`; see
`docs/V1_FROZEN_EVIDENCE.md`. This tree is development work, not final results.
