"""Deterministic event-driven fleet plant for the V3A modeling comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from time import perf_counter, process_time
from typing import Protocol

from .benchmark import Case


@dataclass(frozen=True)
class CustomerView:
    id: int
    demand: float
    service: float
    start: float
    end: float


@dataclass(frozen=True)
class VehicleView:
    id: int
    node: int
    energy: float
    load: float
    status: str


@dataclass(frozen=True)
class StationView:
    id: int
    node: int
    # Earliest predicted availability for each charger, including its current job.
    busy_until: tuple[float, ...]
    waiting: tuple[int, ...]
    rates: tuple[float, ...]
    windows: tuple[tuple[tuple[float, float], ...], ...]


@dataclass(frozen=True)
class Observation:
    now: float
    depot: int
    max_time: float
    battery_capacity: float
    load_capacity: float
    consumption_rate: float
    customers: tuple[CustomerView, ...]
    vehicles: tuple[VehicleView, ...]
    stations: tuple[StationView, ...]
    # Only the observable induced subgraph is revealed. Hidden customer nodes
    # and their windows cannot be reached through the policy interface.
    travel_times: dict[tuple[int, int], float]
    distances: dict[tuple[int, int], float]

    def travel(self, a: int, b: int) -> float:
        return self.travel_times[(a, b)]

    def energy(self, a: int, b: int) -> float:
        return self.distances[(a, b)] * self.consumption_rate


@dataclass(frozen=True)
class Action:
    kind: str  # customer, station, depot
    target: int  # customer ID or station ID; ignored for depot
    charge_to: float = 0.0


class Policy(Protocol):
    def decide(self, observation: Observation, vehicle_id: int) -> Action | None: ...


@dataclass
class Vehicle:
    id: int
    node: int
    energy: float
    load: float
    status: str = "idle"
    queue_station: int | None = None
    charge_to: float = 0.0
    charger_index: int | None = None


@dataclass
class Outcome:
    case: str
    policy: str
    announced: int
    accepted: int
    served: int
    broken_accepted: int
    rejected: int
    charging_wait: float
    resource_conflicts: int
    physical_violations: int
    distance: float
    charging_cost: float
    decision_latencies: list[float]
    decisions: list[dict]
    events: list[dict]
    wall_seconds: float
    cpu_seconds: float
    timed_out: bool = False
    failure: str | None = None


class FleetSimulator:
    def __init__(self, case: Case, *, fleet_size: int = 4, releases: tuple[float, ...] | None = None,
                 decision_limit: float = 5.0, episode_limit: float = 600.0):
        if fleet_size < 1:
            raise ValueError("Fleet must be positive")
        self.case = case
        self.releases = releases or tuple(max(0.0, x - 120.0) for x in case.starts)
        if len(self.releases) != case.n_customers or any(x < 0 for x in self.releases):
            raise ValueError("Invalid releases")
        self.vehicles = [Vehicle(i, case.depot, case.battery_capacity, case.load_capacity)
                         for i in range(fleet_size)]
        self.decision_limit = decision_limit
        self.episode_limit = episode_limit
        self.events: list[dict] = []
        self.decisions: list[dict] = []
        self.heap: list[tuple[float, int, int, str, int, float]] = []
        self.seq = 0
        for i, t in enumerate(self.releases):
            self._push(t, 0, "release", i)
        self.now = 0.0
        self.announced: set[int] = set()
        self.accepted: set[int] = set()
        self.served: set[int] = set()
        self.reserved: set[int] = set()
        self.queue: dict[int, list[tuple[float, int]]] = {s: [] for s in range(case.n_stations)}
        self.busy: dict[tuple[int, int], tuple[int, float]] = {}
        self.charging_wait = 0.0
        self.resource_conflicts = 0
        self.physical_violations = 0
        self.distance = 0.0
        self.charging_cost = 0.0
        self.latencies: list[float] = []

    def _push(self, t: float, priority: int, kind: str, ident: int, value: float = 0.0) -> None:
        if t <= self.case.max_time + 1e-9:
            heapq.heappush(self.heap, (t, priority, self.seq, kind, ident, value))
            self.seq += 1

    def _log(self, kind: str, **fields: object) -> None:
        self.events.append({"time": self.now, "kind": kind, **fields})

    def observation(self) -> Observation:
        c = self.case
        customers = tuple(CustomerView(i, c.demands[i], c.service_times[i], c.starts[i], c.ends[i])
                          for i in sorted(self.accepted - self.served - self.reserved))
        vehicles = tuple(VehicleView(v.id, v.node, v.energy, v.load, v.status) for v in self.vehicles)
        stations = []
        for s in range(c.n_stations):
            chargers = c.station_chargers(s)
            stations.append(StationView(s, c.station_node(s),
                                        tuple(self.busy.get((s, ch.index), (-1, self.now))[1]
                                              for ch in chargers),
                                        tuple(vid for _, vid in sorted(self.queue[s])),
                                        tuple(ch.rate for ch in chargers),
                                        tuple(ch.windows for ch in chargers)))
        nodes = {c.depot} | {v.node for v in self.vehicles} | {x.id for x in customers} | {
            c.station_node(s) for s in range(c.n_stations)}
        pairs = ((a, b) for a in nodes for b in nodes)
        pairs = tuple(pairs)
        return Observation(self.now, c.depot, c.max_time, c.battery_capacity,
                           c.load_capacity, c.consumption_rate, customers, vehicles,
                           tuple(stations), {(a, b): c.times[a][b] for a, b in pairs},
                           {(a, b): c.distances[a][b] for a, b in pairs})

    def _accept(self, i: int) -> bool:
        c = self.case
        earliest = max(self.now + c.times[c.depot][i], c.starts[i])
        return (c.demands[i] <= c.load_capacity and earliest <= c.ends[i] + 1e-9 and
                earliest + c.service_times[i] + c.times[i][c.depot] <= c.max_time + 1e-9)

    def _dispatch(self, v: Vehicle, action: Action) -> None:
        c = self.case
        if action.kind == "customer":
            if action.target not in self.accepted - self.served - self.reserved:
                raise ValueError("Customer not visible and available")
            target = action.target
            if v.load + 1e-9 < c.demands[target]:
                raise ValueError("Insufficient load")
            start = max(self.now + c.times[v.node][target], c.starts[target])
            if (start > c.ends[target] + 1e-9 or
                    start + c.service_times[target] + c.times[target][c.depot] > c.max_time + 1e-9):
                raise ValueError("Customer window violated by dispatch")
            if v.energy + 1e-9 < c.consumption_rate * (c.distances[v.node][target] + c.distances[target][c.depot]):
                raise ValueError("Customer dispatch lacks direct return energy")
            self.reserved.add(target)
        elif action.kind == "station":
            if not 0 <= action.target < c.n_stations:
                raise ValueError("Invalid station")
            target = c.station_node(action.target)
            arrival_energy = v.energy - c.distances[v.node][target] * c.consumption_rate
            if not arrival_energy < action.charge_to <= c.battery_capacity + 1e-9:
                raise ValueError("Invalid partial charging target")
        elif action.kind == "depot":
            target = c.depot
            if v.node == target:
                return
        else:
            raise ValueError("Unknown action")
        energy = c.distances[v.node][target] * c.consumption_rate
        if energy > v.energy + 1e-9:
            raise ValueError("Travel energy violated")
        if v.status == "queued":
            assert v.queue_station is not None
            self.queue[v.queue_station] = [(t, i) for t, i in self.queue[v.queue_station] if i != v.id]
            self._log("queue_abandon", vehicle=v.id, station=v.queue_station)
            v.queue_station = None
        origin = v.node
        v.energy -= energy
        self.distance += c.distances[origin][target]
        v.status = "travel"
        v.charge_to = action.charge_to
        self._log("depart", vehicle=v.id, origin=origin, destination=target,
                  action=action.kind, customer=action.target if action.kind == "customer" else None,
                  station=action.target if action.kind == "station" else None,
                  energy_before=v.energy + energy, energy_after=v.energy)
        self._push(self.now + c.times[origin][target], 1, "arrival", v.id, float(target))

    def _drain_station(self, station: int) -> None:
        c = self.case
        queue = self.queue[station]
        queue.sort()
        while queue:
            arrival, vid = queue[0]
            v = self.vehicles[vid]
            if v.status != "queued":
                queue.pop(0)
                continue
            candidates = []
            for ch in c.station_chargers(station):
                if (station, ch.index) in self.busy:
                    continue
                duration = (v.charge_to - v.energy) / ch.rate
                if duration <= 0:
                    raise ValueError("Invalid charging duration")
                for lo, hi in ch.windows:
                    start = max(self.now, lo)
                    if start + duration <= min(hi, c.max_time) + 1e-9:
                        candidates.append((start, ch.index, duration, ch))
                        break
            if not candidates:
                # A busy charger will trigger this queue on completion. A closed
                # charger triggers it at its next window opening.
                for ch in c.station_chargers(station):
                    for lo, _ in ch.windows:
                        if lo > self.now + 1e-9:
                            self._push(lo, 3, "station_check", station)
                if any(key[0] == station for key in self.busy):
                    self.resource_conflicts += 1
                break
            start, idx, duration, ch = min(candidates, key=lambda x: (x[0], x[1]))
            if start > self.now + 1e-9:
                self._push(start, 3, "station_check", station)
                break
            queue.pop(0)
            self.charging_wait += self.now - arrival
            self.busy[(station, idx)] = (vid, self.now + duration)
            v.status = "charging"
            v.charger_index = idx
            self._log("charge_start", vehicle=vid, station=station, charger=idx,
                      energy_before=v.energy, target=v.charge_to, duration=duration,
                      queue_arrival=arrival)
            self._push(self.now + duration, 2, "charge_done", vid, float(station))

    def _event(self, kind: str, ident: int, value: float) -> None:
        c = self.case
        if kind == "release":
            self.announced.add(ident)
            accepted = self._accept(ident)
            if accepted:
                self.accepted.add(ident)
            self._log("release", customer=ident, accepted=accepted)
        elif kind == "arrival":
            v = self.vehicles[ident]
            target = int(value)
            v.node = target
            self._log("arrival", vehicle=ident, node=target)
            if target < c.n_customers:
                start = max(self.now, c.starts[target])
                if start > c.ends[target] + 1e-9:
                    self.physical_violations += 1
                    v.status = "idle"
                    self.reserved.discard(target)
                else:
                    v.status = "service"
                    self._push(start + c.service_times[target], 2, "service_done", ident, float(target))
            elif target == c.depot:
                v.status = "idle"
                v.load = c.load_capacity
                self.charging_cost += (c.battery_capacity - v.energy) * c.depot_recharge_cost
                v.energy = c.battery_capacity
                self._log("depot_reload", vehicle=ident, energy=v.energy, load=v.load)
            else:
                station = target - c.depot - 1
                v.status = "queued"
                v.queue_station = station
                self.queue[station].append((self.now, ident))
                self._log("queue_enter", vehicle=ident, station=station)
                self._drain_station(station)
        elif kind == "service_done":
            v = self.vehicles[ident]
            customer = int(value)
            v.load -= c.demands[customer]
            v.status = "idle"
            self.reserved.remove(customer)
            self.served.add(customer)
            self._log("service_done", vehicle=ident, customer=customer, load=v.load)
        elif kind == "charge_done":
            v = self.vehicles[ident]
            station = int(value)
            idx = v.charger_index
            assert idx is not None
            ch = next(ch for ch in c.station_chargers(station) if ch.index == idx)
            gained = v.charge_to - v.energy
            self.charging_cost += gained * ch.cost
            v.energy = v.charge_to
            v.status = "idle"
            v.queue_station = None
            v.charger_index = None
            del self.busy[(station, idx)]
            self._log("charge_done", vehicle=ident, station=station, charger=idx,
                      gained=gained, energy=v.energy)
            self._drain_station(station)
        elif kind == "station_check":
            self._drain_station(ident)
        else:
            raise ValueError(kind)

    def run(self, policy: Policy, *, name: str) -> Outcome:
        wall_start, cpu_start = perf_counter(), process_time()
        failure = None
        timed_out = False
        try:
            while self.heap:
                if perf_counter() - wall_start > self.episode_limit:
                    timed_out = True
                    failure = "episode watchdog"
                    break
                t, _, _, kind, ident, value = heapq.heappop(self.heap)
                if t < self.now - 1e-9:
                    raise ValueError("Event time reversed")
                self.now = t
                self._event(kind, ident, value)
                for v in self.vehicles:
                    if v.status not in {"idle", "queued"}:
                        continue
                    obs = self.observation()
                    start = perf_counter()
                    action = policy.decide(obs, v.id)
                    latency = perf_counter() - start
                    self.latencies.append(latency)
                    if latency > self.decision_limit:
                        raise TimeoutError(f"Decision exceeded {self.decision_limit}s")
                    self.decisions.append({"time": self.now, "vehicle": v.id,
                                           "action": vars(action) if action else None,
                                           "latency": latency})
                    if action is not None:
                        self._dispatch(v, action)
        except (ValueError, TimeoutError, AssertionError) as exc:
            failure = f"{type(exc).__name__}: {exc}"
            self.physical_violations += isinstance(exc, ValueError)
        if failure is None and any(v.node != self.case.depot or v.status != "idle" for v in self.vehicles):
            failure = "fleet did not return to depot by horizon"
            self.physical_violations += 1
        return Outcome(self.case.name, name, len(self.announced), len(self.accepted),
                       len(self.served), len(self.accepted - self.served),
                       len(self.announced - self.accepted), self.charging_wait,
                       self.resource_conflicts, self.physical_violations, self.distance,
                       self.charging_cost, self.latencies, self.decisions, self.events,
                       perf_counter() - wall_start, process_time() - cpu_start,
                       timed_out, failure)
