from dataclasses import replace
from time import perf_counter

from evrp.experiments import audit_result, simulation_config
from evrp.fleet_mcts import construct_fleet_root
from evrp.model import Observation
from evrp.optimizers.base import OptimizationContext
from evrp.fleet_mcts import FleetPlan
from evrp.optimizers import hgs
from evrp.optimizers.hgs import HGSOptimizer
from evrp.simulator import EventDrivenSimulator
from tests.test_repair import customer, serves, setup
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


def test_hgs_recovers_released_customer_missing_from_constructor():
    state, obs, mpc = setup((customer("A", 1), customer("B", 2)))
    root = {0: serves("A")}
    context = OptimizationContext(obs, {0: state}, {}, {}, frozenset(obs.customer_by_id),
                                  frozenset(), frozenset(), root, 1, perf_counter() + 2, 3, mpc)
    result = HGSOptimizer(generations=2, population_size=3).optimize(context)
    assert result.customers_covered == {"A", "B"}
    assert result.objective[0] == 0
    assert result.diagnostics.values["root_service_insertions"] >= 1
    assert result.validated[0].actions == result.routes[0]


def test_hgs_biased_fitness_changes_parent_and_survivor_selection(monkeypatch):
    def plan(sequence, score):
        return FleetPlan((sequence,), ((),), (0.0,), (None,), score, {})

    elite = plan(("A", "B", "C"), (0, 0.1))
    middle = plan(("A", "C", "B"), (0, 0.2))
    diverse = plan(("C", "B", "A"), (0, 0.3))
    unserved = plan(("A",), (1, 0.0))
    values = {elite.sequences: 0.0, middle.sequences: 0.5,
              diverse.sequences: 1.0, unserved.sequences: 1.0}
    monkeypatch.setattr(hgs, "_diversity", lambda member, population, ids: values[member.sequences])
    population = [elite, middle, diverse, unserved]

    class AllContestants:
        def sample(self, members, count):
            return list(members)[:count]

    assert hgs._select_parent(population[:3], AllContestants(), (0,)) is diverse
    assert hgs._survivors(population[:3], 2, (0,)) == [elite, diverse]
    assert hgs._biased_ranks(population, (0,))[id(unserved)][0] == 1
    assert hgs._biased_ranks(population, (0,))[id(diverse)][0] == 0


def test_hgs_runs_in_common_event_pipeline():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="MPC_HGS", total_planning_time_limit=1.0))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert all(audit_result(result, base.instance, base.scenario).values())
    assert result.decisions[0]["optimizer"]["name"] == "MPC_HGS"
    assert "root_service_insertions" in result.decisions[0]["optimizer"]["diagnostics"]
