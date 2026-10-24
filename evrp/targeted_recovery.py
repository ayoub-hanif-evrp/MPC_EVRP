"""Bounded observable-state recovery and counterfactual first controls.

Candidate order is heuristic; acceptance always uses the unchanged fleet
objective and independently replayed complete routes. No future requests enter.
"""

from dataclasses import replace
from time import perf_counter

from .fleet_mcts import _FleetProblem, _SearchBudgetReached
from .model import transition
from .planning_budget import (PlanningDeadlineExceeded, check_deadline, remaining_time,
                              reset_deadline, set_deadline)
from .repair import route_proposal


def _routes(problem, plan):
    return {k: plan.actions[index] for index, k in enumerate(problem.ids)}


def _validated(problem, plan):
    proposals = {}
    for k, actions in _routes(problem, plan).items():
        check_deadline()
        if not actions:
            continue
        state = problem.origins[k]
        for action in actions:
            check_deadline()
            state = transition(state, action, problem.observation).after
        proposal = route_proposal(problem.origins[k], actions, problem.observation, problem.config)
        if proposal is None:
            raise ValueError("Targeted candidate failed independent physical replay")
        proposals[k] = proposal
    return proposals


def _initialize(problem, routes, reference_routes):
    plan = problem.initial(routes)
    if reference_routes is not None:
        problem.initial_owners = {a.destination: k for k, actions in reference_routes.items()
                                  for a in actions if a.kind == "serve"}
        score, components = problem._score(plan.sequences, plan.actions, plan.costs)
        plan = replace(plan, score=score, components=components)
    return plan


def _recover(problem, plan, record, rounds=3, on_progress=None):
    current = plan
    for _ in range(rounds):
        check_deadline()
        owned = {c for sequence in current.sequences for c in sequence}
        pending = sorted(problem.pending - owned, key=lambda c: (
            problem.observation.customer_by_id[c].due,
            problem.observation.customer_by_id[c].due - problem.observation.customer_by_id[c].ready, c))
        ranked = []
        for customer in pending[:4]:
            candidates = []
            for _, _, k, position, _ in problem.screened_options(current.sequences, customer)[:8]:
                check_deadline()
                sequence = current.sequences[problem.ids.index(k)]
                candidate = problem.change(current, {k: sequence[:position] + (customer,) + sequence[position:]},
                                           "TW_REGRET_INSERTION")
                record["evaluated_insertions"] += 1
                if candidate is not None:
                    candidates.append(candidate)
            if candidates:
                ordered = sorted(candidates, key=lambda p: p.score)
                costs = sorted(sum(candidate.costs) for candidate in candidates)
                regret = costs[min(1, len(costs)-1)] - costs[0] if len(costs) > 1 else float("inf")
                target = problem.observation.customer_by_id[customer]
                ranked.append(((len(candidates) != 1, -regret, target.due, customer), ordered[0]))
        if ranked:
            candidate = min(ranked, key=lambda row: row[0])[1]
        else:
            chains = []
            for customer in pending[:2]:
                chains.extend(problem._ejection_chain_candidates(current, customer, 2))
            if not chains:
                break
            record["chain_candidates"] += len(chains)
            candidate = min(chains, key=lambda p: p.score)
        if candidate.score >= current.score:
            break
        proposals = _validated(problem, candidate)
        current = candidate
        record["accepted_improvements"] += 1
        if on_progress is not None:
            on_progress(current, proposals)
    return current


def improve_constructor(origins, routes, observation, config, *, seconds=.3, reference_routes=None):
    started = perf_counter()
    record = dict(evaluated_insertions=0, chain_candidates=0, accepted_improvements=0,
                  deadline_reached=False, seconds=0.0)
    result, validated = dict(routes), None
    if remaining_time() < .025:
        return result, validated, record
    token = set_deadline(started + min(seconds, max(0, remaining_time() - .015)))
    try:
        problem = _FleetProblem(origins, observation, config, 5, 2)
        initial = _initialize(problem, routes, reference_routes)
        record["initial_score"] = initial.score
        record["selected_score"] = initial.score
        def remember(candidate, proposals):
            nonlocal result, validated
            result, validated = _routes(problem, candidate), proposals
            record["selected_score"] = candidate.score
        _recover(problem, initial, record, on_progress=remember)
    except (PlanningDeadlineExceeded, _SearchBudgetReached):
        record["deadline_reached"] = True
    finally:
        reset_deadline(token)
    record["seconds"] = perf_counter() - started
    return result, validated, record


def _first_alternatives(problem, plan, ready):
    owned = {c: k for index, k in enumerate(problem.ids) for c in plan.sequences[index]}
    urgent = sorted(problem.pending, key=lambda c: (problem.observation.customer_by_id[c].due, c))[:4]
    seen = set()
    for k in sorted(set(ready) & set(problem.ids)):
        index = problem.ids.index(k)
        sequence = plan.sequences[index]
        targets = list(dict.fromkeys(list(sequence[1:3]) + urgent))
        for customer in targets:
            check_deadline()
            if sequence and customer == sequence[0]:
                continue
            new = (customer,) + tuple(c for c in sequence if c != customer)
            changes = {k: new}
            owner = owned.get(customer)
            if owner is not None and owner != k:
                changes[owner] = tuple(c for c in plan.sequences[problem.ids.index(owner)] if c != customer)
            signature = tuple(sorted(changes.items()))
            if signature in seen:
                continue
            seen.add(signature)
            yield k, changes


def _commitment_opportunities(problem, plan, ready):
    origins, routes = dict(problem.origins), _routes(problem, plan)
    committed = []
    for k in sorted(set(ready) & set(problem.ids)):
        if routes[k]:
            first = routes[k][0]
            origins[k] = transition(origins[k], first, problem.observation).after
            routes[k] = routes[k][1:]
            committed.append(dict(vehicle=k, kind=first.kind, destination=first.destination))
    after = _FleetProblem(origins, problem.observation, problem.config, 3, 2)
    sequences = tuple(tuple(a.destination for a in routes[k] if a.kind == "serve") for k in after.ids)
    owned = {c for sequence in sequences for c in sequence}
    options = {customer: len(after.screened_options(sequences, customer))
               for customer in sorted(after.pending - owned)}
    return dict(first_commitments=committed, screened_options=options,
                interpretation="necessary-condition screens, not physical infeasibility certificates")


def counterfactual_actions(origins, routes, observation, config, ready, *,
                           seconds=.25, reference_routes=None, diagnostic=False):
    started = perf_counter()
    record = dict(evaluated_insertions=0, chain_candidates=0, accepted_improvements=0,
                  first_action_candidates=0, first_action_changes=0, deadline_reached=False,
                  candidates=[], seconds=0.0)
    result, validated = dict(routes), None
    if remaining_time() < .025:
        return result, validated, record
    token = set_deadline(started + min(seconds, max(0, remaining_time() - .015)))
    try:
        problem = _FleetProblem(origins, observation, config, 5, 2)
        initial = best = _initialize(problem, routes, reference_routes)
        record["initial_score"] = initial.score
        record["selected_score"] = initial.score
        if diagnostic:
            record["selected_commitment_state"] = _commitment_opportunities(problem, initial, ready)
        for k, changes in _first_alternatives(problem, initial, ready):
            if record["first_action_candidates"] >= 12:
                break
            candidate = problem.change(initial, changes, "COUNTERFACTUAL_FIRST_CONTROL")
            record["first_action_candidates"] += 1
            if candidate is None:
                record["candidates"].append(dict(vehicle=k, status="bounded_route_reconstruction_failure"))
                continue
            proposals = _validated(problem, candidate)
            if candidate.score < best.score:
                best, validated = candidate, proposals
                result = _routes(problem, best)
                record["selected_score"] = best.score
                record["accepted_improvements"] += 1
            def remember(recovered, proof):
                nonlocal best, validated, result
                if recovered.score < best.score:
                    best, validated, result = recovered, proof, _routes(problem, recovered)
                    record["selected_score"] = best.score
            candidate = _recover(problem, candidate, record, rounds=1, on_progress=remember)
            old_owned = {c for seq in initial.sequences for c in seq}
            new_owned = {c for seq in candidate.sequences for c in seq}
            evidence = dict(vehicle=k, status="physically_validated", score=candidate.score,
                            preserves_planned_service=old_owned <= new_owned,
                            first_action=vars(candidate.actions[problem.ids.index(k)][0]))
            if diagnostic:
                evidence["commitment_state"] = _commitment_opportunities(problem, candidate, ready)
            record["candidates"].append(evidence)
        record["selected_score"] = best.score
    except (PlanningDeadlineExceeded, _SearchBudgetReached):
        record["deadline_reached"] = True
    finally:
        reset_deadline(token)
    record["seconds"] = perf_counter() - started
    record["first_action_changes"] = sum(
        (routes[k][0] if routes.get(k) else None) != (result[k][0] if result.get(k) else None)
        for k in ready)
    return result, validated, record
