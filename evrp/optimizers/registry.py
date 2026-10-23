"""Construction of optimizer adapters for the MPC pipeline."""

from .completion import CompletionOptimizer
from .mcts import FleetMCTSOptimizer
from .alns import ALNSOptimizer, ALNSRecoveryV2, ALNSStableV3
from .hgs import HGSOptimizer
from .acs import ACSOptimizer


def create_optimizer(name, config):
    if name == "MPC_COMPLETION":
        return CompletionOptimizer()
    if name == "MPC_MCTS":
        return FleetMCTSOptimizer(iterations=config.fleet_mcts_iterations,
                               depth=config.fleet_mcts_depth,
                               branch_limit=config.fleet_mcts_branch_limit,
                               position_limit=config.candidate_position_limit,
                               regret_k=config.rollout_regret_k)
    if name == "MPC_ALNS":
        return ALNSOptimizer(iterations=config.lns_iterations,
                             destroy_fraction=config.lns_destroy_fraction)
    if name == "MPC_ALNS_RECOVERY_V2":
        return ALNSRecoveryV2(iterations=config.lns_iterations,
                              destroy_fraction=config.lns_destroy_fraction)
    if name == "MPC_ALNS_STABLE_V3":
        return ALNSStableV3(iterations=config.lns_iterations,
                            destroy_fraction=config.lns_destroy_fraction)
    if name == "MPC_HGS":
        return HGSOptimizer()
    if name == "MPC_ACS":
        return ACSOptimizer()
    raise ValueError(f"Unknown MPC optimizer: {name}")
