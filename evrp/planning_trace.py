"""Opt-in development evidence from the observable planning problem."""

from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class PlanningTrace:
    observation: object
    origins: dict
    busy_actions: dict
    retained_suffixes: dict
    invalid_suffixes: dict
    phase: str = "coordination"
    stages: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    dropped_events: int = 0
    event_limit: int = 100000

    def record(self, kind, **values):
        if len(self.events) >= self.event_limit:
            self.dropped_events += 1
            return
        self.events.append(dict(phase=self.phase, kind=kind, **values))

    def stage(self, name, routes):
        self.phase = name
        self.stages[name] = {k: tuple(actions) for k, actions in routes.items()}


_current = ContextVar("mpc_development_planning_trace", default=None)


def current_trace():
    return _current.get()


def start_trace(trace):
    return _current.set(trace)


def reset_trace(token):
    _current.reset(token)


def record(kind, **values):
    trace = _current.get()
    if trace is not None:
        trace.record(kind, **values)
