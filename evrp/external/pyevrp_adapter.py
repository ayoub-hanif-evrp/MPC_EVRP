"""Explicit pyevrp 0.2.1 conversion; its bundled loader is not trusted."""

from math import isclose
from pathlib import Path

from evrp.instance import Instance, distance


def build_pyevrp_model(instance: Instance, fleet_size: int, model_class=None):
    """Map Schneider data directly through pyevrp's public Model API.

    The returned ID map is required to turn third-party routes back into
    canonical Schneider IDs. This does not qualify bundled solvers as exact
    physics comparators: the bundled greedy uses full charging.
    """
    if fleet_size <= 0:
        raise ValueError("K_ref must be positive")
    if model_class is None:
        from pyevrp import Model
        model_class = Model
    model = model_class(instance.name)
    depot = instance.infrastructure.depot
    p = instance.infrastructure.parameters
    model.add_depot(x=depot.x, y=depot.y, tw_early=depot.ready, tw_late=depot.due)
    customer_map = {}
    for index, customer in enumerate(instance.customers, 1):
        model.add_client(x=customer.x, y=customer.y, demand=customer.demand,
                         service_time=customer.service, tw_early=customer.ready,
                         tw_late=customer.due)
        customer_map[index] = customer.id
    station_map = {}
    for index, station in enumerate(instance.infrastructure.stations, 1):
        model.add_charging_station(x=station.x, y=station.y,
                                   charging_rate=1.0 / p.inverse_charge_rate)
        station_map[index] = station.id
    model.add_vehicle_type(capacity=p.capacity, battery_capacity=p.battery,
                           consumption_rate=p.consumption, num_available=fleet_size,
                           speed=p.speed)
    return model, customer_map, station_map


def verify_pyevrp_data(instance: Instance, data, customer_map: dict[int, str],
                       station_map: dict[int, str], fleet_size: int) -> dict:
    """Check the explicit mapping, including all node windows and arc lengths."""
    errors = []
    p = instance.infrastructure.parameters
    nodes = instance.geometry.by_id
    if data.num_clients != len(instance.customers) or data.num_stations != len(instance.infrastructure.stations):
        errors.append("node counts differ")
    if len(data.vehicle_types) != 1:
        errors.append("vehicle-type count differs")
    else:
        vehicle = data.vehicle_types[0]
        for name, actual, expected in (
            ("K_ref", vehicle.num_available, fleet_size),
            ("capacity", vehicle.capacity, p.capacity),
            ("battery", vehicle.battery.capacity_kwh, p.battery),
            ("consumption", vehicle.battery.consumption_rate, p.consumption),
            ("speed", vehicle.speed, p.speed),
        ):
            if not isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8):
                errors.append(f"{name} differs")
    for external, key in customer_map.items():
        customer = data.client(external)
        ours = nodes[key]
        fields = ((customer.x, ours.x), (customer.y, ours.y),
                  (customer.demand, ours.demand), (customer.tw_early, ours.ready),
                  (customer.tw_late, ours.due), (customer.service_time, ours.service))
        if any(not isclose(a, b, abs_tol=1e-8) for a, b in fields):
            errors.append(f"customer {key} differs")
    for external, key in station_map.items():
        station = data.station(external)
        ours = nodes[key]
        if (not isclose(station.x, ours.x, abs_tol=1e-8)
                or not isclose(station.y, ours.y, abs_tol=1e-8)
                or not isclose(station.charging_rate, 1 / p.inverse_charge_rate, abs_tol=1e-8)):
            errors.append(f"station {key} differs")
    ids = [instance.infrastructure.depot.id, *customer_map.values(), *station_map.values()]
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if not isclose(data.distance(i, j), distance(nodes[a], nodes[b]), abs_tol=1e-8):
                errors.append(f"distance {a}->{b} differs")
    return {"solver": "pyevrp 0.2.1", "instance": instance.name,
            "instance_sha256": instance.sha256, "K_ref": fleet_size,
            "exact_data_mapping": not errors, "physics_comparable": False,
            "errors": errors,
            "limitation": "bundled greedy charges to full and does not enforce num_available"}


def audit_bundled_loader(instance: Instance, path: Path) -> dict:
    """Document the upstream SchneiderLoader failure separately from direct mapping."""
    from pyevrp import SchneiderLoader
    try:
        data = SchneiderLoader.load(path)
    except Exception as error:
        return {"instance": instance.name, "loader_equivalent": False,
                "error": f"{type(error).__name__}: {error}"}
    return {"instance": instance.name,
            "loader_equivalent": data.num_clients == len(instance.customers)
            and data.num_stations == len(instance.infrastructure.stations),
            "customers": data.num_clients, "stations": data.num_stations}


def canonical_routes(solution, customer_map: dict[int, str],
                     station_map: dict[int, str], depot_id: str) -> list[list[str]]:
    from pyevrp.solution.route import VisitType
    routes = []
    for route in solution.routes:
        converted = []
        for visit in route.visits:
            if visit.visit_type == VisitType.DEPOT:
                converted.append(depot_id)
            elif visit.visit_type == VisitType.CLIENT:
                converted.append(customer_map[visit.node_id])
            elif visit.visit_type == VisitType.STATION:
                converted.append(station_map[visit.node_id])
        routes.append(converted)
    return routes
