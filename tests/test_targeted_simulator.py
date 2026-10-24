from dataclasses import replace

import pytest

from evrp.experiments import audit_result
from evrp.simulator import EventDrivenSimulator, SimulationConfig
from tests.test_simulator import synthetic


@pytest.mark.parametrize("algorithm", ["MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"])
@pytest.mark.parametrize("variant", ["original", "constructor", "decoder", "first_action"])
def test_targeted_candidates_keep_all_original_engines_valid(algorithm, variant):
    fixture = synthetic(release=5, fleet=2)
    config = SimulationConfig(algorithm=algorithm, total_planning_time_limit=5,
                              optimizer_initialization_policy="validated_incumbent_v1",
                              coordination_policy="forced_retained_v1")
    if variant == "constructor":
        config = replace(config, constructor_policy="urgency_recovery_v1")
    elif variant == "decoder":
        config = replace(config, mpc=replace(config.mpc, route_decoder_version="resource_labels_v2"))
    elif variant == "first_action":
        config = replace(config, first_action_policy="counterfactual_v1")
    result = EventDrivenSimulator(fixture.instance, fixture.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert result.metrics["max_optimization_latency"] <= 5
    assert all(audit_result(result, fixture.instance, fixture.scenario).values())
    assert any(bool(d.get("targeted_constructor")) for d in result.decisions) == (variant == "constructor")
    assert any(bool(d.get("targeted_control")) for d in result.decisions) == (variant == "first_action")
