from dataclasses import replace
from time import perf_counter

import pytest

from evrp.instance import Location
from evrp.model import Action, transition
from evrp.planning_budget import PlanningDeadlineExceeded, reset_deadline, set_deadline
from evrp.repair import build_route, route_proposal
from tests.test_repair import customer, setup


def test_resource_labels_find_useful_intermediate_charge_without_lp():
    station = Location("S", "f", 5, 5, 0, 0, 100, 0)
    state, obs, config = setup((customer("A", 10, due=34), customer("B", 20, due=45)),
                               stations=(station,), battery=40)
    state = replace(state, location=customer("P", 0), battery=25,
                    departed=True, served_customers=("P",))
    assert build_route(state, ("A", "B"), obs, config) is None
    config = replace(config, route_decoder_version="resource_labels_v2")
    actions = build_route(state, ("A", "B"), obs, config)
    assert actions is not None
    assert route_proposal(state, actions, obs, config) is not None
    assert any(a.kind == "charge" and 30 < a.target_battery < 40 for a in actions)
    for action in actions:
        state = transition(state, action, obs).after
    assert state.served_customers == ("P", "A", "B")


@pytest.mark.parametrize("sequence", [("hidden",), ("busy",), ("A", "A"), ("overload",)])
def test_resource_labels_reject_invalid_observable_sequences(sequence):
    state, obs, config = setup((customer("A", 1), customer("busy", 2),
                                customer("overload", 3, demand=20)))
    obs = replace(obs, committed_customers=(("busy", 1),))
    config = replace(config, route_decoder_version="resource_labels_v2")
    assert build_route(state, sequence, obs, config) is None


def test_resource_labels_respect_full_charge_and_mp_station_topology():
    station = Location("S", "f", 4, 0, 0, 0, 200, 0)
    state, obs, config = setup((customer("A", 6, due=10),), stations=(station,), battery=10)
    state = replace(state, battery=6)
    config = replace(config, route_decoder_version="resource_labels_v2")
    actions = build_route(state, ("A",), obs, config)
    assert actions is not None and route_proposal(state, actions, obs, config) is not None
    assert build_route(state, ("A",), obs, replace(config, charging_mode="full")) is None
    obs = replace(obs, infrastructure=replace(obs.infrastructure, parameters=replace(
        obs.infrastructure.parameters, allow_station_to_station=False)))
    after = transition(state, actions[0], obs).after
    assert build_route(after, ("A",), obs, config) == (Action("serve", "A"),)


def test_resource_decoder_obeys_deadline_and_stale_origin():
    state, obs, config = setup((customer("A", 1),))
    config = replace(config, route_decoder_version="resource_labels_v2")
    assert build_route(state, ("A",), replace(obs, time=1), config) is None
    token = set_deadline(perf_counter()-1)
    try:
        with pytest.raises(PlanningDeadlineExceeded):
            build_route(state, ("A",), obs, config)
    finally:
        reset_deadline(token)


def test_resource_decoder_can_top_up_at_same_station_under_mp():
    station = Location("S", "f", 4, 0, 0, 0, 200, 0)
    state, obs, config = setup((customer("A", 6),), stations=(station,), battery=10)
    state = replace(state, location=station, battery=1, departed=True)
    obs = replace(obs, infrastructure=replace(obs.infrastructure, parameters=replace(
        obs.infrastructure.parameters, allow_station_to_station=False)))
    config = replace(config, route_decoder_version="resource_labels_v2")
    actions = build_route(state, ("A",), obs, config)
    assert actions[0].kind == "charge" and actions[0].destination == "S"
    assert route_proposal(state, actions, obs, config) is not None
