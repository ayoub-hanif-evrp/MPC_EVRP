"""Bounded continuous-charge fallback for fixed observable customer sequences.

The LP only proposes charge amounts and station placements. Every accepted
action is independently replayed with the common plant and terminal check.
Failure under this bounded search is never a claim of route infeasibility.
"""

from itertools import combinations, product
from math import isfinite

from scipy.optimize import linprog

from .instance import distance, energy, travel_time
from .model import Action, EPS, InfeasibleAction, Observation, VehicleState, transition
from .planning_budget import check_deadline, remaining_time


def _station_orders(state, customers, observation):
    p = observation.infrastructure.parameters
    depot = observation.infrastructure.depot
    endpoints = (state.location,) + customers + (depot,)
    choices = []
    for before, after in zip(endpoints, endpoints[1:]):
        if before.kind == "f" and not p.allow_station_to_station:
            choices.append(())
            continue
        feasible = [station for station in observation.infrastructure.stations
                    if energy(before, station, p) <= p.battery + EPS and
                    energy(station, after, p) <= p.battery + EPS]
        feasible.sort(key=lambda station: (distance(before, station) + distance(station, after)
                                           - distance(before, after), station.id))
        choices.append(tuple(feasible[:3]))
    candidates = []
    for visits in (1, 2):
        for gaps in combinations(range(len(choices)), visits):
            for stations in product(*(choices[gap] for gap in gaps)):
                detour = sum(distance(endpoints[gap], station) +
                             distance(station, endpoints[gap + 1]) -
                             distance(endpoints[gap], endpoints[gap + 1])
                             for gap, station in zip(gaps, stations))
                candidates.append((detour, gaps, stations))
    candidates.sort(key=lambda item: (item[0], item[1], tuple(s.id for s in item[2])))
    for _, gaps, stations in candidates[:24]:
        inserted = dict(zip(gaps, stations))
        order = []
        for gap in range(len(endpoints) - 1):
            if gap in inserted:
                order.append(inserted[gap])
            order.append(endpoints[gap + 1])
        yield tuple(order)


def _charge_witness(state, order, observation):
    """Minimize completion time over linear station charges and service times."""
    p = observation.infrastructure.parameters
    stations = [i for i, node in enumerate(order) if node.kind == "f"]
    charge_col = {index: col for col, index in enumerate(stations)}
    n_q, n_t = len(stations), len(order)
    n = n_q + n_t
    objective = [1e-7] * n_q + [0.0] * (n_t - 1) + [1.0]
    inequalities, bounds = [], []
    cumulative_energy = 0.0
    previous = state.location
    for i, node in enumerate(order):
        cumulative_energy += energy(previous, node, p)
        arrival = [0.0] * n
        for j in stations:
            if j < i:
                arrival[charge_col[j]] = -1.0
        inequalities.append(arrival)
        bounds.append(state.battery - cumulative_energy)
        if i in charge_col:
            departure = [-value for value in arrival]
            departure[charge_col[i]] += 1.0
            inequalities.append(departure)
            bounds.append(p.battery - state.battery + cumulative_energy)
        service = node.service if node.kind == "c" else 0.0
        advance = [0.0] * n
        advance[n_q + i] = -1.0
        if i:
            advance[n_q + i - 1] = 1.0
            rhs = -travel_time(previous, node, p) - service
        else:
            rhs = -state.time - travel_time(previous, node, p) - service
        if i in charge_col:
            advance[charge_col[i]] = p.inverse_charge_rate
        inequalities.append(advance)
        bounds.append(rhs)
        ready = [0.0] * n
        ready[n_q + i] = -1.0
        if i in charge_col:
            ready[charge_col[i]] = p.inverse_charge_rate
        inequalities.append(ready)
        bounds.append(-node.ready - service)
        due = [0.0] * n
        due[n_q + i] = 1.0
        if i in charge_col:
            due[charge_col[i]] = -p.inverse_charge_rate
        inequalities.append(due)
        bounds.append(node.due + service)
        previous = node
    horizon = observation.infrastructure.depot.due
    variable_bounds = [(1e-5, p.battery) for _ in stations] + [(0.0, horizon)] * n_t
    limit = min(0.1, max(0.01, remaining_time() - 0.04))
    solution = linprog(objective, A_ub=inequalities, b_ub=bounds,
                       bounds=variable_bounds, method="highs",
                       options={"time_limit": limit})
    if not solution.success:
        return None
    return {index: float(solution.x[col]) for index, col in charge_col.items()}


def decode_linear_charging(state: VehicleState, sequence: tuple[str, ...],
                           observation: Observation, config):
    """Return a plant-validated route or None within a small fallback budget."""
    if (config.charging_mode != "partial" or not sequence or len(sequence) > 8 or
            len(set(sequence)) != len(sequence) or
            any(c not in observation.customer_by_id or c in observation.committed_ids or
                c in state.served_customers for c in sequence)):
        return None
    customers = tuple(observation.customer_by_id[c] for c in sequence)
    if sum(c.demand for c in customers) > state.load + EPS:
        return None
    from .repair import route_proposal
    for order in _station_orders(state, customers, observation):
        check_deadline()
        if remaining_time() < 0.08:
            break
        witness = _charge_witness(state, order, observation)
        if witness is None:
            continue
        actions = []
        measured = state
        try:
            for i, node in enumerate(order):
                if node.kind == "d":
                    break
                if node.kind == "c":
                    action = Action("serve", node.id)
                else:
                    arrival_battery = measured.battery - energy(measured.location, node,
                                                                observation.infrastructure.parameters)
                    target = arrival_battery + witness[i]
                    if not isfinite(target):
                        break
                    action = Action("charge", node.id, target)
                measured = transition(measured, action, observation).after
                actions.append(action)
            else:
                continue
        except InfeasibleAction:
            continue
        if not actions or actions[-1].kind != "serve":
            actions = actions[:max((i + 1 for i, action in enumerate(actions)
                                    if action.kind == "serve"), default=0)]
        if actions and route_proposal(state, tuple(actions), observation, config) is not None:
            return tuple(actions)
    return None
