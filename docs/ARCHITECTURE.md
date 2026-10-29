# Architecture and proposed boundaries

This describes the current implementation. The five original methods remain
independently runnable. MPC-ALNS-SLAD is a research hypothesis and has not been
implemented or evaluated.

## Current execution path

`scripts/run_*.py` and `evrp/experiments.py` load YAML configuration, a
Desaulniers instance, a validated offline reference, and a dynamic scenario.
`evrp/observation.py` releases requests to the online controller. At each
observable event, `evrp/simulator.py` preserves physical commitments and
replays soft route continuations. Its common constructor supplies fleet routes
to one adapter from `evrp/optimizers/registry.py`. Completion, MCTS, ALNS, HGS,
and ACS implement the `OptimizationContext`/`OptimizationResult` contract in
`evrp/optimizers/base.py`. The shared fleet problem and objective live in
`evrp/fleet_mcts.py` and `evrp/optimizers/objective.py`. Proposed routes are
reconstructed through `evrp/repair.py` and `evrp/resource_decoder.py`, checked
with `evrp/model.py` transitions, and only first actions are dispatched.
`evrp/experiments.py`, `evrp/audit.py`, and study-specific auditors independently
replay and validate the saved outcomes.

| Current responsibility | Modules | Intended boundary |
| --- | --- | --- |
| Benchmark and paths | `instance.py`, `storage.py` | `benchmarks/` plus explicit path configuration |
| EV states and physical transitions | `model.py` | `core/`; one authoritative transition validator |
| Offline feasible references | `reference.py`, `reference_extensions.py` | Offline benchmark/reference utilities only |
| Dynamic releases and visible state | `scenario.py`, `observation.py` | `scenarios/`; online observation excludes hidden requests |
| Decision and event control | `mpc.py`, `simulator.py`, `agent.py`, `coordinator.py`, `continuity.py` | `mpc/`, with separate event loop and decision pipeline |
| Five baseline searches | `optimizers/`, `fleet_mcts.py`, `fleet_lns.py` | Baseline adapters and a small common optimizer contract |
| Route and charging reconstruction | `repair.py`, `resource_decoder.py`, `enhanced_decoder.py` | `routing/` behind a tested decoder interface |
| Evaluation and reproducibility | `experiments.py`, `audit.py`, `analysis.py`, `plotting.py`, `scripts/` | Execution, audit, statistics, and rendering in separate layers |

## Dependency and extraction constraints

- `simulator.py` combines event scheduling, constructor and optimizer calls,
  optional first-action policies, final route validation, dispatch, and traces.
  Extract one concern at a time, retaining event and deadline semantics.
- `fleet_mcts.py` defines `_FleetProblem`, which ALNS and other search adapters
  import despite its private name. Moving it requires parity tests for all
  five methods; it is not an isolated MCTS file move.
- `model.transition` is the physical authority, but route proposal checks,
  experiment audits, and report replay also validate outcomes. Shared
  validation should call the same rules without changing charging semantics.
- `evrp/mpc.py` already owns a public import path. A new `evrp/mpc/` package
  would collide with the module name. Keep compatibility imports during a
  staged move. The same applies to users of `evrp/optimizers/`.
- Protocols fingerprint source files, configuration, dataset and raw evidence.
  A behavior-preserving source move can still invalidate a historical hash.
  Keep frozen runners and studies tied to their execution revisions.

The independently extractable first boundary is shared experiment path and
configuration handling. A later pure event-trigger or reporting helper can be
extracted once characterization tests cover its inputs and outputs. The
decoder and `_FleetProblem` have multiple algorithm callers and need broader
parity coverage before relocation.

## Import and test impact of future moves

Keep callers of `evrp.instance.load_instance`, `evrp.model.transition`,
`evrp.mpc.MPCConfig`, and `evrp.optimizers.registry.create_optimizer` working
through explicit compatibility imports. ALNS, HGS, ACS, the shared constructor,
and targeted-recovery policies call `evrp.fleet_mcts._FleetProblem`; a move
there affects more than the MCTS adapter. `evrp.experiments` and historical
`scripts/run_*.py` also import the current paths directly.

Relevant regression gates include `tests/test_desaulniers_dataset.py` and
`tests/test_physics.py` for benchmark and transitions;
`tests/test_reference_scenario.py` and `tests/test_observation.py` for the
information boundary; `tests/test_resource_decoder.py` for charging routes;
`tests/test_optimizer_interface.py`, `tests/test_mpc_optimizer_fairness.py`,
and optimizer-specific tests for the five methods; and
`tests/test_frozen_input_archive.py` and `tests/test_final_cpu_paper.py` for
reproducibility. Those tests should be supplemented with fixed-seed trace
parity before changing event or dispatch code.

## Proposed method boundary

`targeted_recovery.service_guard_v1` already checks whether first commitments
erase screened options for urgent, visible requests.
`targeted_recovery.counterfactual_actions` and `flex_exchange.improve_first_controls`
also test alternative first actions. Existing `ServiceDiagnostics` and
planning-loss scripts are observational; their optimistic screens are not
physical route witnesses or causal proofs. A future proposed-method module
must state what additional observable-state test it performs, how it differs
from these controls, and how it stays within the same five-second total
decision budget. Original `MPC_ALNS` remains a separate baseline.

See [the ordered roadmap](REFACTORING_ROADMAP.md) and
[results retention plan](RESULTS_RETENTION_PLAN.md) before moving modules or
historical evidence.
