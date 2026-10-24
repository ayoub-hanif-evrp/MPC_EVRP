"""Bounded, resumable, preregistered 12-parent five-engine comparison."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from itertools import product
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

from evrp.experiments import audit_result, load_config, simulation_config
from evrp.instance import load_instance
from evrp.reference import ReferenceConfig, ReferenceSchedule, published_full_reference
from evrp.scenario import DynamicScenario, generate
from evrp.simulator import EventDrivenSimulator
from evrp.storage import (BENCHMARK, ROOT, benchmark_hashes, identifier, load_json,
                          save_json, verify_text_digest)
from scripts.run_desaulniers_campaign import CONFIG as BASE_CONFIG, options as base_options

CONFIG = ROOT / "configs/reliability_v2.yaml"
OUTPUT = ROOT / "results/desaulniers/reliability_v2"
INVENTORY = ROOT / "results/desaulniers/targeted_service_v1/reference_inventory.json"
VIOLATIONS = ("battery_violations", "capacity_violations", "time_window_violations",
              "duplicate_service_violations", "hidden_information_violations")


def source_hash():
    files = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__), CONFIG, BASE_CONFIG,
        ROOT / "scripts/analyze_reliability_study.py", ROOT / "scripts/run_desaulniers_campaign.py",
        ROOT / "scripts/run_desaulniers_pilot.py", ROOT / "configs/paper_controller.yaml", INVENTORY]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in files})


def design(config, parents, holdout=False):
    return [[f"{parent}_{size}", dod, seed]
            for index, parent in enumerate(parents)
            for size in ([25, 50, 100] if holdout else [25 if index % 2 == 0 else 50, 100])
            for dod, seed in product(config["dynamicities"], config["seeds"])]


def variants_for(config, case, method, stage, selected):
    if stage == "holdout":
        return ["original"] + ([selected] if selected != "completion_first_action" or method == "MPC_COMPLETION" else [])
    variants = ["original", "flex_exchange"]
    if case[0].endswith("_100") and case[1:] == [.75, 0]:
        variants.append("cache_only")
    if method == "MPC_COMPLETION":
        variants.append("completion_first_action")
    return variants


def validate_config(config):
    allowed = {"first_action_policy", "proposal_cache_policy", "optimizer_initialization_policy", "coordination_policy"}
    if not set(config["common"]) <= allowed or any(not set(v) <= allowed for v in config["variants"].values()):
        raise ValueError("Variants cannot change budget, physics, objective, engines or release assumptions")
    if config["methods"] != ["MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"]:
        raise ValueError("All five original engines are required")
    if len(config["development_parents"]) != 12 or len(config["reserved_parents"]) != 6:
        raise ValueError("The independent-parent design is fixed")


def options(config, case, method, variant):
    result = base_options(load_config(BASE_CONFIG), *case, method)
    result.update(config["common"])
    result.update(config["variants"][variant])
    result["study"] = config["study"]
    if simulation_config(result).total_planning_time_limit != 5:
        raise ValueError("The unchanged five-second end-to-end limit is mandatory")
    return result


def exposed_parents():
    seen = set()
    for path in (ROOT / "results/desaulniers").rglob("manifest.json"):
        if path.is_relative_to(OUTPUT):
            continue
        for row in load_json(path).get("records", []):
            if row.get("raw") and row.get("instance"):
                seen.add(row["instance"].rsplit("_", 1)[0])
    return seen


def archive(stage, kind, name, obj):
    target = OUTPUT / stage / "inputs" / kind / name
    if target.exists():
        data, expected = load_json(target), asdict(obj)
        if not set(expected) <= set(data) or identifier({k: data[k] for k in expected}) != identifier(expected):
            raise ValueError("Archived input conflict")
    else:
        obj.save(target)
    return dict(path=target.relative_to(ROOT).as_posix(), sha256=sha256(target.read_bytes()).hexdigest())


def freeze(stage, selection=None):
    config = load_config(CONFIG)
    validate_config(config)
    path = OUTPUT / stage / "protocol.json"
    if path.exists():
        protocol = load_json(path)
        if protocol["source_sha256"] != source_hash() or protocol["config"] != config:
            raise ValueError("Frozen source or configuration drift; preserve all existing results")
        if stage == "holdout" and (not selection or not selection.get("promoted") or
                                    protocol["development_selection"] != selection):
            raise ValueError("Holdout resume requires the same audited development promotion")
        return protocol
    if stage == "holdout":
        if selection is None or not selection.get("promoted"):
            raise ValueError("Independent holdout requires completed audited development promotion")
        saved = load_json(OUTPUT / "development/analysis.json")
        manifest = load_json(OUTPUT / "development/manifest.json")
        if (saved["selection"] != selection or manifest["status"] != "complete" or
                saved["manifest_sha256"] != sha256((OUTPUT / "development/manifest.json").read_bytes()).hexdigest()):
            raise ValueError("Selection evidence is incomplete or changed")
    scientific = ["evrp", "configs/reliability_v2.yaml", "scripts/run_reliability_study.py",
                  "scripts/analyze_reliability_study.py", "scripts/run_desaulniers_campaign.py",
                  "scripts/run_desaulniers_pilot.py", "configs/paper_controller.yaml"]
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *scientific],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        raise ValueError("Commit all scientific source before freezing provenance")
    parents = config["reserved_parents" if stage == "holdout" else "development_parents"]
    if len(parents) != len(set(parents)) or set(config["development_parents"]) & set(config["reserved_parents"]):
        raise ValueError("Parent split leaks related size variants")
    seen = exposed_parents()
    if set(parents) & seen:
        raise ValueError(f"New comparison parents already exposed: {sorted(set(parents) & seen)}")
    inventory = {r["instance"]: r for r in load_json(INVENTORY)["rows"]}
    cases, excluded = [], []
    for case in design(config, parents, stage == "holdout"):
        instance = load_instance(BENCHMARK / f"{case[0]}.txt")
        row = inventory[instance.name]
        if instance.sha256 != row["instance_sha256"] or not row["physical_witness"]:
            raise ValueError("Published benchmark differs from the audited reference inventory")
        if row["artifact"]:
            artifact = ROOT / row["artifact"]
            verify_text_digest(artifact, row["artifact_sha256"])
            reference = ReferenceSchedule.load(artifact, instance)
        else:
            reference = published_full_reference(instance, ReferenceConfig())
        if reference is None or reference.identifier != row["reference_id"]:
            raise ValueError("Reference identity differs from independently validated witness")
        try:
            scenario = generate(instance, reference, seed=case[2], dynamicity=case[1])
        except ValueError as error:
            if "DoD is ineligible" not in str(error):
                raise
            excluded.append(dict(case=case, reason=str(error)))
            continue
        ref = archive(stage, "references", f"{case[0]}.json", reference)
        sce = archive(stage, "scenarios", f"{identifier(case)[:16]}.json", scenario)
        cases.append(dict(case=case, parent=case[0].rsplit("_", 1)[0], customers=len(instance.customers),
                          instance_sha256=instance.sha256, reference=ref, scenario=sce,
                          reference_id=reference.identifier, scenario_id=scenario.identifier, k_ref=reference.fleet_size))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    protocol = dict(config=config, stage=stage, source_sha256=source_hash(), source_commit=commit,
                    dataset_sha256=identifier(benchmark_hashes()), cases=cases, exclusions=excluded,
                    selected=selection["promoted"] if selection else None,
                    development_selection=selection,
                    parents=parents, historical_exposed_parents=sorted(seen),
                    python=sys.version, platform=platform.platform(),
                    timing_conditions=config["timing_conditions"])
    save_json(path, protocol)
    print(f"Frozen {stage}: {len(cases)} scenarios, {len(parents)} independent parents, {len(excluded)} eligibility exclusions", flush=True)
    return protocol


def inputs(info):
    instance = load_instance(BENCHMARK / f"{info['case'][0]}.txt")
    if instance.sha256 != info["instance_sha256"]:
        raise ValueError("Benchmark bytes changed")
    for key in ("reference", "scenario"):
        record = info[key]
        if sha256((ROOT / record["path"]).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Exact archived input bytes changed")
    reference = ReferenceSchedule.load(ROOT / info["reference"]["path"], instance)
    scenario = DynamicScenario.load(ROOT / info["scenario"]["path"], instance)
    if (scenario.identifier != info["scenario_id"] or reference.identifier != info["reference_id"] or
            scenario.fleet_size != info["k_ref"] or scenario.reference_schedule_identifier != reference.identifier):
        raise ValueError("Paired scenario/reference identity changed")
    return instance, scenario


def raw_path(stage, protocol, index, method, variant):
    return OUTPUT / stage / "raw" / f"{index:03}_{method}_{variant}_{identifier(protocol)[:12]}.json.gz"


def verify(raw, protocol, index, method, variant):
    info, meta, metrics = protocol["cases"][index], raw["metadata"], raw["metrics"]
    expected = asdict(simulation_config(options(protocol["config"], info["case"], method, variant)))
    if (meta["reliability_protocol"] != identifier(protocol) or meta["source_sha256"] != protocol["source_sha256"] or
            meta["scenario_identifier"] != info["scenario_id"] or meta["K_ref"] != info["k_ref"] or
            meta["reference_schedule_identifier"] != info["reference_id"] or
            meta["instance_sha256"] != info["instance_sha256"] or
            meta["scenario_seed"] != info["case"][2] or meta["DoD_target"] != info["case"][1] or
            meta["algorithm"] != method or meta["campaign_variant"] != variant or
            identifier(raw["effective_config"]) != identifier(expected) or
            any(metrics[k] for k in VIOLATIONS) or metrics["max_optimization_latency"] > 5 + 1e-6 or
            not all(meta["independent_audit"].values())):
        raise ValueError("Run failed exact config, identity, information, physical audit or decision budget")


def worker(stage, index, method, variant):
    protocol = load_json(OUTPUT / stage / "protocol.json")
    if protocol["source_sha256"] != source_hash():
        raise ValueError("Worker source drift")
    info = protocol["cases"][index]
    if (method not in protocol["config"]["methods"] or variant not in
            variants_for(protocol["config"], info["case"], method, stage, protocol["selected"])):
        raise ValueError("Worker outside frozen comparison")
    path = raw_path(stage, protocol, index, method, variant)
    if path.exists():
        raise ValueError("Never overwrite existing experimental evidence")
    instance, scenario = inputs(info)
    started = perf_counter()
    result = EventDrivenSimulator(instance, scenario, simulation_config(
        options(protocol["config"], info["case"], method, variant))).run()
    try:
        audit = audit_result(result, instance, scenario)
    except Exception:
        save_json(OUTPUT / stage / "failures" / f"{index}_{method}_{variant}_audit_raw.json.gz", asdict(result))
        raise
    result.metadata.update(reliability_protocol=identifier(protocol), source_sha256=protocol["source_sha256"],
                           source_commit=protocol["source_commit"], campaign_variant=variant,
                           independent_audit=audit, timing_conditions=protocol["timing_conditions"])
    result.metrics["worker_wall_seconds"] = perf_counter() - started
    raw = asdict(result)
    try:
        if protocol["source_sha256"] != source_hash():
            raise ValueError("Scientific source changed during worker execution")
        verify(raw, protocol, index, method, variant)
    except Exception:
        save_json(OUTPUT / stage / "failures" / f"{index}_{method}_{variant}_rejected_raw.json.gz", raw)
        raise
    save_json(path, raw)


def run(stage, protocol, deadline):
    path = OUTPUT / stage / "manifest.json"
    previous = load_json(path) if path.exists() else None
    if previous and previous["protocol_identifier"] != identifier(protocol):
        raise ValueError("Manifest protocol mismatch")
    records = {(r["case_index"], r["method"], r["variant"]): r for r in previous["records"]} if previous else {}
    if previous and len(records) != len(previous["records"]):
        raise ValueError("Duplicate existing records")
    config = protocol["config"]
    keys = [(i, method, variant) for i, info in enumerate(protocol["cases"]) for method in config["methods"]
            for variant in variants_for(config, info["case"], method, stage, protocol["selected"])]
    if not set(records) <= set(keys):
        raise ValueError("Manifest contains out-of-design records")
    for index, method, variant in keys:
        if perf_counter() > deadline and method == config["methods"][0] and variant == "original":
            return False
        target = raw_path(stage, protocol, index, method, variant)
        key = index, method, variant
        if key in records:
            if sha256(target.read_bytes()).hexdigest() != records[key]["raw_sha256"]:
                raise ValueError("Completed run bytes changed")
            verify(load_json(target), protocol, *key)
            continue
        if target.exists():
            raise ValueError("Unmanifested evidence preserved; investigate instead of rerunning")
        command = [sys.executable, "-u", "-m", "scripts.run_reliability_study", "--worker", stage, str(index), method, variant]
        started = perf_counter()
        try:
            subprocess.run(command, cwd=ROOT, check=True, timeout=config["whole_worker_timeout_seconds"])
        except (subprocess.SubprocessError, OSError) as error:
            save_json(OUTPUT / stage / "failures" / f"{index}_{method}_{variant}.json",
                      dict(command=command, error=repr(error), protocol_identifier=identifier(protocol)))
            raise
        raw = load_json(target)
        verify(raw, protocol, *key)
        records[key] = dict(case_index=index, instance=protocol["cases"][index]["case"][0],
                            method=method, variant=variant, raw=target.relative_to(ROOT).as_posix(),
                            raw_sha256=sha256(target.read_bytes()).hexdigest(), metrics=raw["metrics"],
                            independent_audit=raw["metadata"]["independent_audit"], process_seconds=perf_counter()-started)
        save_json(path, dict(protocol_identifier=identifier(protocol), status="complete" if len(records)==len(keys) else "partial",
                            completed_runs=len(records), planned_runs=len(keys), records=list(records.values())))
        print(f"{stage} {len(records)}/{len(keys)} {protocol['cases'][index]['case']} {method}/{variant}: "
              f"served={raw['metrics']['customers_served']}", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=4)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.worker:
        stage, index, method, variant = args.worker
        return worker(stage, int(index), method, variant)
    from scripts.analyze_reliability_study import analyze, report
    deadline = perf_counter() + load_config(CONFIG)["maximum_campaign_hours"] * 3600
    protocol = freeze("development")
    if args.freeze:
        return
    if not run("development", protocol, deadline):
        report("Development paused at the 12-hour scenario boundary; no final claims. Resume the same command.")
        return
    selection = analyze("development")
    if selection["promoted"]:
        holdout = freeze("holdout", selection)
        if not run("holdout", holdout, deadline):
            report("Development promotion earned; independent holdout incomplete. No final superiority claim.")
            return
        analyze("holdout")
    report("Study complete. Retain the original system unless independent holdout evidence supports promotion.")


if __name__ == "__main__":
    main()
