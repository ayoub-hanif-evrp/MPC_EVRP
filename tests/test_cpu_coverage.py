"""Mission accounting must include failed attempts and cannot reset on continuation."""

import pytest

from scripts import complete_cpu_coverage as coverage


def test_allowance_obeys_both_original_mission_caps():
    assert coverage.allowances([dict(charged_seconds=28000, worker_cpu_seconds=100)]) == 800
    assert coverage.allowances([dict(charged_seconds=100, worker_cpu_seconds=43000)]) == 200
    assert coverage.allowances([dict(charged_seconds=14000, worker_cpu_seconds=14000)]) == 4200
    with pytest.raises(ValueError, match="exhausted"):
        coverage.allowances([dict(charged_seconds=28800, worker_cpu_seconds=100)])


def test_accounting_includes_failed_worker_cpu(monkeypatch):
    def read(path):
        if path.name == "budget.json":
            return dict(charged_seconds=100, jobs=[
                dict(status="complete", cpu_seconds=20, elapsed_seconds=22),
                dict(status="incomplete", cpu_seconds=70, elapsed_seconds=78)])
        return dict(status="complete", total_elapsed_seconds=10,
                    modes=dict(sequential=dict(results=[dict(cpu_seconds=4)]),
                               two_workers=dict(results=[dict(cpu_seconds=3)])))
    monkeypatch.setattr(coverage, "load_json", read)
    monkeypatch.setattr(coverage, "digest", lambda path: "frozen")
    rows = coverage.prior_accounting()
    assert sum(row["worker_cpu_seconds"] for row in rows) == 277
    assert sum(row["charged_seconds"] for row in rows) == 310
    assert all(row["attempts"] == 2 for row in rows[:3])


def test_accounting_refuses_an_active_campaign(monkeypatch):
    monkeypatch.setattr(coverage, "load_json", lambda path: dict(jobs=[dict(status="running")]))
    with pytest.raises(ValueError, match="still running"):
        coverage.prior_accounting()
