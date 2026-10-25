import pytest

from scripts import launch_reliability_study as launcher
from scripts.report_reliability_compute import estimate_remaining


def test_user_stop_blocks_launch_before_protocol_or_process_access(tmp_path, monkeypatch, capsys):
    (tmp_path/"STOP_REQUESTED.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(launcher, "OUTPUT", tmp_path)
    def prohibited(*args, **kwargs):
        raise AssertionError("A stopped campaign must not load its protocol or spawn a worker")
    monkeypatch.setattr(launcher, "load_json", prohibited)
    monkeypatch.setattr(launcher.subprocess, "Popen", prohibited)
    assert launcher.main() == 0
    assert "stopped by the user" in capsys.readouterr().out


def test_cost_estimator_uses_only_unexecuted_frozen_jobs():
    protocol = dict(config={"methods": ["MPC_COMPLETION"]},
                    cases=[dict(case=["c106_21_25", .25, 0], customers=25)])
    records = [dict(case_index=0, method="MPC_COMPLETION", variant="original", process_seconds=2),
               dict(case_index=0, method="MPC_COMPLETION", variant="flex_exchange", process_seconds=4)]
    estimate = estimate_remaining(protocol, records)
    assert estimate["remaining_jobs"] == 1
    assert estimate["jobs"][0]["variant"] == "completion_first_action"
    assert estimate["mean_based_hours"] == pytest.approx(3/3600)


def test_cost_estimator_rejects_duplicate_checkpoint_rows():
    protocol = dict(config={"methods": ["MPC_COMPLETION"]},
                    cases=[dict(case=["c106_21_25", .25, 0], customers=25)])
    row = dict(case_index=0, method="MPC_COMPLETION", variant="original", process_seconds=2)
    with pytest.raises(ValueError, match="Duplicate"):
        estimate_remaining(protocol, [row, row])
