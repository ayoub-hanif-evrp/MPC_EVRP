"""Adaptive large-neighborhood search over exact EV route decodes."""

from collections import Counter
from math import ceil, exp, sqrt
from random import Random
from time import perf_counter

from ..fleet_mcts import _FleetProblem, _SearchBudgetReached
from ..instance import distance
from ..planning_budget import PlanningDeadlineExceeded, check_deadline, reset_deadline, set_deadline
from .base import OptimizationContext, OptimizationResult, OptimizerDiagnostics, evaluated_result


DESTROY = ("random", "worst_distance", "related", "critical_tw", "battery_risk", "route_risk")
REPAIR = ("regret2", "regret3", "criticality_first", "reserve_preserving")


def _roulette(names, weights, rng):
    draw = rng.random() * sum(weights[name] for name in names)
    for name in names:
        draw -= weights[name]
        if draw <= 0:
            return name
    return names[-1]


def _removal_order(problem, plan, name, rng):
    owned = [(k, pos, c) for index, k in enumerate(problem.ids)
             for pos, c in enumerate(plan.sequences[index])]
    if name == "random":
        rng.shuffle(owned)
        return owned
    obs = problem.observation
    if name == "related":
        anchor = obs.customer_by_id[rng.choice(owned)[2]]
        return sorted(owned, key=lambda row: (
            distance(anchor, obs.customer_by_id[row[2]]) +
            0.05 * abs(anchor.due - obs.customer_by_id[row[2]].due), row))
    if name == "critical_tw":
        return sorted(owned, key=lambda row: (
            obs.customer_by_id[row[2]].due - obs.customer_by_id[row[2]].ready, row))
    if name in {"battery_risk", "route_risk"}:
        field = "battery" if name == "battery_risk" else None
        def risk(row):
            k = row[0]
            metrics = problem._metrics(k, plan.actions[problem.ids.index(k)])
            return metrics[field] if field else max(metrics[f] for f in
                    ("tw", "battery", "capacity", "time_risk"))
        return sorted(owned, key=lambda row: (-risk(row), row))

    def saving(row):
        k, pos, customer = row
        seq = plan.sequences[problem.ids.index(k)]
        before = problem.origins[k].location if pos == 0 else obs.customer_by_id[seq[pos - 1]]
        after = obs.infrastructure.depot if pos + 1 == len(seq) else obs.customer_by_id[seq[pos + 1]]
        node = obs.customer_by_id[customer]
        return distance(before, node) + distance(node, after) - distance(before, after)
    return sorted(owned, key=lambda row: (-saving(row), row))


def _repair(problem, plan, name, rng, fallback_limit=5):
    current = plan
    while current.score[0] and (problem.search_until is None or perf_counter() < problem.search_until):
        check_deadline()
        critical = problem._criticality(current.sequences)
        if name == "criticality_first":
            targets = [row[0] for row in critical]
        elif name == "reserve_preserving":
            targets = [row[0] for row in critical]
        else:
            def regret(row):
                options = problem.screened_options(current.sequences, row[0])
                index = 1 if name == "regret2" else 2
                if not options:
                    return -1.0
                return (options[min(index, len(options) - 1)][0] - options[0][0]
                        if len(options) > index else float("inf"))
            targets = sorted((row[0] for row in critical),
                             key=lambda c: (-regret(next(row for row in critical if row[0] == c)), c))
        inserted = False
        for customer in targets:
            options = list(problem.screened_options(current.sequences, customer))
            if name == "reserve_preserving":
                options.sort(key=lambda row: (not problem.origins[row[2]].departed and
                                               not current.sequences[problem.ids.index(row[2])], row))
            candidates = []
            batches = (options[:5], options[5:fallback_limit]) if fallback_limit > 5 else (options[:5],)
            for batch in batches:
                for _, _, k, pos, _ in batch:
                    index = problem.ids.index(k)
                    sequence = current.sequences[index]
                    trial = problem.change(current, {k: sequence[:pos] + (customer,) + sequence[pos:]})
                    if trial is not None:
                        candidates.append(trial)
                if candidates:
                    break
            if candidates:
                current = min(candidates, key=lambda trial: trial.score)
                inserted = True
                break
        if not inserted:
            break
    return current


class ALNSOptimizer:
    name = "MPC_ALNS"

    def __init__(self, iterations: int = 100, destroy_fraction: float = 0.1,
                 reaction_factor: float = 0.2, segment_length: int = 12):
        if iterations < 1 or not 0 < destroy_fraction <= 1:
            raise ValueError("Invalid ALNS budget")
        self.iterations = iterations
        self.destroy_fraction = destroy_fraction
        self.reaction_factor = reaction_factor
        self.segment_length = segment_length

    def _destroy_count(self, owned, uncovered):
        return min(owned, 4, max(1, round(owned * self.destroy_fraction)))

    def _repair(self, problem, plan, name, rng):
        return _repair(problem, plan, name, rng)

    def optimize(self, context: OptimizationContext) -> OptimizationResult:
        started = perf_counter()
        rng = Random(context.seed)
        problem = _FleetProblem(dict(context.origins), context.observation, context.mpc, 3, 2)
        problem.search_until = (context.deadline - 0.12 if context.deadline is not None else None)
        token = set_deadline(context.deadline)
        d_weights = {name: 1.0 for name in DESTROY}
        r_weights = {name: 1.0 for name in REPAIR}
        d_counts, r_counts = Counter(), Counter()
        d_segment, r_segment = Counter(), Counter()
        d_rewards, r_rewards = Counter(), Counter()
        accepted = improving = completed = 0
        best_times = []
        deadline_reached = False
        try:
            current = best = problem.initial(dict(context.constructor_routes))
            for iteration in range(self.iterations):
                check_deadline()
                problem._check_search_time()
                owned = sum(map(len, current.sequences))
                if not owned and not current.score[0]:
                    break
                destroy = _roulette(DESTROY, d_weights, rng)
                repair = _roulette(REPAIR, r_weights, rng)
                d_counts[destroy] += 1
                r_counts[repair] += 1
                d_segment[destroy] += 1
                r_segment[repair] += 1
                working = current
                if owned:
                    count = self._destroy_count(owned, current.score[0])
                    for k, _, customer in _removal_order(problem, current, destroy, rng)[:count]:
                        index = problem.ids.index(k)
                        sequence = tuple(c for c in working.sequences[index] if c != customer)
                        candidate = problem.change(working, {k: sequence})
                        if candidate is None:
                            break
                        working = candidate
                candidate = self._repair(problem, working, repair, rng)
                completed += 1
                if candidate.score[0] > current.score[0]:
                    continue
                reward = 0
                if candidate.score < best.score:
                    best = candidate
                    best_times.append(perf_counter() - started)
                    reward = 6
                if candidate.score < current.score:
                    improving += 1
                    reward = max(reward, 3)
                if candidate.score <= current.score:
                    take = True
                else:
                    # Equal-service diversification only; best still uses J_A/J_B.
                    lower_current = sum(min(1.0, max(0.0, float(x))) for x in current.score[1:])
                    lower_candidate = sum(min(1.0, max(0.0, float(x))) for x in candidate.score[1:])
                    temperature = max(0.01, 0.25 * (1 - iteration / self.iterations))
                    take = rng.random() < exp(-max(0.0, lower_candidate - lower_current) /
                                              temperature)
                if take:
                    current = candidate
                    accepted += 1
                    reward = max(reward, 1)
                d_rewards[destroy] += reward
                r_rewards[repair] += reward
                if (iteration + 1) % self.segment_length == 0:
                    for names, weights, counts, rewards in (
                            (DESTROY, d_weights, d_segment, d_rewards),
                            (REPAIR, r_weights, r_segment, r_rewards)):
                        for name in names:
                            if counts[name]:
                                weights[name] = ((1 - self.reaction_factor) * weights[name] +
                                                 self.reaction_factor * rewards[name] / counts[name])
                        counts.clear()
                        rewards.clear()
        except (PlanningDeadlineExceeded, _SearchBudgetReached):
            deadline_reached = True
        finally:
            reset_deadline(token)
        diagnostics = OptimizerDiagnostics(dict(
            iterations=completed, accepted_moves=accepted, improving_moves=improving,
            best_improvement_times=best_times,
            destroy_counts=dict(d_counts), repair_counts=dict(r_counts),
            destroy_weights=d_weights, repair_weights=r_weights,
            exact_decoder_calls=problem.exact_decoded_options))
        return evaluated_result(context, {k: best.actions[index] for index, k in enumerate(problem.ids)},
                                started, diagnostics, "completed", deadline_reached,
                                (best.score, best.components))


class ALNSRecoveryV2(ALNSOptimizer):
    name = "MPC_ALNS_RECOVERY_V2"

    def _destroy_count(self, owned, uncovered):
        original = super()._destroy_count(owned, uncovered)
        if not uncovered:
            return original
        return min(owned, max(original, min(8, ceil(sqrt(owned)))))

    def _repair(self, problem, plan, name, rng):
        return _repair(problem, plan, name, rng, fallback_limit=12)
