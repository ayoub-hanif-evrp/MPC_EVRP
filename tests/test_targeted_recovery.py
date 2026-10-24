from dataclasses import replace

from evrp import targeted_recovery as targeted
from evrp.planning_budget import PlanningDeadlineExceeded, remaining_time
from tests.test_repair import customer, setup


def problem():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    return {0: state, 1: replace(state, id=1)}, observation, config


def test_true_regret_constructor_only_accepts_canonical_valid_improvements():
    origins, observation, config = problem()
    routes, validated, record = targeted.improve_constructor(origins, {}, observation, config, seconds=1)
    assert record["selected_score"] < record["initial_score"]
    assert {a.destination for actions in routes.values() for a in actions if a.kind == "serve"} == {"A", "B"}
    assert all(proposal.actions == routes[k] for k, proposal in validated.items())
    assert remaining_time() == float("inf")


def test_counterfactuals_only_dispatch_ready_evs_and_use_visible_requests():
    origins, observation, config = problem()
    before = dict(origins)
    routes, proof, record = targeted.counterfactual_actions(origins, {}, observation, config, {0},
                                                          seconds=1, diagnostic=True)
    assert record["selected_score"] < record["initial_score"]
    assert record["candidates"] and all(row["vehicle"] == 0 for row in record["candidates"])
    assert all(a.destination in observation.customer_by_id for route in routes.values()
               for a in route if a.kind == "serve")
    assert origins == before
    assert all(proposal.actions == routes[k] for k, proposal in proof.items())


def test_constructor_keeps_validated_progress_when_recovery_deadline_expires(monkeypatch):
    origins, observation, config = problem()

    def interrupted(problem, initial, record, rounds=3, on_progress=None):
        candidate = problem.change(initial, {0: ("A",)})
        on_progress(candidate, targeted._validated(problem, candidate))
        raise PlanningDeadlineExceeded

    monkeypatch.setattr(targeted, "_recover", interrupted)
    routes, proof, record = targeted.improve_constructor(origins, {}, observation, config, seconds=1)
    assert record["deadline_reached"]
    assert routes[0][-1].destination == "A"
    assert proof[0].actions == routes[0]
    assert remaining_time() == float("inf")


def test_expired_counterfactual_probe_restores_deadline_and_preserves_incumbent():
    origins, observation, config = problem()
    original = {0: (), 1: ()}
    routes, proof, record = targeted.counterfactual_actions(origins, original, observation, config,
                                                          {0}, seconds=1e-9)
    assert routes == original and proof is None and record["deadline_reached"]
    assert remaining_time() == float("inf")
