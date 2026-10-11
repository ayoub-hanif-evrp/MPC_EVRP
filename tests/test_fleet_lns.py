from dataclasses import replace

from evrp.fleet_lns import fleet_score, improve_fleet
from evrp.model import Action, Observation, transition
from evrp.mpc import MPCConfig
from evrp.simulator import EventDrivenSimulator
from evrp.experiments import audit_result, simulation_config
from tests.test_repair import customer, serves, setup
from tests.test_simulator import synthetic


def test_fleet_lns_adds_released_work_without_new_vehicles():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    origins = {0: state}
    initial = {0: serves("A")}
    result = improve_fleet(origins, initial, observation, config, seed=7,
                           iterations=8, time_limit=2.0)
    assert result.initial_score[0] == 1
    assert result.best_score[0] == 0
    assert result.best_score <= result.initial_score
    assert fleet_score(origins, result.routes, observation, config) == result.best_score
    assert result.routes[0] in (serves("A", "B"), serves("B", "A"))


def test_fleet_lns_starts_after_immutable_action_and_cannot_see_hidden_work():
    state, observation, config = setup((customer("busy", 1), customer("next", 2)))
    immutable = transition(state, Action("serve", "busy"), observation)
    visible = Observation(0, observation.infrastructure, (observation.customer_by_id["next"],),
                          (("busy", 0),))
    result = improve_fleet({0: immutable.after}, {0: ()}, visible, config, seed=3,
                           iterations=4, time_limit=2.0)
    assert result.best_score[0] == 0
    assert result.routes[0] == serves("next")
    assert immutable.action == Action("serve", "busy")
    assert state.current_committed_action is None


def test_fleet_lns_algorithms_replay_on_synthetic_case():
    base = synthetic(release=5, fleet=2)
    for algorithm in ("ROLLING_ALNS", "MPC_MCTS_ALNS"):
        config = simulation_config(dict(algorithm=algorithm, mcts_iterations=4,
                                        lns_iterations=4, lns_time_limit=0.2))
        result = EventDrivenSimulator(base.instance, base.scenario, config).run()
        assert result.metrics["customers_served"] == 2
        assert result.metrics["vehicles_activated"] <= base.scenario.fleet_size
        assert all(audit_result(result, base.instance, base.scenario).values())
        assert result.metrics["lns_iterations"] >= 0


def test_regret_three_option_preserves_compatibility():
    state, observation, config = setup((customer("A", 1), customer("B", 2)))
    from evrp.repair import regret_repair
    origins = {0: state, 1: replace(state, id=1)}
    routes, records = regret_repair(origins, {}, observation, config, regret_k=3)
    assert len(records) == 2
    assert fleet_score(origins, routes, observation, config)[0] == 0


def test_shortlisted_insertions_fall_back_when_cheapest_position_is_infeasible():
    from evrp.repair import regret_repair
    state, observation, config = setup((customer("A", 1, due=2), customer("B", 2),
                                        customer("X", 0.5, service=2)))
    routes, records = regret_repair({0: state}, {0: serves("A", "B")}, observation,
                                    config, position_limit=1)
    assert len(records) == 1
    assert records[0]["customer"] == "X"
    assert records[0]["position"] > 0
    assert {a.destination for a in routes[0] if a.kind == "serve"} == {"A", "B", "X"}


def test_one_station_decoder_replays_feasible_reference_sequences_offline():
    from evrp.experiments import prepare
    from evrp.observation import initial_global_state
    from evrp.repair import build_route, route_proposal
    instance, reference, scenario, _ = prepare("r101_21", {"dynamicity": 0.0})
    origins = initial_global_state(instance, scenario).vehicles
    observation = Observation(0, instance.infrastructure, instance.customers)
    config = MPCConfig()
    for route in reference.routes:
        k = route.steps[0].before.id
        actions = build_route(origins[k], route.customers, observation, config)
        assert actions is not None
        assert route_proposal(origins[k], actions, observation, config) is not None
        assert sum(a.kind == "serve" for a in actions) == len(route.customers)
