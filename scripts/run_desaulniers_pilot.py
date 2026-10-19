"""Isolated, resumable development pilots for the Desaulniers MP migration."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter
import traceback

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.instance import discover_instances
from evrp.simulator import EventDrivenSimulator
from evrp.storage import (BENCHMARK, BENCHMARK_ARCS, DATASET, PUBLISHED_SOLUTIONS,
                          ROOT, identifier, load_json, save_json)


CONFIG = ROOT / "configs" / "desaulniers_mp_pilot.yaml"
OUTPUT = ROOT / "results" / "desaulniers" / "development_pilot_final_source"
VIOLATIONS = ("hidden_information_violations", "time_window_violations",
              "battery_violations", "capacity_violations")


def family_of(name):
    match = re.fullmatch(r"(rc|r|c)([12])\d+_21_(25|50|100)", name)
    if not match:
        raise ValueError(f"Unknown Desaulniers family or size: {name}")
    return match.group(1).upper() + match.group(2)


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__)]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                       for p in paths})


def dataset_hash():
    return identifier({p.relative_to(DATASET).as_posix(): sha256(p.read_bytes()).hexdigest()
                       for p in sorted(DATASET.rglob("*")) if p.is_file() and p.name != ".DS_Store"})


def selected_cases(config):
    selected = []
    for size in config["pilot_sizes"]:
        paths = [p for p in discover_instances(size) if family_of(p.stem) == config["pilot_family"]]
        if len(paths) < 2:
            raise ValueError(f"No independent development/holdout partition for {size}")
        held_out = paths[-1].stem
        usable = [p for p in paths[:-1] if any((PUBLISHED_SOLUTIONS / variant /
                                                f"solution{p.stem}").is_file()
                                               for variant in ("MF", "SF"))]
        if not usable:
            raise ValueError(f"No full-route offline reference for development size {size}")
        chosen = usable[0]
        selected.append(dict(instance=chosen.stem, size=size,
                             family=family_of(chosen.stem), reserved_untouched=held_out,
                             format1_sha256=sha256(chosen.read_bytes()).hexdigest(),
                             format2_sha256=sha256((BENCHMARK_ARCS /
                                f"{chosen.stem.removesuffix('_100')}.inst").read_bytes()).hexdigest()))
    return selected


def settings(config, name, method):
    base = load_config(ROOT / config["base_controller"])
    return dict(base, algorithm=method, dynamicity=config["dynamicity"],
                scenario_seed=config["scenario_seed"], diagnostics=False,
                trace_level="summary", total_planning_time_limit=5.0,
                engineering_watchdog_seconds=config["engineering_watchdog_seconds"])


def protocol(config):
    if config["charging_policy"] != "MP" or config["total_planning_time_limit"] != 5.0:
        raise ValueError("Pilot requires MP charging and a five-second common decision budget")
    if set(config["methods"]) != {"MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"}:
        raise ValueError("Pilot must compare all five fixed MPC methods")
    data = dict(dataset="Desaulniers et al. 2016", charging_policy="MP",
                status="development_pilot", selected=selected_cases(config),
                methods=config["methods"], dynamicity=config["dynamicity"],
                scenario_seed=config["scenario_seed"],
                dataset_sha256=dataset_hash(), source_sha256=source_hash(),
                config_sha256=sha256(CONFIG.read_bytes()).hexdigest(),
                controller_sha256=sha256((ROOT / config["base_controller"]).read_bytes()).hexdigest())
    path = OUTPUT / "protocol.json"
    if path.exists():
        if load_json(path) != data:
            raise ValueError("Existing pilot protocol differs from source, dataset, or configuration")
    else:
        save_json(path, data)
    return data


def worker(name, method, output):
    config = load_config(CONFIG)
    frozen = protocol(config)
    output = Path(output).resolve()
    if not output.is_relative_to((OUTPUT / "raw").resolve()) or output.exists():
        raise ValueError("Worker output must be a new file under development_pilot_final_source/raw")
    if name not in {case["instance"] for case in frozen["selected"]} or method not in frozen["methods"]:
        raise ValueError("Worker case is absent from pilot protocol")
    try:
        started = perf_counter()
        options = settings(config, name, method)
        instance, reference, scenario, _ = prepare(name, options)
        result = EventDrivenSimulator(instance, scenario, simulation_config(options)).run()
        audit = audit_result(result, instance, scenario)
        if (not all(audit.values()) or any(result.metrics[key] != 0 for key in VIOLATIONS)
                or result.metrics["max_optimization_latency"] > 5.0 + 1e-6
                or result.metadata["K_ref"] != reference.fleet_size):
            raise ValueError("Pilot worker failed physical, information, or budget audit")
        result.metadata.update(isolated_worker=True, independent_audit=audit,
                               source_sha256=frozen["source_sha256"],
                               dataset_sha256=frozen["dataset_sha256"], charging_policy="MP",
                               reference_provenance=reference.provenance)
        result.metrics["worker_wall_seconds"] = perf_counter() - started
        save_json(output, asdict(result))
    except Exception as error:
        save_json(OUTPUT / "failures" / f"{output.name}.failure.json",
                  dict(instance=name, method=method, error_type=type(error).__name__,
                       message=str(error), traceback=traceback.format_exc()))
        raise


def run(sizes=None, methods=None):
    config = load_config(CONFIG)
    frozen = protocol(config)
    selected = [case for case in frozen["selected"] if sizes is None or case["size"] in sizes]
    chosen_methods = methods or frozen["methods"]
    if not set(chosen_methods) <= set(frozen["methods"]):
        raise ValueError("Unknown pilot method")
    manifest_path = OUTPUT / "manifest.json"
    old = load_json(manifest_path) if manifest_path.exists() else None
    fingerprint = identifier(frozen)
    if old and old["protocol_identifier"] != fingerprint:
        raise ValueError("Existing pilot manifest belongs to another protocol")
    records = {(row["scenario_id"], row["method"]): row for row in old["records"]} if old else {}
    for case in selected:
        name = case["instance"]
        instance, reference, scenario, _ = prepare(name, settings(config, name, "MPC_COMPLETION"))
        for method in chosen_methods:
            identity = identifier(dict(protocol=fingerprint, scenario=scenario.identifier, method=method))
            path = OUTPUT / "raw" / f"{name}_{method}_{identity[:12]}.json.gz"
            key = scenario.identifier, method
            if key in records:
                row = records[key]
                if ((ROOT / row["raw"]).resolve() != path.resolve() or not path.is_file() or
                        sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
                    raise ValueError(f"Saved raw run is missing or corrupted: {key}")
                print(f"reused {name} {method}", flush=True)
                continue
            if path.exists():
                raise ValueError(f"Unmanifested pilot raw file exists: {path}")
            subprocess.run([sys.executable, "-m", "scripts.run_desaulniers_pilot",
                            "--worker", name, method, str(path)], cwd=ROOT, check=True,
                           timeout=config["whole_worker_timeout_seconds"])
            raw = load_json(path)
            if (raw["metadata"]["scenario_identifier"] != scenario.identifier or
                    raw["metadata"]["algorithm"] != method or
                    raw["metadata"]["source_sha256"] != frozen["source_sha256"] or
                    not all(raw["metadata"]["independent_audit"].values())):
                raise ValueError("Pilot worker identity or audit mismatch")
            metrics = raw["metrics"]
            records[key] = dict(instance=name, family=case["family"], size=case["size"],
                                dynamicity=config["dynamicity"], scenario_seed=config["scenario_seed"],
                                scenario_id=scenario.identifier, instance_sha256=instance.sha256,
                                reference_identifier=reference.identifier, k_ref=reference.fleet_size,
                                method=method, customers_served=metrics["customers_served"],
                                complete_service=metrics["complete_service"],
                                vehicles_activated=metrics["vehicles_activated"],
                                total_distance=metrics["total_distance"],
                                charging_visits=metrics["total_charging_visits"],
                                mean_optimization_latency=metrics["mean_optimization_latency"],
                                p95_optimization_latency=metrics["p95_optimization_latency"],
                                max_optimization_latency=metrics["max_optimization_latency"],
                                worker_wall_seconds=metrics["worker_wall_seconds"],
                                raw=path.relative_to(ROOT).as_posix(),
                                raw_sha256=sha256(path.read_bytes()).hexdigest())
            save_json(manifest_path, dict(status="pilot_complete" if len(records) ==
                                      len(frozen["selected"]) * len(frozen["methods"]) else "pilot_partial",
                                      expected_records=len(frozen["selected"]) * len(frozen["methods"]),
                                      protocol_identifier=fingerprint,
                                      records=sorted(records.values(), key=lambda r: (r["size"], r["method"]))))
            print(f"pilot {len(records)}/15 {name} {method}: "
                  f"{metrics['customers_served']}/{len(instance.customers)} served", flush=True)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=3, metavar=("INSTANCE", "METHOD", "RAW"))
    parser.add_argument("--sizes", type=int, nargs="*", choices=[25, 50, 100])
    parser.add_argument("--methods", nargs="*")
    args = parser.parse_args()
    if args.worker:
        worker(*args.worker)
    else:
        run(args.sizes, args.methods)


if __name__ == "__main__":
    main()
