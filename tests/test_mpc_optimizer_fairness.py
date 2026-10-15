"""The simulator must pass the same observable MPC root to each optimizer."""

from evrp import optimizers
from evrp.experiments import simulation_config
from evrp.simulator import EventDrivenSimulator
from tests.test_simulator import synthetic


def test_all_optimizers_get_the_same_initial_fleet_context(monkeypatch):
    base = synthetic(release=5, fleet=2)
    original = optimizers.create_optimizer
    captured = {}

    def capture(name, config):
        actual = original(name, config)

        class RecordingOptimizer:
            def optimize(self, context):
                captured.setdefault(name, context)
                return actual.optimize(context)

        return RecordingOptimizer()

    monkeypatch.setattr(optimizers, "create_optimizer", capture)
    for name in ("MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"):
        config = simulation_config(dict(algorithm=name, total_planning_time_limit=1.0,
                                        fleet_mcts_iterations=4, fleet_mcts_depth=2,
                                        fleet_mcts_branch_limit=4, lns_iterations=4))
        EventDrivenSimulator(base.instance, base.scenario, config).run()
    contexts = list(captured.values())
    first = contexts[0]
    assert len(contexts) == 5
    assert all(context.observation == first.observation for context in contexts)
    assert all(context.origins == first.origins for context in contexts)
    assert all(context.constructor_routes == first.constructor_routes for context in contexts)
    assert all(context.released_customers == first.released_customers for context in contexts)
    assert all(context.k_ref == first.k_ref == 2 for context in contexts)
    assert all(context.deadline is not None for context in contexts)
