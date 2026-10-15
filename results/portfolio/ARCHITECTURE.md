# MPC optimizer architecture

All internal optimizers act only at a common event-triggered MPC decision
epoch. They receive the measured fleet origins, released-customer observation,
immutable busy actions, soft suffixes, fixed `K_ref`, deterministic seed,
common constructor root, and shared decision deadline through
`OptimizationContext`. The constructor is `construct_fleet_root`; no optimizer
gets future releases or a private constructor. The first action of an
independently replayed fleet route is executed, then the controller observes
the next physical event.

`MPC_COMPLETION` retains the constructor. `MPC_MCTS` uses normalized tree
values, seeded completion policies and root-control evidence. `MPC_ALNS` uses
six destroy/four repair operators with adaptive weights; `MPC_HGS` uses a
population, route crossover, local education and survivor selection.
`MPC_ACS` constructs routes with insertion pheromone, probabilistic selection,
local updates, evaporation and global-best reinforcement. All candidate
route changes use the canonical EV charging decoder.
The accepted winner in each method uses the same lexicographic `J_A/J_B`
objective. RoutingBlocks is external offline context, not MPC-ALNS.

Each `(scenario, optimizer)` development run starts in its own Python
interpreter, independently audits its trace and saves compressed raw evidence.
The six-family isolated pilot is complete; the 66-scenario grid is still in
progress. Common-state shadow snapshots are selected before any shadow
optimizer outcome is opened.

V1 paper evidence is immutable under `results/paper/`; see
`docs/V1_FROZEN_EVIDENCE.md`. This tree is development work, not final results.
