"""Explicit version of the existing ALNS initialization-timeout correction."""

from .alns import ALNSOptimizer


class ALNSSafeInitV1(ALNSOptimizer):
    """Request the simulator's validated constructor if initialization expires.

    Search, objective, operators, and successful initialization are unchanged.
    The original MPC_ALNS identity retains its historical behavior.
    """

    name = "MPC_ALNS_SAFE_INIT_V1"

    def __init__(self, iterations=100, destroy_fraction=.1):
        super().__init__(iterations=iterations, destroy_fraction=destroy_fraction,
                         initialization_fallback=True)
