"""Strict adapter for Bruglieri--Moreschini CPS-MRT JSON data.

The upstream README uses camelCase labels, while the committed files use
snake_case. Matrix indices are customers, depot, then stations. Coordinates
are intentionally ignored for travel calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Charger:
    station: int
    index: int
    windows: tuple[tuple[float, float], ...]
    rate: float
    cost: float


@dataclass(frozen=True)
class Case:
    name: str
    n_customers: int
    n_stations: int
    load_capacity: float
    battery_capacity: float
    max_time: float
    consumption_rate: float
    depot_recharge_cost: float
    demands: tuple[float, ...]
    service_times: tuple[float, ...]
    starts: tuple[float, ...]
    ends: tuple[float, ...]
    distances: tuple[tuple[float, ...], ...]
    times: tuple[tuple[float, ...], ...]
    chargers: tuple[Charger, ...]
    derived: bool = False

    @property
    def depot(self) -> int:
        return self.n_customers

    def station_node(self, station: int) -> int:
        return self.n_customers + 1 + station

    def station_chargers(self, station: int) -> tuple[Charger, ...]:
        return tuple(c for c in self.chargers if c.station == station)


def from_dict(d: dict, *, one_charger: bool = False) -> Case:
    required = {"name", "n_customers", "n_stations", "load_capacity",
                "battery_capacity", "max_time", "consumption_rate", "depot_recharge_cost",
                "customer_demands", "customer_service_times", "customer_starts",
                "customer_ends", "station_n_chargers", "charger_time_windows",
                "charger_costs", "charger_profiles", "travel_distances", "travel_times"}
    if not required <= d.keys():
        raise ValueError(f"Missing Dataset A keys: {sorted(required - d.keys())}")
    n, s = int(d["n_customers"]), int(d["n_stations"])
    if n < 1 or s < 1:
        raise ValueError("Need customers and charging stations")
    counts = d["station_n_chargers"]
    if len(counts) != s or any(not isinstance(x, int) or x < 1 for x in counts):
        raise ValueError("Invalid station charger counts")
    total = sum(counts)
    if any(len(d[k]) != total for k in ("charger_time_windows", "charger_costs", "charger_profiles")):
        raise ValueError("Charger arrays do not match capacities")
    for key in ("customer_demands", "customer_service_times", "customer_starts", "customer_ends"):
        if len(d[key]) != n:
            raise ValueError(f"Wrong customer array length: {key}")
    size = n + 1 + s
    matrices = []
    for key in ("travel_distances", "travel_times"):
        matrix = d[key]
        if len(matrix) != size or any(len(row) != size for row in matrix):
            raise ValueError(f"Wrong {key} shape")
        if any(float(x) < 0 for row in matrix for x in row):
            raise ValueError(f"Negative {key}")
        if any(abs(float(matrix[i][i])) > 1e-9 for i in range(size)):
            raise ValueError(f"Nonzero {key} diagonal")
        matrices.append(tuple(tuple(float(x) for x in row) for row in matrix))
    if any(float(a) > float(b) for a, b in zip(d["customer_starts"], d["customer_ends"])):
        raise ValueError("Inverted customer window")
    if any(float(x) < 0 for x in d["customer_demands"] + d["customer_service_times"]):
        raise ValueError("Negative customer demand or service time")
    if any(float(d[k]) <= 0 for k in ("load_capacity", "battery_capacity", "max_time", "consumption_rate")):
        raise ValueError("Invalid capacity, horizon or energy rate")
    chargers = []
    offset = 0
    for station, count in enumerate(counts):
        for local in range(count):
            idx = offset + local
            if one_charger and local > 0:
                continue
            windows = tuple((float(a), float(b)) for a, b in d["charger_time_windows"][idx])
            if not windows or any(a < 0 or b <= a for a, b in windows):
                raise ValueError("Invalid charger window")
            profile = d["charger_profiles"][idx]
            if (len(profile) != 2 or len(profile[0]) != 2 or len(profile[1]) != 2 or
                    profile[0] != [0.0, 0.0] or float(profile[1][0]) <= 0 or
                    abs(float(profile[1][1]) - float(d["battery_capacity"])) > 1e-6):
                raise ValueError("Unsupported charging profile")
            rate = float(profile[1][1]) / float(profile[1][0])
            cost = float(d["charger_costs"][idx])
            if cost < 0:
                raise ValueError("Negative charging cost")
            chargers.append(Charger(station, local, windows, rate, cost))
        offset += count
    return Case(str(d["name"]) + ("_derived_1ch" if one_charger else ""), n, s,
                float(d["load_capacity"]), float(d["battery_capacity"]),
                float(d["max_time"]), float(d["consumption_rate"]),
                float(d["depot_recharge_cost"]),
                tuple(map(float, d["customer_demands"])),
                tuple(map(float, d["customer_service_times"])),
                tuple(map(float, d["customer_starts"])),
                tuple(map(float, d["customer_ends"])), matrices[0], matrices[1],
                tuple(chargers), one_charger)


def load(path: str | Path, *, one_charger: bool = False) -> Case:
    return from_dict(json.loads(Path(path).read_text(encoding="utf-8")), one_charger=one_charger)
