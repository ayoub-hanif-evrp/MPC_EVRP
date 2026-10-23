"""Diagnostic traces stay scoped to the released planning problem."""

from dataclasses import replace

from evrp.planning_trace import current_trace
from evrp.simulator import EventDrivenSimulator
from tests.test_simulator import synthetic


def test_planning_trace_contains_observable_root_and_candidate_evidence():
    fixture = synthetic(release=5)
    config = replace(fixture.config, algorithm="MPC_COMPLETION", planning_trace=True,
                     total_planning_time_limit=5.0, trace_level="summary")
    result = EventDrivenSimulator(fixture.instance, fixture.scenario, config).run()
    traces = [d["planning_trace"] for d in result.decisions if "planning_trace" in d]
    assert traces
    assert {c["id"] for c in traces[0]["observation"]["customers"]} == {"A"}
    assert all(set(trace["stages"]) == {"constructor", "optimizer", "validation"}
               for trace in traces)
    assert any(event["kind"] == "route_decode" for trace in traces for event in trace["events"])
    assert all(trace["dropped_events"] == 0 for trace in traces)
    for trace in traces:
        visible = {c["id"] for c in trace["observation"]["customers"]}
        for event in trace["events"]:
            assert set(event.get("sequence", ())) <= visible
            assert event.get("customer") is None or event["customer"] in visible
    assert current_trace() is None
    assert result.metrics["customers_served"] == 2
