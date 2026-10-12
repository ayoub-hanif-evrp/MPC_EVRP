"""Fleet-level MCTS over released customer sequences and EV assignments."""

from dataclasses import dataclass, field
from math import floor, isfinite, sqrt
from random import Random
from time import perf_counter

from .instance import distance, energy, travel_time
from .model import EPS, Action, Observation, VehicleState, escape, transition
from .mpc import MPCConfig, MPCProposal
from .planning_budget import PlanningDeadlineExceeded, check_deadline, remaining_time
from .repair import build_route, regret_repair, route_proposal


class _SearchBudgetReached(Exception):
    pass


@dataclass(frozen=True)
class FleetPlan:
    sequences: tuple[tuple[str, ...], ...]
    actions: tuple[tuple[Action, ...], ...]
    costs: tuple[float, ...]
    proposals: tuple[MPCProposal | None, ...]
    score: tuple[float, ...]
    components: dict[str, float]


@dataclass(frozen=True)
class FleetMCTSResult:
    routes: dict[int, tuple[Action, ...]]
    validated: dict[int, MPCProposal]
    initial_score: tuple[float, ...]
    seed_score: tuple[float, ...]
    best_score: tuple[float, ...]
    best_components: dict[str, float]
    criticality: dict[str, dict]
    iterations: int
    nodes_expanded: int
    tree_improvements: int
    service_seconds: float
    full_seconds: float
    elapsed: float
    deadline_reached: bool


@dataclass
class _Node:
    plan: FleetPlan
    depth: int
    visits: int = 0
    value: float = 0.0
    candidates: list[FleetPlan] | None = None
    children: list["_Node"] = field(default_factory=list)
    prior: float = 1.0


class _FleetProblem:
    def __init__(self, origins: dict[int, VehicleState], observation: Observation,
                 config: MPCConfig, position_limit: int, regret_k: int):
        self.ids = tuple(sorted(origins))
        self.origins = origins
        self.observation = observation
        self.config = config
        self.position_limit = position_limit
        self.regret_k = regret_k
        served = {c for state in origins.values() for c in state.served_customers}
        self.pending = frozenset(observation.customer_by_id) - observation.committed_ids - served
        self.dscale = max(1.0, sum(distance(observation.infrastructure.depot,
                                            observation.customer_by_id[c]) for c in self.pending))
        self.initial_owners: dict[str, int] = {}
        self.route_metrics: dict[tuple[int, tuple[Action, ...]], dict[str, float]] = {}
        self.criticality_cache: dict[tuple[tuple[str, ...], ...], list[tuple[str, int, float, float, float]]] = {}
        self.target_stats: dict[str, dict[str, int]] = {}
        self.search_until: float | None = None
        self.screen_cache: dict[tuple[int, tuple[str, ...]], tuple[tuple[float, ...], tuple[float, ...], float]] = {}
        # This cache belongs only to the immutable root observation and origins.
        self.decoded: dict[tuple[int, tuple[str, ...]], tuple[tuple[Action, ...], MPCProposal | None] | None] = {}

    def _check_search_time(self) -> None:
        if self.search_until is not None and perf_counter() >= self.search_until:
            raise _SearchBudgetReached

    @staticmethod
    def _unit(value: float) -> float:
        return max(0.0, min(1.0, value))

    def _metrics(self, k: int, actions: tuple[Action, ...]) -> dict[str, float]:
        key = (k, actions)
        if key in self.route_metrics:
            return self.route_metrics[key]
        state = self.origins[k]
        p = self.observation.infrastructure.parameters
        tw, battery = [], []
        for action in actions:
            self._check_search_time()
            step = transition(state, action, self.observation)
            state = step.after
            if step.served:
                customer = self.observation.customer_by_id[step.served]
                width = max(EPS, customer.due - customer.ready)
                tw.append(1.0 - self._unit((customer.due - step.service_start) / width))
            if action.kind in {"serve", "charge"}:
                safe_energy = min(energy(state.location, node, p) for node in
                                  (self.observation.infrastructure.depot,) + self.observation.infrastructure.stations)
                battery.append(1.0 - self._unit((state.battery - safe_energy) / p.battery))
        duration = max(0.0, state.time - self.origins[k].time)
        safe = escape(state, self.observation.infrastructure)
        finish = safe.completion if safe is not None else state.time
        horizon = max(EPS, self.observation.infrastructure.depot.due - self.observation.time)
        result = dict(tw=(sum(tw) / len(tw) + max(tw)) / 2 if tw else 0.0,
                      battery=(sum(battery) / len(battery) + max(battery)) / 2 if battery else 0.0,
                      capacity=1.0 - self._unit(state.load / p.capacity) if actions else 0.0,
                      duration=self._unit(duration / horizon),
                      charge=self._unit((state.charging_time - self.origins[k].charging_time) /
                                        horizon),
                      wait=self._unit((state.waiting_time - self.origins[k].waiting_time) /
                                      horizon),
                      time_risk=1.0 - self._unit((self.observation.infrastructure.depot.due - finish) / horizon))
        self.route_metrics[key] = result
        return result

    def _score(self, sequences, actions, costs):
        owned = {c for sequence in sequences for c in sequence}
        uncovered = self.pending - owned
        vehicles = sum(self.origins[k].departed or bool(actions[index])
                       for index, k in enumerate(self.ids))
        risks = [self._metrics(k, actions[index]) for index, k in enumerate(self.ids) if actions[index]]
        mean = lambda field: sum(r[field] for r in risks) / len(risks) if risks else 0.0
        tw = mean("tw")
        battery = mean("battery")
        capacity = mean("capacity")
        active_time_risks = [self._metrics(k, actions[index])["time_risk"]
                             for index, k in enumerate(self.ids)
                             if self.origins[k].departed or actions[index]]
        time_risk = (sum(active_time_risks) / len(active_time_risks)
                     if active_time_risks else 0.0)
        flexibility_risk = (tw + battery + capacity + time_risk) / 4
        route_distance = sum(costs)
        normalized_distance = self._unit(route_distance / max(1.0, self.dscale * 2))
        durations = [r["duration"] for r in risks]
        balance = max(durations) - min(durations) if len(durations) > 1 else 0.0
        moved = sum(self.initial_owners.get(c, k) != k for index, k in enumerate(self.ids)
                    for c in sequences[index])
        instability = moved / max(1, len(owned))
        if uncovered:
            critical = self._criticality(tuple(sequences))
            zero = sum(count == 0 for _, count, _, _, _ in critical)
            one = sum(count == 1 for _, count, _, _, _ in critical)
            components = dict(unserved_customers=len(uncovered), screened_zero_option_customers=zero,
                              screened_one_option_customers=one, time_window_risk=tw,
                              battery_risk=battery, capacity_risk=capacity, time_reserve_risk=time_risk,
                              flexibility_risk=flexibility_risk,
                              normalized_distance=normalized_distance,
                              activated_vehicles=vehicles, distance=route_distance,
                              route_instability=instability)
            score = (len(uncovered), zero, one, tw, battery, capacity, normalized_distance)
        else:
            operational = sum((normalized_distance, mean("duration"), mean("charge"),
                               mean("wait"), tw, battery, balance)) / 7
            components = dict(unserved_customers=0, screened_zero_option_customers=0,
                              screened_one_option_customers=0, time_window_risk=tw,
                              battery_risk=battery, capacity_risk=capacity,
                              time_reserve_risk=time_risk, flexibility_risk=flexibility_risk,
                              normalized_distance=normalized_distance,
                              normalized_route_duration=mean("duration"),
                              normalized_charging_time=mean("charge"),
                              normalized_waiting_time=mean("wait"),
                              route_balance_risk=balance, operational_cost=operational,
                              activated_vehicles=vehicles, distance=route_distance,
                              route_instability=instability)
            score = (0, flexibility_risk, vehicles, operational, route_distance, instability)
        return score, components

    def _screen_profile(self, k: int, sequence: tuple[str, ...]):
        key = (k, sequence)
        if key in self.screen_cache:
            return self.screen_cache[key]
        customer_map = self.observation.customer_by_id
        p = self.observation.infrastructure.parameters
        forward = [self.origins[k].time]
        location = self.origins[k].location
        demand = 0.0
        for customer_id in sequence:
            customer = customer_map[customer_id]
            start = max(forward[-1] + travel_time(location, customer, p), customer.ready)
            forward.append(start + customer.service)
            location = customer
            demand += customer.demand
        backward = [0.0] * len(sequence)
        next_node = self.observation.infrastructure.depot
        latest = next_node.due
        for index in range(len(sequence) - 1, -1, -1):
            customer = customer_map[sequence[index]]
            latest = min(customer.due, latest - travel_time(customer, next_node, p) - customer.service)
            backward[index] = latest
            next_node = customer
        profile = (tuple(forward), tuple(backward), demand)
        self.screen_cache[key] = profile
        return profile

    def _screen_gap(self, k: int, sequence: tuple[str, ...], customer_id: str, position: int) -> tuple[bool, float]:
        p = self.observation.infrastructure.parameters
        customer = self.observation.customer_by_id[customer_id]
        forward, backward, demand = self._screen_profile(k, sequence)
        if demand + customer.demand > self.origins[k].load + EPS:
            return False, -1.0
        before = self.origins[k].location if position == 0 else self.observation.customer_by_id[sequence[position - 1]]
        next_node = (self.observation.infrastructure.depot if position == len(sequence)
                     else self.observation.customer_by_id[sequence[position]])
        start = max(forward[position] + travel_time(before, customer, p), customer.ready)
        if start > customer.due + EPS:
            return False, customer.due - start
        latest_next = (self.observation.infrastructure.depot.due if position == len(sequence)
                       else backward[position])
        if start + customer.service + travel_time(customer, next_node, p) > latest_next + EPS:
            return False, customer.due - start
        safe_nodes = (self.observation.infrastructure.depot,) + self.observation.infrastructure.stations
        if min(energy(customer, node, p) for node in safe_nodes) > p.battery + EPS:
            return False, customer.due - start
        if (position == 0 and energy(before, customer, p) > self.origins[k].battery + EPS
                and all(energy(before, station, p) > self.origins[k].battery + EPS
                        for station in self.observation.infrastructure.stations)):
            return False, customer.due - start
        return True, customer.due - start

    def _criticality(self, sequences: tuple[tuple[str, ...], ...]):
        if sequences in self.criticality_cache:
            return self.criticality_cache[sequences]
        owned = {c for seq in sequences for c in seq}
        ranked = []
        for customer_id in self.pending - owned:
            self._check_search_time()
            customer = self.observation.customer_by_id[customer_id]
            options = []
            for index, k in enumerate(self.ids):
                self._check_search_time()
                sequence = sequences[index]
                for pos in range(len(sequence) + 1):
                    self._check_search_time()
                    passed, slack = self._screen_gap(k, sequence, customer_id, pos)
                    if not passed:
                        continue
                    before = self.origins[k].location if pos == 0 else self.observation.customer_by_id[sequence[pos - 1]]
                    after = (self.observation.infrastructure.depot if pos == len(sequence)
                             else self.observation.customer_by_id[sequence[pos]])
                    delta = distance(before, customer) + distance(customer, after) - distance(before, after)
                    options.append((delta, slack, k, pos))
            options.sort()
            regret = options[1][0] - options[0][0] if len(options) > 1 else float("inf")
            slack = min((option[1] for option in options), default=-1.0)
            ranked.append((customer_id, len(options), regret, slack,
                           options[0][0] if options else float("inf")))
        ranked.sort(key=lambda row: (row[1] != 0, row[1] != 1, -row[2], row[3],
                                     self.observation.customer_by_id[row[0]].due, row[0]))
        self.criticality_cache[sequences] = ranked
        return ranked

    def _track(self, customer: str, field: str) -> None:
        stats = self.target_stats.setdefault(customer, {})
        stats[field] = stats.get(field, 0) + 1

    def _decode(self, k: int, sequence: tuple[str, ...]):
        self._check_search_time()
        check_deadline()
        key = (k, sequence)
        if key not in self.decoded:
            if not sequence:
                self.decoded[key] = ((), None)
            else:
                actions = build_route(self.origins[k], sequence, self.observation, self.config)
                proposal = (route_proposal(self.origins[k], actions, self.observation, self.config)
                            if actions is not None else None)
                self.decoded[key] = (actions, proposal) if proposal is not None else None
        return self.decoded[key]

    def initial(self, routes: dict[int, tuple[Action, ...]]) -> FleetPlan:
        sequences, actions, costs, proposals = [], [], [], []
        for k in self.ids:
            self._check_search_time()
            route = tuple(routes.get(k, ()))
            sequence = tuple(a.destination for a in route if a.kind == "serve")
            if any(c not in self.pending for c in sequence):
                raise ValueError("Fleet incumbent contains hidden or committed customers")
            proposal = route_proposal(self.origins[k], route, self.observation, self.config) if route else None
            if route and proposal is None:
                raise ValueError("Infeasible fleet incumbent")
            self.decoded[k, sequence] = (route, proposal)
            sequences.append(sequence)
            actions.append(route)
            costs.append(proposal.cost if proposal else 0.0)
            proposals.append(proposal)
        if len({c for seq in sequences for c in seq}) != sum(map(len, sequences)):
            raise ValueError("Duplicate customer in fleet incumbent")
        self.initial_owners = {c: k for index, k in enumerate(self.ids) for c in sequences[index]}
        score, components = self._score(sequences, actions, costs)
        return FleetPlan(tuple(sequences), tuple(actions), tuple(costs), tuple(proposals), score, components)

    def change(self, plan: FleetPlan, changes: dict[int, tuple[str, ...]]) -> FleetPlan | None:
        sequences = list(plan.sequences)
        actions = list(plan.actions)
        costs = list(plan.costs)
        proposals = list(plan.proposals)
        for k, sequence in changes.items():
            self._check_search_time()
            check_deadline()
            index = self.ids.index(k)
            decoded = self._decode(k, sequence)
            if decoded is None:
                return None
            route, proposal = decoded
            sequences[index], actions[index], costs[index], proposals[index] = (
                sequence, route, proposal.cost if proposal else 0.0, proposal)
        owned = [c for seq in sequences for c in seq]
        if len(set(owned)) != len(owned) or any(c not in self.pending for c in owned):
            return None
        score, components = self._score(sequences, actions, costs)
        return FleetPlan(tuple(sequences), tuple(actions), tuple(costs), tuple(proposals), score, components)

    def _positions(self, plan: FleetPlan, k: int, customer: str):
        index = self.ids.index(k)
        sequence = plan.sequences[index]
        target = self.observation.customer_by_id[customer]
        depot = self.observation.infrastructure.depot
        def delta(position):
            before = self.origins[k].location if position == 0 else self.observation.customer_by_id[sequence[position - 1]]
            after = depot if position == len(sequence) else self.observation.customer_by_id[sequence[position]]
            return distance(before, target) + distance(target, after) - distance(before, after)
        return sorted((pos for pos in range(len(sequence) + 1)
                       if self._screen_gap(k, sequence, customer, pos)[0]),
                      key=lambda pos: (delta(pos), pos))[:self.position_limit]

    def _urgent(self, plan: FleetPlan, limit: int):
        owned = {c for seq in plan.sequences for c in seq}
        return [row[0] for row in self._criticality(plan.sequences)[:limit]]

    def _nearest_vehicles(self, plan: FleetPlan, customer: str, limit: int = 3):
        target = self.observation.customer_by_id[customer]
        def proximity(k):
            sequence = plan.sequences[self.ids.index(k)]
            nodes = (self.origins[k].location,) + tuple(self.observation.customer_by_id[c] for c in sequence)
            return min(distance(node, target) for node in nodes)
        return sorted(self.ids, key=lambda k: (proximity(k), k))[:limit]

    def _regret_rollout(self, plan: FleetPlan, limit: int,
                        forced: tuple[str, ...] = (), regret_k: int | None = None,
                        due_order: bool = False) -> FleetPlan:
        targets = [c for c in forced if c in self.pending and
                   all(c not in seq for seq in plan.sequences)]
        if due_order:
            owned = {c for seq in plan.sequences for c in seq}
            ordered = sorted(self.pending - owned,
                             key=lambda c: (self.observation.customer_by_id[c].due,
                                            self.observation.customer_by_id[c].ready, c))[:limit]
        else:
            ordered = self._urgent(plan, limit)
        targets += [c for c in ordered if c not in targets]
        targets = targets[:limit]
        if not targets:
            return plan
        included = {c for seq in plan.sequences for c in seq} | set(targets)
        restricted = Observation(self.observation.time, self.observation.infrastructure,
                                 tuple(c for c in self.observation.customers if c.id in included),
                                 self.observation.committed_customers)
        routes = {k: plan.actions[index] for index, k in enumerate(self.ids)}
        repaired, _ = regret_repair(self.origins, routes, restricted, self.config,
                                    regret_k=regret_k or self.regret_k,
                                    position_limit=self.position_limit)
        changed = {k: tuple(a.destination for a in repaired[k] if a.kind == "serve")
                   for index, k in enumerate(self.ids) if repaired[k] != plan.actions[index]}
        return self.change(plan, changed) or plan if changed else plan

    def candidates(self, plan: FleetPlan, branch_limit: int) -> list[FleetPlan]:
        found: dict[tuple[tuple[str, ...], ...], FleetPlan] = {}
        unserved = self._urgent(plan, 3)
        insert_cap = max(1, branch_limit // 3)
        rescue_cap = max(1, branch_limit // 2)
        move_cap = max(1, branch_limit // 4)
        inserted = rescued = moved_count = 0
        for customer in unserved:
            if inserted >= insert_cap:
                break
            for k in self._nearest_vehicles(plan, customer, 5):
                if inserted >= insert_cap:
                    break
                index = self.ids.index(k)
                sequence = plan.sequences[index]
                for position in self._positions(plan, k, customer):
                    check_deadline()
                    self._track(customer, "insert_attempts")
                    candidate = self.change(plan, {k: sequence[:position] + (customer,) + sequence[position:]})
                    if candidate is not None and candidate.sequences not in found:
                        found[candidate.sequences] = candidate
                        inserted += 1
                        self._track(customer, "insert_feasible")
                    if inserted >= insert_cap:
                        break
        for target in unserved[:2]:
            if rescued >= rescue_cap:
                break
            routes = sorted(self.ids, key=lambda k: (
                min(self._gap_delta(plan, k, target, pos) for pos in
                    range(len(plan.sequences[self.ids.index(k)]) + 1)), k))[:3]
            for k in routes:
                if rescued >= rescue_cap:
                    break
                index = self.ids.index(k)
                sequence = plan.sequences[index]
                for position in self._positions(plan, k, target)[:2]:
                    adjacent = tuple(sequence[pos] for pos in (position - 1, position)
                                     if 0 <= pos < len(sequence))
                    eject_sets = ((), *((customer,) for customer in adjacent))
                    if len(adjacent) == 2:
                        eject_sets += (adjacent,)
                    for displaced in eject_sets:
                        check_deadline()
                        self._track(target, "rescue_attempts")
                        reduced = tuple(c for c in sequence if c not in displaced)
                        new_position = position - int(position > 0 and sequence[position - 1] in displaced)
                        ejected = reduced[:new_position] + (target,) + reduced[new_position:]
                        candidate = self.change(plan, {k: ejected})
                        if candidate is None:
                            continue
                        self._track(target, "rescue_feasible")
                        if displaced:
                            candidate = self._regret_rollout(candidate, len(displaced), displaced,
                                                             regret_k=3 if len(displaced) == 2 else 2)
                            if all(c in {item for seq in candidate.sequences for item in seq}
                                   for c in displaced):
                                self._track(target, "rollout_reinserted")
                        if candidate.sequences not in found:
                            found[candidate.sequences] = candidate
                            rescued += 1
                        if rescued >= rescue_cap:
                            break
                    if rescued >= rescue_cap:
                        break
        # These moves restructure future suffixes without touching busy actions.
        for source_index, source in enumerate(self.ids):
            self._check_search_time()
            if moved_count >= move_cap:
                break
            sequence = plan.sequences[source_index]
            if not sequence:
                continue
            customer = sequence[-1] if unserved else sequence[0]
            for target in self._nearest_vehicles(plan, customer, 3):
                if moved_count >= move_cap:
                    break
                if target == source:
                    continue
                target_index = self.ids.index(target)
                target_sequence = plan.sequences[target_index]
                for position in self._positions(plan, target, customer)[:1]:
                    moved = self.change(plan, {source: tuple(c for c in sequence if c != customer),
                                               target: target_sequence[:position] + (customer,) + target_sequence[position:]})
                    if moved is not None:
                        if moved.sequences not in found:
                            found[moved.sequences] = moved
                            moved_count += 1
                if sequence and target_sequence:
                    swapped = self.change(plan, {source: tuple(c for c in sequence if c != customer) + (target_sequence[-1],),
                                                 target: target_sequence[:-1] + (customer,)})
                    if swapped is not None:
                        if swapped.sequences not in found:
                            found[swapped.sequences] = swapped
                            moved_count += 1
        if not unserved:
            for source_index, source in enumerate(self.ids):
                self._check_search_time()
                sequence = plan.sequences[source_index]
                if self.origins[source].departed or not 0 < len(sequence) <= 4:
                    continue
                candidate = plan
                for customer in sequence:
                    self._check_search_time()
                    check_deadline()
                    other = [k for k in self._nearest_vehicles(candidate, customer, 5) if k != source]
                    inserted = None
                    for k in other:
                        target_seq = candidate.sequences[self.ids.index(k)]
                        for position in self._positions(candidate, k, customer):
                            trial = self.change(candidate, {source: tuple(c for c in candidate.sequences[source_index]
                                                            if c != customer),
                                                            k: target_seq[:position] + (customer,) + target_seq[position:]})
                            if trial is not None:
                                inserted = trial
                                break
                        if inserted is not None:
                            break
                    if inserted is None:
                        candidate = plan
                        break
                    candidate = inserted
                if candidate is not plan and candidate.sequences[source_index] == ():
                    found[candidate.sequences] = candidate
                if len(found) >= branch_limit:
                    break
            self._full_service_moves(plan, found, branch_limit)
        return sorted(found.values(), key=lambda p: p.score)[:branch_limit]

    def _full_service_moves(self, plan: FleetPlan,
                            found: dict[tuple[tuple[str, ...], ...], FleetPlan],
                            branch_limit: int) -> None:
        if len(found) >= branch_limit:
            return
        budget = branch_limit * 2

        def keep(changes):
            self._check_search_time()
            check_deadline()
            candidate = self.change(plan, changes)
            if (candidate is not None and candidate.score[0] == 0
                    and candidate.sequences not in found):
                found[candidate.sequences] = candidate

        horizon = max(EPS, self.observation.infrastructure.depot.due - self.observation.time)
        p = self.observation.infrastructure.parameters
        route_order = sorted(
            (k for index, k in enumerate(self.ids) if plan.actions[index]),
            key=lambda k: (-max(self._metrics(k, plan.actions[self.ids.index(k)])[field]
                                for field in ("tw", "battery", "capacity", "time_risk")), k))
        fragile = []
        for source in route_order[:3]:
            state = self.origins[source]
            sequence = plan.sequences[self.ids.index(source)]
            for action in plan.actions[self.ids.index(source)]:
                self._check_search_time()
                step = transition(state, action, self.observation)
                state = step.after
                if not step.served:
                    continue
                customer = self.observation.customer_by_id[step.served]
                slack_risk = 1 - self._unit((customer.due - step.service_start) /
                                             max(EPS, customer.due - customer.ready))
                safe = min(energy(state.location, node, p) for node in
                           (self.observation.infrastructure.depot,) + self.observation.infrastructure.stations)
                battery_risk = 1 - self._unit((state.battery - safe) / p.battery)
                capacity_risk = 1 - self._unit(state.load / p.capacity)
                time_risk = self._unit((state.time - self.origins[source].time) / horizon)
                fragile.append((max(slack_risk, battery_risk, capacity_risk, time_risk),
                                source, sequence.index(step.served), step.served))
        for _, source, pos, customer in sorted(fragile, key=lambda row: (-row[0], row[1], row[2]))[:2]:
            sequence = plan.sequences[self.ids.index(source)]
            reduced = sequence[:pos] + sequence[pos + 1:]
            for target in self._nearest_vehicles(plan, customer, 4):
                if target == source:
                    continue
                target_seq = plan.sequences[self.ids.index(target)]
                for gap in self._positions(plan, target, customer)[:2]:
                    keep({source: reduced,
                          target: target_seq[:gap] + (customer,) + target_seq[gap:]})

        # Try high-detour single-customer moves first; all suffixes remain soft.
        for source_index, source in enumerate(self.ids):
            self._check_search_time()
            sequence = plan.sequences[source_index]
            if not sequence or len(found) >= budget:
                break
            def removal_saving(pos):
                before = (self.origins[source].location if pos == 0
                          else self.observation.customer_by_id[sequence[pos - 1]])
                current = self.observation.customer_by_id[sequence[pos]]
                after = (self.observation.infrastructure.depot if pos == len(sequence) - 1
                         else self.observation.customer_by_id[sequence[pos + 1]])
                return (distance(before, current) + distance(current, after)
                        - distance(before, after))
            ranked = sorted(range(len(sequence)), key=lambda pos: (-removal_saving(pos), pos))
            for pos in ranked[:2]:
                customer = sequence[pos]
                reduced = sequence[:pos] + sequence[pos + 1:]
                for target in self._nearest_vehicles(plan, customer, 4):
                    if target == source or len(found) >= budget:
                        continue
                    target_seq = plan.sequences[self.ids.index(target)]
                    for gap in self._positions(plan, target, customer)[:2]:
                        keep({source: reduced,
                              target: target_seq[:gap] + (customer,) + target_seq[gap:]})
                        if len(found) >= budget:
                            break
            # Or-opt of length two, and intra-route 2-opt, are single tree actions.
            if len(sequence) >= 3:
                for pos in range(min(3, len(sequence) - 1)):
                    pair = sequence[pos:pos + 2]
                    rest = sequence[:pos] + sequence[pos + 2:]
                    for gap in range(len(rest) + 1):
                        if gap != pos:
                            keep({source: rest[:gap] + pair + rest[gap:]})
                        if len(found) >= budget:
                            break
                    if len(found) >= budget:
                        break
            if len(sequence) >= 4 and len(found) < budget:
                for first in range(min(3, len(sequence) - 2)):
                    for last in range(first + 2, min(len(sequence), first + 5)):
                        keep({source: sequence[:first] + tuple(reversed(sequence[first:last + 1]))
                              + sequence[last + 1:]})
                        if len(found) >= budget:
                            break
                    if len(found) >= budget:
                        break
        # Bounded cross-route swap near existing customers.
        for source_index, source in enumerate(self.ids):
            self._check_search_time()
            sequence = plan.sequences[source_index]
            if not sequence or len(found) >= budget:
                break
            customer = sequence[0]
            for target in self._nearest_vehicles(plan, customer, 4):
                if target == source or len(found) >= budget:
                    continue
                target_seq = plan.sequences[self.ids.index(target)]
                if not target_seq:
                    continue
                other = min(target_seq, key=lambda c: (
                    distance(self.observation.customer_by_id[c],
                             self.observation.customer_by_id[customer]), c))
                pos = target_seq.index(other)
                keep({source: (other,) + sequence[1:],
                      target: target_seq[:pos] + (customer,) + target_seq[pos + 1:]})

    def _gap_delta(self, plan: FleetPlan, k: int, customer: str, position: int) -> float:
        sequence = plan.sequences[self.ids.index(k)]
        target = self.observation.customer_by_id[customer]
        before = self.origins[k].location if position == 0 else self.observation.customer_by_id[sequence[position - 1]]
        after = (self.observation.infrastructure.depot if position == len(sequence)
                 else self.observation.customer_by_id[sequence[position]])
        return distance(before, target) + distance(target, after) - distance(before, after)

    def value(self, plan: FleetPlan) -> float:
        metrics = plan.components
        served = len(self.pending) - metrics["unserved_customers"]
        flexibility = (1.0 - metrics["flexibility_risk"] if metrics["unserved_customers"] == 0
                       else 1.0 - self._unit((metrics["screened_zero_option_customers"] +
                                              0.5 * metrics["screened_one_option_customers"]) /
                                             max(1, metrics["unserved_customers"])))
        return (served + 0.30 * flexibility + 0.20 * (1 - metrics["time_window_risk"])
                + 0.15 * (1 - metrics["battery_risk"])
                + 0.10 * (1 - metrics["capacity_risk"])
                + 0.08 * (1 - metrics["activated_vehicles"] / max(1, len(self.ids)))
                + 0.05 * (1 - metrics["normalized_distance"])
                + 0.02 * (1 - metrics["route_instability"]))


def solve_fleet_mcts(origins: dict[int, VehicleState], routes: dict[int, tuple[Action, ...]],
                     observation: Observation, config: MPCConfig, *, seed: int,
                     iterations: int = 256, depth: int = 4, branch_limit: int = 24,
                     position_limit: int = 3, regret_k: int = 2) -> FleetMCTSResult:
    if min(iterations, depth, branch_limit, position_limit) < 1 or regret_k not in {2, 3}:
        raise ValueError("Invalid fleet MCTS configuration")
    started = perf_counter()
    problem = _FleetProblem(origins, observation, config, position_limit, regret_k)
    problem.search_until = perf_counter() + max(0.0, remaining_time() - 0.05)
    try:
        root_plan = problem.initial(routes)
    except _SearchBudgetReached as error:
        raise PlanningDeadlineExceeded from error
    root_criticality = []
    best = root_plan
    root = _Node(root_plan, 0)
    rng = Random(seed)
    expanded = completed = tree_improvements = 0
    service_seconds = full_seconds = 0.0
    deadline_reached = False
    seed_started = started
    seed_accounted = False
    try:
        root_criticality = problem._criticality(root_plan.sequences)
        # Three roots at most: the old soft incumbent and two constructive orders.
        seed_until = perf_counter() + min(remaining_time() * 0.4, 2.0)
        due = root_plan
        while due.score[0] and perf_counter() < seed_until:
            problem._check_search_time()
            check_deadline()
            improved = problem._regret_rollout(due, 2, due_order=True)
            if improved.score >= due.score:
                break
            due = improved
        if due.score < best.score:
            best = due
        critical = root_plan
        critical_until = perf_counter() + min(0.35, max(0.0, remaining_time() - 0.1))
        while critical.score[0] and perf_counter() < critical_until:
            problem._check_search_time()
            improved = problem._regret_rollout(critical, 2)
            if improved.score >= critical.score:
                break
            critical = improved
        if critical.score < best.score:
            best = critical
        service_seconds += perf_counter() - seed_started if root_plan.score[0] else 0.0
        full_seconds += perf_counter() - seed_started if not root_plan.score[0] else 0.0
        seed_accounted = True
        seed_score = best.score
        root = _Node(best, 0)
        for iteration in range(iterations):
            iteration_started = perf_counter()
            phase_service = bool(root.plan.score[0])
            check_deadline()
            try:
                problem._check_search_time()
                node = root
                path = [root]
                while node.depth < depth:
                    problem._check_search_time()
                    check_deadline()
                    if node.candidates is None:
                        node.candidates = problem.candidates(node.plan, branch_limit)
                    allowed = min(branch_limit, 1 + floor(2 * sqrt(node.visits)))
                    if node.candidates and len(node.children) < allowed:
                        parent_plan = node.plan
                        rank = len(node.children)
                        total = len(node.candidates) + rank
                        prior = (total - rank) / (total * (total + 1) / 2)
                        child = _Node(node.candidates.pop(0), node.depth + 1, prior=prior)
                        for customer in problem.pending:
                            if (all(customer not in seq for seq in parent_plan.sequences)
                                    and any(customer in seq for seq in child.plan.sequences)):
                                problem._track(customer, "explored")
                        node.children.append(child)
                        node = child
                        path.append(node)
                        expanded += 1
                        break
                    if not node.children:
                        break
                    scale = sqrt(node.visits + 1)
                    node = max(node.children, key=lambda child: (
                        (child.value / child.visits if child.visits else problem.value(child.plan))
                        + config.uct_c * child.prior * scale / (1 + child.visits), rng.random()))
                    path.append(node)
                rollout = problem._regret_rollout(node.plan, 2, regret_k=2 if iteration % 2 == 0 else 3)
                if rollout.score < best.score:
                    best = rollout
                    tree_improvements += 1
                value = problem.value(rollout)
                for ancestor in path:
                    ancestor.visits += 1
                    ancestor.value += value
                completed += 1
            finally:
                if phase_service:
                    service_seconds += perf_counter() - iteration_started
                else:
                    full_seconds += perf_counter() - iteration_started
    except PlanningDeadlineExceeded:
        deadline_reached = True
    except _SearchBudgetReached:
        deadline_reached = True
    if not seed_accounted:
        if root_plan.score[0]:
            service_seconds += perf_counter() - seed_started
        else:
            full_seconds += perf_counter() - seed_started
    seed_score = root.plan.score
    criticality = {customer: dict(estimated_insertion_gaps=count,
                                  estimated_regret=regret if regret != float("inf") else None,
                                  minimum_optimistic_slack=slack,
                                  cheapest_geometric_delta=delta if isfinite(delta) else None,
                                  **problem.target_stats.get(customer, {}))
                   for customer, count, regret, slack, delta in root_criticality}
    return FleetMCTSResult({k: best.actions[index] for index, k in enumerate(problem.ids)},
                           {k: best.proposals[index] for index, k in enumerate(problem.ids)
                            if best.proposals[index] is not None},
                           root_plan.score, seed_score, best.score, best.components, criticality,
                           completed, expanded,
                           tree_improvements, service_seconds, full_seconds,
                           perf_counter() - started, deadline_reached)
