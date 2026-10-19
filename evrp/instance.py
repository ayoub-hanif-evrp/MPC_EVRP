"""Read-only Desaulniers benchmark parsing and immutable problem data."""

from dataclasses import dataclass
from collections.abc import Mapping
from functools import cached_property, lru_cache
from types import MappingProxyType
from hashlib import sha256
from math import ceil, hypot, isfinite
from pathlib import Path
import re


class FrozenMap(Mapping):
    """Read-only lookup with explicit pickle/deepcopy support for agent workers."""
    def __init__(self, values):
        self._values = MappingProxyType(dict(values))

    def __getitem__(self, key):
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __reduce__(self):
        return type(self), (dict(self._values),)

    def __deepcopy__(self, memo):
        return self


@dataclass(frozen=True)
class Location:
    id: str
    kind: str
    x: float
    y: float
    demand: float
    ready: float
    due: float
    service: float
    distance_precision: int = 0


@dataclass(frozen=True)
class Parameters:
    battery: float
    capacity: float
    consumption: float
    inverse_charge_rate: float
    speed: float
    energy_precision: int = 0
    allow_station_to_station: bool = True


@dataclass(frozen=True)
class Infrastructure:
    depot: Location
    stations: tuple[Location, ...]
    parameters: Parameters

    @cached_property
    def node_by_id(self):
        return FrozenMap((n.id, n) for n in (self.depot,) + self.stations)

    @cached_property
    def _hash(self):
        return hash((self.depot, self.stations, self.parameters))

    def __hash__(self):
        return self._hash


@dataclass(frozen=True)
class Instance:
    name: str
    sha256: str
    infrastructure: Infrastructure
    customers: tuple[Location, ...]

    @cached_property
    def geometry(self):
        nodes = (self.infrastructure.depot,) + self.infrastructure.stations + self.customers
        p = self.infrastructure.parameters
        return StaticGeometry(nodes, FrozenMap((n.id, n) for n in nodes),
                              tuple(tuple(distance(a, b) for b in nodes) for a in nodes),
                              tuple(tuple(travel_time(a, b, p) for b in nodes) for a in nodes),
                              tuple(tuple(energy(a, b, p) for b in nodes) for a in nodes))


@dataclass(frozen=True)
class StaticGeometry:
    nodes: tuple[Location, ...]
    by_id: FrozenMap
    distance: tuple[tuple[float, ...], ...]
    travel_time: tuple[tuple[float, ...], ...]
    energy: tuple[tuple[float, ...], ...]


ProblemInstance = Instance


def distance(a: Location, b: Location) -> float:
    if a.distance_precision != b.distance_precision:
        raise ValueError("Locations use different benchmark distance semantics")
    raw = _distance(a.x, a.y, b.x, b.y)
    return _rounded_up(raw, a.distance_precision)


def _rounded_up(value: float, precision: int) -> float:
    return ceil(value * precision - 1e-9) / precision if precision else value


@lru_cache(maxsize=524288)
def _distance(ax, ay, bx, by):
    return hypot(ax - bx, ay - by)


@lru_cache(maxsize=524288)
def _travel(ax, ay, bx, by, speed):
    return _distance(ax, ay, bx, by) / speed


@lru_cache(maxsize=524288)
def _energy(ax, ay, bx, by, consumption):
    return _distance(ax, ay, bx, by) * consumption


def travel_time(a, b, parameters):
    if a.distance_precision:
        return distance(a, b) / parameters.speed
    return _travel(a.x, a.y, b.x, b.y, parameters.speed)


def energy(a, b, parameters):
    raw = _energy(a.x, a.y, b.x, b.y, parameters.consumption)
    return _rounded_up(raw, parameters.energy_precision)


def discover_instances(size: int | None = None) -> tuple[Path, ...]:
    from .storage import BENCHMARK

    paths = tuple(sorted(path for path in BENCHMARK.glob("*.txt")
                         if path.stem.endswith(("_25", "_50", "_100"))))
    if size is not None and size not in {25, 50, 100}:
        raise ValueError("Supported benchmark sizes are 25, 50, and 100")
    return tuple(path for path in paths if size is None or path.stem.endswith(f"_{size}"))


def _validate_published_arcs(path: Path, nodes: tuple[Location, ...], parameters: Parameters):
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 5 or lines[0].split() != ["CAPACITY", str(int(parameters.capacity))]:
        raise ValueError(f"Invalid Desaulniers arc header: {path}")
    if lines[1].split() != ["BATTERY", str(round(parameters.battery * 100))]:
        raise ValueError(f"Time-equivalent battery mismatch: {path}")
    if lines[2].split() != ["NODES", str(len(nodes))]:
        raise ValueError(f"Node count mismatch: {path}")
    by_id = {node.id: node for node in nodes}
    for line, node in zip(lines[3:3 + len(nodes)], nodes):
        if line.split() != [node.kind, node.id, str(int(node.demand)),
                            str(round(node.ready * 100)), str(round(node.due * 100))]:
            raise ValueError(f"Published node differs from coordinate format: {node.id}")
    marker = 3 + len(nodes)
    header = lines[marker].split()
    if len(header) != 2 or header[0] != "ARCS":
        raise ValueError(f"Missing Desaulniers arc count: {path}")
    count = int(header[1])
    expected = {(a.id, b.id) for a in nodes for b in nodes
                if a.id != b.id and not (a.kind == b.kind == "f")}
    if count != len(expected):
        raise ValueError(f"Unexpected Desaulniers arc topology: {path}")
    seen = set()
    for line in lines[marker + 1:marker + 1 + count]:
        parts = line.split()
        if len(parts) != 5 or (parts[0], parts[1]) not in expected:
            raise ValueError(f"Invalid Desaulniers arc: {line}")
        tail, head = by_id[parts[0]], by_id[parts[1]]
        key = tail.id, head.id
        if key in seen:
            raise ValueError(f"Duplicate Desaulniers arc: {key}")
        seen.add(key)
        actual = tuple(map(int, parts[2:]))
        calculated = (round(distance(tail, head) * 100),
                      round((travel_time(tail, head, parameters) + tail.service) * 100),
                      round(energy(tail, head, parameters) * 100))
        if actual != calculated:
            raise ValueError(f"Rounded Desaulniers arc mismatch at {key}: {actual} != {calculated}")
    if seen != expected:
        raise ValueError(f"Missing Desaulniers arcs: {path}")


def load_instance(path: str | Path) -> Instance:
    from .storage import BENCHMARK, BENCHMARK_ARCS

    path = Path(path)
    if path.parent.resolve() != BENCHMARK.resolve() or path.suffix != ".txt":
        raise ValueError("Only active Desaulniers format-1 instances are supported")
    arc_name = path.stem.removesuffix("_100")
    arc_path = BENCHMARK_ARCS / f"{arc_name}.inst"
    raw = path.read_bytes()
    arc_raw = arc_path.read_bytes()
    rows: list[Location] = []
    params: dict[str, float] = {}
    labels = {"Vehicle fuel tank capacity": "Q", "Vehicle load capacity": "C",
              "Fuel consumption rate": "g", "Inverse refueling rate": "r",
              "Average Velocity": "v"}
    for line in raw.decode("utf-8-sig").splitlines():
        fields = line.split()
        if not fields or fields[0] == "StringID":
            continue
        parameter = re.fullmatch(r"([^/]+)\s*/\s*([^/]+)\s*/", line.strip())
        if parameter and parameter.group(1).strip() in labels:
            key, value = labels[parameter.group(1).strip()], parameter.group(2)
            if key in params:
                raise ValueError(f"Duplicate parameter {key}")
            params[key] = float(value)
            continue
        if len(fields) != 8 or fields[1] not in {"d", "f", "c"}:
            raise ValueError(f"Invalid Desaulniers row: {line!r}")
        row = Location(fields[0], fields[1], *(float(v) for v in fields[2:]), 100)
        values = (row.x, row.y, row.demand, row.ready, row.due, row.service)
        if not all(isfinite(v) for v in values):
            raise ValueError("Non-finite location data")
        if min(row.demand, row.ready, row.service) < 0 or row.ready > row.due:
            raise ValueError(f"Invalid bounds at {row.id}")
        rows.append(row)
    if set(params) != set("QCrgv") or any(not isfinite(v) or v <= 0 for v in params.values()):
        raise ValueError("Five finite positive vehicle parameters are required")
    depots = [row for row in rows if row.kind == "d"]
    if len(depots) != 1 or len({r.id for r in rows}) != len(rows):
        raise ValueError("Exactly one depot and unique location IDs are required")
    depot = depots[0]
    stations = tuple(row for row in rows if row.kind == "f")
    # The published instances give stations the same operating interval as the depot.
    if any(s.ready != depot.ready or s.due != depot.due or s.service or s.demand for s in stations):
        raise ValueError("Stations must share depot hours and have zero demand/service")
    if depot.service or depot.demand:
        raise ValueError("Depot must have zero demand/service")
    if params["g"] != 1 or params["v"] != 1:
        raise ValueError("Published time-equivalent arc validation requires unit consumption and speed")
    parameters = Parameters(_rounded_up(params["Q"] * params["r"], 100), params["C"],
                            params["r"], 1.0, 1.0, 100, False)
    nodes = (depot,) + stations + tuple(row for row in rows if row.kind == "c")
    _validate_published_arcs(arc_path, nodes, parameters)
    identity = sha256(raw + b"\0" + arc_raw + b"\0Desaulniers-2016-MP").hexdigest()
    instance = Instance(path.stem, identity, Infrastructure(depot, stations, parameters),
                        tuple(row for row in rows if row.kind == "c"))
    # The complete matrix stays on Instance, never in the agents' Observation.
    # Coordinate-only caches are prewarmed for known pairs without exposing hidden IDs.
    instance.geometry
    return instance
