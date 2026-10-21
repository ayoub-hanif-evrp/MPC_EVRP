"""Replay release legality at the actual dispatch time, not rounded wait time."""

from dataclasses import replace

import pytest

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.model import InfeasibleAction
from evrp.simulator import EventDrivenSimulator
from scripts.run_desaulniers_final import CONFIG, options


def test_dispatch_time_roundoff_does_not_false_flag_hidden_information():
    config = load_config(CONFIG)
    run_options = options(config, "c109_21_25", 0.75, 0, "MPC_COMPLETION")
    instance, _reference, scenario, _path = prepare("c109_21_25", run_options)
    result = EventDrivenSimulator(instance, scenario, simulation_config(run_options)).run()

    release = dict(scenario.customer_release_times)["C59"]
    step = next(s for s in result.steps if s.served == "C59")
    dispatch = next(e for e in result.events if e.kind == "dispatch" and e.customer_id == "C59")
    assert step.before.time < release == dispatch.time
    assert all(audit_result(result, instance, scenario).values())

    delayed = replace(scenario, customer_release_times=tuple(
        (key, release + 0.01 if key == "C59" else time)
        for key, time in scenario.customer_release_times))
    with pytest.raises(InfeasibleAction, match="unavailable"):
        audit_result(result, instance, delayed)
