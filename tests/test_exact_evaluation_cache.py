from dataclasses import replace
from itertools import permutations
from random import Random
from time import perf_counter

import pytest

from evrp import proposal_memo
from evrp.evaluation_cache import transition as planned_transition
from evrp.fleet_mcts import _FleetProblem
from evrp.instance import Infrastructure, Location
from evrp.model import Action, InfeasibleAction, Observation, transition
from evrp.planning_budget import PlanningDeadlineExceeded, reset_deadline, set_deadline
from evrp.repair import _build_route_original, _decode_one_station, build_route, route_proposal
from tests.test_repair import customer, setup


def compare_routes(state, observation, config, sequences, decoder=build_route):
    _build_route_original.cache_clear()
    expected = [decoder(state, sequence, observation, config) for sequence in sequences]
    _build_route_original.cache_clear()
    memo, token = proposal_memo.begin(incremental=True)
    try:
        actual = [decoder(state, sequence, observation, config) for sequence in sequences]
        assert actual == expected
    finally:
        proposal_memo.end(token)
    for actions in actual:
        if actions:
            current = state
            for action in actions:
                current = transition(current, action, observation).after
            assert route_proposal(state, actions, observation, config) is not None
    return memo


@pytest.mark.parametrize("full", [False, True])
@pytest.mark.parametrize("mp", [False, True])
def test_charging_frontier_prefixes_match_original_exactly(full, mp):
    stations = (Location("S1", "f", 4, 1, 0, 0, 190, 0),
                Location("S2", "f", 12, 1, 0, 0, 190, 0))
    state, observation, config = setup(tuple(customer(c, x, due=100) for c, x in
                                       (("A", 7), ("B", 15), ("C", 9), ("D", 18))),
                                       stations=stations, battery=22)
    infra = Infrastructure(observation.infrastructure.depot, stations,
                           replace(observation.infrastructure.parameters, allow_station_to_station=not mp))
    observation = replace(observation, infrastructure=infra)
    config = replace(config, charging_mode="full" if full else "partial")
    sequences = [("A",), ("A", "B"), ("A", "B", "C"), ("A", "B", "D"), ("A", "C", "D")]
    memo = compare_routes(state, observation, config, sequences, _decode_one_station)
    assert memo.counts["label_prefix_hits"] > 0
    assert memo.counts["transition_hits"] > 0


def test_greedy_prefixes_reuse_physical_states_but_not_changed_roots():
    state, observation, config = setup(tuple(customer(c, x) for c, x in (("A", 1), ("B", 2), ("C", 3), ("D", 4))))
    memo = compare_routes(state, observation, config, [("A", "B"), ("A", "B", "C"), ("A", "B", "D")])
    assert memo.counts["greedy_customers_reused"] >= 4
    memo, token = proposal_memo.begin(incremental=True)
    try:
        assert build_route(state, ("A", "B"), observation, config)
        assert build_route(state, ("A", "B"), replace(observation, committed_customers=(("A", 2),)), config) is None
        assert build_route(replace(state, load=0), ("A",), observation, config) is None
        assert build_route(state, ("hidden",), observation, config) is None
    finally:
        proposal_memo.end(token)


@pytest.mark.parametrize("seed", range(8))
def test_randomized_small_routes_and_failed_decodes_are_exact(seed):
    rng = Random(seed)
    customers = tuple(customer(str(i), rng.uniform(2, 18), due=rng.uniform(12, 65),
                               ready=rng.uniform(0, 8), service=1) for i in range(4))
    station = Location("S", "f", 5, 3, 0, 0, 80, 0)
    state, observation, config = setup(customers, stations=(station,), battery=25, capacity=5)
    sequences = [tuple(c.id for c in customers[:i]) for i in range(1, 5)]
    sequences += list(permutations(tuple(c.id for c in customers), 3))
    compare_routes(state, observation, config, sequences)


@pytest.mark.parametrize("epsilon", [-2e-8, -1e-9, 0, 1e-9, 2e-8])
def test_time_window_and_charging_boundaries_are_not_approximated(epsilon):
    station = Location("S", "f", 2, 0, 0, 0, 7, 0)
    state, observation, config = setup((customer("A", 4, due=6+epsilon), customer("B", 6, due=9+epsilon)),
                                        stations=(station,), battery=12)
    state = replace(state, battery=3)
    compare_routes(state, observation, config, [("A",), ("A", "B")], _decode_one_station)


def test_cached_failure_and_success_match_original_and_deadlines_precede_hits():
    state, observation, _ = setup((customer("A", 1),))
    memo, token = proposal_memo.begin(incremental=True)
    try:
        action = Action("serve", "A")
        assert planned_transition(state, action, observation) == transition(state, action, observation)
        assert planned_transition(state, action, observation) == transition(state, action, observation)
        for _ in range(2):
            with pytest.raises(InfeasibleAction) as error:
                planned_transition(state, Action("serve", "hidden"), observation)
        assert "unavailable" in str(error.value)
        deadline = set_deadline(perf_counter()-1)
        try:
            with pytest.raises(PlanningDeadlineExceeded):
                planned_transition(state, action, observation)
        finally:
            reset_deadline(deadline)
        assert memo.counts["transition_hits"] == 2
    finally:
        proposal_memo.end(token)


def test_objective_cache_preserves_exact_tuple_and_constructor_anchor():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    origins = {0: state, 1: replace(state, id=1)}
    routes = {0: (Action("serve", "A"), Action("serve", "B")), 1: ()}
    baseline = _FleetProblem(origins, observation, config, 3, 2).initial(routes)
    memo, token = proposal_memo.begin(incremental=True)
    try:
        problem = _FleetProblem(origins, observation, config, 3, 2)
        plan = problem.initial(routes)
        assert (plan.score, plan.components) == (baseline.score, baseline.components)
        score, components = problem._score(plan.sequences, plan.actions, plan.costs)
        assert score == baseline.score and components == baseline.components
        components["distance"] = -1
        assert problem._score(plan.sequences, plan.actions, plan.costs)[1]["distance"] >= 0
        problem.initial_owners = {"A": 1, "B": 1}
        changed = problem._score(plan.sequences, plan.actions, plan.costs)
        assert changed[0] != score
        assert memo.counts["objective_hits"] >= 2
    finally:
        proposal_memo.end(token)


def test_caches_have_finite_caps():
    state, observation, _ = setup((customer("A", 1), customer("B", 2)))
    memo, token = proposal_memo.begin(incremental=True)
    memo.transition_limit = 1
    try:
        planned_transition(state, Action("serve", "A"), observation)
        planned_transition(state, Action("serve", "B"), observation)
        assert len(memo.transitions) == 1
    finally:
        proposal_memo.end(token)


@pytest.mark.parametrize("method", ["MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"])
def test_fixed_work_optimizer_routes_and_objectives_are_exact(method):
    from evrp.optimizers import OptimizationContext, create_optimizer
    from evrp.simulator import SimulationConfig
    state, observation, config = setup((customer("A", 1), customer("B", 2), customer("C", 3)))
    origins = {0: state, 1: replace(state, id=1)}
    routes = {0: (Action("serve", "A"), Action("serve", "B")), 1: (Action("serve", "C"),)}
    context = OptimizationContext(observation, origins, {}, {}, frozenset(observation.customer_by_id),
                                   frozenset(), frozenset(), routes, 2, None, 17, config)
    simulation = SimulationConfig(algorithm=method, total_planning_time_limit=5)
    _build_route_original.cache_clear()
    expected = create_optimizer(method, simulation).optimize(context)
    _build_route_original.cache_clear()
    memo, token = proposal_memo.begin(incremental=True)
    try:
        actual = create_optimizer(method, simulation).optimize(context)
        assert actual.routes == expected.routes
        assert actual.objective == expected.objective
        assert actual.components == expected.components
        assert not actual.deadline_reached and not expected.deadline_reached
    finally:
        proposal_memo.end(token)


@pytest.mark.parametrize("method", ["MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"])
def test_incremental_policy_has_independent_physical_audit_and_five_second_cap(method):
    from evrp.experiments import audit_result
    from evrp.simulator import EventDrivenSimulator, SimulationConfig
    from tests.test_simulator import synthetic
    fixture = synthetic(release=5, fleet=2)
    config = SimulationConfig(algorithm=method, total_planning_time_limit=5,
                              proposal_cache_policy="incremental_v1", optimizer_initialization_policy="validated_incumbent_v1",
                              coordination_policy="forced_retained_v1")
    result = EventDrivenSimulator(fixture.instance, fixture.scenario, config).run()
    assert all(audit_result(result, fixture.instance, fixture.scenario).values())
    assert result.metrics["customers_served"] == 2
    assert result.metrics["max_optimization_latency"] <= 5
    assert proposal_memo.current() is None


def test_incremental_cache_never_uses_unrevealed_customer_geometry():
    from evrp.simulator import EventDrivenSimulator, SimulationConfig
    from tests.test_simulator import synthetic
    fixture=synthetic(release=30,fleet=2)
    changed=replace(fixture.instance,customers=(fixture.instance.customers[0],replace(fixture.instance.customers[1],x=3)))
    config=SimulationConfig(algorithm="MPC_ALNS",total_planning_time_limit=5,proposal_cache_policy="incremental_v1",
                            optimizer_initialization_policy="validated_incumbent_v1",coordination_policy="forced_retained_v1")
    results=[EventDrivenSimulator(instance,fixture.scenario,config).run() for instance in (fixture.instance,changed)]
    def policy(result):
        return [(d["time"],d["selected_firsts"],d["route_owners_after_repair"],
                 {k:p["actions"] for k,p in d["plans"].items()}) for d in result.decisions if d["time"]<30]
    assert policy(results[0])==policy(results[1])
