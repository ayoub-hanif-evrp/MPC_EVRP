"""Focused checks for paired, parent-clustered paper summaries."""

from types import SimpleNamespace

import pytest

from scripts import render_final_cpu_paper as paper
from scripts.render_final_cpu_paper import METHODS, aggregate, cluster_ci, paired


def row(parent, case, method, served, total=100):
    return dict(parent=parent, case=case, method=method,
                features=dict(served=served, total=total,
                              complete=int(served == total), wall=1.0, cpu=0.5))


def test_paired_requires_all_five_methods():
    rows = [row("c1", ("c1", .5, 1), method, 99) for method in METHODS[:-1]]
    with pytest.raises(ValueError, match="Missing method"):
        paired(rows)


def test_paired_rejects_duplicate_method():
    rows = [row("c1", ("c1", .5, 1), method, 99) for method in METHODS]
    with pytest.raises(ValueError, match="Duplicate method"):
        paired(rows + [rows[0]])


def test_cluster_bootstrap_resamples_parents_not_scenarios():
    rows = []
    for parent, mcts in (("c1", 90), ("r1", 100)):
        for seed in (1, 2, 3):
            case = (parent, .5, seed)
            for method in METHODS:
                served = mcts if method == "MPC_MCTS" else 90
                rows.append(row(parent, case, method, served))
    result = cluster_ci(paired(rows), "MPC_MCTS", "MPC_COMPLETION", seed=11)
    assert result["parents"] == 2
    assert result["scenarios"] == 6
    assert result["effect"] == 5
    assert (result["wins"], result["ties"], result["losses"]) == (3, 3, 0)
    assert result["low"] == 0
    assert result["high"] == 10


def test_customer_weighted_aggregate_uses_denominators():
    rows = [row("c1", ("a", .5, 1), "MPC_MCTS", 25, total=25),
            row("r1", ("b", .5, 1), "MPC_MCTS", 50, total=100)]
    result = aggregate(rows)
    assert result["served"] == 75
    assert result["total"] == 125
    assert result["service"] == 60
    assert result["complete_rate"] == 50


def test_paired_primary_endpoints_recompute_denominators_with_whole_parent_clusters():
    rows = []
    for parent, total, seeds in (("small", 25, (1, 2, 3)), ("large", 100, (1,))):
        for seed in seeds:
            for method in METHODS:
                wins = (parent == "small") == (method == "MPC_MCTS")
                rows.append(row(parent, (parent, seed), method, total if wins else 0, total))
    groups = paired(rows)
    service = cluster_ci(groups, "MPC_MCTS", "MPC_COMPLETION",
                         endpoint="customer_weighted_service")
    complete = cluster_ci(groups, "MPC_MCTS", "MPC_COMPLETION", endpoint="complete_service")
    parent_equal = cluster_ci(groups, "MPC_MCTS", "MPC_COMPLETION")
    assert service["effect"] == pytest.approx(100 * (75 - 100) / 175)
    assert complete["effect"] == 50
    assert parent_equal["effect"] == 0
    for result in (service, complete, parent_equal):
        assert (result["parents"], result["scenarios"]) == (2, 4)
        assert (result["low"], result["high"]) == (-100, 100)
        assert (result["wins"], result["ties"], result["losses"]) == (3, 0, 1)
    assert service == cluster_ci(groups, "MPC_MCTS", "MPC_COMPLETION",
                                 endpoint="customer_weighted_service")


def test_completion_contrast_counts_completion_changes_not_service_changes():
    rows = [row("p", ("p", 1), method, 99 if method == "MPC_MCTS" else 98)
            for method in METHODS]
    result = cluster_ci(paired(rows), "MPC_MCTS", "MPC_COMPLETION", endpoint="complete_service")
    assert (result["effect"], result["low"], result["high"]) == (0, 0, 0)
    assert (result["wins"], result["ties"], result["losses"]) == (0, 1, 0)


def test_cluster_ci_rejects_mismatched_denominators():
    rows = [row("p", ("p", 1), method, 20, total=25 if method == "MPC_MCTS" else 100)
            for method in METHODS]
    with pytest.raises(ValueError, match="denominator mismatch"):
        cluster_ci(paired(rows), "MPC_MCTS", "MPC_COMPLETION",
                   endpoint="customer_weighted_service")


@pytest.mark.parametrize("before_battery, distance", [(8.0, 1.0), (2.0, 0.0)])
def test_battery_minimum_includes_arrival_and_initial_charge_state(monkeypatch, before_battery, distance):
    instance = SimpleNamespace(
        customers=[SimpleNamespace(id="C1", due=100)],
        infrastructure=SimpleNamespace(parameters=None),
        geometry=SimpleNamespace(by_id={"D0": object(), "S1": object()}))
    monkeypatch.setattr(paper, "travel_time", lambda *args: 1.0)
    monkeypatch.setattr(paper, "energy", lambda *args: 6.0)
    metrics = dict.fromkeys(("battery_violations", "capacity_violations",
                            "time_window_violations", "hidden_information_violations",
                            "duplicate_service_violations"), 0)
    metrics.update(customers_served=0, complete_service=False, total_distance=distance,
                   total_charging_time=8, total_energy_charged=8, total_waiting_time=0,
                   vehicles_activated=1, feasible=True)
    raw = dict(metrics=metrics, unserved_customers=["C1"],
               decisions=[dict(optimization_latency_seconds=.1)], steps=[dict(
                   before=dict(battery=before_battery, location=dict(id="D0")),
                   after=dict(id=0, battery=10.0, time=9, location=dict(id="S1")),
                   distance=distance, energy_charged=8.0, served=None)])
    features = paper.physical_features(raw, instance, 1.0, .5)
    assert features["battery_min"] == 2.0


def test_attempted_cpu_includes_failed_attempt_and_retry():
    initial = dict(jobs=[dict(id="a", status="complete", cpu_seconds=10),
                         dict(id="b", status="incomplete", cpu_seconds=7)])
    correction = dict(jobs=[dict(id="b", status="complete", cpu_seconds=12)])
    assert paper.attempted_cpu_seconds(initial, correction) == 29


@pytest.mark.parametrize("value", [None, float("nan"), -1])
def test_attempted_cpu_does_not_silently_treat_unmeasured_attempts_as_zero(value):
    with pytest.raises(ValueError, match="missing or invalid"):
        paper.attempted_cpu_seconds(dict(jobs=[dict(status="incomplete", cpu_seconds=value)]))


def test_unconditional_operations_keeps_incomplete_runs_and_cohorts_separate():
    cohorts = []
    for cohort, distances in (("primary", (10, 30)), ("replication", (100,))):
        rows = []
        for method in METHODS:
            for index, distance in enumerate(distances):
                item = row(cohort, (cohort, index), method, 100 if index == 0 else 50)
                item["features"].update(dict.fromkeys(paper.OPERATIONAL_FIELDS, 0.0))
                item["features"].update(distance=distance, tw_margin_min=4 if index == 0 else None)
                rows.append(item)
        cohorts.append((cohort, rows))
    output = paper.unconditional_operations(cohorts)
    assert len(output) == 2 * len(METHODS)
    primary, replication = output[0], output[len(METHODS)]
    assert primary[:6] == ["primary", "COMPLETION", 2, "150/200", 1, "20.00"]
    assert replication[:6] == ["replication", "COMPLETION", 1, "100/100", 1, "100.00"]
    margin_index = paper.OPERATIONAL_FIELDS.index("tw_margin_min")
    assert primary[5 + margin_index] == "4.00"
    assert primary[5 + len(paper.OPERATIONAL_FIELDS) + margin_index] == 1
