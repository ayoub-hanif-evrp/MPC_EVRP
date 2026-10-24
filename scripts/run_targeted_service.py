"""Frozen paired development, exact-input archive, and conditional parent holdout."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.reference import ReferenceSchedule
from evrp.scenario import DynamicScenario
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, benchmark_hashes, identifier, load_json, save_json, writable_path
from scripts import run_desaulniers_campaign as base

CONFIG = ROOT / "configs/targeted_service_v1.yaml"
OUTPUT = ROOT / "results/desaulniers/targeted_service_v1"
ALLOWED = {"constructor_policy", "route_decoder_version", "first_action_policy",
           "optimizer_initialization_policy", "coordination_policy"}
VIOLATIONS = ("battery_violations", "capacity_violations", "time_window_violations",
              "duplicate_service_violations", "hidden_information_violations")


def design_cases(config, parents):
    return [[f"{parent}_{size}", config["dynamicities"][(index + seed) % 2], seed]
            for parent in parents for index, size in enumerate(config["sizes"]) for seed in config["seeds"]]


def options(config, case, method, variant):
    result = base.options(load_config(base.CONFIG), *case, method)
    result.update(config["common"])
    result.update(config["variants"][variant])
    result["study"] = config["study"]
    if simulation_config(result).total_planning_time_limit != 5:
        raise ValueError("All methods require the original five-second budget")
    return result


def source_hash():
    files = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__), CONFIG, base.CONFIG,
             ROOT / "configs/paper_controller.yaml", Path(base.__file__),
             ROOT / "scripts/run_desaulniers_pilot.py", ROOT / "scripts/analyze_targeted_service.py"]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in files})


def archive_input(path, kind, obj, instance):
    artifact = OUTPUT / "inputs" / kind / path.name
    if artifact.exists():
        if artifact.read_bytes() != path.read_bytes():
            raise ValueError("Exact input archive conflict")
    else:
        shutil.copyfile(path, writable_path(artifact))
    return dict(artifact=artifact.relative_to(ROOT).as_posix(), cache=path.relative_to(ROOT).as_posix(),
                sha256=sha256(artifact.read_bytes()).hexdigest(), identifier=obj.identifier,
                instance=instance.name, instance_sha256=instance.sha256, kind=kind)


def frozen(stage, selection=None):
    config = load_config(CONFIG)
    if not set(config["common"]) <= ALLOWED or any(not set(v) <= ALLOWED for v in config["variants"].values()):
        raise ValueError("Variant may not override physics, fleet, release or budget")
    if stage == "holdout" and selection is None:
        raise ValueError("Holdout requires independently audited development selection")
    parents = config["development_parents" if stage == "development" else "reserved_parents"]
    methods = config["methods" if stage == "development" else "holdout_methods"]
    variants = list(config["variants"]) if stage == "development" else ["original", selection["selected_variant"]]
    science = dict(config=config, stage=stage, source_sha256=source_hash(),
                   dataset_sha256=identifier(benchmark_hashes()), methods=methods, variants=variants,
                   parent_partition=dict(development=config["development_parents"],
                                         reserved=config["reserved_parents"]), selection=selection)
    target = OUTPUT / stage / "protocol.json"
    if target.exists():
        old = load_json(target)
        if any(old["scientific"][k] != v for k, v in science.items()):
            raise ValueError("Frozen targeted study source or design drift")
        restore_inputs(old)
        return old
    if stage == "holdout":
        seen = set()
        for path in (ROOT / "results/desaulniers").rglob("manifest.json"):
            for row in load_json(path).get("records", []):
                if row.get("raw") and row.get("instance"):
                    seen.add(row["instance"].rsplit("_", 1)[0])
        if set(parents) & seen or set(parents) & set(config["development_parents"]):
            raise ValueError("Reserved holdout parent already exposed")
    cases, excluded, inputs = [], [], {}
    for case in design_cases(config, parents):
        try:
            instance, reference, scenario, scenario_path = prepare(case[0], options(config, case, methods[0], "original"))
        except ValueError as error:
            if "DoD is ineligible" not in str(error):
                raise
            excluded.append(dict(case=case, reason=str(error)))
            continue
        refs = [p for p in (ROOT / "results/reference_schedules").glob(f"{instance.name}_*.json")
                if load_json(p).get("identifier") == reference.identifier]
        if not refs:
            raise ValueError("Exact reference input absent")
        artifacts = [(p, "reference_schedules", reference) for p in refs]
        artifacts.append((scenario_path, "scenarios", scenario))
        for path, kind, obj in artifacts:
            inputs[str(path)] = archive_input(path, kind, obj, instance)
        cases.append(dict(case=case, scenario_id=scenario.identifier, reference_id=reference.identifier,
                          k_ref=reference.fleet_size, customers=len(instance.customers),
                          instance_sha256=instance.sha256, parent=case[0].rsplit("_", 1)[0]))
    science.update(cases=cases, excluded=excluded, inputs=list(inputs.values()))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    result = dict(scientific=science, source_commit=commit, python=sys.version,
                  timing_conditions=config["timing_conditions"])
    save_json(target, result)
    return result


def restore_inputs(protocol):
    for row in protocol["scientific"]["inputs"]:
        artifact, target = ROOT / row["artifact"], ROOT / row["cache"]
        if (not target.resolve().is_relative_to((ROOT / "results").resolve()) or
                sha256(artifact.read_bytes()).hexdigest() != row["sha256"]):
            raise ValueError("Input archive boundary or hash mismatch")
        if target.exists() and target.read_bytes() != artifact.read_bytes():
            raise ValueError("Input cache conflict; never regenerate frozen scientific inputs")
        if not target.exists():
            shutil.copyfile(artifact, writable_path(target))


def target_path(stage, protocol, index, method, variant):
    return OUTPUT / stage / "raw" / f"{index:03}_{method}_{variant}_{identifier(protocol)[:12]}.json.gz"


def verify(raw, protocol, index, method, variant):
    info = protocol["scientific"]["cases"][index]
    meta, metrics = raw["metadata"], raw["metrics"]
    if (meta["targeted_protocol_identifier"] != identifier(protocol) or
            meta["source_sha256"] != protocol["scientific"]["source_sha256"] or
            meta["scenario_identifier"] != info["scenario_id"] or meta["K_ref"] != info["k_ref"] or
            meta["algorithm"] != method or meta["campaign_variant"] != variant or
            not all(meta["independent_audit"].values()) or any(metrics[k] for k in VIOLATIONS) or
            metrics["max_optimization_latency"] > 5 + 1e-6):
        raise ValueError("Targeted raw identity, independent audit or budget failure")


def worker(stage, index, method, variant):
    protocol = load_json(OUTPUT / stage / "protocol.json")
    if protocol["scientific"]["source_sha256"] != source_hash():
        raise ValueError("Worker frozen source drift")
    config = protocol["scientific"]["config"]
    info = protocol["scientific"]["cases"][index]
    if method not in protocol["scientific"]["methods"] or variant not in protocol["scientific"]["variants"]:
        raise ValueError("Worker outside frozen design")
    target = target_path(stage, protocol, index, method, variant)
    if target.exists():
        raise ValueError("Never overwrite existing raw evidence")
    started = perf_counter()
    instance, reference, scenario, _ = prepare(info["case"][0], options(config, info["case"], method, variant))
    if reference.identifier != info["reference_id"] or scenario.identifier != info["scenario_id"]:
        raise ValueError("Worker input mismatch")
    result = EventDrivenSimulator(instance, scenario, simulation_config(options(config, info["case"], method, variant))).run()
    audit = audit_result(result, instance, scenario)
    result.metrics["worker_wall_seconds"] = perf_counter()-started
    result.metadata.update(source_sha256=source_hash(), frozen_source_commit=protocol["source_commit"],
                           targeted_protocol_identifier=identifier(protocol), campaign_variant=variant,
                           independent_audit=audit, isolated_worker=True,
                           timing_conditions=protocol["timing_conditions"])
    raw = asdict(result)
    verify(raw, protocol, index, method, variant)
    save_json(target, raw)


def run(stage, protocol, deadline):
    path = OUTPUT / stage / "manifest.json"
    old = load_json(path) if path.exists() else None
    if old and old["protocol_identifier"] != identifier(protocol):
        raise ValueError("Manifest protocol drift")
    records = {(r["case_index"], r["method"], r["variant"]): r for r in old["records"]} if old else {}
    if old and len(records) != len(old["records"]):
        raise ValueError("Duplicate saved run")
    science = protocol["scientific"]
    total = len(science["cases"]) * len(science["methods"]) * len(science["variants"])
    for index, info in enumerate(science["cases"]):
        # A watchdog pause occurs at a complete scenario boundary, not inside a worker.
        if perf_counter() > deadline:
            return False
        for method in science["methods"]:
            for variant in science["variants"]:
                key = index, method, variant
                target = target_path(stage, protocol, *key)
                if key in records:
                    row = records[key]
                    if sha256(target.read_bytes()).hexdigest() != row["raw_sha256"]:
                        raise ValueError("Saved run bytes changed")
                    verify(load_json(target), protocol, *key)
                    continue
                command = [sys.executable, "-u", "-m", "scripts.run_targeted_service", "--worker", stage,
                           str(index), method, variant]
                if target.exists():
                    raise ValueError("Unmanifested evidence preserved; investigate before resume")
                started = perf_counter()
                try:
                    subprocess.run(command, cwd=ROOT, check=True, timeout=science["config"]["whole_worker_timeout_seconds"])
                except (subprocess.SubprocessError, OSError) as error:
                    save_json(OUTPUT / stage / "failures" / f"{index}_{method}_{variant}.json",
                              dict(command=command, error=repr(error), protocol_identifier=identifier(protocol)))
                    raise
                raw = load_json(target)
                verify(raw, protocol, *key)
                records[key] = dict(case_index=index, instance=info["case"][0], case=info["case"],
                                    parent=info["parent"], method=method, variant=variant,
                                    raw=target.relative_to(ROOT).as_posix(), raw_sha256=sha256(target.read_bytes()).hexdigest(),
                                    metrics=raw["metrics"], independent_audit=raw["metadata"]["independent_audit"],
                                    process_wall_seconds=perf_counter()-started)
                save_json(path, dict(protocol_identifier=identifier(protocol), planned_runs=total,
                          completed_runs=len(records), status="complete" if len(records)==total else "partial",
                          records=list(records.values())))
                print(f"{stage} {len(records)}/{total} {info['case']} {method} {variant}: "
                      f"served={raw['metrics']['customers_served']}", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=4)
    parser.add_argument("--restore", choices=("development", "holdout"))
    args = parser.parse_args()
    if args.worker:
        stage, index, method, variant = args.worker
        return worker(stage, int(index), method, variant)
    if args.restore:
        return restore_inputs(load_json(OUTPUT / args.restore / "protocol.json"))
    from scripts.analyze_targeted_service import analyze, finalize
    deadline = perf_counter() + load_config(CONFIG)["maximum_campaign_hours"] * 3600
    protocol = frozen("development")
    if not run("development", protocol, deadline):
        return print("Paused at scenario boundary; resume the same command.")
    selection = analyze("development")
    if selection["selected_variant"] is not None:
        protocol = frozen("holdout", selection)
        if not run("holdout", protocol, deadline):
            return print("Holdout paused at scenario boundary; resume the same command.")
        analyze("holdout")
    finalize(selection)


if __name__ == "__main__":
    main()
