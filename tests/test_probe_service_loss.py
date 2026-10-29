"""Safeguards for the retrospective, bounded SLAD feasibility probe."""

from dataclasses import replace
from time import perf_counter

import pytest

from evrp.fleet_mcts import _FleetProblem
from evrp.instance import Location, load_instance
from evrp.model import Action
from evrp.storage import BENCHMARK, identifier, load_json
from scripts.experiments import probe_service_loss as probe
from scripts.experiments.paths import artifact_path
from tests.test_repair import customer, setup


def toy_problem(*, station=False):
    stations = (Location("S", "f", 2, 0, 0, 0, 100, 0),) if station else ()
    state, observation, config = setup((customer("A", 5, due=20),
                                        customer("B", 2, due=100, service=1)),
                                       stations=stations, battery=20)
    origins = {0: state, 1: replace(state, id=1)}
    return _FleetProblem(origins, observation, config, 3, 2)


def test_recorded_state_reconstruction_hides_future_and_checks_source_hashes():
    protocol = load_json(probe.SOURCE / "protocol.json")
    manifest = load_json(probe.SOURCE / "manifest.json")
    source = load_json(probe.INSTRUMENTED / "manifest.json")
    records = {r["root"].rsplit("/", 1)[-1][:-5]: r for r in manifest["records"]}
    raw = {r["raw"]: r for r in source["records"]}
    root, problem, _, entry, unserved = probe.load_root(probe.ROOT_NAMES[0], records, raw,
                                                       identifier(protocol))
    visible = {c["id"] for c in root["observation"]["customers"]}
    all_ids = {c.id for c in load_instance(BENCHMARK / (root["instance"] + ".txt")).customers}
    assert visible == set(problem.observation.customer_by_id)
    assert all_ids - visible
    assert not (all_ids - visible) & problem.pending
    assert root["selected_targets"][0]["customer"] in visible & unserved
    assert entry["sha256"] == probe._hash(probe.ROOT / entry["root"])


def test_witness_replays_physics_and_cannot_change_busy_vehicle():
    problem = toy_problem()
    baseline = problem.initial({1: (Action("serve", "B"),)})
    candidate = problem.change(baseline, {0: ("A",)})
    assert candidate is not None
    proof = probe.validate_witness(problem, baseline, candidate, {0}, "A")
    assert "A" in proof["0"]["served"]
    assert proof["1"]["actions"] == [dict(kind="serve", destination="B",
                                           target_battery=0.0, wait_duration=0.0)]
    tampered = replace(candidate, actions=(candidate.actions[0], (Action("serve", "A"),)))
    with pytest.raises(ValueError, match="busy"):
        probe.validate_witness(problem, baseline, tampered, {0}, "A")


@pytest.mark.parametrize("invalid", ["battery", "load", "time_window", "charging", "return"])
def test_witness_rejects_physical_violations(invalid):
    problem = toy_problem(station=True)
    baseline = problem.initial({})
    candidate = problem.change(baseline, {0: ("A",)})
    assert candidate is not None
    if invalid == "battery":
        problem.origins[0] = replace(problem.origins[0], battery=1)
    elif invalid == "load":
        problem.origins[0] = replace(problem.origins[0], load=0)
    elif invalid == "time_window":
        altered = tuple(replace(c, due=1) if c.id == "A" else c
                        for c in problem.observation.customers)
        problem.observation = replace(problem.observation, customers=altered)
    elif invalid == "charging":
        candidate = replace(candidate, actions=((Action("charge", "S", target_battery=999),
                                                 Action("serve", "A")), candidate.actions[1]))
    else:
        depot = replace(problem.observation.infrastructure.depot, due=5)
        infra = replace(problem.observation.infrastructure, depot=depot)
        problem.observation = replace(problem.observation, infrastructure=infra)
    with pytest.raises(ValueError):
        probe.validate_witness(problem, baseline, candidate, {0}, "A")


def test_direct_bound_certifies_only_after_real_commitment_and_ignores_wait():
    state, observation, _ = setup((customer("A", 5, due=6),
                                   customer("B", 2, due=100, service=10)))
    assert not probe.timing_bound({0: state}, observation, "A")["certified"]
    after = probe.timing_bound({0: state}, observation, "A", {0: Action("serve", "B")})
    assert after["certified"] and after["reason"] == "all_direct_arrivals_after_due"
    wait = probe.timing_bound({0: state}, observation, "A", {0: Action("wait", wait_duration=20)})
    assert not wait["certified"] and wait["ignored_interruptible_waits"] == [0]
    late = replace(observation, customers=(replace(observation.customers[0], due=4),
                                           observation.customers[1]))
    assert probe.timing_bound({0: state}, late, "A")["certified"]


def test_candidate_order_is_deterministic_and_limited():
    problem = toy_problem()
    plan = problem.initial({})
    first = probe.candidate_options(problem, plan, {0, 1}, "A")
    assert first == probe.candidate_options(problem, plan, {0, 1}, "A")
    assert first == [(0, 0), (1, 0)]
    assert len(first) <= probe.MAX_CANDIDATES


def test_bounded_decoder_failure_is_inconclusive(monkeypatch):
    problem = toy_problem()
    root = dict(selected_targets=[dict(customer="A", selection="test")],
                ready_vehicles=[0, 1], initial_routes={}, instance="toy", time=0,
                source_raw="recorded", source_raw_sha256="hash", busy_actions={})
    monkeypatch.setattr(probe, "candidate_options", lambda *args: [(0, 0)])
    monkeypatch.setattr(problem, "change", lambda *args: None)
    entry = dict(root="root.json", sha256="hash")
    row = probe.probe_root(root, problem, dict(plans={}), entry, {"A"}, perf_counter() + 1)
    assert row["status"] == "NO_WITNESS_FOUND"
    assert row["candidates"][0]["status"] == "BOUNDED_DECODER_FAILURE"
    assert not row["before_bound"]["certified"]


def test_validation_output_path_rejects_overwrite_and_traversal(tmp_path):
    path = artifact_path(probe.STUDY, "validation", "report.json", tmp_path)
    assert path.is_relative_to(tmp_path / "results" / "research_v2")
    path.parent.mkdir(parents=True)
    path.write_text("preserve")
    with pytest.raises(FileExistsError):
        artifact_path(probe.STUDY, "validation", "report.json", tmp_path)
    with pytest.raises(ValueError):
        artifact_path(probe.STUDY, "validation", "../report.json", tmp_path)
    assert path.read_text() == "preserve"
