"""Optional bounded, observable-state route quality and service recovery."""

from time import perf_counter

from .fleet_mcts import _FleetProblem, _SearchBudgetReached
from .planning_budget import (PlanningDeadlineExceeded, check_deadline, remaining_time,
                              reset_deadline, set_deadline)
from .targeted_recovery import _routes, _validated


def _quality_admissible(anchor, candidate):
    if candidate.score[0] != 0 or candidate.score[0] != anchor.score[0]:
        return False
    before, after = anchor.components, candidate.components
    return (after["distance"] < before["distance"] - .01 and
            after["control_risk"] <= before["control_risk"] + .005 and
            after["flexibility_risk"] <= before["flexibility_risk"] + .01 and
            after["normalized_route_duration"] <= before["normalized_route_duration"] + .02 and
            after["normalized_charging_time"] <= before["normalized_charging_time"] + .02 and
            after["normalized_waiting_time"] <= before["normalized_waiting_time"] + .02 and
            after["activated_vehicles"] <= before["activated_vehicles"])


def refine(origins, routes, observation, config, *, quality=False, recovery=False, seconds=.12):
    """Keep the incumbent unless an exactly validated, service-safe move wins."""
    started = perf_counter()
    record = dict(eligible=False, mode=("quality" if quality else "recovery"),
                  candidates=0, accepted=False, seconds=0.0, deadline_reached=False)
    original = dict(routes)
    if remaining_time() < .15:
        return original, None, record
    owned = {a.destination for route in routes.values() for a in route if a.kind == "serve"}
    served = {c for state in origins.values() for c in state.served_customers}
    uncovered = set(observation.customer_by_id) - observation.committed_ids - served - owned
    if quality and uncovered or recovery and not uncovered:
        return original, None, record
    token = set_deadline(started + min(seconds, max(0.0, remaining_time() - .03)))
    chosen = None
    try:
        problem = _FleetProblem(origins, observation, config, 3, 2)
        anchor = best = problem.initial(routes)
        record["eligible"] = True
        record["original_distance"] = anchor.components["distance"]
        if quality:
            for index, k in enumerate(problem.ids):
                sequence = anchor.sequences[index]
                for i in range(len(sequence) - 1):
                    check_deadline()
                    revised = sequence[:i] + tuple(reversed(sequence[i:i + 2])) + sequence[i + 2:]
                    candidate = problem.change(anchor, {k: revised}, "QUALITY_2OPT")
                    record["candidates"] += 1
                    if candidate is not None and _quality_admissible(anchor, candidate) and (
                            chosen is None or (candidate.components["distance"], candidate.score) <
                            (chosen.components["distance"], chosen.score)):
                        chosen = candidate
                    if record["candidates"] >= 12:
                        break
                if record["candidates"] >= 12:
                    break
        elif recovery:
            targets = []
            for customer in sorted(uncovered):
                options = problem.screened_options(anchor.sequences, customer)
                if options:
                    targets.append((min(option[1] for option in options),
                                    observation.customer_by_id[customer].due, customer, options))
            for _, _, customer, options in sorted(targets)[:2]:
                for _, _, k, position, _ in options[:4]:
                    check_deadline()
                    index = problem.ids.index(k)
                    sequence = anchor.sequences[index]
                    revised = sequence[:position] + (customer,) + sequence[position:]
                    candidate = problem.change(anchor, {k: revised}, "SERVICE_RECOVERY")
                    record["candidates"] += 1
                    if candidate is not None and candidate.score < best.score:
                        best = chosen = candidate
        if chosen is not None:
            proof = _validated(problem, chosen)
            record["accepted"] = True
            record["selected_distance"] = chosen.components["distance"]
            record["selected_score"] = chosen.score
            return _routes(problem, chosen), proof, record
    except (PlanningDeadlineExceeded, _SearchBudgetReached):
        record["deadline_reached"] = True
    finally:
        reset_deadline(token)
        record["seconds"] = perf_counter() - started
    return original, None, record
