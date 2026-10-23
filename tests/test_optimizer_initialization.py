from dataclasses import replace
from time import perf_counter

import pytest

from evrp.experiments import audit_result, simulation_config
from evrp.optimizers.acs import ACSOptimizer
from evrp.optimizers.alns import ALNSOptimizer
from evrp.optimizers.hgs import HGSOptimizer
from evrp.optimizers.base import OptimizationContext, OptimizerInitializationDeadline
from evrp.planning_budget import remaining_time
from evrp.simulator import EventDrivenSimulator
from tests.test_repair import customer, setup
from tests.test_simulator import synthetic


@pytest.mark.parametrize("optimizer", (ALNSOptimizer, HGSOptimizer, ACSOptimizer))
def test_expired_initialization_restores_deadline_and_requests_validated_fallback(optimizer):
    state, observation, config = setup((customer("A", 1),))
    context = OptimizationContext(observation, {0: state}, {}, {}, frozenset({"A"}),
                                  frozenset(), frozenset(), {}, 1, perf_counter()-1, 0, config)
    with pytest.raises(OptimizerInitializationDeadline):
        optimizer(initialization_fallback=True).optimize(context)
    assert remaining_time() == float("inf")


def test_simulator_retains_validated_constructor_after_initialization_timeout(monkeypatch):
    original = ALNSOptimizer.optimize

    def expired_start(self, context):
        return original(self, replace(context, deadline=perf_counter()-1))

    monkeypatch.setattr(ALNSOptimizer, "optimize", expired_start)
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="MPC_ALNS", total_planning_time_limit=1.0,
                                    optimizer_initialization_policy="validated_incumbent_v1",
                                    coordination_policy="forced_retained_v1"))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert result.metrics["optimizer_initialization_fallbacks"] > 0
    assert result.metrics["coordination_solver_invocations"] == 0
    assert result.metrics["coordination_forced_choices"] > 0
    assert all(audit_result(result, base.instance, base.scenario).values())
    assert any(d.get("optimizer_initialization_fallback") for d in result.decisions)
