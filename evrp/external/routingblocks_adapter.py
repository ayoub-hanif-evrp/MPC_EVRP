"""Adapter around the unmodified official RoutingBlocks EVRPTW-PR example."""

from dataclasses import asdict
from pathlib import Path
import random
import sys

from evrp.external.compatibility import compare_geometry
from evrp.instance import Instance


def _example_parser(examples_root: Path):
    root = str(examples_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    from evrptw.instance import parse_evrptw_instance, create_cpp_instance
    return parse_evrptw_instance, create_cpp_instance


def _example_modules(examples_root: Path):
    parse_evrptw_instance, create_cpp_instance = _example_parser(examples_root)
    from evrptw.parameters import ALNSParams
    from evrptw.alns import ALNS
    return parse_evrptw_instance, create_cpp_instance, ALNSParams, ALNS


def verify_routingblocks_instance(instance: Instance, path: Path, examples_root: Path,
                                  fleet_size: int) -> dict:
    """Parse with upstream code and compare every node, arc and resource parameter."""
    if path.resolve().stem != instance.name or fleet_size <= 0:
        raise ValueError("Instance name or K_ref mismatch")
    parse, _ = _example_parser(examples_root)
    parsed = parse(path)
    external_nodes = {key: (vertex.vertex_type.value, vertex.x_coord, vertex.y_coord,
                            vertex.demand, vertex.ready_time, vertex.due_time, vertex.service_time)
                      for key, vertex in parsed.vertices.items()}
    rate = parsed.parameters.recharging_rate
    external_arcs = {key: (arc.distance, arc.travel_time, arc.consumption * rate)
                     for key, arc in parsed.arcs.items()}
    errors = compare_geometry(instance, external_nodes, external_arcs)
    ours = instance.infrastructure.parameters
    for feature, actual, expected in (
        ("battery", parsed.parameters.battery_capacity, ours.battery),
        ("capacity", parsed.parameters.capacity, ours.capacity),
        ("consumption", parsed.parameters.consumption_rate, ours.consumption),
        ("charging rate", rate, 1.0 / ours.inverse_charge_rate),
        ("velocity", parsed.parameters.velocity, ours.speed),
    ):
        if abs(actual - expected) > 1e-9:
            errors.append(f"{feature} differs")
    # Upstream defaults to one EV per customer. The adapter changes only
    # instance data, not the ALNS search or its configuration.
    parsed.parameters.fleet_size = fleet_size
    if parsed.parameters.fleet_size != fleet_size:
        errors.append("K_ref override failed")
    return {"solver": "RoutingBlocks", "instance": instance.name,
            "instance_sha256": instance.sha256, "K_ref": fleet_size,
            "nodes": len(external_nodes), "arcs": len(external_arcs),
            "exact": not errors, "errors": errors}


def run_routingblocks(instance: Instance, path: Path, examples_root: Path,
                      fleet_size: int, seed: int, runtime_budget: float) -> dict:
    """Call upstream ALNS after the strict instance gate; return raw route order."""
    if runtime_budget <= 0:
        raise ValueError("Runtime budget must be positive")
    audit = verify_routingblocks_instance(instance, path, examples_root, fleet_size)
    if not audit["exact"]:
        raise ValueError(f"RoutingBlocks physics mismatch: {audit['errors']}")
    import routingblocks
    from routingblocks import adptw
    from evrptw.__main__ import compute_initial_penalties, format_solution, parse_config

    parse, create_cpp, _, ALNS = _example_modules(examples_root)
    parsed = parse(path)
    parsed.parameters.fleet_size = fleet_size
    cpp_instance = create_cpp(parsed)
    evaluation = adptw.Evaluation(parsed.parameters.battery_capacity_time,
                                  parsed.parameters.capacity)
    overload, overcharge, timeshift = compute_initial_penalties(parsed)
    evaluation.overload_penalty_factor = overload
    evaluation.resource_penalty_factor = overcharge
    evaluation.time_shift_penalty_factor = timeshift
    params = parse_config(examples_root / "evrptw" / "config.json")
    random.seed(seed)
    solver = ALNS(evaluation=evaluation, py_instance=parsed,
                  cpp_instance=cpp_instance, params=params, seed=seed)
    solution = solver.run(runtime_budget, sys.maxsize, sys.maxsize)
    return {"solver": "RoutingBlocks", "instance": instance.name, "seed": seed,
            "runtime_budget": runtime_budget, "runtime": solver.elapsed,
            "external": format_solution(solution), "config": asdict(params),
            "equivalence": audit, "package_version": getattr(routingblocks, "__version__", "unknown")}
