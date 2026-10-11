"""Cooperative wall-clock limit for one event-level planning decision."""

from contextvars import ContextVar
from time import perf_counter


class PlanningDeadlineExceeded(Exception):
    pass


_deadline: ContextVar[float | None] = ContextVar("planning_deadline", default=None)


def set_deadline(deadline: float | None):
    return _deadline.set(deadline)


def reset_deadline(token) -> None:
    _deadline.reset(token)


def check_deadline() -> None:
    deadline = _deadline.get()
    if deadline is not None and perf_counter() >= deadline:
        raise PlanningDeadlineExceeded


def remaining_time() -> float:
    deadline = _deadline.get()
    return float("inf") if deadline is None else max(0.0, deadline - perf_counter())
