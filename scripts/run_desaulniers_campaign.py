"""Resumable, paired Desaulniers MP development grid; never runs the holdout."""

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
from evrp.storage import ROOT, identifier, load_json, save_json
from scripts.run_desaulniers_pilot import (VIOLATIONS, dataset_hash, family_of,
                                          settings)


CONFIG = ROOT / "configs/desaulniers_mp_development.yaml"
OUTPUT = ROOT / "results/desaulniers/development_campaign"
METHODS = {"MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"}


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [
        Path(__file__), ROOT / "scripts/run_desaulniers_pilot.py"]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                       for p in paths})


def selected_instances(config):
    selected = []
    for size in config["sizes"]:
        for family in config["families"]:
            paths = [p for p in discover_instances(size) if family_of(p.stem) == family]
            if len(paths) < 2:
                raise ValueError(f"No development/holdout partition for {size}/{family}")
            selected.append(dict(instance=paths[0].stem, size=size, family=family,
                                 reserved_untouched=paths[-1].stem,
                                 format1_sha256=sha256(paths[0].read_bytes()).hexdigest()))
    return selected


def protocol(config):
    if (config["charging_policy"] != "MP" or
            config["total_planning_time_limit"] != 5.0 or
            set(config["methods"]) != METHODS or len(config["methods"]) != len(METHODS)):
        raise ValueError("Development campaign requires MP, five methods and five seconds")
    if (set(config["sizes"]) != {25, 50, 100} or
            set(config["families"]) != {"C1", "C2", "R1", "R2", "RC1", "RC2"} or
            set(config["dynamicities"]) != {0.25, 0.5, 0.75}):
        raise ValueError("Development campaign grid differs from the fixed design")
    frozen = dict(dataset="Desaulniers et al. 2016", charging_policy="MP",
                  purpose="development_only", selected=selected_instances(config),
                  methods=config["methods"], dynamicities=config["dynamicities"],
                  scenario_seeds=config["scenario_seeds"],
                  ineligible_rule="Record and exclude target DoD above reference eligibility",
                  dataset_sha256=dataset_hash(), source_sha256=source_hash(),
                  config_sha256=sha256(CONFIG.read_bytes()).hexdigest(),
                  controller_sha256=sha256((ROOT / config["base_controller"]).read_bytes()).hexdigest())
    path = OUTPUT / "protocol.json"
    if path.exists():
        if load_json(path) != frozen:
            raise ValueError("Existing development protocol differs from source or dataset")
    else:
        save_json(path, frozen)
    return frozen


def options(config, name, dod, seed, method):
    return dict(settings(dict(config, dynamicity=dod, scenario_seed=seed), name, method),
                study="desaulniers_mp_development")


def worker(name, dod, seed, method, output):
    config = load_config(CONFIG)
    frozen = protocol(config)
    output = Path(output).resolve()
    if not output.is_relative_to((OUTPUT / "raw").resolve()) or output.exists():
        raise ValueError("Worker output must be a new development raw file")
    if (name not in {case["instance"] for case in frozen["selected"]} or
            dod not in frozen["dynamicities"] or seed not in frozen["scenario_seeds"] or
            method not in frozen["methods"]):
        raise ValueError("Worker case is absent from development protocol")
    try:
        started = perf_counter()
        run_options = options(config, name, dod, seed, method)
        instance, reference, scenario, _ = prepare(name, run_options)
        result = EventDrivenSimulator(instance, scenario, simulation_config(run_options)).run()
        audit = audit_result(result, instance, scenario)
        if (not all(audit.values()) or any(result.metrics[key] != 0 for key in VIOLATIONS)
                or result.metrics["max_optimization_latency"] > 5.0 + 1e-6
                or result.metadata["K_ref"] != reference.fleet_size):
            raise ValueError("Development worker failed physical, information, or budget audit")
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
    fingerprint = identifier(frozen)
    scenarios = [(case, dod, seed) for case in frozen["selected"]
                 for dod in frozen["dynamicities"] for seed in frozen["scenario_seeds"]]
    manifest_path = OUTPUT / "manifest.json"
    old = load_json(manifest_path) if manifest_path.exists() else None
    if old and old["protocol_identifier"] != fingerprint:
        raise ValueError("Existing development manifest belongs to another protocol")
    records = {(row["instance"], row["dynamicity"], row["seed"], row["method"]): row
               for row in old["records"]} if old else {}
    excluded = {(row["instance"], row["dynamicity"], row["seed"]): row
                for row in old["ineligible"]} if old else {}

    def checkpoint():
        completed = len(records) + len(excluded) * len(frozen["methods"])
        total = len(scenarios) * len(frozen["methods"])
        save_json(manifest_path, dict(status="development_complete" if completed == total
                                      else "development_partial", protocol_identifier=fingerprint,
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
            excluded[case_key] = dict(instance=name, size=case["size"],
                                      family=case["family"], dynamicity=dod,
                                      seed=seed, reason=str(error))
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
                    raise ValueError(f"Saved development raw run is missing or corrupted: {key}")
                continue
            if path.exists():
                raise ValueError(f"Unmanifested development raw file exists: {path}")
            subprocess.run([sys.executable, "-m", "scripts.run_desaulniers_campaign",
                            "--worker", name, str(dod), str(seed), method, str(path)],
                           cwd=ROOT, check=True, timeout=config["whole_worker_timeout_seconds"])
            raw = load_json(path)
            if (raw["metadata"]["scenario_identifier"] != scenario.identifier or
                    raw["metadata"]["algorithm"] != method or
                    raw["metadata"]["source_sha256"] != frozen["source_sha256"] or
                    not all(raw["metadata"]["independent_audit"].values())):
                raise ValueError("Development worker identity or audit mismatch")
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
            print(f"development {len(records)}/{len(scenarios) * len(frozen['methods'])} "
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
