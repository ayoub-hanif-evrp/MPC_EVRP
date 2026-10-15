from dataclasses import replace
from time import perf_counter

from evrp.experiments import audit_result, simulation_config
from evrp.fleet_mcts import construct_fleet_root
from evrp.model import Observation
from evrp.optimizers.base import OptimizationContext
from evrp.optimizers.hgs import HGSOptimizer
from evrp.simulator import EventDrivenSimulator
from tests.test_repair import customer, setup
from tests.test_simulator import synthetic


def test_hgs_population_crossover_and_exact_replay():
    state, obs, mpc = setup(tuple(customer(chr(65 + i), i + 1) for i in range(4)))
    origins = {0: state, 1: replace(state, id=1)}
    root = construct_fleet_root(origins, {}, obs, mpc).routes
    context = OptimizationContext(obs, origins, {}, {}, frozenset(obs.customer_by_id),
                                  frozenset(), frozenset(), root, 2, perf_counter() + 5, 21, mpc)
    optimizer = HGSOptimizer(generations=6, population_size=5, education_attempts=6)
    first = optimizer.optimize(context)
    second = optimizer.optimize(context)
    assert first.routes == second.routes
    assert first.objective == second.objective
    assert first.diagnostics.values["generations"] > 0
    assert first.diagnostics.values["crossovers"] > 0
    assert first.diagnostics.values["feasible_individuals"] >= 2
    assert first.customers_covered <= context.released_customers
    assert all(proposal.actions == first.routes[k] for k, proposal in first.validated.items())


def test_hgs_cannot_see_future_customer():
    state, obs, mpc = setup((customer("A", 1), customer("future", 2)))
    visible = Observation(0, obs.infrastructure, (obs.customer_by_id["A"],))
    context = OptimizationContext(visible, {0: state}, {}, {}, frozenset({"A"}),
                                  frozenset(), frozenset(), {}, 1, perf_counter() + 1, 3, mpc)
    result = HGSOptimizer(generations=4, population_size=3).optimize(context)
    assert result.customers_covered <= {"A"}


def test_hgs_runs_in_common_event_pipeline():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="MPC_HGS", total_planning_time_limit=1.0))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert all(audit_result(result, base.instance, base.scenario).values())
    assert result.decisions[0]["optimizer"]["name"] == "MPC_HGS"
