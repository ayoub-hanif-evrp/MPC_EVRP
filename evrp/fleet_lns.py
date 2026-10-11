"""Bounded fleet-wide destroy/repair search over released customer routes."""

from dataclasses import dataclass
from math import exp
from random import Random
from time import perf_counter

from .instance import distance
from .model import Action, Observation, VehicleState
from .mpc import MPCConfig
from .repair import build_route, regret_repair, route_proposal


@dataclass(frozen=True)
class FleetLNSResult:
    routes: dict[int, tuple[Action, ...]]
    initial_score: tuple[int, int, float]
    best_score: tuple[int, int, float]
    iterations: int
    improvements: int
    elapsed: float


def fleet_score(origins: dict[int, VehicleState], routes: dict[int, tuple[Action, ...]],
                observation: Observation, config: MPCConfig) -> tuple[int, int, float]:
    """Exact lexicographic score of a complete, customer-disjoint fleet plan."""
    if set(routes) - set(origins):
        raise ValueError("Route outside fixed fleet")
    claimed = set()
    total_distance = 0.0
    for k, actions in routes.items():
        proposal = route_proposal(origins[k], actions, observation, config) if actions else None
        if actions and proposal is None:
            raise ValueError("Infeasible fleet route")
        for action in actions:
            if action.kind != "serve":
                continue
            if action.destination in claimed:
                raise ValueError("Duplicate fleet service")
            claimed.add(action.destination)
        if proposal is not None:
            total_distance += proposal.cost
    pending = set(observation.customer_by_id) - observation.committed_ids
    pending -= {c for state in origins.values() for c in state.served_customers}
    return (len(pending - claimed),
            sum(state.departed or bool(routes.get(k)) for k, state in origins.items()),
            total_distance)


def _sequence(actions: tuple[Action, ...]) -> tuple[str, ...]:
    return tuple(a.destination for a in actions if a.kind == "serve")


def _restricted(observation: Observation, included: set[str]) -> Observation:
    return Observation(observation.time, observation.infrastructure,
                       tuple(c for c in observation.customers if c.id in included),
                       observation.committed_customers)


def _destroy_count(owned_count: int, destroy_fraction: float) -> int:
    return min(owned_count, 4, max(1, round(owned_count * destroy_fraction)))


def improve_fleet(origins: dict[int, VehicleState], routes: dict[int, tuple[Action, ...]],
                  observation: Observation, config: MPCConfig, *, seed: int,
                  iterations: int = 100, time_limit: float = 3.0,
                  destroy_fraction: float = 0.1) -> FleetLNSResult:
    """Search across EVs; never alter a physically executing action.

    Origins are measured ready states or states after immutable busy actions.
    Every proposed suffix is rebuilt and replayed against the current observation.
    Only released customers are visible to the search.
    """
    if iterations < 1 or time_limit <= 0 or not 0 < destroy_fraction <= 1:
        raise ValueError("Invalid fleet LNS budget")
    started = perf_counter()
    rng = Random(seed)
    cache: dict[tuple[int, tuple[str, ...]], tuple[Action, ...] | None] = {}
    best = {k: tuple(routes.get(k, ())) for k in sorted(origins)}
    for k, actions in best.items():
        cache[k, _sequence(actions)] = actions
    initial_score = fleet_score(origins, best, observation, config)
    best_score = initial_score
    current, current_score = best, best_score
    improvements = completed = 0
    available = set(observation.customer_by_id) - observation.committed_ids
    available -= {c for state in origins.values() for c in state.served_customers}

    def decode(k: int, sequence: tuple[str, ...]) -> tuple[Action, ...] | None:
        key = k, sequence
        if key not in cache:
            cache[key] = build_route(origins[k], sequence, observation, config)
        return cache[key]

    def related(customer: str, other: str) -> float:
        a, b = observation.customer_by_id[customer], observation.customer_by_id[other]
        return distance(a, b) + abs(a.due - b.due) * 0.05

    for iteration in range(iterations):
        if perf_counter() - started >= time_limit:
            break
        owned = [(k, c) for k, actions in current.items() for c in _sequence(actions)]
        unserved = sorted(available - {c for _, c in owned},
                          key=lambda c: (observation.customer_by_id[c].due, c))
        if not owned:
            if not unserved:
                break
            target = unserved[iteration % len(unserved)]
            trial_obs = _restricted(observation, {target})
            working, _ = regret_repair(origins, current, trial_obs, config, position_limit=5)
            candidate_score = fleet_score(origins, working, observation, config)
            completed += 1
            if candidate_score < best_score:
                best, best_score = working, candidate_score
                improvements += 1
            current, current_score = working, candidate_score
            continue
        operator = ("rescue", "random", "worst", "related")[iteration % 4]
        count = _destroy_count(len(owned), destroy_fraction)
        target = None
        if operator == "rescue" and unserved:
            target = unserved[iteration % len(unserved)]
            ranked = sorted(owned, key=lambda item: (related(target, item[1]), item))
            removed = {c for _, c in ranked[:min(count, 2)]}
        elif operator == "worst":
            ranked = []
            for k, c in owned:
                sequence = _sequence(current[k])
                pos = sequence.index(c)
                before = origins[k].location if pos == 0 else observation.customer_by_id[sequence[pos - 1]]
                after = observation.infrastructure.depot if pos + 1 == len(sequence) else observation.customer_by_id[sequence[pos + 1]]
                at = observation.customer_by_id[c]
                ranked.append((distance(before, at) + distance(at, after) - distance(before, after), k, c))
            removed = {c for _, _, c in sorted(ranked, reverse=True)[:count]}
        elif operator == "related":
            anchor = rng.choice(owned)[1]
            removed = {c for _, c in sorted(owned, key=lambda item: (related(anchor, item[1]), item))[:count]}
        else:
            removed = {c for _, c in rng.sample(owned, count)}

        working = current.copy()
        for k in sorted(working):
            sequence = tuple(c for c in _sequence(working[k]) if c not in removed)
            if len(sequence) == len(_sequence(working[k])):
                continue
            rebuilt = decode(k, sequence)
            if rebuilt is None:
                break
            working[k] = rebuilt
        else:
            owned_now = {c for actions in working.values() for c in _sequence(actions)}
            if target is None and unserved:
                target = unserved[iteration % len(unserved)]
            if target is not None:
                first_obs = _restricted(observation, owned_now | {target})
                working, _ = regret_repair(origins, working, first_obs, config, position_limit=5)
            retained = {c for actions in working.values() for c in _sequence(actions)}
            remaining = removed - retained
            if remaining:
                repair_obs = _restricted(observation, retained | remaining)
                working, _ = regret_repair(origins, working, repair_obs, config,
                                           regret_k=3 if iteration % 2 else 2, position_limit=5)
            candidate_score = fleet_score(origins, working, observation, config)
            completed += 1
            if candidate_score < best_score:
                best, best_score = working, candidate_score
                improvements += 1
            if candidate_score < current_score:
                current, current_score = working, candidate_score
            elif candidate_score[:2] == current_score[:2]:
                temperature = max(0.01, current_score[2] * 0.005 * (1 - iteration / iterations))
                if rng.random() < exp(min(0.0, (current_score[2] - candidate_score[2]) / temperature)):
                    current, current_score = working, candidate_score
    return FleetLNSResult(best, initial_score, best_score, completed, improvements,
                          perf_counter() - started)
