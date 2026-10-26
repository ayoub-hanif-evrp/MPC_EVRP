"""Focused invariants for the opt-in fast framework."""

from time import perf_counter

from evrp import proposal_memo
from evrp.compute_policy import AdaptiveComputeGate, stable_full_service
from evrp.fleet_mcts import _FleetProblem
from evrp.repair import build_route, route_proposal
from evrp.targeted_recovery import service_guard_v1
from tests.test_repair import customer, setup


def test_fast_screen_preserves_all_operational_bounds():
    state, observation, config = setup((customer("A", 2, due=20),
                                         customer("B", 4, due=30),
                                         customer("C", 7, due=40)))
    baseline = _FleetProblem({0: state}, observation, config, 3, 2)
    memo, token = proposal_memo.begin(incremental=True, fast_screen=True)
    try:
        fast = _FleetProblem({0: state}, observation, config, 3, 2)
        for sequence in ((), ("A",), ("A", "B"), ("B", "A")):
            assert tuple(fast._screen_profile(0, sequence)) == tuple(baseline._screen_profile(0, sequence))
            for target in {"A", "B", "C"} - set(sequence):
                for position in range(len(sequence) + 1):
                    assert fast._screen_gap_detail(0, sequence, target, position) == baseline._screen_gap_detail(
                        0, sequence, target, position)
        assert fast._screen_profile(0, ("A", "B")).safe_return_energy == ()
        assert memo.fast_screen
    finally:
        proposal_memo.end(token)


def test_mcts_rollout_skips_uninsertable_customer():
    state, observation, config = setup((customer("A", 40, due=1), customer("B", 2, due=100)))
    problem = _FleetProblem({0: state}, observation, config, 3, 2)
    root = problem.initial({0: ()})
    assert [(c, count) for c, count, *_ in problem._criticality(root.sequences)] == [("A", 0), ("B", 1)]
    assert problem.complete_rollout(root, perf_counter() + 1).score[0] == 2
    problem.rollout_skip_blocked = True
    improved = problem.complete_rollout(root, perf_counter() + 1)
    assert improved.score[0] == 1
    assert route_proposal(state, improved.actions[0], observation, config) is not None


def test_adaptive_gate_requires_full_service_slack_and_minimum_work():
    state, observation, config = setup((customer("A", 2, due=20),))
    routes = {0: build_route(state, ("A",), observation, config)}
    eligible, reason = stable_full_service({0: state}, routes, observation)
    assert (eligible, reason) == (True, "full_service_with_slack")
    gate = AdaptiveComputeGate(eligible, reason, started=0)
    gate.observe((0, 1.0), now=0)
    assert not gate.should_stop(1, now=2)
    assert not gate.should_stop(2, now=.8)
    assert gate.should_stop(2, now=1.2)
    assert gate.report()["stopped_early"]
    unavailable, _ = stable_full_service({0: state}, {0: ()}, observation)
    assert not unavailable
    low_state, low_observation, low_config = setup((customer("X", 2, due=2),))
    low_route = build_route(low_state, ("X",), low_observation, low_config)
    assert not stable_full_service({0: low_state}, {0: low_route}, low_observation)[0]


def test_service_guard_recovers_last_observable_urgent_option():
    state, observation, config = setup((customer("A", 2, due=4), customer("B", -2, due=100)))
    selected = {0: build_route(state, ("B",), observation, config)}
    repaired, proof, record = service_guard_v1({0: state}, selected, observation, config, {0})
    assert record["triggered"] and record["accepted"] and record["candidates"] <= 2
    assert [action.destination for action in repaired[0] if action.kind == "serve"] == ["A", "B"]
    assert proof[0] == route_proposal(state, repaired[0], observation, config)
