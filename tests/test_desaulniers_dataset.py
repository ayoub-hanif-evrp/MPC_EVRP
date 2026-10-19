"""Compatibility checks against the local Desaulniers 2016 MP benchmark bundle."""

import pytest

from evrp.experiments import audit_result, simulation_config, load_config
from evrp.instance import discover_instances, distance, energy, load_instance, travel_time
from evrp.model import Action, InfeasibleAction, Observation, transition
from evrp.reference import ReferenceConfig, initial_vehicle, published_full_reference, validate_reference
from evrp.scenario import generate
from evrp.simulator import EventDrivenSimulator
from evrp.storage import BENCHMARK, ROOT


def test_discovery_and_all_published_arc_profiles():
    assert {size: len(discover_instances(size)) for size in (25, 50, 100)} == {25: 56, 50: 56, 100: 56}
    for path in discover_instances():
        instance = load_instance(path)
        assert len(instance.customers) == int(path.stem.rsplit("_", 1)[1])
        assert len(instance.infrastructure.stations) == 21
        assert instance.infrastructure.parameters.energy_precision == 100
        assert not instance.infrastructure.parameters.allow_station_to_station


def test_rounded_arcs_and_partial_charge():
    instance = load_instance(BENCHMARK / "c101_21_25.txt")
    infra = instance.infrastructure
    depot, station = infra.depot, infra.stations[1]
    assert distance(depot, station) == 33.07
    assert travel_time(depot, station, infra.parameters) == 33.07
    assert energy(depot, station, infra.parameters) == 112.08
    state = initial_vehicle(instance)
    observation = Observation(0, infra, instance.customers)
    arrival = transition(state, Action("charge", station.id, 180.0), observation).after
    assert arrival.battery == 180.0
    topped = transition(arrival, Action("charge", station.id, 200.0), observation).after
    assert topped.battery == 200.0
    with pytest.raises(InfeasibleAction, match="station-to-station"):
        transition(topped, Action("charge", infra.stations[2].id, 200.0), observation)


@pytest.mark.parametrize("size", [25, 50, 100])
def test_published_full_routes_are_valid_mp_references(size):
    instance = load_instance(BENCHMARK / f"c101_21_{size}.txt")
    reference = published_full_reference(instance, ReferenceConfig())
    assert reference is not None
    assert reference.provenance == "published_MF_full_replay_under_MP"
    assert len(reference.predecessor_departures) == size
    validate_reference(instance, reference)
    scenario = generate(instance, reference, seed=1, dynamicity=.25)
    assert all(dict(scenario.customer_release_times)[cid] <= departure
               for cid, departure in reference.predecessor_departures.items())
    assert scenario.fleet_size == reference.fleet_size


def test_online_observation_cannot_serve_hidden_customer():
    instance = load_instance(BENCHMARK / "c101_21_25.txt")
    reference = published_full_reference(instance, ReferenceConfig())
    scenario = generate(instance, reference, seed=1, dynamicity=.25)
    hidden = next(cid for cid, release in scenario.customer_release_times if release > 0)
    visible = tuple(c for c in instance.customers if dict(scenario.customer_release_times)[c.id] == 0)
    with pytest.raises(InfeasibleAction, match="unavailable"):
        transition(initial_vehicle(instance), Action("serve", hidden),
                   Observation(0, instance.infrastructure, visible))


def test_completion_pilot_is_independently_audited():
    instance = load_instance(BENCHMARK / "c101_21_25.txt")
    reference = published_full_reference(instance, ReferenceConfig())
    scenario = generate(instance, reference, seed=0, dynamicity=.25)
    options = load_config(ROOT / "configs" / "paper_controller.yaml")
    options.update(algorithm="MPC_COMPLETION", diagnostics=False, trace_level="summary",
                   total_planning_time_limit=5.0)
    result = EventDrivenSimulator(instance, scenario, simulation_config(options)).run()
    assert all(audit_result(result, instance, scenario).values())
    assert result.metrics["max_optimization_latency"] <= 5.0 + 1e-6
    assert result.metrics["customers_served"] <= 25
