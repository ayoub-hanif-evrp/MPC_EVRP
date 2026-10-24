from dataclasses import replace
from time import perf_counter

import pytest

from evrp import flex_exchange, proposal_memo
from evrp.experiments import audit_result
from evrp.fleet_mcts import _FleetProblem
from evrp.model import Action, Observation
from evrp.planning_budget import PlanningDeadlineExceeded, remaining_time, reset_deadline, set_deadline
from evrp.repair import route_proposal
from evrp.simulator import EventDrivenSimulator, SimulationConfig
from scripts.diagnose_reliability_events import measured_origins
from tests.test_repair import customer, setup
from tests.test_simulator import synthetic


def test_memo_is_root_local_exact_and_checks_expired_deadline():
    state, observation, config = setup((customer("A", 1),))
    actions = (Action("serve", "A"),)
    expected = route_proposal(state, actions, observation, config)
    memo, token = proposal_memo.begin()
    try:
        assert route_proposal(state, actions, observation, config) == expected
        assert route_proposal(state, actions, observation, config) == expected
        assert memo.hits == 1 and memo.misses == 1
        assert route_proposal(state, actions, Observation(0, observation.infrastructure, ()), config) is None
        assert memo.misses == 2
        deadline = set_deadline(perf_counter()-1)
        try:
            with pytest.raises(PlanningDeadlineExceeded):
                route_proposal(state, actions, observation, config)
        finally:
            reset_deadline(deadline)
    finally:
        proposal_memo.end(token)
    assert proposal_memo.current() is None
    another, token = proposal_memo.begin()
    try:
        assert not another.values
    finally:
        proposal_memo.end(token)


def test_exchange_neighborhood_preserves_ownership_and_never_changes_busy_heads():
    state, observation, config = setup((customer("A", 1), customer("B", 2), customer("C", 3)))
    problem = _FleetProblem({0: state, 1: replace(state, id=1)}, observation, config, 3, 2)
    plan = problem.initial({0: (Action("serve", "A"),), 1: (Action("serve", "B"),)})
    moves = list(flex_exchange.exchange_changes(problem, plan, {0, 1}))
    assert {0: ("B",), 1: ("A",)} in moves
    assert any("C" in s for move in moves for s in move.values())
    for move in moves:
        sequences = [move.get(k, plan.sequences[i]) for i, k in enumerate(problem.ids)]
        customers = [c for sequence in sequences for c in sequence]
        assert {"A", "B"} <= set(customers)
        assert len(customers) == len(set(customers))
    assert not any(move.get(1, ("B",))[0] != "B" and "C" not in move.get(0, ())
                   for move in flex_exchange.exchange_changes(problem, plan, {0}))


def test_exchange_strict_canonical_acceptance_and_deadline_fallback():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    origins = {0: state, 1: replace(state, id=1)}
    routes = {0: (Action("serve", "A"),), 1: ()}
    result, proof, record = flex_exchange.improve_first_controls(origins, routes, observation, config, {0, 1}, seconds=1)
    assert record["selected_score"] < record["initial_score"]
    assert {a.destination for r in result.values() for a in r} == {"A", "B"}
    assert all(p.actions == result[k] for k, p in proof.items())
    result, proof, record = flex_exchange.improve_first_controls(origins, routes, observation, config, {0, 1}, seconds=1e-10)
    assert result == routes and proof is None and record["deadline_reached"]
    assert remaining_time() == float("inf")


def test_exchange_keeps_validated_incumbent_if_next_candidate_times_out(monkeypatch):
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    origins = {0: state, 1: replace(state, id=1)}
    routes = {0: (Action("serve", "A"),), 1: ()}
    def interrupted(*args):
        yield {1: ("B",)}
        raise PlanningDeadlineExceeded
    monkeypatch.setattr(flex_exchange, "exchange_changes", interrupted)
    result, proof, record = flex_exchange.improve_first_controls(origins, routes, observation, config, {0, 1})
    assert proof is not None and result[1] == (Action("serve", "B"),)
    assert record["deadline_reached"] and record["selected_score"] < record["initial_score"]
    assert remaining_time() == float("inf")


def test_idle_waits_are_interruptible_in_event_bounds():
    from dataclasses import asdict
    state, _, _ = setup(())
    step = dict(before=asdict(state), after=asdict(replace(state, time=10)),
                action=asdict(Action("wait", wait_duration=10)))
    origins, busy = measured_origins([step], 5)
    assert origins[0].time == 5 and not busy
    step["action"] = asdict(Action("charge", "S", 100))
    origins, busy = measured_origins([step], 5)
    assert origins[0].time == 10 and 0 in busy


@pytest.mark.parametrize("method", ["MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"])
@pytest.mark.parametrize("variant", ["memo", "exchange"])
def test_all_engines_keep_physics_information_and_budget(method, variant):
    fixture = synthetic(release=5, fleet=2)
    config = SimulationConfig(algorithm=method, total_planning_time_limit=5,
                              optimizer_initialization_policy="validated_incumbent_v1",
                              coordination_policy="forced_retained_v1", proposal_cache_policy="root_v1",
                              first_action_policy="flex_exchange_v2" if variant == "exchange" else "original")
    result = EventDrivenSimulator(fixture.instance, fixture.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert result.metrics["max_optimization_latency"] <= 5
    assert all(audit_result(result, fixture.instance, fixture.scenario).values())
    assert proposal_memo.current() is None
    assert any(d.get("proposal_memo") for d in result.decisions)
