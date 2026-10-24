"""Opt-in two-EV exchanges, ordered by observed first-control flexibility.

No waiting or demand forecasts. Only released requests and measured origins
enter generation. Acceptance uses the original complete canonical evaluator.
"""

from dataclasses import replace
from time import perf_counter

from .fleet_mcts import _FleetProblem, _SearchBudgetReached
from .instance import travel_time
from .planning_budget import (PlanningDeadlineExceeded, check_deadline, remaining_time,
                              reset_deadline, set_deadline)
from .repair import route_proposal
from .resource_decoder import decode_resource_labels
from .targeted_recovery import _initialize, _routes, _validated


def exchange_changes(problem, plan, ready):
    """Head exchanges and uncovered-request insertion with displaced-head relocation."""
    owned = {c for sequence in plan.sequences for c in sequence}
    infra = problem.observation.infrastructure
    def slack(customer):
        c = problem.observation.customer_by_id[customer]
        return c.due - min(max(s.time + travel_time(s.location, c, infra.parameters), c.ready)
                           for s in problem.origins.values())
    ready = set(ready) & set(problem.ids)
    unseen = set()
    candidates = []
    for i, k in enumerate(problem.ids):
        if k not in ready:
            continue
        sequence = plan.sequences[i]
        # Unlike V1, change both vehicle assignments in a single validated move.
        for j, other in enumerate(problem.ids):
            if j <= i or other not in ready or not sequence or not plan.sequences[j]:
                continue
            second = plan.sequences[j]
            changes = {k: (second[0],) + sequence[1:], other: (sequence[0],) + second[1:]}
            candidates.append((min(slack(sequence[0]), slack(second[0])), changes))
        for target in sorted(problem.pending - owned, key=lambda c: (slack(c), c))[:3]:
            if not sequence:
                candidates.append((slack(target), {k: (target,)}))
                continue
            head, rest = sequence[0], sequence[1:]
            for j, other in enumerate(problem.ids):
                if k == other:
                    continue
                destination = plan.sequences[j]
                positions = problem._positions(plan, other, head)
                for position in positions[:2]:
                    changes = {k: (target,) + rest,
                               other: destination[:position] + (head,) + destination[position:]}
                    candidates.append((slack(target), changes))
    # Slack and remaining resources affect generation only, never final scoring.
    for _, changes in sorted(candidates, key=lambda row: (row[0], tuple(sorted(row[1].items())))):
        signature = tuple(sorted(changes.items()))
        if signature not in unseen:
            unseen.add(signature)
            yield changes


def improve_first_controls(origins, routes, observation, config, ready, *, seconds=.35,
                           reference_routes=None):
    started = perf_counter()
    record = dict(candidates=0, validated=0, selected=0, selective_label_attempts=0,
                  deadline_reached=False, seconds=0.0)
    result, proof = dict(routes), None
    if not origins or remaining_time() < .025:
        return result, proof, record
    token = set_deadline(started + min(seconds, max(0, remaining_time() - .015)))
    try:
        problem = _FleetProblem(origins, observation, config, 3, 2)
        initial = best = _initialize(problem, routes, reference_routes)
        record.update(initial_score=initial.score, selected_score=initial.score)
        for changes in exchange_changes(problem, initial, ready):
            check_deadline()
            if record["candidates"] >= 48:
                break
            record["candidates"] += 1
            candidate = problem.change(initial, changes, "FLEX_TWO_EV_EXCHANGE")
            if candidate is None and record["selective_label_attempts"] < 6:
                # Exact useful partial-charge targets only after the old decoder fails.
                for k, sequence in changes.items():
                    if problem.decoded.get((k, sequence), True) is not None:
                        continue
                    record["selective_label_attempts"] += 1
                    actions = decode_resource_labels(origins[k], sequence, observation,
                                                     replace(config, route_decoder_version="resource_labels_v2"))
                    proposal = route_proposal(origins[k], actions, observation, config) if actions else None
                    if proposal is not None:
                        problem.decoded[k, sequence] = (actions, proposal)
                    if record["selective_label_attempts"] >= 6:
                        break
                candidate = problem.change(initial, changes, "FLEX_TWO_EV_EXCHANGE")
            if candidate is None or candidate.score >= best.score:
                continue
            validated = _validated(problem, candidate)
            record["validated"] += 1
            best, result, proof = candidate, _routes(problem, candidate), validated
            record.update(selected=record["selected"] + 1, selected_score=best.score)
    except (PlanningDeadlineExceeded, _SearchBudgetReached):
        record["deadline_reached"] = True
    finally:
        reset_deadline(token)
    record["seconds"] = perf_counter() - started
    return result, proof, record
