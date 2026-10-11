from dataclasses import replace
from time import perf_counter

from evrp.experiments import audit_result, simulation_config
from evrp.fleet_mcts import _FleetProblem, solve_fleet_mcts
from evrp.model import Observation
from evrp.mpc import MPCConfig
from evrp.planning_budget import reset_deadline, set_deadline
from evrp.simulator import EventDrivenSimulator
from tests.test_repair import customer, serves, setup
from tests.test_simulator import synthetic


def test_fleet_mcts_serves_released_work_and_preserves_lexicographic_value():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    origins = {0: state}
    result = solve_fleet_mcts(origins, {}, observation, config, seed=7,
                              iterations=8, depth=2, branch_limit=4)
    assert result.best_score[0] == 0
    assert {a.destination for a in result.routes[0] if a.kind == "serve"} == {"A", "B"}
    problem = _FleetProblem(origins, observation, config, 3, 2)
    empty = problem.initial({})
    full = problem.initial(result.routes)
    assert problem.value(full) > problem.value(empty)
    assert full.score[0] == 0
    assert len(full.score) == 5
    assert len(empty.score) == 7
    assert result.best_components["unserved_customers"] == 0
    assert 0 <= result.best_components["operational_cost"] <= 1
    assert result.validated[0].actions == result.routes[0]
    assert {"A", "B"} <= set(result.criticality)


def test_fleet_mcts_does_not_insert_hidden_customer():
    state, observation, config = setup((customer("A", 1), customer("hidden", 2)))
    visible = Observation(0, observation.infrastructure, (observation.customer_by_id["A"],))
    result = solve_fleet_mcts({0: state}, {}, visible, config, seed=2,
                              iterations=4, depth=2, branch_limit=3)
    assert result.best_score[0] == 0
    assert {a.destination for a in result.routes[0] if a.kind == "serve"} == {"A"}


def test_candidate_vehicle_ranking_uses_planned_route_geometry():
    state, observation, config = setup((customer("A", 1), customer("B", 5),
                                        customer("X", 5.2)))
    origins = {0: state, 1: replace(state, id=1)}
    problem = _FleetProblem(origins, observation, config, 3, 2)
    plan = problem.initial({0: serves("A"), 1: serves("B")})
    assert problem._nearest_vehicles(plan, "X", 1) == [1]


def test_fleet_mcts_expired_budget_returns_validated_incumbent():
    state, observation, config = setup((customer("A", 1),))
    token = set_deadline(perf_counter() - 1)
    try:
        result = solve_fleet_mcts({0: state}, {}, observation, config, seed=0)
    finally:
        reset_deadline(token)
    assert result.deadline_reached
    assert result.routes == {0: ()}


def test_fleet_mcts_simulator_replays_without_future_information():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="FLEET_MPC_MCTS", total_planning_time_limit=2.0,
                                    fleet_mcts_iterations=8, fleet_mcts_depth=2,
                                    fleet_mcts_branch_limit=4, candidate_position_limit=2))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert result.metrics["fleet_mcts_iterations"] >= 0
    assert all(audit_result(result, base.instance, base.scenario).values())


def test_rolling_lns_accepts_the_same_total_event_budget():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="ROLLING_LNS", total_planning_time_limit=2.0,
                                    lns_time_limit=2.0, lns_iterations=4))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert result.metrics["total_deadline_overrun_rate"] == 0
    assert all(audit_result(result, base.instance, base.scenario).values())
