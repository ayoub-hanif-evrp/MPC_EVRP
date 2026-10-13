"""Conservative physics and online-state gates for external benchmarks."""

from dataclasses import dataclass
from math import isclose

from evrp.instance import Instance, distance, energy, travel_time


FEATURES = (
    "coordinates/distances", "travel-time model", "customer service times",
    "demands", "vehicle capacity", "customer time windows", "depot horizon",
    "battery capacity", "linear distance-based energy consumption",
    "charging rate", "partial recharge", "multiple station visits",
    "same K_ref fleet upper bound", "safe depot return",
)


@dataclass(frozen=True)
class Compatibility:
    solver: str
    feature: str
    ours: str
    external: str
    exact: bool | None
    evidence: str


def routingblocks_matrix(instance: Instance, fleet_size: int) -> tuple[Compatibility, ...]:
    """Audit the official EVRPTW-PR example, including its required fleet override.

    A source-level capability is not a passed instance equivalence test. Consumers
    must run ``verify_routingblocks_instance`` before marking a run comparable.
    """
    p = instance.infrastructure.parameters
    if fleet_size <= 0 or fleet_size > len(instance.customers):
        raise ValueError("K_ref must be a positive physical fleet bound")
    values = (
        ("Euclidean floating-point", "Euclidean floating-point", True),
        (f"distance/{p.speed}", f"distance*{p.speed} in example", isclose(p.speed, 1.0)),
        ("Schneider service", "Schneider service", True),
        ("Schneider demands", "Schneider demands", True),
        (str(p.capacity), "Schneider C", True),
        ("hard ready/due", "hard ready/due", True),
        ("hard depot due", "depot vertex due", True),
        (str(p.battery), "Q converted to charge-time resource", True),
        (f"distance*{p.consumption}", "r*distance/g in charge-time units", True),
        (f"energy*{p.inverse_charge_rate}", "g parameter converted to energy/time", True),
        ("continuous partial", "ADPTW partial recharge", True),
        ("repeat station allowed", "intermediate station visits", True),
        (str(fleet_size), "example defaults to customer count; adapter must override", None),
        ("every activated EV returns", "depot-ended routes", True),
    )
    return tuple(Compatibility("RoutingBlocks", feature, ours, external, exact,
                               "official examples/evrptw source at pinned SHA")
                 for feature, (ours, external, exact) in zip(FEATURES, values))


def pyevrp_matrix(instance: Instance, fleet_size: int) -> tuple[Compatibility, ...]:
    p = instance.infrastructure.parameters
    values = (
        ("Euclidean floating-point", "Model uses Euclidean", True),
        (f"distance/{p.speed}", "vehicle speed can be set on Model", None),
        ("Schneider service", "Model supports service time", True),
        ("Schneider demands", "Model supports demand", True),
        (str(p.capacity), "Model capacity can be set", True),
        ("hard ready/due", "Model supports windows", True),
        ("hard depot due", "Model depot window; bundled validator checks arrival", None),
        (str(p.battery), "Model battery capacity can be set", True),
        (f"distance*{p.consumption}", "Model consumption rate can be set", True),
        (f"energy*{p.inverse_charge_rate}", "station rate can be set", True),
        ("continuous partial", "bundled GreedyInsertion charges to full", False),
        ("repeat station allowed", "not established for bundled greedy", None),
        (str(fleet_size), "Model num_available; bundled greedy does not enforce", False),
        ("every activated EV returns", "greedy appends depot; validator checks", True),
    )
    return tuple(Compatibility("pyevrp 0.2.1", feature, ours, external, exact,
                               "PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377")
                 for feature, (ours, external, exact) in zip(FEATURES, values))


def static_qualified(rows: tuple[Compatibility, ...]) -> bool:
    return all(row.exact is True for row in rows)


def dynamic_qualified(solver: str) -> bool:
    # Neither official implementation models heterogeneous mid-route vehicle
    # states plus immutable busy actions under our event information boundary.
    if solver in {"RoutingBlocks", "pyevrp 0.2.1"}:
        return False
    raise ValueError(f"Unknown external solver: {solver}")


def compare_geometry(instance: Instance, external_nodes: dict, external_arcs: dict) -> list[str]:
    """Compare parsed nodes/arcs after an adapter normalizes field names.

    external_nodes: id -> (kind, x, y, demand, ready, due, service)
    external_arcs: (from_id, to_id) -> (distance, travel_time, energy)
    """
    nodes = instance.geometry.by_id
    errors = []
    if set(external_nodes) != set(nodes):
        errors.append("node IDs/count differ")
    for key in set(external_nodes) & set(nodes):
        ours = nodes[key]
        expected = (ours.kind, ours.x, ours.y, ours.demand, ours.ready, ours.due, ours.service)
        actual = external_nodes[key]
        if actual[0] != expected[0] or any(not isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-8)
                                               for a, b in zip(actual[1:], expected[1:])):
            errors.append(f"node {key} differs")
    for (a, b), actual in external_arcs.items():
        if a not in nodes or b not in nodes:
            errors.append(f"unknown arc {a}->{b}")
            continue
        expected = (distance(nodes[a], nodes[b]), travel_time(nodes[a], nodes[b], instance.infrastructure.parameters),
                    energy(nodes[a], nodes[b], instance.infrastructure.parameters))
        if any(not isclose(float(x), y, rel_tol=1e-10, abs_tol=1e-8) for x, y in zip(actual, expected)):
            errors.append(f"arc {a}->{b} differs")
    if len(external_arcs) != len(nodes) ** 2:
        errors.append("arc matrix incomplete")
    return errors
