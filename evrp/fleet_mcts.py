"""Fleet-level MCTS over released customer sequences and EV assignments."""

from dataclasses import dataclass, field
from math import log, sqrt
from random import Random
from time import perf_counter

from .instance import distance
from .model import Action, Observation, VehicleState
from .mpc import MPCConfig
from .planning_budget import PlanningDeadlineExceeded, check_deadline, remaining_time
from .repair import build_route, regret_repair, route_proposal


@dataclass(frozen=True)
class FleetPlan:
    sequences: tuple[tuple[str, ...], ...]
    actions: tuple[tuple[Action, ...], ...]
    costs: tuple[float, ...]
    score: tuple[int, int, float]


@dataclass(frozen=True)
class FleetMCTSResult:
    routes: dict[int, tuple[Action, ...]]
    initial_score: tuple[int, int, float]
    seed_score: tuple[int, int, float]
    best_score: tuple[int, int, float]
    iterations: int
    nodes_expanded: int
    tree_improvements: int
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
        # The origin and observation are fixed for this MPC epoch, so this local
        # cache cannot cross incompatible vehicle states or release sets.
        self.decoded: dict[tuple[int, tuple[str, ...]], tuple[tuple[Action, ...], float] | None] = {}

    def _score(self, sequences, actions, costs):
        owned = {c for sequence in sequences for c in sequence}
        return (len(self.pending - owned),
                sum(self.origins[k].departed or bool(actions[index])
                    for index, k in enumerate(self.ids)), sum(costs))

    def _decode(self, k: int, sequence: tuple[str, ...]):
        check_deadline()
        key = (k, sequence)
        if key not in self.decoded:
            if not sequence:
                self.decoded[key] = ((), 0.0)
            else:
                actions = build_route(self.origins[k], sequence, self.observation, self.config)
                proposal = (route_proposal(self.origins[k], actions, self.observation, self.config)
                            if actions is not None else None)
                self.decoded[key] = (actions, proposal.cost) if proposal is not None else None
        return self.decoded[key]

    def initial(self, routes: dict[int, tuple[Action, ...]]) -> FleetPlan:
        sequences, actions, costs = [], [], []
        for k in self.ids:
            route = tuple(routes.get(k, ()))
            sequence = tuple(a.destination for a in route if a.kind == "serve")
            if any(c not in self.pending for c in sequence):
                raise ValueError("Fleet incumbent contains hidden or committed customers")
            proposal = route_proposal(self.origins[k], route, self.observation, self.config) if route else None
            if route and proposal is None:
                raise ValueError("Infeasible fleet incumbent")
            self.decoded[k, sequence] = (route, proposal.cost if proposal else 0.0)
            sequences.append(sequence)
            actions.append(route)
            costs.append(proposal.cost if proposal else 0.0)
        if len({c for seq in sequences for c in seq}) != sum(map(len, sequences)):
            raise ValueError("Duplicate customer in fleet incumbent")
        return FleetPlan(tuple(sequences), tuple(actions), tuple(costs),
                         self._score(sequences, actions, costs))

    def change(self, plan: FleetPlan, changes: dict[int, tuple[str, ...]]) -> FleetPlan | None:
        sequences = list(plan.sequences)
        actions = list(plan.actions)
        costs = list(plan.costs)
        for k, sequence in changes.items():
            check_deadline()
            index = self.ids.index(k)
            decoded = self._decode(k, sequence)
            if decoded is None:
                return None
            sequences[index], actions[index], costs[index] = sequence, *decoded
        owned = [c for seq in sequences for c in seq]
        if len(set(owned)) != len(owned) or any(c not in self.pending for c in owned):
            return None
        return FleetPlan(tuple(sequences), tuple(actions), tuple(costs),
                         self._score(sequences, actions, costs))

    def _positions(self, plan: FleetPlan, k: int, customer: str):
        index = self.ids.index(k)
        sequence = plan.sequences[index]
        target = self.observation.customer_by_id[customer]
        depot = self.observation.infrastructure.depot
        def delta(position):
            before = self.origins[k].location if position == 0 else self.observation.customer_by_id[sequence[position - 1]]
            after = depot if position == len(sequence) else self.observation.customer_by_id[sequence[position]]
            return distance(before, target) + distance(target, after) - distance(before, after)
        return sorted(range(len(sequence) + 1), key=lambda pos: (delta(pos), pos))[:self.position_limit]

    def _urgent(self, plan: FleetPlan, limit: int):
        owned = {c for seq in plan.sequences for c in seq}
        return sorted(self.pending - owned,
                      key=lambda c: (self.observation.customer_by_id[c].due,
                                     self.observation.customer_by_id[c].ready, c))[:limit]

    def _nearest_vehicles(self, plan: FleetPlan, customer: str, limit: int = 3):
        target = self.observation.customer_by_id[customer]
        def proximity(k):
            sequence = plan.sequences[self.ids.index(k)]
            nodes = (self.origins[k].location,) + tuple(self.observation.customer_by_id[c] for c in sequence)
            return min(distance(node, target) for node in nodes)
        return sorted(self.ids, key=lambda k: (proximity(k), k))[:limit]

    def _regret_rollout(self, plan: FleetPlan, limit: int,
                        forced: tuple[str, ...] = ()) -> FleetPlan:
        targets = [c for c in forced if c in self.pending and
                   all(c not in seq for seq in plan.sequences)]
        targets += [c for c in self._urgent(plan, limit) if c not in targets]
        targets = targets[:limit]
        if not targets:
            return plan
        included = {c for seq in plan.sequences for c in seq} | set(targets)
        restricted = Observation(self.observation.time, self.observation.infrastructure,
                                 tuple(c for c in self.observation.customers if c.id in included),
                                 self.observation.committed_customers)
        routes = {k: plan.actions[index] for index, k in enumerate(self.ids)}
        repaired, _ = regret_repair(self.origins, routes, restricted, self.config,
                                    regret_k=self.regret_k, position_limit=self.position_limit)
        changed = {k: tuple(a.destination for a in repaired[k] if a.kind == "serve")
                   for index, k in enumerate(self.ids) if repaired[k] != plan.actions[index]}
        return self.change(plan, changed) or plan if changed else plan

    def candidates(self, plan: FleetPlan, branch_limit: int) -> list[FleetPlan]:
        found: dict[tuple[tuple[str, ...], ...], FleetPlan] = {}
        unserved = self._urgent(plan, 3)
        insert_cap = max(1, branch_limit // 2)
        rescue_cap = max(1, branch_limit // 6)
        move_cap = max(1, branch_limit // 6)
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
                    candidate = self.change(plan, {k: sequence[:position] + (customer,) + sequence[position:]})
                    if candidate is not None and candidate.sequences not in found:
                        found[candidate.sequences] = candidate
                        inserted += 1
                    if inserted >= insert_cap:
                        break
        if unserved:
            target = unserved[0]
            for k in self._nearest_vehicles(plan, target, 4):
                if rescued >= rescue_cap:
                    break
                index = self.ids.index(k)
                sequence = plan.sequences[index]
                related = sorted(sequence, key=lambda c: (distance(self.observation.customer_by_id[c],
                                                      self.observation.customer_by_id[target]), c))[:2]
                for displaced in related:
                    check_deadline()
                    position = sequence.index(displaced)
                    ejected = sequence[:position] + (target,) + sequence[position + 1:]
                    candidate = self.change(plan, {k: ejected})
                    if candidate is not None:
                        candidate = self._regret_rollout(candidate, 1, (displaced,))
                        if candidate.sequences not in found:
                            found[candidate.sequences] = candidate
                            rescued += 1
                    if rescued >= rescue_cap:
                        break
                if rescued < rescue_cap and len(related) == 2:
                    check_deadline()
                    displaced = tuple(related)
                    position = min(sequence.index(c) for c in displaced)
                    reduced = tuple(c for c in sequence if c not in displaced)
                    ejected = reduced[:position] + (target,) + reduced[position:]
                    candidate = self.change(plan, {k: ejected})
                    if candidate is not None:
                        candidate = self._regret_rollout(candidate, 2, displaced)
                        if candidate.sequences not in found:
                            found[candidate.sequences] = candidate
                            rescued += 1
        # These moves restructure future suffixes without touching busy actions.
        for source_index, source in enumerate(self.ids):
            if moved_count >= move_cap:
                break
            sequence = plan.sequences[source_index]
            if not sequence:
                continue
            customer = sequence[-1]
            for target in self._nearest_vehicles(plan, customer, 3):
                if moved_count >= move_cap:
                    break
                if target == source:
                    continue
                target_index = self.ids.index(target)
                target_sequence = plan.sequences[target_index]
                for position in self._positions(plan, target, customer)[:1]:
                    moved = self.change(plan, {source: sequence[:-1],
                                               target: target_sequence[:position] + (customer,) + target_sequence[position:]})
                    if moved is not None:
                        if moved.sequences not in found:
                            found[moved.sequences] = moved
                            moved_count += 1
                if sequence and target_sequence:
                    swapped = self.change(plan, {source: sequence[:-1] + (target_sequence[-1],),
                                                 target: target_sequence[:-1] + (customer,)})
                    if swapped is not None:
                        if swapped.sequences not in found:
                            found[swapped.sequences] = swapped
                            moved_count += 1
        if not unserved:
            for source_index, source in enumerate(self.ids):
                sequence = plan.sequences[source_index]
                if self.origins[source].departed or not 0 < len(sequence) <= 2:
                    continue
                candidate = plan
                for customer in sequence:
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
        return sorted(found.values(), key=lambda p: p.score)[:branch_limit]

    def value(self, plan: FleetPlan) -> float:
        unserved, vehicles, route_distance = plan.score
        k = len(self.ids)
        served = len(self.pending) - unserved
        return (served + (k - vehicles) / (k + 1)
                + (1 / (2 * (k + 1))) / (1 + route_distance / self.dscale))


def solve_fleet_mcts(origins: dict[int, VehicleState], routes: dict[int, tuple[Action, ...]],
                     observation: Observation, config: MPCConfig, *, seed: int,
                     iterations: int = 64, depth: int = 4, branch_limit: int = 12,
                     position_limit: int = 3, regret_k: int = 2) -> FleetMCTSResult:
    if min(iterations, depth, branch_limit, position_limit) < 1 or regret_k not in {2, 3}:
        raise ValueError("Invalid fleet MCTS configuration")
    started = perf_counter()
    problem = _FleetProblem(origins, observation, config, position_limit, regret_k)
    root_plan = problem.initial(routes)
    best = root_plan
    root = _Node(root_plan, 0)
    rng = Random(seed)
    expanded = completed = tree_improvements = 0
    deadline_reached = False
    try:
        # Construct a feasible released-only incumbent before tree search, but
        # leave at least half of the remaining event budget for MCTS itself.
        seed_until = perf_counter() + min(remaining_time() * 0.4, 2.0)
        while best.score[0] and perf_counter() < seed_until:
            check_deadline()
            improved = problem._regret_rollout(best, 2)
            if improved.score >= best.score:
                break
            best = improved
        seed_score = best.score
        root = _Node(best, 0)
        for _ in range(iterations):
            check_deadline()
            node = root
            path = [root]
            while node.depth < depth:
                check_deadline()
                if node.candidates is None:
                    node.candidates = problem.candidates(node.plan, branch_limit)
                if node.candidates:
                    child = _Node(node.candidates.pop(0), node.depth + 1)
                    node.children.append(child)
                    node = child
                    path.append(node)
                    expanded += 1
                    break
                if not node.children:
                    break
                scale = sqrt(log(max(2, node.visits + 1)))
                node = max(node.children, key=lambda child: (
                    child.value / child.visits + config.uct_c * scale / sqrt(child.visits)
                    if child.visits else float("inf"), rng.random()))
                path.append(node)
            rollout = problem._regret_rollout(node.plan, 2)
            if rollout.score < best.score:
                best = rollout
                tree_improvements += 1
            value = problem.value(rollout)
            for ancestor in path:
                ancestor.visits += 1
                ancestor.value += value
            completed += 1
    except PlanningDeadlineExceeded:
        deadline_reached = True
    seed_score = root.plan.score
    return FleetMCTSResult({k: best.actions[index] for index, k in enumerate(problem.ids)},
                           root_plan.score, seed_score, best.score, completed, expanded,
                           tree_improvements,
                           perf_counter() - started, deadline_reached)
