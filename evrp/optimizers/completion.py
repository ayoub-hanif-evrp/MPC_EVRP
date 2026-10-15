"""No-search optimizer: retain the common constructor's exact solution."""

from time import perf_counter

from .base import OptimizationContext, OptimizationResult, OptimizerDiagnostics, evaluated_result


class CompletionOptimizer:
    name = "MPC_COMPLETION"

    def optimize(self, context: OptimizationContext) -> OptimizationResult:
        started = perf_counter()
        return evaluated_result(context, context.constructor_routes, started,
                                OptimizerDiagnostics(), "completed", False)
