"""Small-population hybrid genetic search with exact EV route decoding."""

from random import Random
from time import perf_counter

from ..fleet_mcts import _FleetProblem, _SearchBudgetReached
from ..planning_budget import PlanningDeadlineExceeded, check_deadline, reset_deadline, set_deadline
from .base import OptimizationContext, OptimizationResult, OptimizerDiagnostics, evaluated_result


def _edges(plan, ids):
    return frozenset((k, before, customer) for index, k in enumerate(ids)
                     for before, customer in zip((None,) + plan.sequences[index],
                                                 plan.sequences[index]))


def _diversity(plan, population, ids):
    edges = _edges(plan, ids)
    others = [_edges(other, ids) for other in population if other.sequences != plan.sequences]
    return (sum(len(edges ^ other) / max(1, len(edges | other)) for other in others) /
            len(others) if others else 0.0)


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
        return root
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
    return child


class HGSOptimizer:
    name = "MPC_HGS"

    def __init__(self, generations: int = 32, population_size: int = 8,
                 education_attempts: int = 8):
        if min(generations, population_size, education_attempts) < 1:
            raise ValueError("Invalid HGS budget")
        self.generations = generations
        self.population_size = population_size
        self.education_attempts = education_attempts

    def optimize(self, context: OptimizationContext) -> OptimizationResult:
        started = perf_counter()
        rng = Random(context.seed)
        problem = _FleetProblem(dict(context.origins), context.observation, context.mpc, 3, 2)
        problem.search_until = context.deadline - 0.12 if context.deadline is not None else None
        token = set_deadline(context.deadline)
        best = None
        generations = crossovers = educated = 0
        population = []
        deadline_reached = False
        try:
            root = best = problem.initial(dict(context.constructor_routes))
            population = [root]
            for _ in range(self.population_size - 1):
                individual = _diversify(problem, root, rng)
                individual = _educate(problem, individual, rng, self.education_attempts)
                if individual.sequences not in {p.sequences for p in population}:
                    population.append(individual)
                if individual.score < best.score:
                    best = individual
            for _ in range(self.generations):
                check_deadline()
                problem._check_search_time()
                if len(population) < 2:
                    alternate = _diversify(problem, population[0], rng)
                    if alternate.sequences != population[0].sequences:
                        population.append(alternate)
                    else:
                        break
                def select():
                    contestants = rng.sample(population, min(3, len(population)))
                    return min(contestants, key=lambda p: (p.score, -_diversity(p, population, problem.ids)))
                parent_a, parent_b = select(), select()
                child = _crossover(problem, root, parent_a, parent_b, rng)
                crossovers += 1
                child = _educate(problem, child, rng, self.education_attempts)
                educated += 1
                generations += 1
                if child.score < best.score:
                    best = child
                if child.sequences not in {p.sequences for p in population}:
                    population.append(child)
                view = tuple(population)
                population.sort(key=lambda p: (p.score, -_diversity(p, view, problem.ids)))
                # Keep the elite and a diversity-aware remainder.
                elite = population[0]
                survivors = [elite]
                for individual in sorted(population[1:],
                                         key=lambda p: (p.score, -_diversity(p, survivors, problem.ids))):
                    if len(survivors) >= self.population_size:
                        break
                    if individual.sequences not in {p.sequences for p in survivors}:
                        survivors.append(individual)
                population = survivors
        except (PlanningDeadlineExceeded, _SearchBudgetReached):
            deadline_reached = True
        finally:
            reset_deadline(token)
        diagnostics = OptimizerDiagnostics(dict(
            generations=generations, crossovers=crossovers, educated=educated,
            population_size=len(population), feasible_individuals=len(population),
            diversity=_diversity(best, population, problem.ids),
            exact_decoder_calls=problem.exact_decoded_options))
        return evaluated_result(context, {k: best.actions[index] for index, k in enumerate(problem.ids)},
                                started, diagnostics, "completed", deadline_reached,
                                (best.score, best.components))
