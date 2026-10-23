from dataclasses import replace
from time import perf_counter
from types import SimpleNamespace

from evrp.experiments import audit_result, simulation_config
from evrp.fleet_mcts import construct_fleet_root
from evrp.model import Observation
from evrp.optimizers.alns import ALNSOptimizer, ALNSRecoveryV2, ALNSStableV3, DESTROY, REPAIR
from evrp.optimizers.base import OptimizationContext
from evrp.simulator import EventDrivenSimulator
from tests.test_repair import customer, setup
from tests.test_simulator import synthetic


def test_alns_is_seeded_adaptive_and_exact():
    state, obs, mpc = setup(tuple(customer(chr(65 + i), i + 1) for i in range(4)))
    root = construct_fleet_root({0: state}, {}, obs, mpc).routes
    context = OptimizationContext(obs, {0: state}, {}, {}, frozenset(obs.customer_by_id),
                                  frozenset(), frozenset(), root, 1, perf_counter() + 5, 13, mpc)
    optimizer = ALNSOptimizer(iterations=24, segment_length=4)
    first = optimizer.optimize(context)
    second = optimizer.optimize(context)
    assert first.objective == second.objective
    assert first.routes == second.routes
    assert first.objective[0] <= 4
    assert first.diagnostics.values["iterations"] > 0
    assert set(first.diagnostics.values["destroy_counts"]) <= set(DESTROY)
    assert set(first.diagnostics.values["repair_counts"]) <= set(REPAIR)
    assert sum(first.diagnostics.values["destroy_counts"].values()) == first.diagnostics.values["iterations"]
    assert first.validated[0].actions == first.routes[0]


def test_alns_never_sees_future_customer():
    state, obs, mpc = setup((customer("A", 1), customer("future", 2)))
    visible = Observation(0, obs.infrastructure, (obs.customer_by_id["A"],))
    context = OptimizationContext(visible, {0: state}, {}, {}, frozenset({"A"}),
                                  frozenset(), frozenset(), {}, 1, perf_counter() + 1, 3, mpc)
    result = ALNSOptimizer(iterations=8).optimize(context)
    assert result.customers_covered <= {"A"}


def test_alns_runs_in_common_event_pipeline():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="MPC_ALNS", total_planning_time_limit=1.0,
                                    lns_iterations=8))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert all(audit_result(result, base.instance, base.scenario).values())
    assert result.decisions[0]["optimizer"]["name"] == "MPC_ALNS"
    assert "destroy_counts" in result.decisions[0]["optimizer"]["diagnostics"]


def test_recovery_v2_is_separate_and_scales_only_when_service_missing():
    original = ALNSOptimizer()
    enhanced = ALNSRecoveryV2()
    assert original._destroy_count(100, 1) == 4
    assert enhanced._destroy_count(100, 1) == 8
    assert enhanced._destroy_count(100, 0) == 4
    assert enhanced._destroy_count(3, 1) == 2
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="MPC_ALNS_RECOVERY_V2",
                                    total_planning_time_limit=1.0, lns_iterations=8))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert all(audit_result(result, base.instance, base.scenario).values())
    assert result.decisions[0]["optimizer"]["name"] == "MPC_ALNS_RECOVERY_V2"


def test_stable_v3_guards_equal_service_customer_replacement_only():
    incumbent = SimpleNamespace(score=(1, .4), sequences=(("A", "B"), ()))
    swapped = SimpleNamespace(score=(1, .2), sequences=(("A", "C"), ()))
    rearranged = SimpleNamespace(score=(1, .2), sequences=(("B",), ("A",)))
    increased = SimpleNamespace(score=(0, .8), sequences=(("A", "B", "C"), ()))
    enhanced = ALNSStableV3()
    assert not enhanced._eligible_best(swapped, incumbent)
    assert enhanced._eligible_best(rearranged, incumbent)
    assert enhanced._eligible_best(increased, incumbent)
    assert ALNSOptimizer()._eligible_best(swapped, incumbent)


def test_stable_v3_runs_with_original_physics_and_information_boundary():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="MPC_ALNS_STABLE_V3",
                                    total_planning_time_limit=1.0, lns_iterations=8))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert all(audit_result(result, base.instance, base.scenario).values())
    assert result.decisions[0]["optimizer"]["name"] == "MPC_ALNS_STABLE_V3"
