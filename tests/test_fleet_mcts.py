from dataclasses import replace
from time import perf_counter, sleep

import evrp.fleet_mcts as fleet_mcts
import evrp.repair as repair
import pytest

from evrp.experiments import audit_result, simulation_config
from evrp.fleet_mcts import _FleetProblem, solve_fleet_mcts
from evrp.model import Observation
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, remaining_time, reset_deadline, set_deadline
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
    assert len(full.score) == 6
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


def test_full_service_tree_actions_preserve_coverage_and_feasibility():
    state, observation, config = setup((customer("A", 1), customer("B", 2),
                                        customer("C", 3), customer("D", 4)))
    origins = {0: state, 1: replace(state, id=1)}
    problem = _FleetProblem(origins, observation, config, 3, 2)
    plan = problem.initial({0: serves("A", "B"), 1: serves("C", "D")})
    candidates = problem.candidates(plan, 24)
    assert candidates
    assert all(candidate.score[0] == 0 for candidate in candidates)
    assert all({c for seq in candidate.sequences for c in seq} == {"A", "B", "C", "D"}
               for candidate in candidates)


def test_screened_gaps_use_forward_and_backward_windows_and_capacity():
    state, observation, config = setup((customer("A", 1, due=3),
                                        customer("B", 3, due=6),
                                        customer("X", 5, due=30)))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    sequence = ("A", "B")
    forward, backward, demand = problem._screen_profile(0, sequence)
    assert forward == (0, 1, 3)
    assert backward == (3, 6)
    assert demand == 2
    assert not problem._screen_gap(0, sequence, "X", 1)[0]
    assert problem._screen_gap(0, sequence, "X", 2)[0]
    tight = _FleetProblem({0: replace(state, load=2)}, observation, config, 3, 2)
    assert not tight._screen_gap(0, sequence, "X", 2)[0]


def test_full_coverage_flexibility_precedes_vehicle_count():
    state, observation, config = setup((customer("A", 1), customer("B", 8)))
    origins = {0: state, 1: replace(state, id=1)}
    problem = _FleetProblem(origins, observation, config, 3, 2)
    compact = problem.initial({0: serves("A", "B")})
    split = problem.initial({0: serves("A"), 1: serves("B")})
    assert compact.score[0] == split.score[0] == 0
    assert split.components["flexibility_risk"] < compact.components["flexibility_risk"]
    assert split.components["activated_vehicles"] > compact.components["activated_vehicles"]
    assert split.score < compact.score


def test_full_service_search_can_continue_past_old_075_second_cap(monkeypatch):
    state, observation, config = setup((customer("A", 1),))
    original = fleet_mcts._FleetProblem.candidates
    delayed = [False]

    def candidates(self, plan, branch_limit):
        if not delayed[0]:
            delayed[0] = True
            sleep(0.8)
        return original(self, plan, branch_limit)

    monkeypatch.setattr(fleet_mcts._FleetProblem, "candidates", candidates)
    token = set_deadline(perf_counter() + 1.5)
    try:
        result = solve_fleet_mcts({0: state}, {0: serves("A")}, observation,
                                  config, seed=0, iterations=2, depth=1, branch_limit=4)
    finally:
        reset_deadline(token)
    assert delayed[0]
    assert result.full_seconds >= 0.75
    assert result.iterations >= 1
    assert result.best_score[0] == 0


def test_fleet_mcts_expired_before_root_defers_to_simulator_incumbent():
    state, observation, config = setup((customer("A", 1),))
    token = set_deadline(perf_counter() - 1)
    try:
        with pytest.raises(PlanningDeadlineExceeded):
            solve_fleet_mcts({0: state}, {}, observation, config, seed=0)
    finally:
        reset_deadline(token)


def test_fleet_mcts_simulator_replays_without_future_information():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="FLEET_MPC_MCTS", total_planning_time_limit=2.0,
                                    fleet_mcts_iterations=8, fleet_mcts_depth=2,
                                    fleet_mcts_branch_limit=4, candidate_position_limit=2))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert result.metrics["fleet_mcts_iterations"] >= 0
    assert all(audit_result(result, base.instance, base.scenario).values())


def test_final_validation_uses_original_event_deadline(monkeypatch):
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="FLEET_MPC_MCTS", total_planning_time_limit=1.0,
                                    fleet_mcts_iterations=2, fleet_mcts_depth=1,
                                    fleet_mcts_branch_limit=3))
    original_solve = fleet_mcts.solve_fleet_mcts
    original_replay = repair.route_proposal
    remaining_after_search = []
    final_replay_remaining = []

    def solve(*args, **kwargs):
        result = original_solve(*args, **kwargs)
        remaining_after_search.append(remaining_time())
        return result

    def replay(*args, **kwargs):
        if remaining_after_search and len(final_replay_remaining) < len(remaining_after_search):
            final_replay_remaining.append(remaining_time())
        return original_replay(*args, **kwargs)

    monkeypatch.setattr(fleet_mcts, "solve_fleet_mcts", solve)
    monkeypatch.setattr(repair, "route_proposal", replay)
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert final_replay_remaining
    assert all(after <= before + 0.002 for before, after in
               zip(remaining_after_search, final_replay_remaining))
    assert result.metrics["deadline_fallback_count"] >= 0
    assert result.metrics["final_validation_seconds_total"] >= 0


def test_rolling_lns_accepts_the_same_total_event_budget():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="ROLLING_LNS", total_planning_time_limit=2.0,
                                    lns_time_limit=2.0, lns_iterations=4))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert result.metrics["total_deadline_overrun_rate"] == 0
    assert all(audit_result(result, base.instance, base.scenario).values())
