"""Frozen, resumable Desaulniers MP holdout on reserved benchmark instances."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import traceback

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.instance import discover_instances
from evrp.simulator import EventDrivenSimulator
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json
from scripts.run_desaulniers_campaign import (
    CONFIG as DEVELOPMENT_CONFIG, METHODS, OUTPUT as DEVELOPMENT_OUTPUT,
    selected_instances as development_instances,
)
from scripts.run_desaulniers_pilot import VIOLATIONS, dataset_hash, family_of, settings


CONFIG = ROOT / "configs/desaulniers_mp_final.yaml"
OUTPUT = ROOT / "results/desaulniers/final_holdout"


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [
        ROOT / "scripts/run_desaulniers_pilot.py",
        ROOT / "scripts/run_desaulniers_campaign.py", Path(__file__),
    ]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                       for p in paths})


def selected_instances(config):
    development = development_instances(load_config(DEVELOPMENT_CONFIG))
    selected = []
    for row in development:
        name = row["reserved_untouched"]
        paths = [p for p in discover_instances(row["size"])
                 if family_of(p.stem) == row["family"]]
        if name != paths[-1].stem or name == row["instance"]:
            raise ValueError("Holdout partition differs from frozen development selection")
        path = BENCHMARK / f"{name}.txt"
        selected.append(dict(instance=name, size=row["size"], family=row["family"],
                             development_instance=row["instance"],
                             format1_sha256=sha256(path.read_bytes()).hexdigest()))
    if (len(selected) != 18 or
            {(r["size"], r["family"]) for r in selected} !=
            {(s, f) for s in config["sizes"] for f in config["families"]}):
        raise ValueError("Holdout selection does not cover the frozen grid")
    return selected


def protocol(config):
    if (config["charging_policy"] != "MP" or
            config["total_planning_time_limit"] != 5.0 or
            set(config["methods"]) != METHODS or len(config["methods"]) != len(METHODS) or
            set(config["sizes"]) != {25, 50, 100} or
            set(config["families"]) != {"C1", "C2", "R1", "R2", "RC1", "RC2"} or
            set(config["dynamicities"]) != {0.25, 0.5, 0.75} or
            config["scenario_seeds"] != [0]):
        raise ValueError("Final protocol differs from the fixed five-method MP design")
    development = load_json(DEVELOPMENT_OUTPUT / "protocol.json")
    frozen = dict(dataset="Desaulniers et al. 2016", charging_policy="MP",
                  purpose="final_holdout", selected=selected_instances(config),
                  methods=config["methods"], dynamicities=config["dynamicities"],
                  scenario_seeds=config["scenario_seeds"],
                  ineligible_rule="Record and exclude target DoD above reference eligibility",
                  development_protocol_identifier=identifier(development),
                  dataset_sha256=dataset_hash(), source_sha256=source_hash(),
                  config_sha256=sha256(CONFIG.read_bytes()).hexdigest(),
                  controller_sha256=sha256((ROOT / config["base_controller"]).read_bytes()).hexdigest())
    path = OUTPUT / "protocol.json"
    if path.exists():
        if load_json(path) != frozen:
            raise ValueError("Existing final protocol differs from source or dataset")
    else:
        save_json(path, frozen)
    return frozen


def require_completed_development():
    manifest = load_json(DEVELOPMENT_OUTPUT / "manifest.json")
    if manifest["status"] != "development_complete":
        raise ValueError("Development must complete before the final holdout opens")


def options(config, name, dod, seed, method):
    return dict(settings(dict(config, dynamicity=dod, scenario_seed=seed), name, method),
                study="desaulniers_mp_final")


def worker(name, dod, seed, method, output):
    require_completed_development()
    config = load_config(CONFIG)
    frozen = protocol(config)
    output = Path(output).resolve()
    if not output.is_relative_to((OUTPUT / "raw").resolve()) or output.exists():
        raise ValueError("Worker output must be a new final raw file")
    if (name not in {case["instance"] for case in frozen["selected"]} or
            dod not in frozen["dynamicities"] or seed not in frozen["scenario_seeds"] or
            method not in frozen["methods"]):
        raise ValueError("Worker case is absent from final protocol")
    try:
        started = perf_counter()
        run_options = options(config, name, dod, seed, method)
        instance, reference, scenario, _ = prepare(name, run_options)
        result = EventDrivenSimulator(instance, scenario, simulation_config(run_options)).run()
        audit = audit_result(result, instance, scenario)
        if (not all(audit.values()) or any(result.metrics[key] != 0 for key in VIOLATIONS)
                or result.metrics["max_optimization_latency"] > 5.0 + 1e-6
                or result.metadata["K_ref"] != reference.fleet_size):
            raise ValueError("Final worker failed physical, information, or budget audit")
        result.metadata.update(isolated_worker=True, independent_audit=audit,
                               source_sha256=frozen["source_sha256"],
                               dataset_sha256=frozen["dataset_sha256"], charging_policy="MP",
                               reference_provenance=reference.provenance)
        result.metrics["worker_wall_seconds"] = perf_counter() - started
        save_json(output, asdict(result))
    except Exception as error:
        save_json(OUTPUT / "failures" / f"{output.name}.failure.json",
                  dict(instance=name, dynamicity=dod, seed=seed, method=method,
                       error_type=type(error).__name__, message=str(error),
                       traceback=traceback.format_exc()))
        raise


def run(scenario_limit=None):
    config = load_config(CONFIG)
    frozen = protocol(config)
    if scenario_limit != 0:
        require_completed_development()
    fingerprint = identifier(frozen)
    scenarios = [(case, dod, seed) for case in frozen["selected"]
                 for dod in frozen["dynamicities"] for seed in frozen["scenario_seeds"]]
    manifest_path = OUTPUT / "manifest.json"
    old = load_json(manifest_path) if manifest_path.exists() else None
    if old and old["protocol_identifier"] != fingerprint:
        raise ValueError("Existing final manifest belongs to another protocol")
    records = {(r["instance"], r["dynamicity"], r["seed"], r["method"]): r
               for r in old["records"]} if old else {}
    excluded = {(r["instance"], r["dynamicity"], r["seed"]): r
                for r in old["ineligible"]} if old else {}

    def checkpoint():
        completed = len(records) + len(excluded) * len(frozen["methods"])
        total = len(scenarios) * len(frozen["methods"])
        save_json(manifest_path, dict(status="final_complete" if completed == total
                                      else "final_partial", protocol_identifier=fingerprint,
                                      planned_runs=total, completed_runs=len(records),
                                      ineligible_scenarios=len(excluded),
                                      records=sorted(records.values(), key=lambda row: (
                                          row["size"], row["family"], row["instance"],
                                          row["dynamicity"], row["seed"], row["method"])),
                                      ineligible=sorted(excluded.values(), key=lambda row: (
                                          row["instance"], row["dynamicity"], row["seed"]))))

    for case, dod, seed in scenarios[:scenario_limit]:
        name = case["instance"]
        case_key = name, dod, seed
        if case_key in excluded:
            continue
        try:
            instance, reference, scenario, _ = prepare(
                name, options(config, name, dod, seed, "MPC_COMPLETION"))
        except ValueError as error:
            if not str(error).startswith("Target DoD is ineligible:"):
                raise
            excluded[case_key] = dict(instance=name, size=case["size"], family=case["family"],
                                      dynamicity=dod, seed=seed, reason=str(error))
            checkpoint()
            continue
        for method in frozen["methods"]:
            key = name, dod, seed, method
            identity = identifier(dict(protocol=fingerprint, scenario=scenario.identifier,
                                       method=method))
            path = OUTPUT / "raw" / f"{name}_{dod}_{seed}_{method}_{identity[:12]}.json.gz"
            if key in records:
                row = records[key]
                if ((ROOT / row["raw"]).resolve() != path.resolve() or not path.is_file() or
                        sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
                    raise ValueError(f"Saved final raw run is missing or corrupted: {key}")
                continue
            if path.exists():
                raise ValueError(f"Unmanifested final raw file exists: {path}")
            subprocess.run([sys.executable, "-m", "scripts.run_desaulniers_final",
                            "--worker", name, str(dod), str(seed), method, str(path)],
                           cwd=ROOT, check=True, timeout=config["whole_worker_timeout_seconds"])
            raw = load_json(path)
            if (raw["metadata"]["scenario_identifier"] != scenario.identifier or
                    raw["metadata"]["algorithm"] != method or
                    raw["metadata"]["source_sha256"] != frozen["source_sha256"] or
                    not all(raw["metadata"]["independent_audit"].values())):
                raise ValueError("Final worker identity or audit mismatch")
            records[key] = dict(instance=name, size=case["size"], family=case["family"],
                                dynamicity=dod, seed=seed, scenario_id=scenario.identifier,
                                instance_sha256=instance.sha256,
                                reference_identifier=reference.identifier,
                                k_ref=reference.fleet_size, method=method,
                                customers_served=raw["metrics"]["customers_served"],
                                complete_service=raw["metrics"]["complete_service"],
                                vehicles_activated=raw["metrics"]["vehicles_activated"],
                                total_distance=raw["metrics"]["total_distance"],
                                max_optimization_latency=raw["metrics"]["max_optimization_latency"],
                                raw=path.relative_to(ROOT).as_posix(),
                                raw_sha256=sha256(path.read_bytes()).hexdigest())
            checkpoint()
            print(f"final {len(records)}/{len(scenarios) * len(frozen['methods'])} "
                  f"{name} DoD={dod} seed={seed} {method} "
                  f"served={raw['metrics']['customers_served']}", flush=True)
    checkpoint()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-limit", type=int)
    parser.add_argument("--worker", nargs=5, metavar=("INSTANCE", "DOD", "SEED", "METHOD", "OUTPUT"))
    args = parser.parse_args()
    if args.worker:
        name, dod, seed, method, output = args.worker
        worker(name, float(dod), int(seed), method, output)
    else:
        run(args.scenario_limit)
