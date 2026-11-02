from copy import deepcopy

import pytest

from scripts.experiments.analyze_mpc_reliability_pilot import summarize


def fixture():
    raw = dict(worker_wall_seconds=2, worker_cpu_seconds=1, audit=dict(physical=True),
        result=dict(metrics=dict(customers_served=1, total_distance=1, total_charging_time=0,
            total_energy_charged=0, vehicles_activated=1, max_optimization_latency=4,
            total_deadline_events=2, optimizer_initialization_fallbacks=0),
            steps=[dict(served="A", action=dict(kind="serve"), before=dict(battery=10),
                        after=dict(battery=9), energy_charged=0)],
            decisions=[dict(optimization_latency_seconds=4, optimizer=dict(deadline_reached=True))]))
    info = dict(instance="toy", parent="toy", size=2)
    spec = dict(id="test", case_index=0, method="MPC_ALNS")
    return raw, info, spec


def test_missing_legacy_counter_is_explicitly_unavailable_and_raw_stays_unchanged():
    raw, info, spec = fixture()
    saved = deepcopy(raw)
    row, served = summarize(raw, info, spec)
    assert row["validated_fallbacks"] is None
    assert row["fallback_counter_availability"] == "not recorded by this frozen method"
    assert row["deadline_events"] == 2 and row["optimizer_deadline_decisions"] == 1
    assert row["p95_latency"] == row["max_latency"] == 4
    assert served == ["A"] and raw == saved


def test_explicit_zero_is_not_confused_with_missing_and_bad_counts_are_rejected():
    raw, info, spec = fixture()
    raw["result"]["metrics"]["deadline_fallback_count"] = 0
    assert summarize(raw, info, spec)[0]["validated_fallbacks"] == 0
    raw["result"]["metrics"]["customers_served"] = 2
    with pytest.raises(ValueError, match="inconsistent"):
        summarize(raw, info, spec)
