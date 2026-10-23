"""Immutable decision-epoch contract for fleet optimizers."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Protocol
from time import perf_counter

from ..model import Action, Observation, VehicleState
from ..mpc import MPCConfig, MPCProposal
from ..repair import route_proposal
from ..planning_budget import PlanningDeadlineExceeded


class OptimizerInitializationDeadline(PlanningDeadlineExceeded):
    """The validated constructor must be used because search never initialized."""


@dataclass(frozen=True)
class OptimizationContext:
    observation: Observation
    origins: Mapping[int, VehicleState]
    busy_actions: Mapping[int, Action]
    soft_suffixes: Mapping[int, tuple[Action, ...]]
    released_customers: frozenset[str]
    committed_customers: frozenset[str]
    served_customers: frozenset[str]
    constructor_routes: Mapping[int, tuple[Action, ...]]
    k_ref: int
    deadline: float | None
    seed: int
    mpc: MPCConfig

    def __post_init__(self):
        for field_name in ("origins", "busy_actions", "soft_suffixes", "constructor_routes"):
            object.__setattr__(self, field_name, MappingProxyType(dict(getattr(self, field_name))))
        visible = frozenset(self.observation.customer_by_id)
        if self.released_customers != visible:
            raise ValueError("Released customers must equal the visible observation")
        if self.k_ref < len(self.origins) or self.k_ref < 1:
            raise ValueError("Invalid K_ref")
        if any(a.kind != "serve" or a.destination not in visible
               for route in self.constructor_routes.values() for a in route if a.kind == "serve"):
            raise ValueError("Constructor refers to an unreleased customer")
        if self.deadline is not None and self.deadline <= 0:
            raise ValueError("Invalid deadline")

    def time_left(self) -> float:
        return float("inf") if self.deadline is None else max(0.0, self.deadline - perf_counter())


@dataclass(frozen=True)
class OptimizerDiagnostics:
    values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True)
class OptimizationResult:
    routes: Mapping[int, tuple[Action, ...]]
    validated: Mapping[int, MPCProposal]
    objective: tuple[float, ...]
    components: Mapping[str, float]
    customers_covered: frozenset[str]
    vehicles_activated: int
    distance: float
    runtime: float
    diagnostics: OptimizerDiagnostics
    status: str
    deadline_reached: bool

    def __post_init__(self):
        object.__setattr__(self, "routes", MappingProxyType(dict(self.routes)))
        object.__setattr__(self, "validated", MappingProxyType(dict(self.validated)))
        object.__setattr__(self, "components", MappingProxyType(dict(self.components)))


class FleetOptimizer(Protocol):
    name: str

    def optimize(self, context: OptimizationContext) -> OptimizationResult:
        ...


def evaluated_result(context: OptimizationContext, routes: Mapping[int, tuple[Action, ...]],
                     started: float, diagnostics: OptimizerDiagnostics,
                     status: str, deadline_reached: bool,
                     known_objective: tuple[tuple[float, ...], Mapping[str, float]] | None = None) -> OptimizationResult:
    """Independently replay and score an optimizer's chosen fleet suffixes."""
    from ..fleet_mcts import _FleetProblem

    routes = {k: tuple(routes.get(k, ())) for k in context.origins}
    proposals = {}
    for k, actions in routes.items():
        if not actions:
            continue
        proposal = route_proposal(context.origins[k], actions, context.observation, context.mpc)
        if proposal is None:
            raise ValueError("Optimizer returned a non-replayable route")
        proposals[k] = proposal
    ids = tuple(sorted(context.origins))
    sequences = tuple(tuple(a.destination for a in routes[k] if a.kind == "serve") for k in ids)
    if len({c for seq in sequences for c in seq}) != sum(map(len, sequences)):
        raise ValueError("Optimizer duplicated a customer")
    if any(c not in context.released_customers - context.committed_customers - context.served_customers
           for seq in sequences for c in seq):
        raise ValueError("Optimizer planned an unavailable customer")
    actions = tuple(routes[k] for k in ids)
    costs = tuple(proposals[k].cost if k in proposals else 0.0 for k in ids)
    if known_objective is None:
        problem = _FleetProblem(dict(context.origins), context.observation, context.mpc, 3, 2)
        problem.initial_owners = {a.destination: k for k, actions in context.constructor_routes.items()
                                  for a in actions if a.kind == "serve"}
        score, components = problem._score(sequences, actions, costs)
    else:
        score, components = known_objective
        if score[0] != len(set(context.released_customers - context.committed_customers -
                                context.served_customers) - {c for seq in sequences for c in seq}):
            raise ValueError("Optimizer objective does not match replayed coverage")
        if components["distance"] != sum(costs):
            raise ValueError("Optimizer objective does not match replayed distance")
    covered = frozenset(c for seq in sequences for c in seq)
    return OptimizationResult(routes, proposals, score, components, covered,
                              int(components["activated_vehicles"]), components["distance"],
                              perf_counter() - started, diagnostics, status, deadline_reached)
