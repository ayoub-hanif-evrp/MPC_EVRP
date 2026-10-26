"""Decision-local memoization of pure full-suffix replay, disabled by default."""

from contextvars import ContextVar
from dataclasses import dataclass, field
from collections import Counter


@dataclass
class ProposalMemo:
    values: dict = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    limit: int = 4096
    incremental: bool = False
    fast_screen: bool = False
    transitions: dict = field(default_factory=dict)
    greedy_prefixes: dict = field(default_factory=dict)
    label_prefixes: dict = field(default_factory=dict)
    counts: Counter = field(default_factory=Counter)
    transition_limit: int = 8192
    prefix_limit: int = 1024
    label_limit: int = 256
    observations: dict = field(default_factory=dict, repr=False)

    def observation_key(self, observation):
        # Frozen observations are held strongly until this decision ends; IDs cannot be recycled.
        key = id(observation)
        if key not in self.observations:
            if len(self.observations) >= 256:
                return None
            self.observations[key] = observation
        return key


_current = ContextVar("mpc_proposal_memo", default=None)


def begin(*, incremental=False, fast_screen=False):
    memo = ProposalMemo(incremental=incremental, fast_screen=fast_screen)
    return memo, _current.set(memo)


def end(token):
    _current.reset(token)


def current():
    return _current.get()
