"""Independent physical replay of externally supplied static route node orders."""

from dataclasses import dataclass
from math import isfinite

from scipy.optimize import linprog

from evrp.instance import Instance, distance, energy, travel_time
from evrp.model import Action, InfeasibleAction, Observation, transition
from evrp.reference import initial_vehicle


@dataclass(frozen=True)
class ReplayResult:
    feasible: bool
    complete: bool
    served: int
    vehicles: int
    distance: float
    reason: str = ""


def _charge_witness(instance: Instance, sequence: tuple[str, ...]) -> dict[int, float]:
    """Find continuous charges for the given station order, without rerouting it."""
    nodes = instance.geometry.by_id
    p = instance.infrastructure.parameters
    stations = [i for i in range(1, len(sequence) - 1) if nodes[sequence[i]].kind == "f"]
    charge_col = {index: col for col, index in enumerate(stations)}
    n_q, n_t = len(stations), len(sequence) - 1
    n = n_q + n_t
    objective = [1e-7] * n_q + [1e-8] * (n_t - 1) + [1.0]
    inequalities, limits = [], []

    def at(i):
        return n_q + i - 1

    def add(row, limit):
        inequalities.append(row)
        limits.append(limit)

    cumulative_energy = 0.0
    for i in range(1, len(sequence)):
        before, node = nodes[sequence[i - 1]], nodes[sequence[i]]
        cumulative_energy += energy(before, node, p)
        prior = [position for position in stations if position < i]
        arrival = [0.0] * n
        for position in prior:
            arrival[charge_col[position]] = -1.0
        # Q + prior charges - consumed energy >= 0.
        add(arrival, p.battery - cumulative_energy)
        if i in charge_col:
            departure = [-value for value in arrival]
            departure[charge_col[i]] += 1.0
            # Q + all charges - consumed energy <= Q.
            add(departure, cumulative_energy)

        service = node.service if node.kind == "c" else 0.0
        row = [0.0] * n
        row[at(i)] = -1.0
        if i > 1:
            row[at(i - 1)] = 1.0
        if i in charge_col:
            row[charge_col[i]] = p.inverse_charge_rate
        add(row, -travel_time(before, node, p) - service)

        ready_row = [0.0] * n
        ready_row[at(i)] = -1.0
        if i in charge_col:
            ready_row[charge_col[i]] = p.inverse_charge_rate
        add(ready_row, -node.ready - service)

        due_row = [0.0] * n
        due_row[at(i)] = 1.0
        if i in charge_col:
            due_row[charge_col[i]] = -p.inverse_charge_rate
        add(due_row, node.due + service)

    bounds = [(1e-6, p.battery) for _ in stations] + [(0.0, instance.infrastructure.depot.due)] * n_t
    solved = linprog(objective, A_ub=inequalities, b_ub=limits, bounds=bounds, method="highs")
    if not solved.success:
        raise ValueError(f"no charging/time witness: {solved.message}")
    return {position: float(solved.x[col]) for position, col in charge_col.items()}


def replay_routes(instance: Instance, routes: list[list[str]] | tuple[tuple[str, ...], ...],
                  fleet_size: int) -> ReplayResult:
    """Validate external order with our own physics; missing service is reported."""
    depot = instance.infrastructure.depot.id
    nodes = instance.geometry.by_id
    customer_ids = {customer.id for customer in instance.customers}
    seen: set[str] = set()
    vehicles, total_distance = 0, 0.0
    if fleet_size <= 0:
        return ReplayResult(False, False, 0, 0, 0.0, "invalid K_ref")
    for route in routes:
        sequence = tuple(route)
        if not sequence or sequence == (depot, depot):
            continue
        if len(sequence) < 3 or sequence[0] != depot or sequence[-1] != depot:
            return ReplayResult(False, False, len(seen), vehicles, total_distance, "route must start/end at depot")
        if any(key not in nodes for key in sequence):
            return ReplayResult(False, False, len(seen), vehicles, total_distance, "unknown vertex")
        if any(key == depot for key in sequence[1:-1]):
            return ReplayResult(False, False, len(seen), vehicles, total_distance, "intermediate depot")
        if not any(key in customer_ids for key in sequence):
            return ReplayResult(False, False, len(seen), vehicles, total_distance, "station-only route")
        vehicles += 1
        if vehicles > fleet_size:
            return ReplayResult(False, False, len(seen), vehicles, total_distance, "K_ref exceeded")
        route_customers = [key for key in sequence if key in customer_ids]
        if len(set(route_customers)) != len(route_customers) or seen.intersection(route_customers):
            return ReplayResult(False, False, len(seen), vehicles, total_distance, "duplicate customer")
        if sum(nodes[key].demand for key in route_customers) > instance.infrastructure.parameters.capacity + 1e-8:
            return ReplayResult(False, False, len(seen), vehicles, total_distance, "capacity exceeded")
        try:
            charges = _charge_witness(instance, sequence)
            state = initial_vehicle(instance, vehicles - 1)
            observation = Observation(state.time, instance.infrastructure, instance.customers)
            for i, key in enumerate(sequence[1:], 1):
                node = nodes[key]
                if node.kind == "f":
                    arrival = state.battery - energy(state.location, node, instance.infrastructure.parameters)
                    action = Action("charge", key, arrival + charges[i])
                elif node.kind == "c":
                    action = Action("serve", key)
                else:
                    action = Action("return", key)
                step = transition(state, action, observation)
                state = step.after
                total_distance += step.distance
            if not state.finished or state.location.id != depot or not isfinite(total_distance):
                raise ValueError("missing safe depot return")
        except (ValueError, InfeasibleAction) as error:
            return ReplayResult(False, False, len(seen), vehicles, total_distance, str(error))
        seen.update(route_customers)
    return ReplayResult(True, seen == customer_ids, len(seen), vehicles, total_distance)
