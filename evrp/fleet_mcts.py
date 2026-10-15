"""Fleet-level MCTS over released customer sequences and EV assignments."""

from dataclasses import dataclass, field, replace
from math import floor, isfinite, sqrt
from random import Random
from time import perf_counter

from .instance import distance, energy, travel_time
from .model import EPS, Action, Observation, VehicleState, escape, transition
from .mpc import MPCConfig, MPCPlanningProblem, MPCProposal
from .planning_budget import PlanningDeadlineExceeded, check_deadline, remaining_time
from .repair import build_route, route_proposal
from .optimizers.objective import FleetObjectiveEvaluator


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
    action_kind: str = "ROOT"


@dataclass(frozen=True)
class _RouteProfile:
    earliest: tuple[float, ...]
    latest: tuple[float, ...]
    demand: float
    prefix_distance: tuple[float, ...]
    safe_return_energy: tuple[float, ...]

    def __iter__(self):
        yield self.earliest
        yield self.latest
        yield self.demand


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
    root_uncovered: int
    completed_root_uncovered: int
    final_uncovered: int
    service_gain_over_root: int
    rollout_count: int
    rollout_customers_completed: int
    maximum_rollout_residual: int
    screened_customer_count: int
    screened_vehicle_evaluations: int
    exact_decoded_options: int
    service_improvements: int
    objective_only_improvements: int
    screened_insertions: int = 0
    screen_cache_hits: int = 0
    screen_cache_lookups: int = 0
    ejection_chains_generated: int = 0
    ejection_chains_feasible: int = 0
    ejection_chains_selected: int = 0
    rollout_policy_usage: dict[str, int] = field(default_factory=dict)
    rollout_policy_improvements: dict[str, int] = field(default_factory=dict)
    root_control_visits: dict[str, int] = field(default_factory=dict)
    root_control_statistics: dict[str, dict] = field(default_factory=dict)
    selected_root_control: str = "KEEP_CONSTRUCTOR"


@dataclass(frozen=True)
class FleetConstructorResult:
    routes: dict[int, tuple[Action, ...]]
    insertions: list[dict]
    retained_score: tuple[float, ...]
    chosen_score: tuple[float, ...]
    screened_insertions: int
    exact_decoder_calls: int
    zero_option_customers: int
    cache_hits: int
    cache_lookups: int
    candidate: str


@dataclass
class _Node:
    plan: FleetPlan
    depth: int
    visits: int = 0
    value: float = 0.0
    candidates: list[FleetPlan] | None = None
    children: list["_Node"] = field(default_factory=list)
    prior: float = 1.0


@dataclass
class _RootControlEvidence:
    best_plan: FleetPlan
    visits: int = 0
    total_value: float = 0.0

    @property
    def mean_value(self) -> float:
        return self.total_value / self.visits if self.visits else 0.0

    def record(self, plan: FleetPlan, value: float) -> None:
        self.visits += 1
        self.total_value += value
        if plan.score < self.best_plan.score:
            self.best_plan = plan


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
        self.control_metrics: dict[tuple[int, tuple[Action, ...]], dict[str, float]] = {}
        self.criticality_cache: dict[tuple[tuple[str, ...], ...], list[tuple[str, int, float, float, float]]] = {}
        self.option_cache: dict[tuple[tuple[tuple[str, ...], ...], str], tuple[tuple[float, float, int, int, bool], ...]] = {}
        self.vehicle_option_cache: dict[tuple[int, tuple[str, ...], str], tuple[tuple[float, float, int, int, bool], ...]] = {}
        self.screened_customer_count = 0
        self.screened_vehicle_evaluations = 0
        self.screened_insertions = 0
        self.exact_decoded_options = 0
        self.screen_cache_hits = 0
        self.screen_cache_lookups = 0
        self.ejection_chains_generated = 0
        self.ejection_chains_feasible = 0
        self.ejection_chains_selected = 0
        self.target_stats: dict[str, dict[str, int]] = {}
        self.search_until: float | None = None
        self.screen_cache: dict[tuple[int, tuple[str, ...]], _RouteProfile] = {}
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

    def _control_metrics(self, k: int, actions: tuple[Action, ...]) -> dict[str, float]:
        key = (k, actions)
        if key in self.control_metrics:
            return self.control_metrics[key]
        self._check_search_time()
        origin = self.origins[k]
        infra = self.observation.infrastructure
        p = infra.parameters
        tw = 0.0
        if origin.time > self.observation.time + EPS:
            # The busy action is immutable; origin is already its measured after-state.
            after = origin
        elif not actions and origin.location.kind == "d" and not origin.departed:
            # An unused depot EV is an interruptible reserve, not a horizon-long wait.
            after = origin
        else:
            if actions:
                first = actions[0]
            else:
                idle = MPCPlanningProblem(self.observation, origin,
                                          replace(self.config, max_idle_wait=0))
                first = idle.fallback(idle.initial)
            step = transition(origin, first, self.observation)
            after = step.after
            if step.served:
                customer = self.observation.customer_by_id[step.served]
                tw = 1.0 - self._unit((customer.due - step.service_start) /
                                      max(EPS, customer.due - customer.ready))
        safe_energy = min(energy(after.location, node, p) for node in
                          (infra.depot,) + infra.stations)
        horizon = max(EPS, infra.depot.due - self.observation.time)
        result = dict(tw=tw,
                      battery=1.0 - self._unit((after.battery - safe_energy) / p.battery),
                      capacity=1.0 - self._unit(after.load / p.capacity),
                      time=1.0 - self._unit((infra.depot.due - after.time) / horizon))
        result["total"] = sum(result.values()) / 4
        self.control_metrics[key] = result
        return result

    def _score(self, sequences, actions, costs):
        evaluator = FleetObjectiveEvaluator(
            self.ids, self.origins, self.pending, self.dscale, self.initial_owners,
            self._metrics, self._control_metrics, self._criticality)
        return evaluator.evaluate(sequences, actions, costs)

    def _screen_profile(self, k: int, sequence: tuple[str, ...]):
        key = (k, sequence)
        self.screen_cache_lookups += 1
        if key in self.screen_cache:
            self.screen_cache_hits += 1
            return self.screen_cache[key]
        customer_map = self.observation.customer_by_id
        p = self.observation.infrastructure.parameters
        safe_nodes = (self.observation.infrastructure.depot,) + self.observation.infrastructure.stations
        forward = [self.origins[k].time]
        prefix_distance = [0.0]
        safe_energy = [min(energy(self.origins[k].location, node, p) for node in safe_nodes)]
        location = self.origins[k].location
        demand = 0.0
        for customer_id in sequence:
            customer = customer_map[customer_id]
            start = max(forward[-1] + travel_time(location, customer, p), customer.ready)
            forward.append(start + customer.service)
            prefix_distance.append(prefix_distance[-1] + distance(location, customer))
            safe_energy.append(min(energy(customer, node, p) for node in safe_nodes))
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
        profile = _RouteProfile(tuple(forward), tuple(backward), demand,
                                tuple(prefix_distance), tuple(safe_energy))
        self.screen_cache[key] = profile
        return profile

    def _screen_gap(self, k: int, sequence: tuple[str, ...], customer_id: str, position: int) -> tuple[bool, float]:
        passed, slack, _ = self._screen_gap_detail(k, sequence, customer_id, position)
        return passed, slack

    def _screen_gap_detail(self, k: int, sequence: tuple[str, ...], customer_id: str,
                           position: int) -> tuple[bool, float, str]:
        p = self.observation.infrastructure.parameters
        customer = self.observation.customer_by_id[customer_id]
        profile = self._screen_profile(k, sequence)
        if profile.demand + customer.demand > self.origins[k].load + EPS:
            return False, -1.0, "capacity"
        before = self.origins[k].location if position == 0 else self.observation.customer_by_id[sequence[position - 1]]
        next_node = (self.observation.infrastructure.depot if position == len(sequence)
                     else self.observation.customer_by_id[sequence[position]])
        start = max(profile.earliest[position] + travel_time(before, customer, p), customer.ready)
        if start > customer.due + EPS:
            return False, customer.due - start, "time_window"
        latest_next = (self.observation.infrastructure.depot.due if position == len(sequence)
                       else profile.latest[position])
        if start + customer.service + travel_time(customer, next_node, p) > latest_next + EPS:
            return False, customer.due - start, "time_window"
        safe_nodes = (self.observation.infrastructure.depot,) + self.observation.infrastructure.stations
        if min(energy(customer, node, p) for node in safe_nodes) > p.battery + EPS:
            return False, customer.due - start, "safe_return"
        if (position == 0 and energy(before, customer, p) > self.origins[k].battery + EPS
                and all(energy(before, station, p) > self.origins[k].battery + EPS
                        for station in self.observation.infrastructure.stations)):
            return False, customer.due - start, "battery"
        return True, customer.due - start, "feasible"

    def _option_rank(self, option, customer_id: str, sequences):
        delta, slack, k, pos, _ = option
        sequence = sequences[self.ids.index(k)]
        p = self.observation.infrastructure.parameters
        customer = self.observation.customer_by_id[customer_id]
        before = self.origins[k].location if pos == 0 else self.observation.customer_by_id[sequence[pos - 1]]
        after = (self.observation.infrastructure.depot if pos == len(sequence)
                 else self.observation.customer_by_id[sequence[pos]])
        capacity_loss = customer.demand / max(EPS, self.origins[k].load)
        energy_loss = max(0.0, energy(before, customer, p) + energy(customer, after, p)
                          - energy(before, after, p)) / max(EPS, p.battery)
        tw_loss = customer.service / max(1.0, slack + customer.service)
        return (delta + tw_loss + capacity_loss + energy_loss, delta, -slack, k, pos)

    def screened_options(self, sequences: tuple[tuple[str, ...], ...], customer_id: str):
        key = (sequences, customer_id)
        if key in self.option_cache:
            self.screen_cache_lookups += 1
            self.screen_cache_hits += 1
            return self.option_cache[key]
        self.screened_customer_count += 1
        options = []
        customer = self.observation.customer_by_id[customer_id]
        for index, k in enumerate(self.ids):
            self._check_search_time()
            sequence = sequences[index]
            vehicle_key = (k, sequence, customer_id)
            self.screen_cache_lookups += 1
            if vehicle_key in self.vehicle_option_cache:
                self.screen_cache_hits += 1
                options.extend(self.vehicle_option_cache[vehicle_key])
                continue
            self.screened_vehicle_evaluations += 1
            vehicle_options = []
            for pos in range(len(sequence) + 1):
                self._check_search_time()
                self.screened_insertions += 1
                passed, slack = self._screen_gap(k, sequence, customer_id, pos)
                if not passed:
                    continue
                before = (self.origins[k].location if pos == 0
                          else self.observation.customer_by_id[sequence[pos - 1]])
                after = (self.observation.infrastructure.depot if pos == len(sequence)
                         else self.observation.customer_by_id[sequence[pos]])
                delta = distance(before, customer) + distance(customer, after) - distance(before, after)
                vehicle_options.append((delta, slack, k, pos,
                                        not self.origins[k].departed and not sequence))
            self.vehicle_option_cache[vehicle_key] = tuple(vehicle_options)
            options.extend(vehicle_options)
        result = tuple(sorted(options, key=lambda row: self._option_rank(row, customer_id, sequences)))
        self.option_cache[key] = result
        return result

    def _criticality(self, sequences: tuple[tuple[str, ...], ...]):
        if sequences in self.criticality_cache:
            return self.criticality_cache[sequences]
        owned = {c for seq in sequences for c in seq}
        ranked = []
        for customer_id in self.pending - owned:
            self._check_search_time()
            options = self.screened_options(sequences, customer_id)
            distances = sorted(option[0] for option in options)
            regret = distances[1] - distances[0] if len(distances) > 1 else float("inf")
            slack = min((option[1] for option in options), default=-1.0)
            ranked.append((customer_id, len(options), regret, slack,
                           distances[0] if distances else float("inf")))
        ranked.sort(key=lambda row: (row[1] != 0, row[1] != 1,
                                     self.observation.customer_by_id[row[0]].due,
                                     row[3], row[1], -row[2], row[0]))
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
            self.exact_decoded_options += 1
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

    def change(self, plan: FleetPlan, changes: dict[int, tuple[str, ...]],
               action_kind: str = "STRUCTURAL") -> FleetPlan | None:
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
        return FleetPlan(tuple(sequences), tuple(actions), tuple(costs), tuple(proposals),
                         score, components, action_kind)

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

    def complete_rollout(self, plan: FleetPlan, local_until: float,
                         policy: str = "CRITICAL_REGRET") -> FleetPlan:
        """Seeded insertion completion; every accepted route uses exact decoding."""
        if policy not in {"CRITICAL_REGRET", "EARLIEST_DEADLINE", "RESERVE_PRESERVING"}:
            raise ValueError("Unknown rollout policy")
        current = plan
        previous_until = self.search_until
        self.search_until = min(local_until - 0.02, previous_until or local_until)
        try:
            while current.score[0] and perf_counter() < local_until - 0.02:
                self._check_search_time()
                check_deadline()
                ranked = self._criticality(current.sequences)
                if policy == "EARLIEST_DEADLINE":
                    ranked = sorted(ranked, key=lambda row: (
                        self.observation.customer_by_id[row[0]].due, row[0]))
                elif policy == "RESERVE_PRESERVING":
                    ranked = sorted(ranked, key=lambda row: (
                        row[1] == 0, row[1] > 1,
                        self.observation.customer_by_id[row[0]].due, row[0]))
                target, count, _, _, _ = ranked[0]
                if count == 0:
                    break
                chosen = None
                options = list(self.screened_options(current.sequences, target))
                if policy == "RESERVE_PRESERVING":
                    options.sort(key=lambda option: (option[4], option[0], -option[1],
                                                     option[2], option[3]))
                for _, _, k, pos, _ in options[:3]:
                    if perf_counter() >= local_until - 0.02:
                        break
                    index = self.ids.index(k)
                    sequence = current.sequences[index]
                    proposed = sequence[:pos] + (target,) + sequence[pos:]
                    if self._decode(k, proposed) is not None:
                        chosen = k, proposed
                        break
                if chosen is None:
                    break
                k, proposed = chosen
                updated = self.change(current, {k: proposed})
                if updated is None:
                    break
                current = updated
        except (PlanningDeadlineExceeded, _SearchBudgetReached):
            pass
        finally:
            self.search_until = previous_until
        return current

    def _chain_rank(self, candidate: FleetPlan):
        metrics = candidate.components
        return (candidate.score[0], metrics["screened_zero_option_customers"],
                metrics["screened_one_option_customers"], metrics["control_risk"],
                metrics["flexibility_risk"], metrics["normalized_distance"])

    def _ejection_chain_candidates(self, plan: FleetPlan, customer: str,
                                    limit: int) -> list[FleetPlan]:
        # Screen on drafts; decode only complete chains, never partial ejections.
        gaps = []
        for index, k in enumerate(self.ids):
            sequence = plan.sequences[index]
            for pos in range(len(sequence) + 1):
                self._check_search_time()
                passed, slack, reason = self._screen_gap_detail(k, sequence, customer, pos)
                if passed:
                    continue
                gaps.append((reason == "capacity", -slack,
                             self._gap_delta(plan, k, customer, pos), k, pos))
        results = {}
        for _, _, _, source, gap in sorted(gaps)[:3]:
            source_index = self.ids.index(source)
            sequence = plan.sequences[source_index]
            blockers = list(dict.fromkeys(sequence[pos] for pos in (gap - 1, gap)
                                          if 0 <= pos < len(sequence)))
            if sequence:
                blockers.extend(c for c in sorted(sequence, key=lambda c: (
                    -self.observation.customer_by_id[c].demand,
                    self.observation.customer_by_id[c].due, c))[:1] if c not in blockers)
            for displaced in blockers[:3]:
                self._check_search_time()
                reduced = tuple(c for c in sequence if c != displaced)
                new_gap = min(gap - int(sequence.index(displaced) < gap), len(reduced))
                if not self._screen_gap(source, reduced, customer, new_gap)[0]:
                    continue
                source_new = reduced[:new_gap] + (customer,) + reduced[new_gap:]
                draft = list(plan.sequences)
                draft[source_index] = source_new
                for _, _, target, pos, _ in self.screened_options(tuple(draft), displaced)[:3]:
                    if target == source:
                        continue
                    target_index = self.ids.index(target)
                    target_seq = draft[target_index]
                    direct = list(draft)
                    direct[target_index] = target_seq[:pos] + (displaced,) + target_seq[pos:]
                    self.ejection_chains_generated += 1
                    candidate = self.change(plan, {source: direct[source_index],
                                                   target: direct[target_index]},
                                            "EJECTION_CHAIN_2")
                    if candidate is not None and candidate.score[0] < plan.score[0]:
                        self.ejection_chains_feasible += 1
                        results[candidate.sequences] = candidate
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
                for target in self.ids:
                    if target == source:
                        continue
                    target_index = self.ids.index(target)
                    target_seq = draft[target_index]
                    for victim in target_seq[:2]:
                        reduced_target = tuple(c for c in target_seq if c != victim)
                        for pos in range(len(reduced_target) + 1):
                            if not self._screen_gap(target, reduced_target, displaced, pos)[0]:
                                continue
                            nested = list(draft)
                            nested[target_index] = (reduced_target[:pos] + (displaced,)
                                                    + reduced_target[pos:])
                            for _, _, last, last_pos, _ in self.screened_options(tuple(nested), victim)[:2]:
                                if last in {source, target}:
                                    continue
                                last_index = self.ids.index(last)
                                last_seq = nested[last_index]
                                nested[last_index] = (last_seq[:last_pos] + (victim,)
                                                      + last_seq[last_pos:])
                                self.ejection_chains_generated += 1
                                candidate = self.change(plan, {
                                    source: nested[source_index], target: nested[target_index],
                                    last: nested[last_index]}, "EJECTION_CHAIN_2")
                                if candidate is not None and candidate.score[0] < plan.score[0]:
                                    self.ejection_chains_feasible += 1
                                    results[candidate.sequences] = candidate
                                nested[last_index] = last_seq
                                if len(results) >= limit:
                                    break
                            if len(results) >= limit:
                                break
                        if len(results) >= limit:
                            break
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        return sorted(results.values(), key=self._chain_rank)[:limit]

    def _service_candidates(self, plan: FleetPlan, branch_limit: int) -> list[FleetPlan]:
        critical = self._criticality(plan.sequences)
        found = {}
        for customer, _, _, _, _ in critical[:3]:
            for _, _, k, pos, _ in self.screened_options(plan.sequences, customer)[:3]:
                index = self.ids.index(k)
                sequence = plan.sequences[index]
                self._track(customer, "insert_attempts")
                candidate = self.change(plan, {k: sequence[:pos] + (customer,) + sequence[pos:]})
                if candidate is not None:
                    self._track(customer, "insert_feasible")
                    found[candidate.sequences] = candidate
                if len(found) >= max(3, branch_limit // 2):
                    break
            if len(found) >= max(3, branch_limit // 2):
                break
        if critical:
            target = critical[0][0]
            if not any(target in seq for candidate in found.values()
                       for seq in candidate.sequences):
                for candidate in self._ejection_chain_candidates(plan, target, 3):
                    found[candidate.sequences] = candidate
        return sorted(found.values(), key=self._chain_rank)[:branch_limit]

    def candidates(self, plan: FleetPlan, branch_limit: int) -> list[FleetPlan]:
        if plan.score[0]:
            return self._service_candidates(plan, branch_limit)
        found: dict[tuple[tuple[str, ...], ...], FleetPlan] = {}
        urgent = self._urgent(plan, 3)
        owned = {c for sequence in plan.sequences for c in sequence}
        due = sorted(self.pending - owned,
                     key=lambda c: (self.observation.customer_by_id[c].due, c))[:3]
        unserved = list(dict.fromkeys(urgent[:1] + due + urgent[1:]))
        insert_cap = max(1, branch_limit // 3)
        rescue_cap = max(1, branch_limit // 2)
        move_cap = max(1, branch_limit // 4)
        inserted = rescued = moved_count = 0
        for customer in unserved:
            if inserted >= insert_cap:
                break
            target_inserted = 0
            for _, _, k, position, _ in self.screened_options(plan.sequences, customer)[:8]:
                if inserted >= insert_cap or target_inserted >= 2:
                    break
                index = self.ids.index(k)
                sequence = plan.sequences[index]
                check_deadline()
                self._track(customer, "insert_attempts")
                candidate = self.change(plan, {k: sequence[:position] + (customer,) + sequence[position:]})
                if candidate is not None and candidate.sequences not in found:
                    found[candidate.sequences] = candidate
                    inserted += 1
                    target_inserted += 1
                    self._track(customer, "insert_feasible")
        blocked_targets = [c for c in unserved if not self.screened_options(plan.sequences, c)]
        rescue_targets = list(dict.fromkeys(blocked_targets[:1] + unserved[:2]))
        for target in rescue_targets:
            if rescued >= rescue_cap:
                break
            screened = self.screened_options(plan.sequences, target)
            if screened:
                gaps = [(delta, k, pos) for delta, _, k, pos, _ in screened]
            else:
                # A zero-option customer needs an explicit tree ejection; all
                # physical EVs are considered before ranking candidate gaps.
                gaps = [(self._gap_delta(plan, k, target, pos), k, pos)
                        for k in self.ids
                        for pos in range(len(plan.sequences[self.ids.index(k)]) + 1)]
            for _, k, position in sorted(gaps)[:max(12, branch_limit * 2)]:
                if rescued >= rescue_cap:
                    break
                index = self.ids.index(k)
                sequence = plan.sequences[index]
                adjacent = tuple(sequence[pos] for pos in (position - 1, position)
                                 if 0 <= pos < len(sequence))
                eject_sets = tuple((customer,) for customer in adjacent)
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
                    if candidate.sequences not in found:
                        found[candidate.sequences] = candidate
                        rescued += 1
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
            self._full_service_moves(plan, found, branch_limit)
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
        blocked = blocked_targets[0] if blocked_targets else None
        def rank(candidate):
            frees_blocked = (blocked is not None and
                             any(blocked in seq for seq in candidate.sequences))
            return (not frees_blocked if blocked is not None else False, candidate.score)
        return sorted(found.values(), key=rank)[:branch_limit]

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

        ready = [k for k in self.ids if self.origins[k].time <= self.observation.time + EPS
                 and plan.sequences[self.ids.index(k)]]
        control_order = sorted(ready, key=lambda k: (
            -self._control_metrics(k, plan.actions[self.ids.index(k)])["total"], k))
        # CONTROL-RELOCATE changes the next service assignment, not just a suffix.
        for source in control_order[:3]:
            sequence = plan.sequences[self.ids.index(source)]
            customer = sequence[0]
            for target in [k for k in self._nearest_vehicles(plan, customer, 4)
                           if k != source][:3]:
                target_seq = plan.sequences[self.ids.index(target)]
                for gap in self._positions(plan, target, customer)[:self.position_limit]:
                    keep({source: sequence[1:],
                          target: target_seq[:gap] + (customer,) + target_seq[gap:]})
        # CONTROL-SWAP exchanges first/early service across feasible route heads.
        if control_order:
            source = control_order[0]
            sequence = plan.sequences[self.ids.index(source)]
            customer = sequence[0]
            for target in [k for k in self._nearest_vehicles(plan, customer, 4)
                           if k != source][:3]:
                target_seq = plan.sequences[self.ids.index(target)]
                for pos, other in enumerate(target_seq[:2]):
                    keep({source: (other,) + sequence[1:],
                          target: target_seq[:pos] + (customer,) + target_seq[pos + 1:]})

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
        critical = 1.0 - self._unit((metrics["screened_zero_option_customers"] +
                                     0.5 * metrics["screened_one_option_customers"]) /
                                    max(1, metrics["unserved_customers"]))
        operational = metrics.get("operational_cost", metrics["normalized_distance"])
        secondary = (0.30 * (1 - self._unit(metrics["control_risk"]))
                     + 0.20 * (1 - self._unit(metrics["flexibility_risk"]))
                     + 0.12 * critical
                     + 0.08 * (1 - self._unit(metrics["activated_vehicles"] / max(1, len(self.ids))))
                     + 0.05 * (1 - self._unit(operational))
                     + 0.03 * (1 - self._unit(metrics["normalized_distance"]))
                     + 0.02 * (1 - self._unit(metrics["route_instability"])))
        n = max(1, len(self.pending))
        return (served + 0.49 * self._unit(secondary / 0.80)) / (n + 0.49)


ROLLOUT_POLICIES = ("CRITICAL_REGRET", "EARLIEST_DEADLINE", "RESERVE_PRESERVING")


def first_control_signature(problem: _FleetProblem, plan: FleetPlan):
    return tuple((k, plan.actions[index][0] if plan.actions[index] else None)
                 for index, k in enumerate(problem.ids))


def select_root_control(constructor: FleetPlan, constructor_signature,
                        evidence: dict) -> tuple[tuple, FleetPlan]:
    """Choose an executable control using service, support and canonical safety."""
    eligible = [(signature, stats) for signature, stats in evidence.items()
                if stats.best_plan.score <= constructor.score]
    if not eligible:
        return constructor_signature, constructor
    signature, stats = min(eligible, key=lambda item: (
        item[1].best_plan.score[0], -item[1].visits, -item[1].mean_value,
        item[1].best_plan.score, repr(item[0])))
    return signature, stats.best_plan


def solve_fleet_mcts(origins: dict[int, VehicleState], routes: dict[int, tuple[Action, ...]],
                     observation: Observation, config: MPCConfig, *, seed: int,
                     iterations: int = 256, depth: int = 4, branch_limit: int = 24,
                     position_limit: int = 3, regret_k: int = 2) -> FleetMCTSResult:
    if min(iterations, depth, branch_limit, position_limit) < 1 or regret_k not in {2, 3}:
        raise ValueError("Invalid fleet MCTS configuration")
    started = perf_counter()
    problem = _FleetProblem(origins, observation, config, position_limit, regret_k)
    problem.search_until = perf_counter() + max(0.0, remaining_time() - 0.15)
    try:
        root_plan = problem.initial(routes)
    except _SearchBudgetReached as error:
        raise PlanningDeadlineExceeded from error
    root_criticality = []
    best = root_plan
    root = _Node(root_plan, 0)
    rng = Random(seed)
    policy_usage = {policy: 0 for policy in ROLLOUT_POLICIES}
    policy_improvements = {policy: 0 for policy in ROLLOUT_POLICIES}
    constructor_signature = first_control_signature(problem, root_plan)
    root_evidence = {constructor_signature: _RootControlEvidence(root_plan)}
    expanded = completed = tree_improvements = 0
    service_improvements = objective_only_improvements = 0
    rollout_count = rollout_customers_completed = maximum_rollout_residual = 0
    service_seconds = full_seconds = 0.0
    deadline_reached = False
    try:
        root_criticality = problem._criticality(root_plan.sequences)
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
                        structural = node.candidates.pop(0)
                        child = _Node(structural, node.depth + 1, prior=prior)
                        if structural.action_kind == "EJECTION_CHAIN_2":
                            problem.ejection_chains_selected += 1
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
                completion_until = perf_counter() + min(0.12, max(0.0, remaining_time() - 0.08))
                policy = rng.choice(ROLLOUT_POLICIES)
                policy_usage[policy] += 1
                rollout = problem.complete_rollout(node.plan, completion_until, policy)
                rollout_count += 1
                rollout_customers_completed += max(0, node.plan.score[0] - rollout.score[0])
                maximum_rollout_residual = max(maximum_rollout_residual, int(rollout.score[0]))
                if rollout.score < best.score:
                    policy_improvements[policy] += 1
                    if rollout.score[0] < best.score[0]:
                        service_improvements += 1
                    else:
                        objective_only_improvements += 1
                    best = rollout
                    tree_improvements += 1
                value = problem.value(rollout)
                signature = first_control_signature(problem, rollout)
                root_evidence.setdefault(signature, _RootControlEvidence(rollout)).record(
                    rollout, value)
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
    seed_score = root_plan.score
    selected_signature, best = select_root_control(root_plan, constructor_signature,
                                                   root_evidence)
    def label(signature):
        return "KEEP_CONSTRUCTOR" if signature == constructor_signature else str(signature)
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
                           perf_counter() - started, deadline_reached,
                           int(root_plan.score[0]), int(seed_score[0]), int(best.score[0]),
                           max(0, int(seed_score[0] - best.score[0])),
                           rollout_count, rollout_customers_completed, maximum_rollout_residual,
                           problem.screened_customer_count,
                           problem.screened_vehicle_evaluations,
                           problem.exact_decoded_options,
                           service_improvements, objective_only_improvements,
                           problem.screened_insertions,
                           problem.screen_cache_hits, problem.screen_cache_lookups,
                           problem.ejection_chains_generated,
                           problem.ejection_chains_feasible,
                           problem.ejection_chains_selected,
                           policy_usage, policy_improvements,
                           {label(signature): entry.visits
                            for signature, entry in root_evidence.items()},
                           {label(signature): dict(
                               visits=entry.visits, cumulative_value=entry.total_value,
                               mean_value=entry.mean_value,
                               best_service_level=len(problem.pending) - entry.best_plan.score[0],
                               best_score=entry.best_plan.score,
                               constructor_alternative=signature == constructor_signature)
                            for signature, entry in root_evidence.items()},
                           label(selected_signature))


def construct_fleet_root(origins: dict[int, VehicleState],
                         routes: dict[int, tuple[Action, ...]],
                         observation: Observation, config: MPCConfig) -> FleetConstructorResult:
    """Bounded parallel insertion beside the retained soft incumbent."""
    problem = _FleetProblem(origins, observation, config, 3, 2)
    problem.search_until = perf_counter() + max(0.0, remaining_time() - 0.12)
    retained = problem.initial(routes)
    current_routes = {k: retained.actions[index] for index, k in enumerate(problem.ids)}
    sequences = list(retained.sequences)
    costs = list(retained.costs)
    pending = set(problem.pending) - {c for seq in sequences for c in seq}
    insertions = []
    try:
        while pending and remaining_time() > 0.20:
            problem._check_search_time()
            chosen = None
            for customer, count, regret, _, _ in problem._criticality(tuple(sequences)):
                if customer not in pending or count == 0:
                    continue
                feasible = None
                for _, slack, k, pos, activation in problem.screened_options(
                        tuple(sequences), customer)[:3]:
                    index = problem.ids.index(k)
                    sequence = sequences[index]
                    proposed = sequence[:pos] + (customer,) + sequence[pos:]
                    decoded = problem._decode(k, proposed)
                    if decoded is None:
                        continue
                    actions, proposal = decoded
                    feasible = (proposal.cost - costs[index], k, pos, proposed,
                                actions, proposal, slack, activation)
                    break
                if feasible is not None:
                    chosen = customer, regret, feasible, count
                    break
            if chosen is None:
                break
            customer, regret, insertion, count = chosen
            delta, k, pos, proposed, actions, proposal, slack, activation = insertion
            index = problem.ids.index(k)
            sequences[index] = proposed
            costs[index] = proposal.cost
            current_routes[k] = actions
            pending.remove(customer)
            insertions.append(dict(vehicle_id=k, customer=customer, position=pos,
                                   incremental_cost=delta,
                                   regret2=regret if isfinite(regret) else None,
                                   feasible_options=1, screened_options=count,
                                   remaining_tw_slack=slack,
                                   new_activation=activation, fast_parallel=True))
    except (PlanningDeadlineExceeded, _SearchBudgetReached):
        pass
    problem.search_until = None
    best_routes = dict(routes)
    best_score = retained.score
    chosen_candidate = "retained"
    try:
        candidate_score, _ = problem._score(tuple(sequences),
                                            tuple(current_routes[k] for k in problem.ids),
                                            tuple(costs))
        if candidate_score < best_score:
            best_routes, best_score, chosen_candidate = current_routes, candidate_score, "parallel"
        if pending and remaining_time() > 0.25:
            from .repair import regret_repair
            regret_routes, _ = regret_repair(
                origins, routes, observation, config, position_limit=5,
                return_partial_on_deadline=True, screened_shortlist=True)
            regret_sequences = tuple(tuple(a.destination for a in regret_routes.get(k, ())
                                           if a.kind == "serve") for k in problem.ids)
            regret_proposals = [route_proposal(origins[k], regret_routes[k], observation, config)
                                if regret_routes.get(k) else None for k in problem.ids]
            if any(regret_routes.get(k) and regret_proposals[index] is None
                   for index, k in enumerate(problem.ids)):
                raise ValueError("Regret root is not physically feasible")
            regret_costs = tuple(proposal.cost if proposal else 0.0
                                 for proposal in regret_proposals)
            regret_score, _ = problem._score(
                regret_sequences, tuple(regret_routes.get(k, ()) for k in problem.ids),
                regret_costs)
            if regret_score < best_score:
                best_routes, best_score, chosen_candidate = regret_routes, regret_score, "regret"
    except (PlanningDeadlineExceeded, _SearchBudgetReached):
        pass
    zero_option = 0
    if remaining_time() > 0.04:
        try:
            chosen_sequences = tuple(tuple(a.destination for a in best_routes.get(k, ())
                                           if a.kind == "serve") for k in problem.ids)
            zero_option = sum(row[1] == 0 for row in problem._criticality(chosen_sequences))
        except (PlanningDeadlineExceeded, _SearchBudgetReached):
            pass
    return FleetConstructorResult(best_routes,
                                  insertions if chosen_candidate == "parallel" else [],
                                  retained.score, best_score, problem.screened_insertions,
                                  problem.exact_decoded_options, zero_option,
                                  problem.screen_cache_hits, problem.screen_cache_lookups,
                                  chosen_candidate)
