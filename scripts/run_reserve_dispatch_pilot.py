"""Isolated matched pilot of one-EV slack reserve on development losses."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from time import perf_counter

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts import run_desaulniers_campaign as development


OUTPUT = ROOT / "results/desaulniers/publication_development/reserve_pilot"
CASES = (("r101_21_25", 0.75, 0), ("rc101_21_50", 0.75, 0),
         ("r101_21_100", 0.75, 0))
METHODS = ("MPC_COMPLETION", "MPC_ALNS")
VARIANTS = ("original", "depot_slack_reserve_v2")


def options(config, name, dod, seed, method, variant):
    return dict(development.options(config, name, dod, seed, method),
                study="mpc_publication_reserve_development_pilot", dispatch_policy=variant)


def protocol(config):
    historical = load_json(development.OUTPUT / "manifest.json")
    indexed = {(r["instance"], r["dynamicity"], r["seed"], r["method"])
               for r in historical["records"]}
    if historical["completed_runs"] != historical["planned_runs"] or any(
            (name, dod, seed, method) not in indexed
            for name, dod, seed in CASES for method in METHODS):
        raise ValueError("Selected development cases are not fully audited")
    sources = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__),
               ROOT / "scripts/run_desaulniers_campaign.py"]
    frozen = dict(purpose="selected_loss_development_pilot_not_final",
                  selection="One loss case per size, selected before reserve results",
                  cases=[list(case) for case in CASES], methods=list(METHODS),
                  variants=list(VARIANTS), five_second_limit=5.0,
                  source_sha256=identifier({p.relative_to(ROOT).as_posix():
                                            sha256(p.read_bytes()).hexdigest() for p in sources}),
                  config_sha256=sha256(development.CONFIG.read_bytes()).hexdigest(),
                  historical_protocol=historical["protocol_identifier"])
    path = OUTPUT / "protocol.json"
    if path.exists():
        if load_json(path) != frozen:
            raise ValueError("Reserve pilot source/protocol drift")
    else:
        save_json(path, frozen)
    return frozen


def worker(name, dod, seed, method, variant, path):
    config = load_config(development.CONFIG)
    frozen = protocol(config)
    path = Path(path).resolve()
    if ((name, dod, seed) not in CASES or method not in METHODS or variant not in VARIANTS
            or not path.is_relative_to((OUTPUT / "raw").resolve()) or path.exists()):
        raise ValueError("Invalid or existing reserve pilot worker output")
    instance, reference, scenario, _ = prepare(name, options(config, name, dod, seed, method, variant))
    started = perf_counter()
    result = EventDrivenSimulator(instance, scenario,
                                  simulation_config(options(config, name, dod, seed, method, variant))).run()
    audit = audit_result(result, instance, scenario)
    if (not all(audit.values()) or result.metadata["K_ref"] != reference.fleet_size
            or result.metrics["max_optimization_latency"] > 5.0 + 1e-6
            or any(result.metrics[key] for key in ("battery_violations", "capacity_violations",
                                                    "time_window_violations", "duplicate_service_violations",
                                                    "hidden_information_violations"))):
        raise ValueError("Reserve pilot independent replay or budget failed")
    result.metadata.update(isolated_worker=True, independent_audit=audit,
                           source_sha256=frozen["source_sha256"],
                           pilot_protocol_identifier=identifier(frozen), dispatch_variant=variant)
    result.metrics["worker_wall_seconds"] = perf_counter() - started
    save_json(path, asdict(result))


def run():
    config = load_config(development.CONFIG)
    frozen = protocol(config)
    fingerprint = identifier(frozen)
    manifest_path = OUTPUT / "manifest.json"
    old = load_json(manifest_path) if manifest_path.exists() else None
    if old and old["protocol_identifier"] != fingerprint:
        raise ValueError("Existing reserve pilot manifest belongs to another protocol")
    records = {(r["instance"], r["dynamicity"], r["seed"], r["method"], r["variant"]): r
               for r in old["records"]} if old else {}
    total = len(CASES) * len(METHODS) * len(VARIANTS)
    for name, dod, seed in CASES:
        for method in METHODS:
            for variant in VARIANTS:
                key = name, dod, seed, method, variant
                path = OUTPUT / "raw" / f"{name}_{dod}_{seed}_{method}_{variant}_{identifier(key)[:12]}.json.gz"
                if key in records:
                    row = records[key]
                    if ((ROOT / row["raw"]).resolve() != path.resolve() or not path.exists() or
                            sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
                        raise ValueError(f"Saved reserve pilot raw is missing or corrupt: {key}")
                    continue
                if path.exists():
                    raise ValueError(f"Unmanifested reserve pilot raw: {path}")
                subprocess.run([sys.executable, "-m", "scripts.run_reserve_dispatch_pilot",
                                "--worker", name, str(dod), str(seed), method, variant, str(path)],
                               cwd=ROOT, check=True, timeout=config["whole_worker_timeout_seconds"])
                raw = load_json(path)
                if (raw["metadata"]["source_sha256"] != frozen["source_sha256"] or
                        raw["metadata"]["pilot_protocol_identifier"] != fingerprint):
                    raise ValueError("Reserve worker identity mismatch")
                record = dict(instance=name, dynamicity=dod, seed=seed, method=method,
                              variant=variant, customers_served=raw["metrics"]["customers_served"],
                              complete_service=raw["metrics"]["complete_service"],
                              max_optimization_latency=raw["metrics"]["max_optimization_latency"],
                              worker_wall_seconds=raw["metrics"]["worker_wall_seconds"],
                              scenario_id=raw["metadata"]["scenario_identifier"],
                              k_ref=raw["metadata"]["K_ref"],
                              independent_audit=raw["metadata"]["independent_audit"],
                              raw=path.relative_to(ROOT).as_posix(),
                              raw_sha256=sha256(path.read_bytes()).hexdigest())
                records[key] = record
                save_json(manifest_path, dict(status="complete" if len(records) == total else "partial",
                                              protocol_identifier=fingerprint, planned_runs=total,
                                              completed_runs=len(records), records=list(records.values())))
                print(f"reserve {len(records)}/{total}: {name} {method} {variant} "
                      f"served={record['customers_served']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=6)
    args = parser.parse_args()
    if args.worker:
        name, dod, seed, method, variant, path = args.worker
        worker(name, float(dod), int(seed), method, variant, path)
    else:
        run()
