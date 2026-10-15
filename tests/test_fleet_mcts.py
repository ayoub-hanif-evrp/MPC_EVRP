from dataclasses import replace
from time import perf_counter, sleep

import evrp.fleet_mcts as fleet_mcts
import evrp.repair as repair
import pytest

from evrp.experiments import audit_result, simulation_config
from evrp.fleet_mcts import _FleetProblem, construct_fleet_root, solve_fleet_mcts
from evrp.model import Action, Observation, transition
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, remaining_time, reset_deadline, set_deadline
from evrp.simulator import EventDrivenSimulator
from evrp.repair import route_proposal
from tests.test_repair import customer, serves, setup
from tests.test_simulator import synthetic
from scripts.final_control_horizon_campaign import cases


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
    assert len(full.score) == 7
    assert len(empty.score) == 8
    assert result.best_components["unserved_customers"] == 0
    assert 0 <= result.best_components["operational_cost"] <= 1
    assert result.validated[0].actions == result.routes[0]
    assert {"A", "B"} <= set(result.criticality)


def test_normalized_tree_value_cannot_trade_service_for_secondary_terms():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    empty = problem.initial({})
    one = problem.change(empty, {0: ("A",)})
    assert one is not None
    favorable = dict(empty.components, control_risk=0, flexibility_risk=0,
                     screened_zero_option_customers=0, screened_one_option_customers=0,
                     activated_vehicles=0, operational_cost=0,
                     normalized_distance=0, route_instability=0)
    unfavorable = dict(one.components, control_risk=1, flexibility_risk=1,
                       screened_zero_option_customers=2, screened_one_option_customers=2,
                       activated_vehicles=1, operational_cost=1,
                       normalized_distance=1, route_instability=1)
    assert 0 <= problem.value(replace(empty, components=favorable)) < problem.value(
        replace(one, components=unfavorable)) <= 1


def test_seeded_rollouts_record_all_three_policies_and_safe_root():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    result = solve_fleet_mcts({0: state}, {}, observation, config, seed=7,
                              iterations=24, depth=2, branch_limit=4)
    assert set(result.rollout_policy_usage) == {
        "CRITICAL_REGRET", "EARLIEST_DEADLINE", "RESERVE_PRESERVING"}
    assert sum(result.rollout_policy_usage.values()) == result.rollout_count
    assert all(count > 0 for count in result.rollout_policy_usage.values())
    assert result.best_score <= result.initial_score
    assert sum(result.root_control_visits.values()) == result.rollout_count


def test_default_policy_completes_more_than_two_released_customers():
    state, observation, config = setup(tuple(customer(chr(65 + i), i + 1)
                                               for i in range(5)))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    root = problem.initial({})
    completed = problem.complete_rollout(root, perf_counter() + 2)
    assert root.score[0] == 5
    assert completed.score[0] == 0
    assert len(completed.sequences[0]) == 5


def test_tree_child_remains_structural_after_terminal_rollout(monkeypatch):
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    visited_children = []

    def candidates(self, plan, branch_limit):
        if plan.score[0] == 2:
            return [self.change(plan, {0: ("A",)})]
        visited_children.append(plan.score[0])
        return []

    monkeypatch.setattr(fleet_mcts._FleetProblem, "candidates", candidates)
    result = solve_fleet_mcts({0: state}, {}, observation, config, seed=0,
                              iterations=2, depth=2, branch_limit=2)
    assert result.best_score[0] == 0
    assert visited_children == [1]
    assert result.rollout_customers_completed >= 1


def test_service_screen_considers_farther_ev_after_five_infeasible_ones():
    state, observation, config = setup((customer("A", 1),))
    origins = {k: replace(state, id=k, load=0) for k in range(5)}
    origins[5] = replace(state, id=5, location=replace(state.location, x=10),
                         departed=True)
    problem = _FleetProblem(origins, observation, config, 3, 2)
    options = problem.screened_options(((),) * 6, "A")
    assert {option[2] for option in options} == {5}
    assert problem.screened_vehicle_evaluations == 6


def test_tree_shortlist_exposes_early_due_customer(monkeypatch):
    state, observation, config = setup((customer("E", 1, due=10),
                                        customer("L1", 2), customer("L2", 3),
                                        customer("L3", 4)))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    root = problem.initial({})
    monkeypatch.setattr(problem, "_urgent", lambda plan, limit: ["L1", "L2", "L3"][:limit])
    candidates = problem.candidates(root, 24)
    assert any("E" in sequence for candidate in candidates
               for sequence in candidate.sequences)


def test_rollout_stops_when_most_critical_customer_has_no_direct_option():
    state, observation, config = setup((customer("A", 100, due=1),
                                        customer("B", 1)))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    root = problem.initial({})
    assert problem._criticality(root.sequences)[0][0] == "A"
    assert problem.complete_rollout(root, perf_counter() + 1).sequences == root.sequences


def test_three_fleet_methods_share_initial_constructor():
    base = synthetic(release=5, fleet=2)
    firsts = []
    for algorithm in ("FLEET_MPC_MCTS", "ROLLING_LNS", "FLEET_MPC_COMPLETION_ONLY"):
        config = simulation_config(dict(algorithm=algorithm, total_planning_time_limit=1.0,
                                        fleet_mcts_iterations=4, fleet_mcts_depth=2,
                                        fleet_mcts_branch_limit=4, lns_iterations=4))
        result = EventDrivenSimulator(base.instance, base.scenario, config).run()
        firsts.append((result.decisions[0]["retained_service"],
                       result.decisions[0]["constructor_service"]))
        assert result.metrics["customers_served"] == 2
        assert all(audit_result(result, base.instance, base.scenario).values())
    assert firsts == [(0, 1)] * 3


def test_uncovered_work_waits_for_service_completion_trigger(monkeypatch):
    base = synthetic(release=0)
    config = simulation_config(dict(algorithm="FLEET_MPC_MCTS",
                                    total_planning_time_limit=1.0,
                                    fleet_mcts_iterations=8, fleet_mcts_depth=2,
                                    fleet_mcts_branch_limit=4))
    original = fleet_mcts.solve_fleet_mcts
    calls = [0]

    def leave_one_uncovered(origins, routes, observation, mpc, **kwargs):
        result = original(origins, routes, observation, mpc, **kwargs)
        calls[0] += 1
        if calls[0] == 1:
            actions = serves("A")
            proposal = route_proposal(origins[0], actions, observation, mpc)
            return replace(result, routes={0: actions}, validated={0: proposal})
        return result

    monkeypatch.setattr(fleet_mcts, "solve_fleet_mcts", leave_one_uncovered)
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    reasons = [d["optimization_trigger_reason"] for d in result.decisions
               if d["optimization_trigger_reason"]]
    assert result.metrics["customers_served"] == 2
    assert reasons == ["initial,release", "service_completion_uncovered"]
    assert all("uncovered_work" not in reason for reason in reasons)


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


def test_screen_cache_reuses_unchanged_vehicle_summaries():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    origins = {0: state, 1: replace(state, id=1)}
    problem = _FleetProblem(origins, observation, config, 3, 2)
    problem.screened_options(((), ()), "B")
    assert problem.screened_vehicle_evaluations == 2
    problem.screened_options((("A",), ()), "B")
    assert problem.screened_vehicle_evaluations == 3
    assert problem.screen_cache_hits > 0


def test_parallel_constructor_prioritizes_early_due_work():
    state, observation, config = setup((customer("Late", 1, due=150),
                                        customer("Early", 2, due=20)))
    result = construct_fleet_root({0: state}, {}, observation, config)
    assert [row["customer"] for row in result.insertions] == ["Early", "Late"]
    assert result.chosen_score[0] == 0
    assert result.screened_insertions >= result.exact_decoder_calls


def test_ejection_chain_reinserts_blocker_on_another_vehicle():
    state, observation, config = setup((customer("A", 1, due=100),
                                        customer("U", 0, due=1)), capacity=1)
    other = replace(state, id=1, location=replace(state.location, x=10), departed=True)
    problem = _FleetProblem({0: state, 1: other}, observation, config, 3, 2)
    plan = problem.initial({0: serves("A")})
    assert not problem.screened_options(plan.sequences, "U")
    candidates = problem.candidates(plan, 24)
    assert any(candidate.action_kind == "EJECTION_CHAIN_2" and
               candidate.sequences == (("U",), ("A",)) for candidate in candidates)
    assert problem.ejection_chains_feasible > 0


def test_full_coverage_flexibility_precedes_vehicle_count():
    state, observation, config = setup((customer("A", 1), customer("B", 8)))
    origins = {0: state, 1: replace(state, id=1)}
    problem = _FleetProblem(origins, observation, config, 3, 2)
    compact = problem.initial({0: serves("A", "B")})
    split = problem.initial({0: serves("A"), 1: serves("B")})
    assert compact.score[0] == split.score[0] == 0
    assert split.components["flexibility_risk"] < compact.components["flexibility_risk"]
    assert split.components["activated_vehicles"] > compact.components["activated_vehicles"]
    assert split.score[1] == split.components["control_risk"]
    assert compact.score[1] == compact.components["control_risk"]


def test_control_risk_replays_only_first_executed_action():
    state, observation, config = setup((customer("A", 1), customer("B", 8)))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    short = problem.initial({0: serves("A")})
    long = problem.initial({0: serves("A", "B")})
    metrics = problem._control_metrics(0, serves("A"))
    assert metrics["tw"] == pytest.approx(0.01)
    assert metrics["battery"] == pytest.approx(0.02)
    assert metrics["capacity"] == pytest.approx(0.1)
    assert metrics["time"] == pytest.approx(0.005)
    assert short.components["control_risk"] == long.components["control_risk"]


def test_control_risk_uses_busy_after_state_and_dispatched_idle_action():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    assert problem._control_metrics(0, ())["time"] == pytest.approx(0.0)
    busy = transition(state, Action("serve", "A"), observation).after
    visible = Observation(0, observation.infrastructure,
                          (observation.customer_by_id["B"],), (("A", 0),))
    busy_problem = _FleetProblem({0: busy}, visible, config, 3, 2)
    assert busy_problem._control_metrics(0, ()) == busy_problem._control_metrics(0, serves("B"))


def test_unused_depot_vehicle_remains_available_reserve():
    state, observation, config = setup((customer("A", 1),))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    reserve = problem._control_metrics(0, ())
    assert reserve["time"] == pytest.approx(0.0)
    assert reserve["total"] < 0.1


@pytest.mark.parametrize("algorithm", ["FLEET_MPC_MCTS", "ROLLING_LNS"])
def test_deterministic_completion_reuses_validated_suffix(algorithm):
    base = synthetic(release=0)
    config = simulation_config(dict(algorithm=algorithm, total_planning_time_limit=1.0,
                                    fleet_mcts_iterations=8, fleet_mcts_depth=2,
                                    fleet_mcts_branch_limit=4, lns_iterations=8))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert result.metrics["optimization_triggers"] == 1
    assert result.metrics["mcts_calls"] == (1 if algorithm == "FLEET_MPC_MCTS" else 0)
    assert any(d["optimization_trigger_reason"] is None for d in result.decisions)
    assert all(not d["mcts_called"] for d in result.decisions[1:])
    assert all(audit_result(result, base.instance, base.scenario).values())


def test_safer_first_action_wins_at_equal_service():
    state, observation, config = setup((customer("A", 1), customer("B", 8)))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    safer = problem.initial({0: serves("A", "B")})
    riskier = problem.initial({0: serves("B", "A")})
    assert safer.score[0] == riskier.score[0] == 0
    assert safer.components["control_risk"] < riskier.components["control_risk"]
    assert safer.score < riskier.score


def test_control_head_relocate_and_swap_keep_full_service():
    state, observation, config = setup((customer("A", 8), customer("B", 9),
                                        customer("C", 1), customer("D", 2)))
    origins = {0: state, 1: replace(state, id=1)}
    problem = _FleetProblem(origins, observation, config, 3, 2)
    plan = problem.initial({0: serves("A", "B"), 1: serves("C", "D")})
    found = {}
    problem._full_service_moves(plan, found, 24)
    candidates = list(found.values())
    assert any(candidate.sequences == (("B",), ("A", "C", "D")) or
               candidate.sequences == (("B",), ("C", "A", "D")) or
               candidate.sequences == (("B",), ("C", "D", "A"))
               for candidate in candidates)
    assert any(candidate.sequences[0][0] == "C" and "A" in candidate.sequences[1]
               for candidate in candidates)
    assert all(candidate.score[0] == 0 and
               {c for seq in candidate.sequences for c in seq} == {"A", "B", "C", "D"}
               for candidate in candidates)


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
    assert result.metrics["maximum_planning_time"] <= 2.0
    assert all(audit_result(result, base.instance, base.scenario).values())


def test_final_control_horizon_grid_is_fixed_and_matched():
    static = list(cases("static"))
    development = list(cases("development"))
    assert len(static) == 6
    assert len(development) == 24
    assert all(config["dynamicity"] == 0 and config["algorithm"] == "FLEET_MPC_MCTS"
               for _, config in static)
    for instance in {name for name, _ in development}:
        for seed in (0, 1):
            pair = [config for name, config in development
                    if name == instance and config["scenario_seed"] == seed]
            assert {config["algorithm"] for config in pair} == {
                "FLEET_MPC_MCTS", "ROLLING_LNS"}
            assert all(config["dynamicity"] == 0.5 and config["experiment_seed"] == 0
                       and config["total_planning_time_limit"] == 5.0 for config in pair)
            assert all(config["fleet_mcts_iterations"] == 256 and
                       config["fleet_mcts_depth"] == 4 and
                       config["fleet_mcts_branch_limit"] == 24 and
                       config["candidate_position_limit"] == 3 and
                       config["uct_c"] == 1.4 for config in pair)
