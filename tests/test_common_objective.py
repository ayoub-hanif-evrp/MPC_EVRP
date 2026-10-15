"""Golden objective hierarchy checks independent of the MCTS search loop."""

from dataclasses import replace

import pytest

from evrp.fleet_mcts import _FleetProblem
from evrp.optimizers.objective import FleetObjectiveEvaluator
from tests.test_repair import customer, serves, setup


def _evaluator(problem):
    return FleetObjectiveEvaluator(problem.ids, problem.origins, problem.pending,
                                   problem.dscale, problem.initial_owners,
                                   problem._metrics, problem._control_metrics,
                                   problem._criticality)


def test_common_objective_matches_legacy_mcts_for_uncovered_and_complete_routes():
    state, obs, config = setup((customer("A", 1), customer("B", 2)))
    origins = {0: state, 1: replace(state, id=1)}
    problem = _FleetProblem(origins, obs, config, 3, 2)
    problem.initial({0: serves("A")})
    for routes in ({}, {0: serves("A")}, {0: serves("A", "B")},
                   {0: serves("A"), 1: serves("B")}):
        sequences = tuple(tuple(a.destination for a in routes.get(k, ()) if a.kind == "serve")
                          for k in problem.ids)
        actions = tuple(routes.get(k, ()) for k in problem.ids)
        costs = tuple(float(2 * len(seq)) for seq in sequences)
        assert _evaluator(problem).evaluate(sequences, actions, costs) == problem._score(
            sequences, actions, costs)
        score, components = _evaluator(problem).evaluate(sequences, actions, costs)
        if score[0]:
            assert score == (components["unserved_customers"],
                             components["screened_zero_option_customers"],
                             components["screened_one_option_customers"],
                             components["control_risk"], components["time_window_risk"],
                             components["battery_risk"], components["capacity_risk"],
                             components["normalized_distance"])
        else:
            assert score == (0, components["control_risk"], components["flexibility_risk"],
                             components["activated_vehicles"], components["operational_cost"],
                             components["distance"], components["route_instability"])


def test_service_count_dominates_every_lower_objective_component():
    state, obs, config = setup((customer("A", 1), customer("B", 2)))
    problem = _FleetProblem({0: state}, obs, config, 3, 2)
    incomplete = problem.initial({0: serves("A")})
    complete = problem.initial({0: serves("A", "B")})
    assert complete.score < incomplete.score
    assert len(incomplete.score) == 8
    assert len(complete.score) == 7


def test_frozen_v1_score_values_on_simple_decision_epoch():
    state, obs, config = setup((customer("A", 1), customer("B", 2)))
    problem = _FleetProblem({0: state}, obs, config, 3, 2)
    assert problem.initial({}).score == pytest.approx((2, 0, 2, 0, 0, 0, 0, 0))
    assert problem.initial({0: serves("A")}).score == pytest.approx(
        (1, 0, 0, 0.03375, 0.01, 0.02, 0.1, 1 / 3))
    assert problem.initial({0: serves("A", "B")}).score == pytest.approx(
        (0, 0.03375, 0.068125, 1, 0.10416666666666666, 4, 0))
