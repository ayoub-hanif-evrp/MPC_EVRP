"""Fleet optimizers used within the common event-triggered MPC controller."""

from .base import FleetOptimizer, OptimizationContext, OptimizationResult, OptimizerDiagnostics

def create_optimizer(name, config):
    from .registry import create_optimizer as create
    return create(name, config)

__all__ = ["FleetOptimizer", "OptimizationContext", "OptimizationResult",
           "OptimizerDiagnostics", "create_optimizer"]
