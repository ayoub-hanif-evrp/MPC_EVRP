"""Exact, bounded planning-only transition reuse; plant and auditor are unchanged."""

from .model import InfeasibleAction, transition as physical_transition
from .planning_budget import check_deadline
from .proposal_memo import current


def transition(state, action, observation, require_return=True):
    memo = current()
    if memo is None or not memo.incremental:
        return physical_transition(state, action, observation, require_return)
    check_deadline()
    observation_key = memo.observation_key(observation)
    if observation_key is None:
        return physical_transition(state, action, observation, require_return)
    key = (state, action, observation_key, require_return)
    if key in memo.transitions:
        memo.counts["transition_hits"] += 1
        result = memo.transitions[key]
        if isinstance(result, tuple):
            raise InfeasibleAction(*result)
        return result
    memo.counts["transition_misses"] += 1
    try:
        result = physical_transition(state, action, observation, require_return)
    except InfeasibleAction as error:
        if len(memo.transitions) < memo.transition_limit:
            memo.transitions[key] = (str(error), error.reason)
        raise
    if len(memo.transitions) < memo.transition_limit:
        memo.transitions[key] = result
    return result
