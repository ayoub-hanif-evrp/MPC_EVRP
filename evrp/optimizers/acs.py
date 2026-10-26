"""Ant Colony System over exact, observable fleet insertion choices."""

from random import Random
from time import perf_counter

from ..fleet_mcts import _FleetProblem, _SearchBudgetReached
from ..planning_budget import PlanningDeadlineExceeded, check_deadline, reset_deadline, set_deadline
from .base import (OptimizationContext, OptimizationResult, OptimizerDiagnostics,
                   OptimizerInitializationDeadline, evaluated_result)


class ACSOptimizer:
    name = "MPC_ACS"

    def __init__(self, ants: int = 8, alpha: float = 1.0, beta: float = 2.0,
                 rho: float = 0.1, q0: float = 0.85, local_rate: float = 0.1,
                 initialization_fallback: bool = False):
        if ants < 1 or alpha <= 0 or beta <= 0 or not 0 < rho < 1 or not 0 <= q0 <= 1:
            raise ValueError("Invalid ACS parameters")
        self.ants, self.alpha, self.beta = ants, alpha, beta
        self.rho, self.q0, self.local_rate = rho, q0, local_rate
        self.initialization_fallback = initialization_fallback

    @staticmethod
    def _edges(problem, plan):
        return ((k, predecessor, customer)
                for index, k in enumerate(problem.ids)
                for predecessor, customer in zip((None,) + plan.sequences[index],
                                                 plan.sequences[index]))

    def _choose(self, options, pheromone, initial_tau, rng):
        weighted = []
        for key, candidate, eta in options:
            tau = pheromone.get(key, initial_tau)
            weighted.append((max(1e-9, tau) ** self.alpha * eta ** self.beta,
                             key, candidate))
        if rng.random() < self.q0:
            _, key, candidate = max(weighted, key=lambda row: (row[0], repr(row[1])))
            return key, candidate
        draw = rng.random() * sum(row[0] for row in weighted)
        for weight, key, candidate in weighted:
            draw -= weight
            if draw <= 0:
                return key, candidate
        return weighted[-1][1:]

    def optimize(self, context: OptimizationContext) -> OptimizationResult:
        started = perf_counter()
        rng = Random(context.seed)
        problem = _FleetProblem(dict(context.origins), context.observation, context.mpc, 3, 2)
        problem.search_until = context.deadline - 0.12 if context.deadline is not None else None
        token = set_deadline(context.deadline)
        pheromone = {}
        initial_tau = 1.0 / max(1, len(problem.pending))
        completed = complete_service = updates = 0
        service_improvements = objective_improvements = 0
        improvement_times = []
        deadline_reached = False
        initializing = True
        try:
            best = constructor = problem.initial(dict(context.constructor_routes))
            initializing = False
            if context.compute_gate is not None:
                context.compute_gate.observe(best.score)
            # Every ant builds afresh; the common constructor is retained separately.
            empty = problem.change(constructor, {k: () for k in problem.ids})
            if empty is None:
                raise ValueError("Empty fleet route is not feasible")
            for _ in range(self.ants):
                if context.compute_gate is not None and context.compute_gate.should_stop(completed):
                    break
                check_deadline()
                problem._check_search_time()
                current = empty
                while current.score[0]:
                    check_deadline()
                    problem._check_search_time()
                    ranked = problem._criticality(current.sequences)
                    choices = []
                    for customer, count, _, _, _ in ranked:
                        if count == 0:
                            continue
                        for delta, slack, k, pos, _ in problem.screened_options(
                                current.sequences, customer)[:3]:
                            index = problem.ids.index(k)
                            sequence = current.sequences[index]
                            candidate = problem.change(current, {
                                k: sequence[:pos] + (customer,) + sequence[pos:]})
                            if candidate is None:
                                continue
                            predecessor = sequence[pos - 1] if pos else None
                            key = (k, predecessor, customer)
                            node = context.observation.customer_by_id[customer]
                            width = max(1.0, node.due - node.ready)
                            urgency = 1.0 + 1.0 / max(1, count)
                            slack_factor = 1.0 + 0.5 * max(0.0, 1.0 - slack / width)
                            eta = urgency * slack_factor / (1.0 + max(0.0, delta))
                            choices.append((key, candidate, eta))
                        if len(choices) >= 12:
                            break
                    if not choices:
                        break
                    key, candidate = self._choose(choices, pheromone, initial_tau, rng)
                    pheromone[key] = ((1 - self.local_rate) * pheromone.get(key, initial_tau)
                                      + self.local_rate * initial_tau)
                    updates += 1
                    current = candidate
                completed += 1
                complete_service += current.score[0] == 0
                if current.score < best.score:
                    if current.score[0] < best.score[0]:
                        service_improvements += 1
                    else:
                        objective_improvements += 1
                    best = current
                    if context.compute_gate is not None:
                        context.compute_gate.observe(best.score)
                    improvement_times.append(perf_counter() - started)
                for key in tuple(pheromone):
                    pheromone[key] = max(1e-9, (1 - self.rho) * pheromone[key])
                    updates += 1
                deposit = self.rho / (1.0 + max(0.0, best.score[0]))
                for key in self._edges(problem, best):
                    pheromone[key] = pheromone.get(key, initial_tau) + deposit
                    updates += 1
        except (PlanningDeadlineExceeded, _SearchBudgetReached):
            if initializing and self.initialization_fallback:
                raise OptimizerInitializationDeadline from None
            deadline_reached = True
        finally:
            reset_deadline(token)
        diagnostics = OptimizerDiagnostics(dict(
            ants_completed=completed, complete_service_ants=complete_service,
            best_improvement_times=improvement_times,
            pheromone_updates=updates, pheromone_edges=len(pheromone),
            exact_decoder_calls=problem.exact_decoded_options,
            service_improvements_over_constructor=service_improvements,
            objective_improvements_at_equal_service=objective_improvements))
        return evaluated_result(context, {k: best.actions[index] for index, k in enumerate(problem.ids)},
                                started, diagnostics, "completed", deadline_reached,
                                (best.score, best.components))
