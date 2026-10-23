"""Source-frozen, isolated and audited campaigns for publication development."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.simulator import EventDrivenSimulator, OPTIMIZER_ALGORITHMS
from evrp.storage import ROOT, benchmark_hashes, identifier, load_json, save_json
from scripts import run_desaulniers_campaign as development


ALLOWED_OVERRIDES = {"planning_trace", "dispatch_policy", "route_decoder_version",
                     "shared_constructor_version"}


def configuration(path):
    path = Path(path).resolve()
    config = load_config(path)
    output = (ROOT / config["output"]).resolve()
    if not output.is_relative_to((ROOT / "results/desaulniers/publication_development").resolve()):
        raise ValueError("Campaign output must stay in publication_development")
    if (not config["cases"] or not config["methods"] or not config["variants"] or
            not set(config["methods"]) <= OPTIMIZER_ALGORITHMS or
            len(set(config["methods"])) != len(config["methods"])):
        raise ValueError("Invalid campaign design")
    if len({tuple(case) for case in config["cases"]}) != len(config["cases"]):
        raise ValueError("Duplicate campaign cases")
    for overrides in config["variants"].values():
        if not set(overrides) <= ALLOWED_OVERRIDES:
            raise ValueError("Variant may not change physical, release, fleet or budget parameters")
    return path, config, output


def options(config, case, method, variant):
    name, dod, seed = case
    base = development.options(load_config(development.CONFIG), name, dod, seed, method)
    result = dict(base, study=config["study"], **config["variants"][variant])
    effective = simulation_config(result)
    if effective.total_planning_time_limit != 5.0:
        raise ValueError("Every method must retain the five-second decision budget")
    return result


def protocol(path, config, output):
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__),
             ROOT / "scripts/run_desaulniers_campaign.py", development.CONFIG, path]
    source = identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                         for p in paths})
    cases = []
    for case in config["cases"]:
        instance, reference, scenario, _ = prepare(case[0], options(
            config, case, config["methods"][0], next(iter(config["variants"]))))
        cases.append(dict(instance=case[0], dynamicity=case[1], seed=case[2],
                          scenario_id=scenario.identifier, k_ref=reference.fleet_size,
                          customers=len(instance.customers), instance_sha256=instance.sha256))
    scientific = dict(design=config, cases=cases, source_sha256=source,
                      dataset_sha256=identifier(benchmark_hashes()),
                      base_config_sha256=sha256(development.CONFIG.read_bytes()).hexdigest(),
                      execution="sequential isolated workers", decision_limit_seconds=5.0)
    target = output / "protocol.json"
    if target.exists():
        frozen = load_json(target)
        if frozen["scientific"] != scientific:
            raise ValueError("Frozen campaign source, dataset or design drift")
        return frozen
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.strip()
    frozen = dict(scientific=scientific, source_commit=commit,
                  environment=dict(python=sys.version, platform=platform.platform()))
    save_json(target, frozen)
    return frozen


def raw_path(output, fingerprint, case, method, variant):
    key = [*case, method, variant]
    return output / "raw" / f"{case[0]}_{method}_{variant}_{identifier([fingerprint, key])[:16]}.json.gz"


def verify(raw, frozen, case_info, method, variant):
    meta, metrics = raw["metadata"], raw["metrics"]
    if (meta["campaign_protocol_identifier"] != identifier(frozen) or
            meta["source_sha256"] != frozen["scientific"]["source_sha256"] or
            meta["scenario_identifier"] != case_info["scenario_id"] or
            meta["K_ref"] != case_info["k_ref"] or meta["algorithm"] != method or
            meta["campaign_variant"] != variant or not meta["isolated_worker"] or
            not all(meta["independent_audit"].values()) or
            metrics["max_optimization_latency"] > 5.0 + 1e-6):
        raise ValueError("Campaign worker identity, audit or budget mismatch")


def worker(path, config, output, index, method, variant, target):
    frozen = protocol(path, config, output)
    if method not in config["methods"] or variant not in config["variants"]:
        raise ValueError("Unknown campaign method or variant")
    case = config["cases"][index]
    target = Path(target).resolve()
    if target != raw_path(output, identifier(frozen), case, method, variant).resolve() or target.exists():
        raise ValueError("Worker output must be a new protocol-bound raw file")
    instance, reference, scenario, _ = prepare(case[0], options(config, case, method, variant))
    if (scenario.identifier != frozen["scientific"]["cases"][index]["scenario_id"] or
            reference.fleet_size != frozen["scientific"]["cases"][index]["k_ref"]):
        raise ValueError("Worker scenario changed")
    started = perf_counter()
    result = EventDrivenSimulator(instance, scenario,
                                  simulation_config(options(config, case, method, variant))).run()
    audit = audit_result(result, instance, scenario)
    if not all(audit.values()) or any(result.metrics[k] for k in (
            "battery_violations", "capacity_violations", "time_window_violations",
            "duplicate_service_violations", "hidden_information_violations")):
        raise ValueError("Independent campaign physical audit failed")
    result.metrics["worker_wall_seconds"] = perf_counter() - started
    result.metadata.update(isolated_worker=True, independent_audit=audit,
                           source_sha256=frozen["scientific"]["source_sha256"],
                           frozen_source_commit=frozen["source_commit"],
                           campaign_protocol_identifier=identifier(frozen), campaign_variant=variant)
    raw = asdict(result)
    verify(raw, frozen, frozen["scientific"]["cases"][index], method, variant)
    save_json(target, raw)


def run(path, config, output, maximum):
    frozen = protocol(path, config, output)
    fingerprint = identifier(frozen)
    manifest_path = output / "manifest.json"
    old = load_json(manifest_path) if manifest_path.exists() else None
    if old and old["protocol_identifier"] != fingerprint:
        raise ValueError("Manifest belongs to another campaign")
    records = {(r["case_index"], r["method"], r["variant"]): r
               for r in old["records"]} if old else {}
    if old and len(records) != len(old["records"]):
        raise ValueError("Duplicate manifest keys")
    total = len(config["cases"]) * len(config["methods"]) * len(config["variants"])
    new = 0
    for index, case in enumerate(config["cases"]):
        for method in config["methods"]:
            for variant in config["variants"]:
                target = raw_path(output, fingerprint, case, method, variant)
                key = index, method, variant
                if key in records:
                    row = records[key]
                    if (ROOT / row["raw"]).resolve() != target.resolve() or not target.exists() or (
                            sha256(target.read_bytes()).hexdigest() != row["raw_sha256"]):
                        raise ValueError(f"Saved raw missing or corrupted: {key}")
                    verify(load_json(target), frozen, frozen["scientific"]["cases"][index], method, variant)
                    continue
                if maximum is not None and new >= maximum:
                    return
                if target.exists():
                    raise ValueError(f"Unmanifested raw preserved for investigation: {target}")
                command = [sys.executable, "-u", "-m", "scripts.run_publication_campaign",
                           "--config", str(path), "--worker", str(index), method, variant, str(target)]
                try:
                    subprocess.run(command, cwd=ROOT, check=True,
                                   timeout=config.get("whole_worker_timeout_seconds", 3900))
                except (subprocess.SubprocessError, OSError) as error:
                    save_json(output / "failures" / f"{index}_{method}_{variant}.json",
                              dict(case=case, method=method, variant=variant, error=repr(error),
                                   command=command, protocol_identifier=fingerprint))
                    raise
                raw = load_json(target)
                verify(raw, frozen, frozen["scientific"]["cases"][index], method, variant)
                record = dict(case_index=index, instance=case[0], dynamicity=case[1], seed=case[2],
                              method=method, variant=variant, scenario_id=raw["metadata"]["scenario_identifier"],
                              k_ref=raw["metadata"]["K_ref"], metrics=raw["metrics"],
                              independent_audit=raw["metadata"]["independent_audit"],
                              raw=target.relative_to(ROOT).as_posix(),
                              raw_sha256=sha256(target.read_bytes()).hexdigest())
                records[key] = record
                save_json(manifest_path, dict(protocol_identifier=fingerprint,
                          status="complete" if len(records) == total else "partial", planned_runs=total,
                          completed_runs=len(records), records=list(records.values())))
                new += 1
                print(f"{config['study']} {len(records)}/{total}: {case} {method} {variant} "
                      f"served={raw['metrics']['customers_served']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--max-new-runs", type=int)
    parser.add_argument("--worker", nargs=4)
    args = parser.parse_args()
    path, config, output = configuration(args.config)
    if args.worker:
        index, method, variant, target = args.worker
        worker(path, config, output, int(index), method, variant, target)
    else:
        run(path, config, output, args.max_new_runs)
