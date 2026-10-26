"""Frozen CPU-only replication of the original five MPC methods."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter, process_time
import traceback

from evrp.experiments import audit_result, load_config, simulation_config
from evrp.instance import load_instance
from evrp.reference import ReferenceConfig, ReferenceSchedule, published_full_reference
from evrp.scenario import DynamicScenario, generate
from evrp.simulator import EventDrivenSimulator
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json
from scripts.performance_budget import HardBudget, admit
from scripts.run_desaulniers_pilot import settings

CONFIG = ROOT / "configs/final_cpu_replication_v1.yaml"
OUTPUT = ROOT / "results/desaulniers/final_cpu_paper_v1"
HISTORY = ROOT / "results/desaulniers/robustness_v3/manifest.json"
METHODS = ("MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS")


def source_hash():
    files = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__),
        ROOT / "scripts/run_desaulniers_pilot.py", ROOT / "scripts/performance_budget.py",
        CONFIG, ROOT / "configs/paper_controller.yaml"]
    return identifier({path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                       for path in files})


def options(config, seed, method):
    values = settings(dict(config, dynamicity=config["dynamicity"], scenario_seed=seed), "", method)
    values["study"] = "final_cpu_replication_v1"
    for key in ("dispatch_policy", "constructor_policy", "first_action_policy", "proposal_cache_policy",
                "computation_policy", "mcts_rollout_policy", "quality_policy", "service_recovery_policy"):
        values[key] = "original"
    return values


def input_record(path):
    return dict(path=path.relative_to(ROOT).as_posix(), sha256=sha256(path.read_bytes()).hexdigest())


def archived_case(info):
    instance = load_instance(BENCHMARK / f"{info['instance']}.txt")
    if instance.sha256 != info["instance_sha256"]:
        raise ValueError("Benchmark instance changed")
    for row in (info["reference"], info["scenario"]):
        path = ROOT / row["path"]
        if sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Archived input changed")
    reference = ReferenceSchedule.load(ROOT / info["reference"]["path"], instance)
    scenario = DynamicScenario.load(ROOT / info["scenario"]["path"], instance)
    if (reference.identifier != info["reference_id"] or scenario.identifier != info["scenario_id"] or
            scenario.fleet_size != reference.fleet_size or reference.fleet_size != info["k_ref"]):
        raise ValueError("Reference, scenario, or fleet identity changed")
    return instance, reference, scenario


def job_id(index, method):
    return f"original_{index}_{method}"


def freeze():
    config = load_config(CONFIG)
    if (tuple(config["methods"]) != METHODS or config["charging_policy"] != "MP" or
            config["total_planning_time_limit"] != 5.0 or
            config["maximum_wall_seconds"] != 28800 or
            config["maximum_worker_cpu_seconds"] != 43200 or
            not config["no_enhanced_holdout"] or len(config["instances"]) != 6 or
            len(config["scenario_seeds"]) != 2):
        raise ValueError("Replication protocol must preserve five original methods and hard limits")
    path = OUTPUT / "protocol.json"
    if path.exists():
        frozen = load_json(path)
        if frozen["source_sha256"] != source_hash() or frozen["config"] != config:
            raise ValueError("Frozen replication source/config drift")
        return frozen
    scoped = ["evrp", "configs/final_cpu_replication_v1.yaml", "scripts/run_final_cpu_replication.py"]
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *scoped],
                      cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip():
        raise ValueError("Commit scientific source before freezing replication")
    history = load_json(HISTORY)["records"]
    historical = {}
    for row in history:
        key = row["size"], row["method"]
        historical[key] = max(historical.get(key, 0.0),
                              load_json(ROOT / row["raw"])["metrics"]["worker_wall_seconds"])
    cases = []
    for name in config["instances"]:
        instance = load_instance(BENCHMARK / f"{name}.txt")
        prefix = name.split("_", 1)[0]
        family = ("RC" + prefix[2] if prefix.startswith("rc") else prefix[0].upper() + prefix[1])
        reference = published_full_reference(instance, ReferenceConfig())
        if reference is None or len(reference.predecessor_departures) != len(instance.customers):
            raise ValueError(f"No full published physical reference: {name}")
        ref_path = OUTPUT / "inputs" / "references" / f"{name}.json"
        if ref_path.exists():
            raise ValueError("Unregistered replication input exists")
        reference.save(ref_path)
        for seed in config["scenario_seeds"]:
            scenario = generate(instance, reference, seed, config["dynamicity"])
            scenario_path = OUTPUT / "inputs" / "scenarios" / f"{name}_{seed}.json"
            if scenario_path.exists():
                raise ValueError("Unregistered replication scenario exists")
            scenario.save(scenario_path)
            cases.append(dict(instance=name, size=len(instance.customers), family=family,
                              seed=seed, dynamicity=config["dynamicity"],
                              instance_sha256=instance.sha256, reference_id=reference.identifier,
                              scenario_id=scenario.identifier, k_ref=reference.fleet_size,
                              reference=input_record(ref_path), scenario=input_record(scenario_path)))
    blocks = []
    for index, info in enumerate(cases):
        order = METHODS if index % 2 == 0 else tuple(reversed(METHODS))
        jobs = []
        for method in order:
            upper = min(900.0, max(60.0, 1.5 * historical[info["size"], method] + 30.0))
            jobs.append(dict(id=job_id(index, method), index=index, method=method,
                             upper_seconds=upper, historical_max_seconds=historical[info["size"], method]))
        blocks.append(dict(case_index=index, jobs=jobs))
    conservative = (config["setup_charge_seconds"] + config["analysis_reserve_seconds"] +
                    sum(job["upper_seconds"] for block in blocks for job in block["jobs"]))
    if conservative > config["maximum_wall_seconds"]:
        raise ValueError("All prespecified paired blocks exceed the eight-hour wall allowance")
    frozen = dict(config=config, selected=cases, blocks=blocks, source_sha256=source_hash(),
                  source_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                capture_output=True, text=True, check=True).stdout.strip(),
                  historical_cost_rule="1.5 x maximum matching size/method robustness worker + 30 s; floor 60, cap 900",
                  conservative_wall_upper_seconds=conservative,
                  hypothesis="Independent replication of original five-method service ranking; no enhanced-method claim",
                  primary_endpoints=["customer-weighted service", "complete-service scenarios"],
                  selection_rule="lexicographically first as-yet-unrun published-full-reference parent in each family, "
                                 "with two each at sizes 25/50/100; DoD 0.50 and unused seeds 6,7",
                  no_post_outcome_exclusions=True)
    for case in cases:
        archived_case(case)
        baseline = asdict(simulation_config(options(config, case["seed"], METHODS[0])))
        if baseline["total_planning_time_limit"] != 5.0:
            raise ValueError("Controller planning limit changed")
        for method in METHODS[1:]:
            other = asdict(simulation_config(options(config, case["seed"], method)))
            if {key for key in baseline if baseline[key] != other[key]} != {"algorithm"}:
                raise ValueError("Methods do not share all MPC and physical settings")
    save_json(path, frozen)
    return frozen


def worker(index, method):
    frozen = load_json(OUTPUT / "protocol.json")
    if frozen["source_sha256"] != source_hash():
        raise ValueError("Scientific source changed after freeze")
    config = frozen["config"]
    if index not in range(len(frozen["selected"])) or method not in METHODS:
        raise ValueError("Worker not in frozen protocol")
    info = frozen["selected"][index]
    path = OUTPUT / "raw" / f"{job_id(index, method)}.json.gz"
    if path.exists():
        raise ValueError("Never overwrite raw evidence")
    started, cpu = perf_counter(), process_time()
    try:
        instance, reference, scenario = archived_case(info)
        run_config = simulation_config(options(config, info["seed"], method))
        result = EventDrivenSimulator(instance, scenario, run_config).run()
        audit = audit_result(result, instance, scenario)
        if (not all(audit.values()) or result.metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                result.metadata["K_ref"] != info["k_ref"] or
                result.metadata["scenario_identifier"] != info["scenario_id"]):
            raise ValueError("Independent physical/information/deadline audit failed")
        result.metadata.update(independent_audit=audit, source_sha256=frozen["source_sha256"],
                               cpu_replication_protocol=identifier(frozen), isolated_worker=True)
        save_json(path, dict(job_id=job_id(index, method), result=asdict(result),
                             worker_wall_seconds=perf_counter()-started,
                             worker_cpu_seconds=process_time()-cpu))
    except Exception as exc:
        save_json(OUTPUT / "audit" / "failures" / f"{job_id(index, method)}.json",
                  dict(error_type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()))
        raise


def verify_raw(frozen, spec, raw):
    if raw["job_id"] != spec["id"]:
        raise ValueError("Worker ID mismatch")
    info = frozen["selected"][spec["index"]]
    result = raw["result"]
    meta, metrics = result["metadata"], result["metrics"]
    if (meta["source_sha256"] != frozen["source_sha256"] or
            meta["cpu_replication_protocol"] != identifier(frozen) or
            meta["scenario_identifier"] != info["scenario_id"] or
            meta["reference_schedule_identifier"] != info["reference_id"] or
            meta["K_ref"] != info["k_ref"] or meta["algorithm"] != spec["method"] or
            metrics["max_optimization_latency"] > 5.0 + 1e-6 or
            not all(meta["independent_audit"].values())):
        raise ValueError("Saved worker violates frozen identity, physics, or decision budget")


def run():
    frozen = freeze()
    budget = HardBudget(OUTPUT, frozen["config"]["maximum_wall_seconds"])
    if not budget.path.exists():
        budget.data["charged_seconds"] = frozen["config"]["setup_charge_seconds"]
        budget.data["worker_cpu_charged_seconds"] = 0.0
        budget.flush()
    manifest_path = OUTPUT / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else dict(
        status="partial", protocol_identifier=identifier(frozen), records=[])
    if manifest["protocol_identifier"] != identifier(frozen):
        raise ValueError("Manifest protocol drift")
    records = {r["id"]: r for r in manifest["records"]}
    if len(records) != len(manifest["records"]):
        raise ValueError("Duplicate saved job")
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = "0"
    environment.update({key: "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                               "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    status = "complete"
    for block in frozen["blocks"]:
        pending = [spec for spec in block["jobs"] if spec["id"] not in records]
        upper = sum(spec["upper_seconds"] for spec in pending)
        if pending and (not admit(budget.remaining(), upper, frozen["config"]["analysis_reserve_seconds"]) or
                        budget.data["worker_cpu_charged_seconds"] + upper >
                        frozen["config"]["maximum_worker_cpu_seconds"]):
            status = "budget_admission_pause"
            break
        for spec in block["jobs"]:
            path = OUTPUT / "raw" / f"{spec['id']}.json.gz"
            if spec["id"] in records:
                if sha256(path.read_bytes()).hexdigest() != records[spec["id"]]["sha256"]:
                    raise ValueError("Saved raw hash changed")
                verify_raw(frozen, spec, load_json(path))
                continue
            if path.exists():
                raise ValueError("Unmanifested raw evidence; no silent retry")
            command = [sys.executable, "-u", "-m", "scripts.run_final_cpu_replication", "--worker",
                       str(spec["index"]), spec["method"]]
            execution = budget.execute(spec["id"], command, spec["upper_seconds"],
                                       env=environment, reserve=frozen["config"]["analysis_reserve_seconds"])
            if execution is None or execution["status"] != "complete":
                status = "worker_incomplete_preserved"
                break
            raw = load_json(path)
            verify_raw(frozen, spec, raw)
            budget.data["worker_cpu_charged_seconds"] += raw["worker_cpu_seconds"]
            budget.flush()
            records[spec["id"]] = dict(id=spec["id"], index=spec["index"], method=spec["method"],
                                       raw=path.relative_to(ROOT).as_posix(),
                                       sha256=sha256(path.read_bytes()).hexdigest(), execution=execution)
            manifest.update(status="partial", records=list(records.values()),
                            completed_runs=len(records), planned_runs=60)
            save_json(manifest_path, manifest)
            print(f"replication {len(records)}/60 {spec['id']} served="
                  f"{raw['result']['metrics']['customers_served']} "
                  f"wall={execution['elapsed_seconds']:.1f}s", flush=True)
        if status != "complete":
            break
    manifest.update(status=status, records=list(records.values()), completed_runs=len(records), planned_runs=60)
    save_json(manifest_path, manifest)
    budget.flush()
    print(f"Replication {status}: {len(records)}/60; wall charge "
          f"{budget.data['charged_seconds']:.1f}/28800 s, worker CPU "
          f"{budget.data['worker_cpu_charged_seconds']:.1f}/43200 s", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--worker", nargs=2, metavar=("INDEX", "METHOD"))
    args = parser.parse_args()
    if args.worker:
        worker(int(args.worker[0]), args.worker[1])
    elif args.freeze:
        data = freeze()
        print(f"Frozen {len(data['blocks'])} scenarios / 60 method runs; upper "
              f"{data['conservative_wall_upper_seconds']:.1f}/28800 s", flush=True)
    else:
        run()
