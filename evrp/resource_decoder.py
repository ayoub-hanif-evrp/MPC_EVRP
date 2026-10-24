"""Opt-in bounded MP reconstruction with incremental optimistic time bounds.

Linear charge targets combine necessary energy with useful short customer
blocks and remaining slack. Labels dominate only at the same customer stage;
truncation is heuristic and failure never certifies physical infeasibility.
"""

from functools import lru_cache

from .instance import distance, energy, travel_time
from .model import Action, EPS, InfeasibleAction, escape, transition
from .planning_budget import check_deadline


def _latest(customers, infrastructure):
    node, latest = infrastructure.depot, infrastructure.depot.due
    values = [0.0] * len(customers)
    for index in range(len(customers)-1, -1, -1):
        customer = customers[index]
        latest = min(customer.due, latest - travel_time(customer, node, infrastructure.parameters)
                     - customer.service)
        values[index] = latest
        node = customer
    return values


def _successors(state, actions, customers, index, latest, observation, config):
    customer = customers[index]
    p, infra = observation.infrastructure.parameters, observation.infrastructure
    goal = Action("serve", customer.id)
    try:
        step = transition(state, goal, observation)
        if step.service_start <= latest[index] + EPS:
            yield step.after, actions + (goal,)
    except InfeasibleAction:
        pass
    safe_nodes = (infra.depot,) + infra.stations
    stations = sorted(infra.stations, key=lambda station: (
        distance(state.location, station) + distance(station, customer) - distance(state.location, customer),
        station.id))
    for station in stations:
        check_deadline()
        if (state.location.kind == "f" and not p.allow_station_to_station
                and station.id != state.location.id):
            continue
        consumed = energy(state.location, station, p)
        if consumed > state.battery + EPS:
            continue
        arrival_battery = max(0.0, state.battery - consumed)
        arrival_time = max(state.time + travel_time(state.location, station, p), station.ready)
        slack = latest[index] - arrival_time - travel_time(station, customer, p)
        if slack <= EPS:
            continue
        upper = (min(p.battery, arrival_battery + slack / p.inverse_charge_rate)
                 if p.inverse_charge_rate > 0 else p.battery)
        needed = energy(station, customer, p) + min(energy(customer, node, p) for node in safe_nodes)
        if needed > upper + EPS:
            continue
        targets = {p.battery} if config.charging_mode == "full" else {
            upper, *(p.battery*fraction for fraction in config.charge_fractions)}
        accumulated, previous = 0.0, station
        if config.charging_mode == "partial":
            for future in customers[index:index+4]:
                accumulated += energy(previous, future, p)
                target = accumulated + min(energy(future, node, p) for node in safe_nodes)
                if target <= upper + EPS:
                    targets.add(min(upper, max(arrival_battery + 1e-6, target)))
                previous = future
        for target in sorted(targets):
            check_deadline()
            if not arrival_battery + EPS < target <= upper + EPS:
                continue
            charge = Action("charge", station.id, min(target, p.battery))
            try:
                charged = transition(state, charge, observation)
                served = transition(charged.after, goal, observation)
            except InfeasibleAction:
                continue
            if served.service_start <= latest[index] + EPS:
                yield served.after, actions + (charge, goal)


def _dominates(a, b):
    return (a.location == b.location and a.load >= b.load - EPS and
            a.time <= b.time + EPS and a.battery >= b.battery - EPS and
            a.distance_travelled <= b.distance_travelled + EPS)


@lru_cache(maxsize=16384)
def decode_resource_labels(state, sequence, observation, config):
    check_deadline()
    if (state.finished or state.current_committed_action is not None or
            state.time < observation.time - EPS or len(set(sequence)) != len(sequence) or
            any(c not in observation.customer_by_id or c in observation.committed_ids or
                c in state.served_customers for c in sequence)):
        return None
    customers = tuple(observation.customer_by_id[c] for c in sequence)
    if sum(c.demand for c in customers) > state.load + EPS:
        return None
    if not sequence:
        return () if escape(state, observation.infrastructure) is not None else None
    latest = _latest(customers, observation.infrastructure)
    if max(state.time + travel_time(state.location, customers[0], observation.infrastructure.parameters),
           customers[0].ready) > latest[0] + EPS:
        return None
    # A single-label construction handles cheap cases before bounded backtracking.
    greedy, actions = state, ()
    for index in range(len(customers)):
        check_deadline()
        goal = Action("serve", customers[index].id)
        try:
            direct = transition(greedy, goal, observation)
            if direct.service_start <= latest[index] + EPS:
                greedy, actions = direct.after, actions + (goal,)
                continue
        except InfeasibleAction:
            pass
        choices = list(_successors(greedy, actions, customers, index, latest, observation, config))
        if not choices:
            break
        greedy, actions = min(choices, key=lambda row: (row[0].time, row[0].distance_travelled,
                                                       -row[0].battery))
    else:
        from .repair import route_proposal
        if route_proposal(state, actions, observation, config) is not None:
            return actions
    labels = [(state, ())]
    for index in range(len(customers)):
        frontier = []
        for current, actions in labels:
            check_deadline()
            for candidate in _successors(current, actions, customers, index, latest, observation, config):
                if any(_dominates(old, candidate[0]) for old, _ in frontier):
                    continue
                frontier = [(old, prior) for old, prior in frontier if not _dominates(candidate[0], old)]
                frontier.append(candidate)
        if not frontier:
            return None
        labels = sorted(frontier, key=lambda row: (row[0].time, row[0].distance_travelled,
                                                  -row[0].battery))[:12]
    from .repair import route_proposal
    proposals = []
    for _, actions in labels:
        check_deadline()
        proposal = route_proposal(state, actions, observation, config)
        if proposal is not None:
            proposals.append(proposal)
    return min(proposals, key=lambda p: (p.cost, p.completion_time)).actions if proposals else None
