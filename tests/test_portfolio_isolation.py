"""Campaign process isolation must make optimizer order irrelevant."""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.run_portfolio_campaign as campaign


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = """
import json, os, sys
from evrp.experiments import audit_result, simulation_config
from evrp.simulator import EventDrivenSimulator
from tests.test_simulator import synthetic
base = synthetic(release=5, fleet=2)
config = simulation_config(dict(algorithm=sys.argv[1], total_planning_time_limit=1.0,
                                fleet_mcts_iterations=4, fleet_mcts_depth=2,
                                fleet_mcts_branch_limit=4))
result = EventDrivenSimulator(base.instance, base.scenario, config).run()
audit_result(result, base.instance, base.scenario)
print(json.dumps(dict(pid=os.getpid(), served=result.metrics['customers_served'],
                      vehicles=result.metrics['vehicles_activated'],
                      distance=result.metrics['total_distance'],
                      actions=[(s.before.id, s.action.kind, s.action.destination)
                               for s in result.steps])))
"""


def test_fresh_process_results_are_order_invariant():
    def execute(order):
        return {method: json.loads(subprocess.check_output(
            [sys.executable, "-c", SCRIPT, method], cwd=ROOT, text=True))
                for method in order}

    forward = execute(("MPC_COMPLETION", "MPC_MCTS"))
    reverse = execute(("MPC_MCTS", "MPC_COMPLETION"))
    assert len({row["pid"] for row in (*forward.values(), *reverse.values())}) == 4
    for method in forward:
        assert {k: v for k, v in forward[method].items() if k != "pid"} == {
            k: v for k, v in reverse[method].items() if k != "pid"}


def test_failed_worker_preserves_raw_diagnostic_outside_authoritative_manifest(monkeypatch):
    @dataclass
    class FakeResult:
        metadata: dict
        metrics: dict

    result = FakeResult({}, {})
    saved = []
    study = dict(methods=["MPC_ALNS"], base_controller="configs/paper_controller.yaml",
                 total_planning_time_limit=5.0)
    monkeypatch.setattr(campaign, "load_config", lambda path: study if path == campaign.CONFIG_PATH else {})
    monkeypatch.setattr(campaign, "prepare", lambda *args: (
        object(), None, SimpleNamespace(fleet_size=1), None))
    monkeypatch.setattr(campaign, "simulation_config", lambda options: options)
    monkeypatch.setattr(campaign, "EventDrivenSimulator", lambda *args: SimpleNamespace(run=lambda: result))
    monkeypatch.setattr(campaign, "audit_result", lambda *args: (_ for _ in ()).throw(
        AssertionError("diagnostic failure")))
    monkeypatch.setattr(campaign, "source_hash", lambda: "frozen-test-source")
    monkeypatch.setattr(campaign, "save_json", lambda path, data: saved.append((path, data)))
    output = ROOT / "results/portfolio/development/raw/fake_MPC_ALNS.json.gz"
    with pytest.raises(AssertionError, match="diagnostic failure"):
        campaign.run_worker("fake", 0.25, 2, "MPC_ALNS", output)
    assert len(saved) == 1
    assert saved[0][0] == campaign.failure_path(output)
    assert saved[0][1]["metadata"]["failed_audit"]["source_sha256"] == "frozen-test-source"
    assert saved[0][1]["metadata"]["failed_audit"]["message"] == "diagnostic failure"
