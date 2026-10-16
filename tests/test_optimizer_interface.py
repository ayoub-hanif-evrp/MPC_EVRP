"""Common-root and replay guarantees for the first MPC optimizer adapters."""

from dataclasses import replace
from time import perf_counter

import pytest

from evrp.experiments import (audit_result, requires_constructor_insertion_retention,
                              simulation_config)
from evrp.fleet_mcts import construct_fleet_root, solve_fleet_mcts
from evrp.model import Observation
from evrp.optimizers import OptimizationContext, create_optimizer
from evrp.repair import route_proposal
from evrp.simulator import EventDrivenSimulator
from tests.test_repair import customer, setup
from tests.test_simulator import synthetic


def test_search_may_replace_constructor_insertions_but_not_lose_service():
    assert not any(requires_constructor_insertion_retention(method) for method in
                   ("MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"))
    assert requires_constructor_insertion_retention("MPC_COMPLETION")
    assert requires_constructor_insertion_retention("RH_REGRET")
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="MPC_COMPLETION", total_planning_time_limit=1.0))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    decision = next(row for row in result.decisions if "constructor_service" in row)
    assert all(audit_result(result, base.instance, base.scenario).values())
    decision["best_service_after_search"] = decision["constructor_service"] - 1
    with pytest.raises(AssertionError, match="Optimizer lost constructor service"):
        audit_result(result, base.instance, base.scenario)


def _context(state, observation, config, root):
    return OptimizationContext(observation, {0: state}, {}, {},
                               frozenset(observation.customer_by_id), frozenset(), frozenset(),
                               root, 1, perf_counter() + 5, 17, config)


def test_adapters_receive_identical_visible_root_and_exactly_replay():
    state, obs, mpc = setup((customer("A", 1), customer("B", 2)))
    root = construct_fleet_root({0: state}, {}, obs, mpc).routes
    context = _context(state, obs, mpc, root)
    for name in ("MPC_COMPLETION", "MPC_MCTS", "MPC_ACS"):
        config = simulation_config(dict(algorithm=name, fleet_mcts_iterations=8,
                                        fleet_mcts_depth=2, fleet_mcts_branch_limit=4))
        result = create_optimizer(name, config).optimize(context)
        assert result.customers_covered <= context.released_customers
        assert result.objective[0] == len(context.released_customers - result.customers_covered)
        assert result.vehicles_activated <= context.k_ref
        for k, proposal in result.validated.items():
            assert proposal == route_proposal(context.origins[k], result.routes[k], obs, mpc)


def test_context_rejects_future_customer_and_copies_route_maps():
    state, obs, mpc = setup((customer("A", 1), customer("hidden", 2)))
    visible = Observation(obs.time, obs.infrastructure, (obs.customer_by_id["A"],))
    root = {0: ()}
    context = _context(state, visible, mpc, root)
    root[0] = ( )
    assert dict(context.constructor_routes) == {0: ()}
    with pytest.raises(ValueError, match="Released customers"):
        replace(context, released_customers=frozenset(obs.customer_by_id))


def test_acs_cannot_plan_unreleased_customer():
    state, observation, mpc = setup((customer("A", 1), customer("hidden", 2)))
    visible = Observation(observation.time, observation.infrastructure,
                          (observation.customer_by_id["A"],))
    context = _context(state, visible, mpc, {0: ()})
    config = simulation_config(dict(algorithm="MPC_ACS"))
    result = create_optimizer("MPC_ACS", config).optimize(context)
    assert result.customers_covered <= {"A"}
    assert all(action.destination != "hidden" for route in result.routes.values()
               for action in route)


def test_mcts_interface_preserves_direct_solver_result():
    state, obs, mpc = setup((customer("A", 1), customer("B", 2)))
    root = construct_fleet_root({0: state}, {}, obs, mpc).routes
    context = _context(state, obs, mpc, root)
    config = simulation_config(dict(algorithm="MPC_MCTS", fleet_mcts_iterations=8,
                                    fleet_mcts_depth=2, fleet_mcts_branch_limit=4))
    direct = solve_fleet_mcts({0: state}, root, obs, mpc, seed=17, iterations=8,
                              depth=2, branch_limit=4, position_limit=3, regret_k=2)
    adapted = create_optimizer("MPC_MCTS", config).optimize(context)
    assert adapted.routes == direct.routes
    assert adapted.objective == direct.best_score
    assert adapted.components == direct.best_components


def test_event_level_mcts_adapter_matches_historical_path():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="FLEET_MPC_MCTS", total_planning_time_limit=1.0,
                                    fleet_mcts_iterations=4, fleet_mcts_depth=2,
                                    fleet_mcts_branch_limit=4))
    historical = EventDrivenSimulator(base.instance, base.scenario, config).run()
    adapted = EventDrivenSimulator(base.instance, base.scenario,
                                   replace(config, algorithm="MPC_MCTS")).run()
    assert historical.metrics["customers_served"] == adapted.metrics["customers_served"]
    assert [d["route_owners_after_repair"] for d in historical.decisions] == [
        d["route_owners_after_repair"] for d in adapted.decisions]
    assert "tree_improvements" in adapted.decisions[0]["optimizer"]["diagnostics"]
    assert all(audit_result(adapted, base.instance, base.scenario).values())


def test_completion_adapter_matches_historical_constructor_only_path():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="FLEET_MPC_COMPLETION_ONLY",
                                    total_planning_time_limit=1.0))
    historical = EventDrivenSimulator(base.instance, base.scenario, config).run()
    adapted = EventDrivenSimulator(base.instance, base.scenario,
                                   replace(config, algorithm="MPC_COMPLETION")).run()
    assert historical.metrics["customers_served"] == adapted.metrics["customers_served"]
    assert [d["route_owners_after_repair"] for d in historical.decisions] == [
        d["route_owners_after_repair"] for d in adapted.decisions]
