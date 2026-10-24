"""Decision-local memoization of pure full-suffix replay, disabled by default."""

from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class ProposalMemo:
    values: dict = field(default_factory=dict)
    hits: int = 0
    misses: int = 0
    limit: int = 4096


_current = ContextVar("mpc_proposal_memo", default=None)


def begin():
    memo = ProposalMemo()
    return memo, _current.set(memo)


def end(token):
    _current.reset(token)


def current():
    return _current.get()
