"""Physical and timeout regressions without changing frozen baseline behavior."""

from dataclasses import replace
from time import perf_counter

import pytest

from evrp.experiments import audit_result, simulation_config
from evrp.instance import Location
from evrp.model import Action, Observation, escape, transition
from evrp.optimizers.alns import ALNSOptimizer
from evrp.optimizers.alns_safe_init import ALNSSafeInitV1
from evrp.optimizers.base import OptimizationContext, OptimizerInitializationDeadline
from evrp.optimizers.registry import create_optimizer
from evrp.planning_budget import PlanningDeadlineExceeded, remaining_time
from evrp.repair import route_proposal
from evrp.simulator import EventDrivenSimulator
from tests.test_repair import customer, setup
from tests.test_simulator import synthetic


def context(state, observation, config, routes=None, deadline=None):
    return OptimizationContext(observation, {state.id: state}, {}, {},
        frozenset(observation.customer_by_id), frozenset(), frozenset(state.served_customers),
        routes or {}, 1, deadline, 17, config)


def test_original_timeout_defect_is_preserved_and_explicit_variant_corrects_it():
    state, obs, config = setup((customer("A", 1),))
    expired = context(state, obs, config, deadline=perf_counter() - 1)
    with pytest.raises(NameError, match=r"(?:best|local variable)"):
        ALNSOptimizer().optimize(expired)
    with pytest.raises(OptimizerInitializationDeadline):
        ALNSSafeInitV1().optimize(expired)
    assert remaining_time() == float("inf")
    original = create_optimizer("MPC_ALNS", simulation_config(dict(algorithm="MPC_ALNS")))
    fixed = create_optimizer("MPC_ALNS_SAFE_INIT_V1", simulation_config(dict(algorithm="MPC_ALNS_SAFE_INIT_V1")))
    assert type(original) is ALNSOptimizer and not original.initialization_fallback
    assert type(fixed) is ALNSSafeInitV1 and fixed.initialization_fallback


def test_corrected_variant_uses_validated_constructor_after_expired_initialization(monkeypatch):
    original = ALNSOptimizer.optimize
    def expired(self, epoch):
        return original(self, replace(epoch, deadline=perf_counter() - 1))
    monkeypatch.setattr(ALNSOptimizer, "optimize", expired)
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="MPC_ALNS_SAFE_INIT_V1", total_planning_time_limit=5))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert result.metrics["customers_served"] == 2
    assert result.metrics["optimizer_initialization_fallbacks"] > 0
    assert all(audit_result(result, base.instance, base.scenario).values())
    assert result.metrics["max_optimization_latency"] <= 5


def test_safe_variant_has_same_seeded_search_when_initialization_succeeds():
    state, obs, config = setup(tuple(customer(str(i), i + 1) for i in range(4)))
    epoch = context(state, obs, config)
    a = ALNSOptimizer(iterations=12).optimize(epoch)
    b = ALNSSafeInitV1(iterations=12).optimize(epoch)
    assert a.routes == b.routes and a.objective == b.objective
    assert a.customers_covered == b.customers_covered
    stable = lambda values: {k: v for k, v in values.items() if k != "best_improvement_times"}
    assert stable(a.diagnostics.values) == stable(b.diagnostics.values)


def test_multiple_partial_charges_are_replayed_with_exact_resources():
    station = Location("S", "f", 3, 0, 0, 0, 200, 0)
    state, obs, config = setup((customer("A", 6, service=2), customer("B", 9, service=2)),
                               stations=(station,), battery=20, charge_rate=2)
    state = replace(state, battery=9)
    actions = (Action("charge", "S", target_battery=12), Action("serve", "A"),
               Action("charge", "S", target_battery=16), Action("serve", "B"))
    assert route_proposal(state, actions, obs, config) is not None
    measured = state
    partial = 0
    for action in actions:
        step = transition(measured, action, obs)
        if action.kind == "charge":
            partial += action.target_battery < 20
            assert step.after.time - step.service_start == pytest.approx(step.energy_charged * 2)
        assert step.after.battery >= 0 and step.after.load >= 0
        measured = step.after
    assert partial == 2 and escape(measured, obs.infrastructure) is not None
    epoch = context(state, obs, config, {0: actions})
    result = ALNSSafeInitV1(iterations=8).optimize(epoch)
    assert result.customers_covered == {"A", "B"}
    assert route_proposal(state, result.routes[0], obs, config) == result.validated[0]


@pytest.mark.parametrize("case", ("depleted", "capacity", "late", "no_station", "empty"))
def test_empty_or_impossible_neighborhood_is_reported_as_uncovered(case):
    request = customer("A", 5, due=100, demand=1)
    if case == "late":
        request = replace(request, due=1)
    if case == "capacity":
        request = replace(request, demand=100)
    state, obs, config = setup(() if case == "empty" else (request,), battery=20)
    if case in {"depleted", "no_station"}:
        state = replace(state, battery=0 if case == "depleted" else 1)
    result = ALNSSafeInitV1(iterations=4).optimize(context(state, obs, config))
    assert not result.customers_covered
    assert result.objective[0] == (0 if case == "empty" else 1)
    assert not result.routes[0]


def test_new_request_during_busy_action_preserves_action_and_future_visibility():
    base = synthetic(release=5, fleet=2)
    config = simulation_config(dict(algorithm="MPC_ALNS", total_planning_time_limit=5,
                                    lns_iterations=8, planning_trace=True))
    result = EventDrivenSimulator(base.instance, base.scenario, config).run()
    assert all(audit_result(result, base.instance, base.scenario).values())
    releases = dict(base.scenario.customer_release_times)
    assert any(s.before.time < 5 < s.after.time for s in result.steps if s.action.kind != "wait")
    served = [s.served for s in result.steps if s.served]
    assert len(served) == len(set(served)) == 2
    for decision in result.decisions:
        assert all(releases[c] <= decision["time"] for c in decision["available"])
        owners = decision.get("route_owners_after_repair", {})
        assert set(owners) <= set(decision["available"])
        trace = decision.get("planning_trace")
        if trace:
            for key in trace["busy_actions"]:
                assert trace["origins"][key]["time"] >= decision["time"]


def test_timeout_after_initialization_retains_replayable_incumbent(monkeypatch):
    state, obs, config = setup((customer("A", 1),))
    actions = (Action("serve", "A"),)
    def expire(*args):
        raise PlanningDeadlineExceeded
    monkeypatch.setattr(ALNSSafeInitV1, "_repair", expire)
    result = ALNSSafeInitV1(iterations=8).optimize(context(state, obs, config, {0: actions}))
    assert result.deadline_reached and result.customers_covered == {"A"}
    assert result.routes[0] == actions


def test_busy_after_state_suffix_can_change_without_reexecuting_committed_customer():
    state, obs, config = setup((customer("A", 1), customer("B", 2)))
    action = Action("serve", "A")
    after = transition(state, action, obs).after
    visible = Observation(.5, obs.infrastructure, (obs.customer_by_id["B"],), (("A", 0),))
    epoch = OptimizationContext(visible, {0: after}, {0: action}, {}, frozenset({"B"}),
                               frozenset({"A"}), frozenset(), {}, 1, None, 0, config)
    result = ALNSSafeInitV1(iterations=8).optimize(epoch)
    assert result.customers_covered == {"B"}
    assert epoch.busy_actions[0] == action and epoch.origins[0] == after
    assert result.routes[0][0] == Action("serve", "B")
