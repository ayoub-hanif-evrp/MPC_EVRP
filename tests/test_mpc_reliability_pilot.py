"""Pilot admission and evidence tests without benchmark optimization runs."""

from copy import deepcopy
import json

import pytest

from scripts.experiments import run_mpc_reliability_pilot as pilot


def model():
    return dict(strata=[dict(size=size, method=method, cap_seconds=60, storage_cap=65536)
                       for size in (25, 50, 100) for method in pilot.METHODS])


def test_five_original_methods_share_every_other_setting():
    configs = pilot.shared_configs()
    assert set(configs) == {"MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"}
    common = [{k: v for k, v in config.items() if k != "algorithm"} for config in configs.values()]
    assert all(config == common[0] for config in common)
    assert common[0]["total_planning_time_limit"] == 5
    assert all(common[0][key] == "original" for key in pilot.POLICIES)
    with pytest.raises(ValueError, match="original"):
        pilot.original_options("MPC_ALNS_SAFE_INIT_V1")


def test_only_ten_jobs_are_admitted_and_full_design_is_separate():
    jobs = pilot.jobs_for([dict(size=25), dict(size=100)], model())
    assert len(jobs) == len({j["id"] for j in jobs}) == 10
    assert [j["method"] for j in jobs[:5]] == list(pilot.METHODS)
    assert [j["method"] for j in jobs[5:]] == list(reversed(pilot.METHODS))
    assert pilot.allowance(jobs)["admitted"]
    assert not pilot.allowance(jobs, limit=1000)["admitted"]
    assert not pilot.allowance(jobs, storage_limit=1)["admitted"]
    assert len(pilot.jobs_for([dict(size=25)] * 54, model())) == 270


def fixture():
    config = pilot.shared_configs()["MPC_ALNS"]
    spec = dict(id="pilot_0_MPC_ALNS", case_index=0, method="MPC_ALNS")
    data = dict(protocol_identifier="protocol", protocol=dict(source_sha256="source",
        configs={"MPC_ALNS": config}, cases=[dict(scenario_id="scenario", k_ref=2)]))
    raw = dict(id=spec["id"], protocol_identifier="protocol", config_sha256=pilot.identifier(config),
        audit=dict(physical=True, information=True), result=dict(effective_config=config,
        metadata=dict(source_sha256="source", algorithm="MPC_ALNS", scenario_identifier="scenario", K_ref=2),
        metrics=dict(max_optimization_latency=4.9)))
    return data, spec, raw


def test_raw_configuration_identity_survives_json_transport():
    data, spec, raw = fixture()
    pilot.verify_result(json.loads(json.dumps(data)), spec, raw)
    bad = deepcopy(raw)
    bad["result"]["effective_config"]["total_planning_time_limit"] = 6
    with pytest.raises(ValueError, match="gates"):
        pilot.verify_result(data, spec, bad)
    bad = deepcopy(raw)
    bad["audit"]["information"] = False
    with pytest.raises(ValueError, match="gates"):
        pilot.verify_result(data, spec, bad)


def test_outcomes_and_failure_evidence_are_never_overwritten(tmp_path, monkeypatch):
    output = tmp_path / "study"
    monkeypatch.setattr(pilot, "OUTPUT", output)
    data, spec, _ = fixture()
    data["protocol"]["jobs"] = [spec]
    data["protocol"]["cases"][0]["instance"] = "toy"
    monkeypatch.setattr(pilot, "frozen", lambda: data)
    def fail(name):
        raise RuntimeError("recorded failure")
    monkeypatch.setattr(pilot, "prepare_case", fail)
    with pytest.raises(RuntimeError, match="recorded failure"):
        pilot.worker(0, "MPC_ALNS")
    path = output / "failures" / (spec["id"] + ".json")
    saved = path.read_bytes()
    record = json.loads(saved)
    assert record["protocol_identifier"] == "protocol" and record["error_type"] == "RuntimeError"
    with pytest.raises(FileExistsError):
        pilot.worker(0, "MPC_ALNS")
    assert path.read_bytes() == saved
    path = tmp_path / "protocol.json"
    pilot.exclusive(path, {"version": 1})
    with pytest.raises(FileExistsError):
        pilot.exclusive(path, {"version": 2})


def test_duplicate_supervisor_cannot_start_and_owned_lock_is_released(tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, "OUTPUT", tmp_path)
    monkeypatch.setattr(pilot, "frozen", lambda: {})
    monkeypatch.setattr(pilot, "_run_pilot", lambda: None)
    lock = tmp_path / "supervisor.lock"
    lock.write_text("other-supervisor")
    with pytest.raises(FileExistsError):
        pilot.run_pilot()
    assert lock.read_text() == "other-supervisor"
    lock.unlink()
    pilot.run_pilot()
    assert not lock.exists()
