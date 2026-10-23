"""Small deterministic reproducer for expired optimizer initialization."""

from time import perf_counter

from evrp.instance import Infrastructure, Instance, Location, Parameters
from evrp.model import Observation
from evrp.mpc import MPCConfig
from evrp.optimizers.alns import ALNSOptimizer
from evrp.optimizers.acs import ACSOptimizer
from evrp.optimizers.hgs import HGSOptimizer
from evrp.optimizers.base import OptimizationContext
from evrp.reference import initial_vehicle


def reproduce():
    depot = Location("D", "d", 0, 0, 0, 0, 100, 0)
    request = Location("A", "c", 1, 0, 1, 0, 50, 1)
    instance = Instance("timeout_toy", "synthetic", Infrastructure(
        depot, (), Parameters(100, 10, 1, 1, 1)), (request,))
    observation = Observation(0, instance.infrastructure, instance.customers)
    context = OptimizationContext(observation, {0: initial_vehicle(instance)}, {}, {},
                                  frozenset({"A"}), frozenset(), frozenset(), {}, 1,
                                  perf_counter() - 1, 0, MPCConfig())
    results = {}
    for optimizer in (ALNSOptimizer(), HGSOptimizer(), ACSOptimizer()):
        try:
            optimizer.optimize(context)
            results[optimizer.name] = "returned_result"
        except Exception as error:
            results[optimizer.name] = type(error).__name__ + ": " + str(error)
    return results


if __name__ == "__main__":
    print(reproduce())
