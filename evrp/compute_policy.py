"""Observable, decision-local search stopping rule for the optional controller."""

from dataclasses import dataclass, field
from time import perf_counter

from .instance import energy
from .model import EPS, transition


def stable_full_service(origins, routes, observation):
    served = {c for state in origins.values() for c in state.served_customers}
    pending = set(observation.customer_by_id) - observation.committed_ids - served
    planned = [a.destination for actions in routes.values() for a in actions if a.kind == "serve"]
    if not pending or set(planned) != pending or len(planned) != len(pending):
        return False, "uncovered_or_duplicate"
    infra = observation.infrastructure
    safe_nodes = (infra.depot,) + infra.stations
    minimum_time = float("inf")
    minimum_energy = float("inf")
    for k, actions in routes.items():
        state = origins[k]
        for action in actions:
            step = transition(state, action, observation)
            state = step.after
            if step.served:
                customer = observation.customer_by_id[step.served]
                minimum_time = min(minimum_time, customer.due - step.service_start)
                minimum_energy = min(minimum_energy,
                                     state.battery - min(energy(state.location, node, infra.parameters)
                                                         for node in safe_nodes))
    if minimum_time < 2.0 - EPS or minimum_energy < 0.02 * infra.parameters.battery - EPS:
        return False, "low_time_or_energy_slack"
    return True, "full_service_with_slack"


@dataclass
class AdaptiveComputeGate:
    eligible: bool
    reason: str
    started: float = field(default_factory=perf_counter)
    best_score: tuple | None = None
    last_meaningful: float | None = None
    stopped_early: bool = False

    def observe(self, score, now=None):
        now = perf_counter() if now is None else now
        score = tuple(score)
        if self.best_score is None:
            self.best_score = score
            self.last_meaningful = now
        elif score < self.best_score:
            if score[0] < self.best_score[0] or self.best_score[1] - score[1] >= 0.01:
                self.last_meaningful = now
            self.best_score = score

    def should_stop(self, completed_work, now=None):
        if not self.eligible or self.best_score is None or self.best_score[0] != 0:
            return False
        now = perf_counter() if now is None else now
        if completed_work >= 2 and now - self.started >= 1.1 and now - self.last_meaningful >= 0.35:
            self.stopped_early = True
        return self.stopped_early

    def report(self):
        return dict(eligible=self.eligible, reason=self.reason, stopped_early=self.stopped_early)
