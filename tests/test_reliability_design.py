from copy import deepcopy
from dataclasses import asdict

import pytest

from evrp.experiments import load_config, simulation_config
from scripts.analyze_reliability_study import interval, promotion
from scripts.run_reliability_study import CONFIG, design, freeze, options, validate_config, variants_for, verify, VIOLATIONS
from evrp.storage import identifier


def test_crossed_seed_dynamicity_balanced_partial_size_and_all_engines():
    config = load_config(CONFIG)
    cases = design(config, config["development_parents"])
    assert len(cases) == 96
    assert len({c[0].rsplit("_", 1)[0] for c in cases}) == 12
    assert sum(c[0].endswith("_100") for c in cases) == 48
    for name in {c[0] for c in cases}:
        assert {(c[1], c[2]) for c in cases if c[0] == name} == {(.25, 0), (.25, 1), (.75, 0), (.75, 1)}
    keys = [(i, m, v) for i, c in enumerate(cases) for m in config["methods"]
            for v in variants_for(config, c, m, "development", None)]
    assert len(keys) == 1116
    assert sum(v == "cache_only" for _, _, v in keys) == 60
    assert sum(v == "completion_first_action" for _, _, v in keys) == 96
    for _, method, variant in keys[:100]:
        a = asdict(simulation_config(options(config, cases[0], method, "original")))
        b = asdict(simulation_config(options(config, cases[0], method, variant)))
        assert a["total_planning_time_limit"] == b["total_planning_time_limit"] == 5
        assert a["mpc"] == b["mpc"]
        assert {k for k in a if a[k] != b[k]} <= {"first_action_policy", "proposal_cache_policy"}


def test_variants_cannot_silently_change_science():
    config = deepcopy(load_config(CONFIG))
    config["variants"]["flex_exchange"]["total_planning_time_limit"] = 10
    with pytest.raises(ValueError, match="physics"):
        validate_config(config)


def test_holdout_requires_actual_audited_promotion_before_inputs_are_opened():
    with pytest.raises(ValueError, match="promotion"):
        freeze("holdout")


def test_interval_resamples_parents_not_individual_seed_rows():
    config = load_config(CONFIG)
    rows = [dict(parent=p, delta=d, size=100) for p, d in (("a", 1), ("a", 1), ("b", -1), ("b", -1))]
    bounds = interval(rows, lambda r: r["delta"], lambda r: r["size"], config)
    assert bounds == [-.01, .01]


def test_predeclared_completion_gate_is_separate_and_uncertain_gains_fail():
    config = load_config(CONFIG)
    summary = dict(method="MPC_COMPLETION", variant="completion_first_action", hundred_complete_interval=[.01, .1],
                   parent_service_interval=[-.001, .01], complete_gain=2, service_gain=5, hundred_service_gain=3,
                   seed_gains={"0": 2, "1": 3}, parents=12)
    assert promotion([summary], config)["promoted"] is None
    summary["parent_service_interval"] = [.001, .01]
    assert promotion([summary], config)["promoted"] == "completion_first_action"


@pytest.mark.parametrize("tamper", ["budget", "leak", "fleet", "config", "reference"])
def test_raw_verification_rejects_scientific_or_budget_tampering(tamper):
    config = load_config(CONFIG)
    case = ["c106_21_100", .25, 0]
    info = dict(case=case, scenario_id="scenario", reference_id="reference", instance_sha256="instance", k_ref=3)
    protocol = dict(config=config, cases=[info], source_sha256="source")
    raw = dict(metadata=dict(reliability_protocol=identifier(protocol), source_sha256="source", scenario_identifier="scenario",
               K_ref=3, reference_schedule_identifier="reference", instance_sha256="instance", scenario_seed=0,
               DoD_target=.25, algorithm="MPC_COMPLETION", campaign_variant="original", independent_audit={"physical": True}),
               effective_config=asdict(simulation_config(options(config, case, "MPC_COMPLETION", "original"))),
               metrics={**{k: 0 for k in VIOLATIONS}, "max_optimization_latency": 4.9})
    verify(raw, protocol, 0, "MPC_COMPLETION", "original")
    if tamper == "budget":
        raw["metrics"]["max_optimization_latency"] = 5.01
    elif tamper == "leak":
        raw["metrics"]["hidden_information_violations"] = 1
    elif tamper == "fleet":
        raw["metadata"]["K_ref"] = 4
    elif tamper == "reference":
        raw["metadata"]["reference_schedule_identifier"] = "other"
    else:
        raw["effective_config"]["mpc"]["iterations"] = 1
    with pytest.raises(ValueError, match="audit"):
        verify(raw, protocol, 0, "MPC_COMPLETION", "original")
