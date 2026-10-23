"""Small deterministic reproducer for expired optimizer initialization."""

import argparse
from time import perf_counter

from evrp.instance import Infrastructure, Instance, Location, Parameters
from evrp.model import Observation
from evrp.mpc import MPCConfig
from evrp.optimizers.alns import ALNSOptimizer
from evrp.optimizers.acs import ACSOptimizer
from evrp.optimizers.hgs import HGSOptimizer
from evrp.optimizers.base import OptimizationContext
from evrp.reference import initial_vehicle
from evrp.storage import save_json


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
    for guarded in (False, True):
        for cls in (ALNSOptimizer, HGSOptimizer, ACSOptimizer):
            optimizer = cls(initialization_fallback=guarded)
            key = optimizer.name + ("_guarded" if guarded else "_original")
            try:
                optimizer.optimize(context)
                results[key] = "returned_result"
            except Exception as error:
                results[key] = type(error).__name__ + ": " + str(error)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    results = reproduce()
    if args.output:
        save_json(args.output, results)
    print(results)
