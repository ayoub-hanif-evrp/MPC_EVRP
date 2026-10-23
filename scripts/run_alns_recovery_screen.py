"""Balanced 18-instance development screen of original versus recovery ALNS."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from time import perf_counter

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json
from scripts import run_desaulniers_campaign as development


OUTPUT = ROOT / "results/desaulniers/enhancement_development/alns_recovery_screen"
VARIANTS = ("MPC_ALNS", "MPC_ALNS_RECOVERY_V2")
MAX_WALL_SECONDS = 12 * 3600


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__),
             ROOT / "scripts/run_desaulniers_campaign.py",
             ROOT / "scripts/run_desaulniers_pilot.py"]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                       for p in paths})


def cases():
    historical = load_json(development.OUTPUT / "manifest.json")
    if historical["completed_runs"] != historical["planned_runs"]:
        raise ValueError("Original development campaign incomplete")
    selected = sorted({(r["instance"], r["dynamicity"], r["seed"])
                       for r in historical["records"]
                       if r["method"] == "MPC_ALNS" and r["dynamicity"] == 0.75})
    if (len(selected) != 18 or len({name for name, _, _ in selected}) != 18 or
            {int(name.rsplit("_", 1)[1]) for name, _, _ in selected} != {25, 50, 100}):
        raise ValueError("Balanced screen must contain 18 development instances across three sizes")
    return selected


def options(config, name, dod, seed, variant):
    return dict(development.options(config, name, dod, seed, variant),
                study="mpc_enhancement_alns_recovery_balanced_development_screen",
                dispatch_policy="original", route_decoder_version="original")


def protocol(config):
    prior = load_json(development.OUTPUT / "manifest.json")
    selected = cases()
    frozen = dict(purpose="balanced_alns_recovery_development_screen_not_final",
                  selection="All 18 original development base instances at DoD 0.75, seed 0",
                  cases=[list(c) for c in selected], variants=list(VARIANTS),
                  dispatch_policy="original", route_decoder_version="original",
                  five_second_limit=5.0, max_wall_seconds=MAX_WALL_SECONDS,
                  execution="isolated sequential subprocesses",
                  original_development_protocol=prior["protocol_identifier"],
                  source_sha256=source_hash(),
                  config_sha256=sha256(development.CONFIG.read_bytes()).hexdigest())
    path = OUTPUT / "protocol.json"
    if path.exists():
        if load_json(path) != frozen:
            raise ValueError("Existing balanced screen protocol differs")
    else:
        save_json(path, frozen)
    return frozen


def worker(name, dod, seed, variant, path):
    config = load_config(development.CONFIG)
    frozen = protocol(config)
    path = Path(path).resolve()
    if ((name, dod, seed) not in cases() or variant not in VARIANTS or
            not path.is_relative_to((OUTPUT / "raw").resolve()) or path.exists()):
        raise ValueError("Unknown balanced screen case or invalid worker path")
    run_opts = options(config, name, dod, seed, variant)
    instance, reference, scenario, _ = prepare(name, run_opts)
    started = perf_counter()
    result = EventDrivenSimulator(instance, scenario, simulation_config(run_opts)).run()
    audit = audit_result(result, instance, scenario)
    if (not all(audit.values()) or result.metadata["K_ref"] != reference.fleet_size or
            result.metrics["max_optimization_latency"] > 5.0 + 1e-6 or
            any(result.metrics[k] for k in ("battery_violations", "capacity_violations",
                                            "time_window_violations", "duplicate_service_violations",
                                            "hidden_information_violations"))):
        raise ValueError("Balanced screen failed independent audit or budget")
    result.metadata.update(isolated_worker=True, independent_audit=audit,
                           source_sha256=frozen["source_sha256"],
                           variant=variant, protocol_identifier=identifier(frozen))
    result.metrics["worker_wall_seconds"] = perf_counter() - started
    save_json(path, asdict(result))


def run():
    config = load_config(development.CONFIG)
    frozen = protocol(config)
    fingerprint = identifier(frozen)
    selected = cases()
    manifest_path = OUTPUT / "manifest.json"
    old = load_json(manifest_path) if manifest_path.exists() else None
    if old and old["protocol_identifier"] != fingerprint:
        raise ValueError("Existing balanced screen manifest differs")
    records = {(r["instance"], r["dynamicity"], r["seed"], r["variant"]): r
               for r in old["records"]} if old else {}
    total = len(selected) * len(VARIANTS)
    started = perf_counter()
    for name, dod, seed in selected:
        if perf_counter() - started >= MAX_WALL_SECONDS:
            print(f"Paused after {len(records)}/{total} runs at scenario boundary", flush=True)
            break
        for variant in VARIANTS:
            key = name, dod, seed, variant
            identity = identifier(dict(protocol=fingerprint, case=key))
            path = OUTPUT / "raw" / f"{name}_{dod}_{seed}_{variant}_{identity[:12]}.json.gz"
            if key in records:
                row = records[key]
                if ((ROOT / row["raw"]).resolve() != path.resolve() or not path.is_file() or
                        sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
                    raise ValueError(f"Saved balanced screen run missing or corrupt: {key}")
                continue
            if path.exists():
                raise ValueError(f"Unmanifested raw file: {path}")
            subprocess.run([sys.executable, "-m", "scripts.run_alns_recovery_screen",
                            "--worker", name, str(dod), str(seed), variant, str(path)],
                           cwd=ROOT, check=True, timeout=config["whole_worker_timeout_seconds"])
            raw = load_json(path)
            instance, reference, scenario, _ = prepare(name, options(config, name, dod, seed, variant))
            if (raw["metadata"]["scenario_identifier"] != scenario.identifier or
                    raw["metadata"]["K_ref"] != reference.fleet_size or
                    raw["metadata"]["source_sha256"] != frozen["source_sha256"] or
                    raw["metadata"]["variant"] != variant):
                raise ValueError(f"Balanced screen worker identity mismatch: {key}")
            records[key] = dict(instance=name, dynamicity=dod, seed=seed, variant=variant,
                                size=len(instance.customers),
                                customers_served=raw["metrics"]["customers_served"],
                                complete_service=raw["metrics"]["complete_service"],
                                max_optimization_latency=raw["metrics"]["max_optimization_latency"],
                                worker_wall_seconds=raw["metrics"]["worker_wall_seconds"],
                                scenario_id=scenario.identifier, k_ref=reference.fleet_size,
                                independent_audit=raw["metadata"]["independent_audit"],
                                raw=path.relative_to(ROOT).as_posix(),
                                raw_sha256=sha256(path.read_bytes()).hexdigest())
            save_json(manifest_path, dict(status="complete" if len(records) == total else "partial",
                                          protocol_identifier=fingerprint, planned_runs=total,
                                          completed_runs=len(records), records=list(records.values())))
            print(f"balanced screen {len(records)}/{total}: {name} DoD={dod} "
                  f"{variant} served={records[key]['customers_served']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=5)
    args = parser.parse_args()
    if args.worker:
        name, dod, seed, variant, path = args.worker
        worker(name, float(dod), int(seed), variant, path)
    else:
        run()
