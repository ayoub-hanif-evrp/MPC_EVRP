"""Isolated, audited dispatch-policy mechanism pilot on seen development cases."""

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


OUTPUT = ROOT / "results/desaulniers/enhancement_development/dispatch_pilot"
METHODS = ("MPC_COMPLETION", "MPC_ALNS")
VARIANTS = ("original", "depot_window_wait_v1")
CASES = (("rc101_21_25", 0.75, 0), ("r101_21_50", 0.5, 0),
         ("r101_21_100", 0.75, 0))


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__),
             ROOT / "scripts/run_desaulniers_campaign.py",
             ROOT / "scripts/run_desaulniers_pilot.py"]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                       for p in paths})


def run_options(config, name, dod, seed, method, variant):
    opts = development.options(config, name, dod, seed, method)
    return dict(opts, study="mpc_enhancement_dispatch_development_pilot",
                dispatch_policy=variant)


def protocol(config):
    historical = load_json(development.OUTPUT / "manifest.json")
    if historical["completed_runs"] != historical["planned_runs"]:
        raise ValueError("Frozen development campaign is incomplete")
    indexed = {(r["instance"], r["dynamicity"], r["seed"], r["method"]): r
               for r in historical["records"]}
    for name, dod, seed in CASES:
        for method in METHODS:
            if (name, dod, seed, method) not in indexed:
                raise ValueError("Pilot case absent from frozen development campaign")
    frozen = dict(purpose="dispatch_mechanism_development_pilot_not_final",
                  selection="Previously identified ALNS-loss cases, one each at sizes 25/50/100",
                  cases=[list(case) for case in CASES], methods=list(METHODS),
                  variants=list(VARIANTS),
                  five_second_limit=5.0, execution="isolated sequential subprocesses",
                  historical_development_protocol=historical["protocol_identifier"],
                  source_sha256=source_hash(),
                  config_sha256=sha256(development.CONFIG.read_bytes()).hexdigest())
    path = OUTPUT / "protocol.json"
    if path.exists():
        if load_json(path) != frozen:
            raise ValueError("Frozen dispatch pilot protocol differs")
    else:
        save_json(path, frozen)
    return frozen


def worker(name, dod, seed, method, variant, path):
    config = load_config(development.CONFIG)
    frozen = protocol(config)
    path = Path(path).resolve()
    if (name, dod, seed) not in CASES or method not in METHODS or variant not in VARIANTS:
        raise ValueError("Unknown dispatch pilot case")
    if not path.is_relative_to((OUTPUT / "raw").resolve()) or path.exists():
        raise ValueError("Worker output must be a new raw pilot file")
    opts = run_options(config, name, dod, seed, method, variant)
    instance, reference, scenario, _ = prepare(name, opts)
    started = perf_counter()
    result = EventDrivenSimulator(instance, scenario, simulation_config(opts)).run()
    audit = audit_result(result, instance, scenario)
    if (not all(audit.values()) or result.metadata["K_ref"] != reference.fleet_size or
            result.metrics["max_optimization_latency"] > 5.0 + 1e-6 or
            any(result.metrics[k] for k in ("battery_violations", "capacity_violations",
                                            "time_window_violations", "duplicate_service_violations",
                                            "hidden_information_violations"))):
        raise ValueError("Dispatch pilot failed independent audit or decision budget")
    result.metadata.update(isolated_worker=True, independent_audit=audit,
                           source_sha256=frozen["source_sha256"],
                           dispatch_variant=variant,
                           pilot_protocol_identifier=identifier(frozen))
    result.metrics["worker_wall_seconds"] = perf_counter() - started
    save_json(path, asdict(result))


def run():
    config = load_config(development.CONFIG)
    frozen = protocol(config)
    fingerprint = identifier(frozen)
    manifest_path = OUTPUT / "manifest.json"
    old = load_json(manifest_path) if manifest_path.exists() else None
    if old and old["protocol_identifier"] != fingerprint:
        raise ValueError("Existing pilot manifest belongs to another protocol")
    records = {(r["instance"], r["dynamicity"], r["seed"], r["method"], r["variant"]): r
               for r in old["records"]} if old else {}
    total = len(CASES) * len(METHODS) * len(VARIANTS)
    for name, dod, seed in CASES:
        for method in METHODS:
            for variant in VARIANTS:
                key = name, dod, seed, method, variant
                identity = identifier(dict(protocol=fingerprint, case=key))
                path = OUTPUT / "raw" / f"{name}_{dod}_{seed}_{method}_{variant}_{identity[:12]}.json.gz"
                if key in records:
                    row = records[key]
                    if ((ROOT / row["raw"]).resolve() != path.resolve() or not path.is_file() or
                            sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
                        raise ValueError(f"Saved pilot run missing or corrupted: {key}")
                    continue
                if path.exists():
                    raise ValueError(f"Unmanifested raw pilot file: {path}")
                subprocess.run([sys.executable, "-m", "scripts.run_enhancement_development",
                                "--worker", name, str(dod), str(seed), method, variant, str(path)],
                               cwd=ROOT, check=True,
                               timeout=config["whole_worker_timeout_seconds"])
                raw = load_json(path)
                if (raw["metadata"]["scenario_identifier"] !=
                        prepare(name, run_options(config, name, dod, seed, method, variant))[2].identifier or
                        raw["metadata"]["source_sha256"] != frozen["source_sha256"] or
                        raw["metadata"]["dispatch_variant"] != variant):
                    raise ValueError(f"Pilot worker identity mismatch: {key}")
                record = dict(instance=name, dynamicity=dod, seed=seed, method=method,
                              variant=variant, size=int(name.rsplit("_", 1)[1]),
                              customers_served=raw["metrics"]["customers_served"],
                              complete_service=raw["metrics"]["complete_service"],
                              max_optimization_latency=raw["metrics"]["max_optimization_latency"],
                              worker_wall_seconds=raw["metrics"]["worker_wall_seconds"],
                              k_ref=raw["metadata"]["K_ref"],
                              scenario_id=raw["metadata"]["scenario_identifier"],
                              independent_audit=raw["metadata"]["independent_audit"],
                              raw=path.relative_to(ROOT).as_posix(),
                              raw_sha256=sha256(path.read_bytes()).hexdigest())
                records[key] = record
                save_json(manifest_path, dict(status="complete" if len(records) == total else "partial",
                                              protocol_identifier=fingerprint,
                                              planned_runs=total, completed_runs=len(records),
                                              records=list(records.values())))
                print(f"dispatch pilot {len(records)}/{total}: {name} DoD={dod} {method} "
                      f"{variant} served={record['customers_served']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=6)
    args = parser.parse_args()
    if args.worker:
        name, dod, seed, method, variant, path = args.worker
        worker(name, float(dod), int(seed), method, variant, path)
    else:
        run()
