"""Construction of optimizer adapters for the MPC pipeline."""

from .completion import CompletionOptimizer
from .mcts import MCTSV1Optimizer
from .alns import ALNSOptimizer
from .hgs import HGSOptimizer


def create_optimizer(name, config):
    if name == "MPC_COMPLETION":
        return CompletionOptimizer()
    if name == "MPC_MCTS_V1":
        return MCTSV1Optimizer(iterations=config.fleet_mcts_iterations,
                               depth=config.fleet_mcts_depth,
                               branch_limit=config.fleet_mcts_branch_limit,
                               position_limit=config.candidate_position_limit,
                               regret_k=config.rollout_regret_k)
    if name == "MPC_ALNS":
        return ALNSOptimizer(iterations=config.lns_iterations,
                             destroy_fraction=config.lns_destroy_fraction)
    if name == "MPC_HGS":
        return HGSOptimizer()
    raise ValueError(f"Unknown MPC optimizer: {name}")
