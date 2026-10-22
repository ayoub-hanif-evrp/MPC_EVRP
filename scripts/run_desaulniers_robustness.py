"""Versioned, isolated, resumable multi-seed robustness campaign."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import traceback

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.instance import load_instance
from evrp.reference import ReferenceConfig, published_full_reference
from evrp.scenario import generate
from evrp.simulator import EventDrivenSimulator
from evrp.storage import BENCHMARK, BENCHMARK_ARCS, ROOT, identifier, load_json, save_json
from scripts.run_desaulniers_pilot import VIOLATIONS, dataset_hash, family_of, settings


CONFIG = ROOT / "configs/desaulniers_mp_robustness_v2.yaml"
OUTPUT = ROOT / "results/desaulniers/robustness_v2"
PILOT = ROOT / "results/desaulniers/robustness_pilot_v2"
METHODS = ("MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS")


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [
        ROOT / "scripts/run_desaulniers_pilot.py", Path(__file__)]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                       for p in paths})


def selected(config, pilot=False):
    names = [config["pilot_instance"]] if pilot else config["instances"]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate robustness instance")
    if not pilot and (len(names) != 6 or
            {family_of(n) for n in names} != {"C1", "C2", "R1", "R2", "RC1", "RC2"} or
            sorted(int(n.rsplit("_", 1)[1]) for n in names) != [25, 25, 50, 50, 100, 100]):
        raise ValueError("Robustness instance selection is not balanced")
    frozen = []
    for name in names:
        path = BENCHMARK / f"{name}.txt"
        instance = load_instance(path)
        arc = BENCHMARK_ARCS / f"{name.removesuffix('_100')}.inst"
        if published_full_reference(instance, ReferenceConfig()) is None:
            raise ValueError(f"Selected instance lacks a validated published MP reference: {name}")
        frozen.append(dict(instance=name, size=len(instance.customers), family=family_of(name),
                           format1_sha256=sha256(path.read_bytes()).hexdigest(),
                           format2_sha256=sha256(arc.read_bytes()).hexdigest()))
    if not pilot:
        old = load_json(ROOT / "results/desaulniers/development_campaign/protocol.json")
        final = load_json(ROOT / "results/desaulniers/final_holdout_audit_erratum/protocol.json")
        prior = {r["instance"] for r in old["selected"]} | {r["instance"] for r in final["selected"]}
        if set(names) & prior:
            raise ValueError("Robustness selection overlaps development or final instances")
    return frozen


def protocol(config, pilot=False):
    if (config["charging_policy"] != "MP" or
            config["total_planning_time_limit"] != 5.0 or
            tuple(config["methods"]) != METHODS or
            config["dynamicities"] != [0.25, 0.5, 0.75] or
            config["scenario_seeds"] != [1, 2, 3, 4, 5]):
        raise ValueError("Robustness protocol differs from the fixed five-method design")
    cases = selected(config, pilot)
    dods = [config["pilot_dynamicity"]] if pilot else config["dynamicities"]
    seeds = [config["pilot_seed"]] if pilot else config["scenario_seeds"]
    eligibility = []
    for case in cases:
        instance = load_instance(BENCHMARK / f"{case['instance']}.txt")
        reference = published_full_reference(instance, ReferenceConfig())
        for dod in dods:
            try:
                generate(instance, reference, seeds[0], dod)
                eligibility.append(dict(instance=instance.name, dynamicity=dod, eligible=True))
            except ValueError as error:
                if not str(error).startswith("Target DoD is ineligible:"):
                    raise
                eligibility.append(dict(instance=instance.name, dynamicity=dod,
                                        eligible=False, reason=str(error)))
    frozen = dict(purpose="engineering_pilot" if pilot else "multi_seed_robustness_v2",
                  dataset="Desaulniers et al. 2016", charging_policy="MP",
                  selected=cases, eligibility=eligibility, methods=list(METHODS),
                  dynamicities=dods, scenario_seeds=seeds, total_planning_time_limit=5.0,
                  execution="sequential isolated worker processes",
                  dataset_sha256=dataset_hash(), source_sha256=source_hash(),
                  config_sha256=sha256(CONFIG.read_bytes()).hexdigest(),
                  controller_sha256=sha256((ROOT / config["base_controller"]).read_bytes()).hexdigest())
    path = (PILOT if pilot else OUTPUT) / "protocol.json"
    if path.exists():
        if load_json(path) != frozen:
            raise ValueError("Existing robustness protocol differs from source, data, or config")
    else:
        save_json(path, frozen)
    return frozen


def options(config, dod, seed, method):
    return dict(settings(dict(config, dynamicity=dod, scenario_seed=seed), "", method),
                study="desaulniers_mp_robustness_v2")


def worker(name, dod, seed, method, path, pilot=False):
    config = load_config(CONFIG)
    frozen = protocol(config, pilot)
    output = PILOT if pilot else OUTPUT
    path = Path(path).resolve()
    if (not path.is_relative_to((output / "raw").resolve()) or path.exists() or
            name not in {r["instance"] for r in frozen["selected"]} or
            dod not in frozen["dynamicities"] or seed not in frozen["scenario_seeds"] or
            method not in METHODS):
        raise ValueError("Worker case/path does not belong to frozen robustness protocol")
    try:
        started = perf_counter()
        run_options = options(config, dod, seed, method)
        instance, reference, scenario, _ = prepare(name, run_options)
        result = EventDrivenSimulator(instance, scenario, simulation_config(run_options)).run()
        audit = audit_result(result, instance, scenario)
        if (not all(audit.values()) or any(result.metrics[key] for key in VIOLATIONS) or
                result.metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                result.metadata["K_ref"] != reference.fleet_size):
            raise ValueError("Robustness worker failed physical, information, or budget audit")
        result.metadata.update(isolated_worker=True, independent_audit=audit,
                               source_sha256=frozen["source_sha256"],
                               dataset_sha256=frozen["dataset_sha256"], charging_policy="MP",
                               reference_provenance=reference.provenance)
        result.metrics["worker_wall_seconds"] = perf_counter() - started
        save_json(path, asdict(result))
    except Exception as error:
        save_json(output / "failures" / f"{path.name}.failure.json",
                  dict(instance=name, dynamicity=dod, seed=seed, method=method,
                       error_type=type(error).__name__, message=str(error),
                       traceback=traceback.format_exc()))
        raise


def run(pilot=False, freeze=False, limit=None):
    config = load_config(CONFIG)
    frozen = protocol(config, pilot)
    if freeze:
        print(f"Frozen {identifier(frozen)}", flush=True)
        return
    output = PILOT if pilot else OUTPUT
    scenarios = [(c, dod, seed) for c in frozen["selected"]
                 for dod in frozen["dynamicities"] for seed in frozen["scenario_seeds"]]
    old_path = output / "manifest.json"
    old = load_json(old_path) if old_path.exists() else None
    fingerprint = identifier(frozen)
    if old and old["protocol_identifier"] != fingerprint:
        raise ValueError("Existing robustness manifest belongs to another protocol")
    records = {(r["instance"], r["dynamicity"], r["seed"], r["method"]): r
               for r in old["records"]} if old else {}
    excluded = {(r["instance"], r["dynamicity"], r["seed"]): r
                for r in old["ineligible"]} if old else {}
    eligibility = {(r["instance"], r["dynamicity"]): r for r in frozen["eligibility"]}

    def checkpoint():
        total = len(scenarios) * len(METHODS)
        completed = len(records) + len(excluded) * len(METHODS)
        save_json(old_path, dict(status="complete" if completed == total else "partial",
                                 protocol_identifier=fingerprint, planned_runs=total,
                                 completed_runs=len(records), ineligible_scenarios=len(excluded),
                                 records=sorted(records.values(), key=lambda r: (
                                     r["instance"], r["dynamicity"], r["seed"], r["method"])),
                                 ineligible=sorted(excluded.values(), key=lambda r: (
                                     r["instance"], r["dynamicity"], r["seed"]))))

    for case, dod, seed in scenarios[:limit]:
        name = case["instance"]
        if not eligibility[name, dod]["eligible"]:
            excluded[name, dod, seed] = dict(instance=name, dynamicity=dod, seed=seed,
                                              reason=eligibility[name, dod]["reason"])
            checkpoint()
            continue
        instance, reference, scenario, _ = prepare(name, options(config, dod, seed, METHODS[0]))
        for method in METHODS:
            key = name, dod, seed, method
            identity = identifier(dict(protocol=fingerprint, scenario=scenario.identifier,
                                       method=method))
            path = output / "raw" / f"{name}_{dod}_{seed}_{method}_{identity[:12]}.json.gz"
            if key in records:
                row = records[key]
                if ((ROOT / row["raw"]).resolve() != path.resolve() or not path.is_file() or
                        sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
                    raise ValueError(f"Saved robustness raw run is missing or corrupted: {key}")
                continue
            if path.exists():
                raise ValueError(f"Unmanifested robustness raw file exists: {path}")
            subprocess.run([sys.executable, "-m", "scripts.run_desaulniers_robustness",
                            "--worker", name, str(dod), str(seed), method, str(path),
                            *( ["--pilot"] if pilot else [] )], cwd=ROOT, check=True,
                           timeout=config["whole_worker_timeout_seconds"])
            raw = load_json(path)
            if (raw["metadata"]["scenario_identifier"] != scenario.identifier or
                    raw["metadata"]["algorithm"] != method or
                    raw["metadata"]["source_sha256"] != frozen["source_sha256"] or
                    not all(raw["metadata"]["independent_audit"].values())):
                raise ValueError("Robustness worker identity or audit mismatch")
            records[key] = dict(instance=name, size=case["size"], family=case["family"],
                                dynamicity=dod, seed=seed, scenario_id=scenario.identifier,
                                instance_sha256=instance.sha256,
                                reference_identifier=reference.identifier, k_ref=reference.fleet_size,
                                method=method, customers_served=raw["metrics"]["customers_served"],
                                complete_service=raw["metrics"]["complete_service"],
                                vehicles_activated=raw["metrics"]["vehicles_activated"],
                                total_distance=raw["metrics"]["total_distance"],
                                max_optimization_latency=raw["metrics"]["max_optimization_latency"],
                                raw=path.relative_to(ROOT).as_posix(),
                                raw_sha256=sha256(path.read_bytes()).hexdigest())
            checkpoint()
            print(f"{'pilot' if pilot else 'robustness'} {len(records)}/{len(scenarios)*len(METHODS)} "
                  f"{name} DoD={dod} seed={seed} {method} "
                  f"served={raw['metrics']['customers_served']}", flush=True)
    checkpoint()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--scenario-limit", type=int)
    parser.add_argument("--worker", nargs=5,
                        metavar=("INSTANCE", "DOD", "SEED", "METHOD", "OUTPUT"))
    args = parser.parse_args()
    if args.worker:
        name, dod, seed, method, path = args.worker
        worker(name, float(dod), int(seed), method, path, args.pilot)
    else:
        run(args.pilot, args.freeze, args.scenario_limit)
