"""Checks for post-commitment suffix replay and bounded V2 conclusions."""

from dataclasses import asdict, replace
from time import perf_counter

import pytest

from evrp.fleet_mcts import _FleetProblem, _SearchBudgetReached
from evrp.instance import Location
from evrp.model import Action, InfeasibleAction, transition
from evrp.storage import identifier, load_json
from scripts.analyze_planning_losses import routes
from scripts.experiments import probe_service_loss as v1
from scripts.experiments import probe_service_loss_v2 as v2
from scripts.experiments.paths import artifact_path
from tests.test_repair import customer, setup


@pytest.fixture(scope="module")
def frozen():
    return v2.load_contexts()[0]


def test_recorded_transitions_replay_committed_actions_and_hide_future(frozen):
    for _, early_name, late_name in v2.PAIRS:
        earlier, later = frozen[early_name], frozen[late_name]
        target, newly_busy = v2.check_transition(earlier, later)
        assert target in earlier[1].observation.customer_by_id
        assert target in later[1].observation.customer_by_id
        assert newly_busy
        for root, problem, _, _, _ in (earlier, later):
            visible = {c["id"] for c in root["observation"]["customers"]}
            assert visible == set(problem.observation.customer_by_id)
            assert set(problem.pending) <= visible
            plan = problem.initial(routes(root["initial_routes"]))
            assert v2.replay_plan(problem, plan, root)
    assert v1.timing_bound(frozen[v2.NEGATIVE][1].origins,
                           frozen[v2.NEGATIVE][1].observation, "C61")["certified"]


def toy_busy():
    state, observation, config = setup(
        (customer("A", 5, due=20), customer("B", 2, due=100, service=1)),
        stations=(Location("S", "f", 2, 0, 0, 0, 100, 0),), battery=20)
    committed = Action("serve", "B")
    after = transition(state, committed, observation).after
    problem = _FleetProblem({0: after, 1: replace(state, id=1)}, observation, config, 3, 2)
    root = dict(ready_vehicles=[1], busy_actions={"0": asdict(committed)})
    return problem, root


def test_busy_suffix_can_change_but_executing_action_cannot():
    problem, root = toy_busy()
    baseline = problem.initial({})
    candidate = problem.change(baseline, {0: ("A",)})
    assert candidate is not None
    proof = v2.replay_plan(problem, candidate, root)
    assert proof["0"]["recorded_busy_action"] == root["busy_actions"]["0"]
    assert proof["0"]["origin"] == asdict(problem.origins[0])
    assert proof["0"]["service_sequence"] == ["A"]
    assert v2.coverage_accounting(set(), {"A"}, "A")["additional_coverage"]
    assert not v2.first_action_changes(problem, candidate, dict(plans={
        "1": dict(first_action=asdict(Action("wait", wait_duration=1)))}), {1})
    tampered = dict(root, busy_actions={"0": asdict(Action("serve", "A"))})
    with pytest.raises(ValueError, match="post-action"):
        v2.replay_plan(problem, candidate, tampered)


@pytest.mark.parametrize("invalid", ["battery", "load", "time_window", "charging", "return"])
def test_replay_rejects_invalid_physics_and_unsafe_return(invalid):
    problem, root = toy_busy()
    baseline = problem.initial({})
    candidate = problem.change(baseline, {0: ("A",)})
    assert candidate is not None
    if invalid == "battery":
        problem.origins[0] = replace(problem.origins[0], battery=0)
    elif invalid == "load":
        problem.origins[0] = replace(problem.origins[0], load=0)
    elif invalid == "time_window":
        customers = tuple(replace(c, due=1) if c.id == "A" else c
                          for c in problem.observation.customers)
        problem.observation = replace(problem.observation, customers=customers)
    elif invalid == "charging":
        candidate = replace(candidate, actions=((Action("charge", "S", target_battery=999),
                                                 Action("serve", "A")), candidate.actions[1]))
    else:
        depot = replace(problem.observation.infrastructure.depot, due=5)
        infra = replace(problem.observation.infrastructure, depot=depot)
        problem.observation = replace(problem.observation, infrastructure=infra)
    with pytest.raises((ValueError, InfeasibleAction)):
        v2.replay_plan(problem, candidate, root)


def test_coverage_and_ready_first_action_accounting():
    added = v2.coverage_accounting({"B"}, {"A", "B"}, "A")
    swap = v2.coverage_accounting({"B"}, {"A"}, "A")
    assert added["additional_coverage"] and added["baseline_preserved"]
    assert added["service_delta"] == 1
    assert swap["equal_service_swap"] and not swap["additional_coverage"]
    assert swap["added"] == ["A"] and swap["dropped"] == ["B"]
    problem, _ = toy_busy()
    baseline = problem.initial({})
    candidate = problem.change(baseline, {1: ("A",)})
    assert candidate is not None
    decision = dict(plans={"1": dict(first_action=asdict(Action("wait", wait_duration=1)))})
    assert v2.first_action_changes(problem, candidate, decision, {1}) == [1]
    assert v2.first_action_changes(problem, baseline, decision, {1}) == []


def test_bounded_decoder_and_timeout_remain_inconclusive(monkeypatch):
    problem, root = toy_busy()
    baseline = problem.initial({})
    root.update(instance="toy", time=0)
    decision = dict(plans={"1": dict(first_action=asdict(Action("wait", wait_duration=1)))})
    earlier = (root, problem, decision, {}, {"A"})
    later = (root, problem, decision, {}, {"A"})
    monkeypatch.setattr(v2, "candidate_changes", lambda *args: iter([
        ("test", {0: ("A",)})]))
    monkeypatch.setattr(v2, "decode_candidate", lambda *args: (None, 0))
    result = v2.probe_later(earlier, later, "A", baseline, baseline, perf_counter() + 1)
    assert result["status"] == "NO_WITNESS_FOUND"
    assert result["candidates"][0]["status"] == "BOUNDED_SEARCH_FAILURE"
    def timeout(*args):
        raise _SearchBudgetReached
        yield
    monkeypatch.setattr(v2, "candidate_changes", timeout)
    result = v2.probe_later(earlier, later, "A", baseline, baseline, perf_counter() + 1)
    assert result["timed_out"] and result["status"] == "NO_WITNESS_FOUND"


def test_optimistic_arrival_is_not_physical_ev_feasibility():
    problem, root = toy_busy()
    assert not v1.timing_bound(problem.origins, problem.observation, "A")["certified"]
    baseline = problem.initial({})
    candidate = problem.change(baseline, {0: ("A",)})
    assert candidate is not None
    problem.origins[0] = replace(problem.origins[0], battery=0)
    with pytest.raises((ValueError, InfeasibleAction)):
        v2.replay_plan(problem, candidate, root)


def test_v2_artifacts_cannot_overwrite_v1_or_escape_workspace(tmp_path):
    v1_path = artifact_path(v1.STUDY, "validation", "report.json", tmp_path)
    v1_path.parent.mkdir(parents=True)
    v1_path.write_text("historical")
    v2_path = artifact_path(v2.STUDY, "validation", "report.json", tmp_path)
    assert v2_path != v1_path
    v2_path.parent.mkdir(parents=True)
    v2_path.write_text("new")
    with pytest.raises(FileExistsError):
        artifact_path(v2.STUDY, "validation", "report.json", tmp_path)
    with pytest.raises(ValueError):
        artifact_path(v2.STUDY, "validation", "../report.json", tmp_path)
    assert v1_path.read_text() == "historical"
