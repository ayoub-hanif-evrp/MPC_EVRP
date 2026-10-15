"""V1 fleet-MCTS adapter; search remains in the frozen implementation."""

from dataclasses import asdict
from time import perf_counter

from ..fleet_mcts import solve_fleet_mcts
from ..planning_budget import reset_deadline, set_deadline
from .base import OptimizationContext, OptimizationResult, OptimizerDiagnostics, evaluated_result


class MCTSV1Optimizer:
    name = "MPC_MCTS_V1"

    def __init__(self, *, iterations: int = 256, depth: int = 4,
                 branch_limit: int = 12, position_limit: int = 3, regret_k: int = 2):
        self.iterations = iterations
        self.depth = depth
        self.branch_limit = branch_limit
        self.position_limit = position_limit
        self.regret_k = regret_k

    def optimize(self, context: OptimizationContext) -> OptimizationResult:
        started = perf_counter()
        token = set_deadline(context.deadline)
        try:
            result = solve_fleet_mcts(dict(context.origins), dict(context.constructor_routes),
                                      context.observation, context.mpc, seed=context.seed,
                                      iterations=self.iterations, depth=self.depth,
                                      branch_limit=self.branch_limit,
                                      position_limit=self.position_limit, regret_k=self.regret_k)
        finally:
            reset_deadline(token)
        diagnostics = asdict(result)
        diagnostics.pop("routes")
        diagnostics.pop("validated")
        return evaluated_result(context, result.routes, started,
                                OptimizerDiagnostics(diagnostics), "completed",
                                result.deadline_reached,
                                (result.best_score, result.best_components))
