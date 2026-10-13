"""External benchmark gates work without either optional solver installed."""

from dataclasses import replace
from pathlib import Path

import pytest

from evrp.external.compatibility import (compare_geometry, dynamic_qualified,
                                         pyevrp_matrix, routingblocks_matrix)
from evrp.external.pyevrp_adapter import build_pyevrp_model
from evrp.external.replay import replay_routes
from evrp.external.routingblocks_adapter import run_routingblocks
from evrp.external import routingblocks_worker
from evrp.instance import distance, energy, load_instance, travel_time
from evrp.reference import ReferenceSchedule
from evrp.storage import BENCHMARK, ROOT


@pytest.fixture(scope="module")
def reference_case():
    instance = load_instance(BENCHMARK / "c101C5.txt")
    files = list((ROOT / "data/reference_schedules").glob("c101C5_*.json"))
    assert len(files) == 1
    reference = ReferenceSchedule.load(files[0], instance)
    routes = [[instance.infrastructure.depot.id, *
               (step.action.destination for step in route.steps)] for route in reference.routes]
    return instance, reference.fleet_size, routes


def test_source_level_physics_gate(reference_case):
    instance, fleet_size, _ = reference_case
    rb = {row.feature: row for row in routingblocks_matrix(instance, fleet_size)}
    py = {row.feature: row for row in pyevrp_matrix(instance, fleet_size)}
    assert rb["same K_ref fleet upper bound"].exact is None
    assert py["partial recharge"].exact is False
    assert py["same K_ref fleet upper bound"].exact is False
    assert not dynamic_qualified("RoutingBlocks")
    assert not dynamic_qualified("pyevrp 0.2.1")


def test_all_node_and_arc_fields_compared(reference_case):
    instance, _, _ = reference_case
    nodes = instance.geometry.by_id
    external_nodes = {key: (n.kind, n.x, n.y, n.demand, n.ready, n.due, n.service)
                      for key, n in nodes.items()}
    p = instance.infrastructure.parameters
    arcs = {(a, b): (distance(x, y), travel_time(x, y, p), energy(x, y, p))
            for a, x in nodes.items() for b, y in nodes.items()}
    assert compare_geometry(instance, external_nodes, arcs) == []
    first = instance.customers[0].id
    changed = dict(external_nodes)
    changed[first] = (*changed[first][:-2], changed[first][-2] - 1, changed[first][-1])
    assert any("node" in error for error in compare_geometry(instance, changed, arcs))
    bad_arcs = dict(arcs)
    bad_arcs[(instance.infrastructure.depot.id, first)] = (arcs[(instance.infrastructure.depot.id, first)][0],
                                                            arcs[(instance.infrastructure.depot.id, first)][1], 0)
    assert any("arc" in error for error in compare_geometry(instance, external_nodes, bad_arcs))


def test_direct_model_mapping_preserves_fleet_and_charge_rate(reference_case):
    instance, fleet_size, _ = reference_case

    class FakeModel:
        def __init__(self, name):
            self.name = name
            self.depot = None
            self.clients = []
            self.stations = []
            self.vehicle = None

        def add_depot(self, **values):
            self.depot = values

        def add_client(self, **values):
            self.clients.append(values)

        def add_charging_station(self, **values):
            self.stations.append(values)

        def add_vehicle_type(self, **values):
            self.vehicle = values

    model, customers, stations = build_pyevrp_model(instance, fleet_size, FakeModel)
    assert len(customers) == len(instance.customers)
    assert len(stations) == len(instance.infrastructure.stations)
    assert model.vehicle["num_available"] == fleet_size
    assert model.vehicle["battery_capacity"] == instance.infrastructure.parameters.battery
    assert model.stations[0]["charging_rate"] == pytest.approx(
        1 / instance.infrastructure.parameters.inverse_charge_rate)
    assert model.clients[0]["tw_late"] == instance.customers[0].due


def test_reference_route_independently_replays(reference_case):
    instance, fleet_size, routes = reference_case
    result = replay_routes(instance, routes, fleet_size)
    assert result.feasible and result.complete
    assert result.served == len(instance.customers)
    assert result.vehicles == fleet_size


def test_bad_routes_rejected(reference_case):
    instance, fleet_size, routes = reference_case
    assert not replay_routes(instance, routes, fleet_size - 1).feasible
    assert not replay_routes(instance, [[*routes[0][:-1], routes[0][1], routes[0][-1]]], fleet_size).feasible
    assert not replay_routes(instance, [[routes[0][0], "HIDDEN_CUSTOMER", routes[0][-1]]], fleet_size).feasible
    assert not replay_routes(instance, [[routes[0][0], routes[0][1]]], fleet_size).feasible


def test_battery_time_window_capacity_rejected(reference_case):
    instance, fleet_size, routes = reference_case
    p = instance.infrastructure.parameters
    low_battery = replace(instance, infrastructure=replace(instance.infrastructure,
                          parameters=replace(p, battery=0.001)))
    assert not replay_routes(low_battery, routes, fleet_size).feasible
    tight_capacity = replace(instance, infrastructure=replace(instance.infrastructure,
                            parameters=replace(p, capacity=0.001)))
    assert not replay_routes(tight_capacity, routes, fleet_size).feasible
    customer = instance.customers[0]
    closed = replace(instance, customers=(replace(customer, due=0), *instance.customers[1:]))
    assert not replay_routes(closed, routes, fleet_size).feasible


def test_runtime_budget_checked_before_optional_import(reference_case):
    instance, fleet_size, _ = reference_case
    with pytest.raises(ValueError, match="Runtime budget"):
        run_routingblocks(instance, BENCHMARK / "c101C5.txt", Path("missing"), fleet_size, 0, 0)


def test_worker_propagates_seed_fleet_and_runtime_budget(reference_case, monkeypatch):
    instance, fleet_size, _ = reference_case
    observed = {}
    monkeypatch.setattr(routingblocks_worker, "load_instance", lambda path: instance)
    monkeypatch.setattr(routingblocks_worker, "run_routingblocks",
                        lambda *args: observed.update({"args": args}) or {"solver": "RoutingBlocks"})
    monkeypatch.setattr(routingblocks_worker, "save_json",
                        lambda path, raw: observed.update({"path": path, "raw": raw}))
    monkeypatch.setattr("sys.argv", ["routingblocks_worker", "--instance", "case.txt",
                                "--examples", "examples", "--fleet-size", str(fleet_size),
                                "--seed", "7", "--budget", "30", "--output", "out.json"])
    routingblocks_worker.main()
    assert observed["args"][3:] == (fleet_size, 7, 30.0)
    assert observed["raw"]["status"] == "completed"
