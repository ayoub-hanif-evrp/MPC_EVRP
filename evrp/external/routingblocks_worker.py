"""Isolated Python 3.11 entry point for the pinned RoutingBlocks wheel."""

import argparse
from pathlib import Path
import traceback

from evrp.external.routingblocks_adapter import run_routingblocks
from evrp.instance import load_instance
from evrp.storage import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--fleet-size", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    instance = load_instance(args.instance)
    try:
        raw = run_routingblocks(instance, args.instance, args.examples,
                                args.fleet_size, args.seed, args.budget)
        raw["status"] = "completed"
    except Exception as error:
        raw = {"status": "failed", "solver": "RoutingBlocks", "instance": instance.name,
               "seed": args.seed, "runtime_budget": args.budget,
               "error": f"{type(error).__name__}: {error}",
               "traceback": traceback.format_exc()}
    save_json(args.output, raw)


if __name__ == "__main__":
    main()
