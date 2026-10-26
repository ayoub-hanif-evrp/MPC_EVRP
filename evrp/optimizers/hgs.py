"""Small-population hybrid genetic search with exact EV route decoding."""

from random import Random
from time import perf_counter

from ..fleet_mcts import _FleetProblem, _SearchBudgetReached
from ..planning_budget import PlanningDeadlineExceeded, check_deadline, reset_deadline, set_deadline
from .base import (OptimizationContext, OptimizationResult, OptimizerDiagnostics,
                   OptimizerInitializationDeadline, evaluated_result)


def _edges(plan, ids):
    return frozenset((k, before, customer) for index, k in enumerate(ids)
                     for before, customer in zip((None,) + plan.sequences[index],
                                                 plan.sequences[index]))


def _diversity(plan, population, ids):
    edges = _edges(plan, ids)
    others = [_edges(other, ids) for other in population if other.sequences != plan.sequences]
    return (sum(len(edges ^ other) / max(1, len(edges | other)) for other in others) /
            len(others) if others else 0.0)


def _biased_ranks(population, ids, diversity_weight=1.25):
    """Rank service first, then trade objective rank against diversity rank."""
    ranks = {}
    for unserved in sorted({plan.score[0] for plan in population}):
        group = [plan for plan in population if plan.score[0] == unserved]
        objective = {id(plan): index for index, plan in enumerate(
            sorted(group, key=lambda plan: plan.score))}
        diversity = {id(plan): _diversity(plan, group, ids) for plan in group}
        diverse_order = sorted(group, key=lambda plan: (-diversity[id(plan)], plan.score))
        diversity_rank = {id(plan): index for index, plan in enumerate(diverse_order)}
        for plan in group:
            rank = objective[id(plan)]
            ranks[id(plan)] = (unserved, rank + diversity_weight * diversity_rank[id(plan)], rank)
    return ranks


def _select_parent(population, rng, ids):
    ranks = _biased_ranks(population, ids)
    contestants = rng.sample(population, min(3, len(population)))
    return min(contestants, key=lambda plan: ranks[id(plan)])


def _survivors(population, size, ids):
    elite = min(population, key=lambda plan: plan.score)
    ranks = _biased_ranks(population, ids)
    survivors = [elite]
    for plan in sorted(population, key=lambda plan: ranks[id(plan)]):
        if len(survivors) >= size:
            break
        if plan.sequences not in {member.sequences for member in survivors}:
            survivors.append(plan)
    return survivors


def _insert_missing(problem, plan):
    """Attempt every released, uncovered customer with exact fleet decoding."""
    current = plan
    insertions = 0
    timed_out = False
    try:
        while current.score[0]:
            check_deadline()
            problem._check_search_time()
            inserted = False
            for customer, _, _, _, _ in problem._criticality(current.sequences):
                candidates = []
                for _, _, k, pos, _ in problem.screened_options(current.sequences, customer):
                    check_deadline()
                    problem._check_search_time()
                    index = problem.ids.index(k)
                    sequence = current.sequences[index]
                    candidate = problem.change(current, {
                        k: sequence[:pos] + (customer,) + sequence[pos:]})
                    if candidate is not None:
                        candidates.append(candidate)
                        if len(candidates) >= 5:
                            break
                if candidates:
                    current = min(candidates, key=lambda candidate: candidate.score)
                    insertions += 1
                    inserted = True
                    break
            if not inserted:
                break
    except (PlanningDeadlineExceeded, _SearchBudgetReached):
        timed_out = True
    return current, insertions, timed_out


def _educate(problem, plan, rng, attempts=8):
    best = plan
    ids = problem.ids
    for _ in range(attempts):
        check_deadline()
        problem._check_search_time()
        nonempty = [k for index, k in enumerate(ids) if best.sequences[index]]
        if not nonempty:
            break
        source = rng.choice(nonempty)
        source_index = ids.index(source)
        sequence = best.sequences[source_index]
        target = rng.choice(ids)
        target_index = ids.index(target)
        target_sequence = best.sequences[target_index]
        operation = rng.choice(("relocate", "swap", "two_opt", "or_opt"))
        candidate = None
        if operation == "two_opt" and len(sequence) >= 3:
            first, last = sorted(rng.sample(range(len(sequence)), 2))
            candidate = problem.change(best, {source: sequence[:first] +
                                               tuple(reversed(sequence[first:last + 1])) +
                                               sequence[last + 1:]})
        elif operation == "or_opt" and len(sequence) >= 3:
            first = rng.randrange(len(sequence) - 1)
            pair = sequence[first:first + 2]
            remaining = sequence[:first] + sequence[first + 2:]
            gap = rng.randrange(len(remaining) + 1)
            candidate = problem.change(best, {source: remaining[:gap] + pair + remaining[gap:]})
        elif operation == "swap" and target_sequence and target != source:
            first = rng.randrange(len(sequence))
            second = rng.randrange(len(target_sequence))
            candidate = problem.change(best, {
                source: sequence[:first] + (target_sequence[second],) + sequence[first + 1:],
                target: target_sequence[:second] + (sequence[first],) + target_sequence[second + 1:]})
        elif operation == "relocate":
            first = rng.randrange(len(sequence))
            customer = sequence[first]
            reduced = sequence[:first] + sequence[first + 1:]
            if target == source:
                gap = rng.randrange(len(reduced) + 1)
                candidate = problem.change(best, {source: reduced[:gap] + (customer,) + reduced[gap:]})
            else:
                gap = rng.randrange(len(target_sequence) + 1)
                candidate = problem.change(best, {
                    source: reduced,
                    target: target_sequence[:gap] + (customer,) + target_sequence[gap:]})
        if candidate is not None and candidate.score < best.score:
            best = candidate
    return best


def _diversify(problem, root, rng, attempts=12):
    ids = problem.ids
    for _ in range(attempts):
        check_deadline()
        problem._check_search_time()
        sources = [k for index, k in enumerate(ids) if root.sequences[index]]
        if not sources:
            break
        source = rng.choice(sources)
        sequence = root.sequences[ids.index(source)]
        pos = rng.randrange(len(sequence))
        customer = sequence[pos]
        target = rng.choice(ids)
        reduced = sequence[:pos] + sequence[pos + 1:]
        if target == source:
            gap = rng.randrange(len(reduced) + 1)
            candidate = problem.change(root, {source: reduced[:gap] + (customer,) + reduced[gap:]})
        else:
            target_sequence = root.sequences[ids.index(target)]
            gap = rng.randrange(len(target_sequence) + 1)
            candidate = problem.change(root, {
                source: reduced,
                target: target_sequence[:gap] + (customer,) + target_sequence[gap:]})
        if candidate is not None and candidate.sequences != root.sequences and candidate.score[0] == root.score[0]:
            return candidate
    return root


def _crossover(problem, root, parent_a, parent_b, rng):
    ids = problem.ids
    inherited = [k for index, k in enumerate(ids)
                 if parent_a.sequences[index] and rng.random() < 0.5]
    if not inherited:
        nonempty = [k for index, k in enumerate(ids) if parent_a.sequences[index]]
        if nonempty:
            inherited = [rng.choice(nonempty)]
    child = problem.change(root, {k: parent_a.sequences[ids.index(k)] if k in inherited else ()
                                  for k in ids})
    if child is None:
        return root, 0, False
    owned = {c for sequence in child.sequences for c in sequence}
    order = [c for sequence in parent_b.sequences for c in sequence if c not in owned]
    order += [c for sequence in parent_a.sequences for c in sequence if c not in owned and c not in order]
    for customer in order:
        check_deadline()
        problem._check_search_time()
        candidates = []
        for _, _, k, pos, _ in problem.screened_options(child.sequences, customer)[:5]:
            index = ids.index(k)
            sequence = child.sequences[index]
            trial = problem.change(child, {k: sequence[:pos] + (customer,) + sequence[pos:]})
            if trial is not None:
                candidates.append(trial)
        if candidates:
            child = min(candidates, key=lambda plan: plan.score)
    return _insert_missing(problem, child)


class HGSOptimizer:
    name = "MPC_HGS"

    def __init__(self, generations: int = 32, population_size: int = 8,
                 education_attempts: int = 8, initialization_fallback: bool = False):
        if min(generations, population_size, education_attempts) < 1:
            raise ValueError("Invalid HGS budget")
        self.generations = generations
        self.population_size = population_size
        self.education_attempts = education_attempts
        self.initialization_fallback = initialization_fallback

    def optimize(self, context: OptimizationContext) -> OptimizationResult:
        started = perf_counter()
        rng = Random(context.seed)
        problem = _FleetProblem(dict(context.origins), context.observation, context.mpc, 3, 2)
        problem.search_until = context.deadline - 0.12 if context.deadline is not None else None
        token = set_deadline(context.deadline)
        best = None
        generations = crossovers = educated = 0
        root_service_insertions = offspring_service_insertions = 0
        population = []
        deadline_reached = False
        initializing = True
        try:
            root = best = problem.initial(dict(context.constructor_routes))
            initializing = False
            population = [root]
            recovered, root_service_insertions, recovery_timed_out = _insert_missing(problem, root)
            if recovered.sequences != root.sequences:
                population.append(recovered)
                best = recovered
            if recovery_timed_out:
                raise PlanningDeadlineExceeded
            seed = recovered
            for _ in range(self.population_size - len(population)):
                individual = _diversify(problem, seed, rng)
                individual = _educate(problem, individual, rng, self.education_attempts)
                if individual.sequences not in {p.sequences for p in population}:
                    population.append(individual)
                if individual.score < best.score:
                    best = individual
            if context.compute_gate is not None:
                context.compute_gate.observe(best.score)
            for _ in range(self.generations):
                if context.compute_gate is not None and context.compute_gate.should_stop(generations):
                    break
                check_deadline()
                problem._check_search_time()
                if len(population) < 2:
                    alternate = _diversify(problem, population[0], rng)
                    if alternate.sequences != population[0].sequences:
                        population.append(alternate)
                    else:
                        break
                parent_a = _select_parent(population, rng, problem.ids)
                parent_b = _select_parent(population, rng, problem.ids)
                child, recovered_count, crossover_timed_out = _crossover(
                    problem, root, parent_a, parent_b, rng)
                crossovers += 1
                offspring_service_insertions += recovered_count
                if child.score < best.score:
                    best = child
                    if context.compute_gate is not None:
                        context.compute_gate.observe(best.score)
                if crossover_timed_out:
                    raise PlanningDeadlineExceeded
                child = _educate(problem, child, rng, self.education_attempts)
                educated += 1
                generations += 1
                if child.score < best.score:
                    best = child
                    if context.compute_gate is not None:
                        context.compute_gate.observe(best.score)
                if child.sequences not in {p.sequences for p in population}:
                    population.append(child)
                population = _survivors(population, self.population_size, problem.ids)
        except (PlanningDeadlineExceeded, _SearchBudgetReached):
            if initializing and self.initialization_fallback:
                raise OptimizerInitializationDeadline from None
            deadline_reached = True
        finally:
            reset_deadline(token)
        diagnostics = OptimizerDiagnostics(dict(
            generations=generations, crossovers=crossovers, educated=educated,
            population_size=len(population), feasible_individuals=len(population),
            diversity=_diversity(best, population, problem.ids),
            root_service_insertions=root_service_insertions,
            offspring_service_insertions=offspring_service_insertions,
            exact_decoder_calls=problem.exact_decoded_options))
        return evaluated_result(context, {k: best.actions[index] for index, k in enumerate(problem.ids)},
                                started, diagnostics, "completed", deadline_reached,
                                (best.score, best.components))
