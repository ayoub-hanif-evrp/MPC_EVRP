"""Frozen paired development ablation; never selects on independent results."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter, process_time
import traceback

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json
from scripts.performance_budget import HardBudget, admit
from scripts.run_desaulniers_campaign import options as development_options
from scripts.run_desaulniers_pilot import VIOLATIONS, family_of


CONFIG = ROOT / "configs/final_cpu_development_v1.yaml"
OUTPUT = ROOT / "results/desaulniers/final_cpu_development_v1"
VARIANTS = {
    "original": {},
    "recovery": {"constructor_policy": "urgency_recovery_v1",
                 "service_recovery_policy": "critical_insert_v1"},
    "first_action": {"first_action_policy": "service_guard_v1"},
    "quality": {"quality_policy": "epsilon_route_v1"},
    "cpu": {"proposal_cache_policy": "incremental_v1"},
    "combined": {"constructor_policy": "urgency_recovery_v1",
                 "service_recovery_policy": "critical_insert_v1",
                 "first_action_policy": "service_guard_v1",
                 "quality_policy": "epsilon_route_v1",
                 "proposal_cache_policy": "incremental_v1"},
}
ABLATION_CASES = frozenset({0, 2, 4})


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__), CONFIG,
        ROOT / "configs/paper_controller.yaml", ROOT / "scripts/run_desaulniers_campaign.py",
        ROOT / "scripts/run_desaulniers_pilot.py", ROOT / "scripts/performance_budget.py"]
    return identifier({path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                       for path in paths})


def run_options(config, case, method, variant):
    opts = development_options(config, case, config["dynamicity"], config["scenario_seed"], method)
    opts.update(study="final_cpu_development_v1", **VARIANTS[variant])
    return opts


def job_id(index, method, variant):
    return f"dev_{index}_{method}_{variant}"


def freeze():
    config = load_config(CONFIG)
    if (config["charging_policy"] != "MP" or config["total_planning_time_limit"] != 5.0 or
            config["maximum_wall_seconds"] != 21600 or config["maximum_worker_cpu_seconds"] != 36000 or
            len(config["instances"]) != 6 or len(config["methods"]) != 5 or
            set(config["methods"]) != {"MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"} or
            sorted(int(name.rsplit("_", 1)[1]) for name in config["instances"]) != [25, 25, 50, 50, 100, 100] or
            {family_of(name) for name in config["instances"]} != {"C1", "C2", "R1", "R2", "RC1", "RC2"}):
        raise ValueError("Development design differs from the fixed six-family, five-method grid")
    path = OUTPUT / "protocol.json"
    if path.exists():
        frozen = load_json(path)
        if frozen["source_sha256"] != source_hash() or frozen["config"] != config:
            raise ValueError("Frozen development source/config drift")
        return frozen
    scoped = ["evrp", CONFIG.relative_to(ROOT).as_posix(), Path(__file__).relative_to(ROOT).as_posix()]
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *scoped],
                      cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip():
        raise ValueError("Commit scientific source before freezing development")
    cases = []
    blocks = []
    historical = {}
    for row in load_json(ROOT / "results/desaulniers/robustness_v3/manifest.json")["records"]:
        key = row["size"], row["method"]
        historical.setdefault(key, []).append(load_json(ROOT / row["raw"])["metrics"]["worker_wall_seconds"])
    for index, name in enumerate(config["instances"]):
        instance, reference, scenario, _ = prepare(name, run_options(config, name, config["methods"][0], "original"))
        reference_path = OUTPUT / "inputs/references" / f"{name}.json"
        scenario_path = OUTPUT / "inputs/scenarios" / f"{name}_{config['scenario_seed']}.json"
        if reference_path.exists() or scenario_path.exists():
            raise ValueError("Unregistered development input")
        reference.save(reference_path)
        scenario.save(scenario_path)
        cases.append(dict(instance=name, family=family_of(name), size=len(instance.customers),
                          instance_sha256=instance.sha256, reference_id=reference.identifier,
                          scenario_id=scenario.identifier, k_ref=reference.fleet_size,
                          reference=dict(path=reference_path.relative_to(ROOT).as_posix(),
                                         sha256=sha256(reference_path.read_bytes()).hexdigest()),
                          scenario=dict(path=scenario_path.relative_to(ROOT).as_posix(),
                                        sha256=sha256(scenario_path.read_bytes()).hexdigest())))
        methods = config["methods"] if index % 2 == 0 else list(reversed(config["methods"]))
        variants = tuple(VARIANTS) if index in ABLATION_CASES else ("original", "combined")
        jobs = [dict(id=job_id(index, method, variant), index=index, method=method, variant=variant,
                     upper_seconds=min(600, max(30, 1.25 * sorted(historical[len(instance.customers), method])[
                         int(.9 * (len(historical[len(instance.customers), method]) - 1))] + 20)))
                for variant in variants for method in methods]
        blocks.append(dict(case_index=index, jobs=jobs))
    frozen = dict(config=config, variants=VARIANTS, selected=cases, blocks=blocks,
                  source_sha256=source_hash(),
                  source_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.strip(),
                  purpose="balanced development ablation, not independent confirmation",
                  hypothesis="Test service-safe recovery, first-action protection, equal-service quality and CPU cache",
                  primary_endpoints=["customer-weighted service", "complete-service scenarios"],
                  design="Original and combined on all six family/size cases; four component ablations "
                         "on fixed cases 0, 2 and 4 (one each at 25/50/100 customers).",
                  watchdog_rule="Historical size-method p90 x 1.25 + 20 s, floor 30 s, cap 600 s",
                  selection_rule="Promote only a variant with no aggregate service loss, no repeated family harm, "
                                 "and a useful service or conditional-quality gain; otherwise keep original",
                  no_post_outcome_exclusions=True)
    save_json(path, frozen)
    return frozen


def worker(index, method, variant):
    frozen = load_json(OUTPUT / "protocol.json")
    if frozen["source_sha256"] != source_hash():
        raise ValueError("Scientific source changed after freeze")
    config = frozen["config"]
    if index not in range(len(frozen["selected"])) or method not in config["methods"] or variant not in VARIANTS:
        raise ValueError("Worker absent from frozen protocol")
    info = frozen["selected"][index]
    path = OUTPUT / "raw" / f"{job_id(index, method, variant)}.json.gz"
    if path.exists():
        raise ValueError("Never overwrite raw evidence")
    started, cpu = perf_counter(), process_time()
    try:
        instance, reference, scenario, _ = prepare(info["instance"], run_options(config, info["instance"], method, variant))
        if (instance.sha256 != info["instance_sha256"] or reference.identifier != info["reference_id"] or
                scenario.identifier != info["scenario_id"] or reference.fleet_size != info["k_ref"]):
            raise ValueError("Frozen scenario or fleet mismatch")
        for item in ("reference", "scenario"):
            archived = ROOT / info[item]["path"]
            if sha256(archived.read_bytes()).hexdigest() != info[item]["sha256"]:
                raise ValueError("Archived input hash mismatch")
        opts = run_options(config, info["instance"], method, variant)
        result = EventDrivenSimulator(instance, scenario, simulation_config(opts)).run()
        audit = audit_result(result, instance, scenario)
        if (not all(audit.values()) or any(result.metrics[key] for key in VIOLATIONS) or
                result.metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                result.metadata["K_ref"] != info["k_ref"]):
            raise ValueError("Physical, information, or deadline audit failed")
        result.metadata.update(independent_audit=audit, source_sha256=frozen["source_sha256"],
                               development_protocol=identifier(frozen), variant=variant,
                               isolated_worker=True)
        save_json(path, dict(job_id=job_id(index, method, variant), result=asdict(result),
                             worker_wall_seconds=perf_counter() - started,
                             worker_cpu_seconds=process_time() - cpu))
    except Exception as error:
        save_json(OUTPUT / "audit/failures" / f"{job_id(index, method, variant)}.json",
                  dict(error_type=type(error).__name__, message=str(error), traceback=traceback.format_exc()))
        raise


def verify_raw(frozen, spec, raw):
    info = frozen["selected"][spec["index"]]
    meta, metrics = raw["result"]["metadata"], raw["result"]["metrics"]
    if (raw["job_id"] != spec["id"] or meta["source_sha256"] != frozen["source_sha256"] or
            meta["development_protocol"] != identifier(frozen) or meta["scenario_identifier"] != info["scenario_id"] or
            meta["reference_schedule_identifier"] != info["reference_id"] or meta["K_ref"] != info["k_ref"] or
            meta["algorithm"] != spec["method"] or meta["variant"] != spec["variant"] or
            metrics["max_optimization_latency"] > 5.0 + 1e-6 or
            not all(meta["independent_audit"].values())):
        raise ValueError("Saved worker failed frozen identity or audit")


def run():
    frozen = freeze()
    config = frozen["config"]
    budget = HardBudget(OUTPUT, config["maximum_wall_seconds"])
    manifest_path = OUTPUT / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else dict(
        status="partial", protocol_identifier=identifier(frozen), records=[])
    if manifest["protocol_identifier"] != identifier(frozen):
        raise ValueError("Development manifest protocol mismatch")
    records = {row["id"]: row for row in manifest["records"]}
    if len(records) != len(manifest["records"]):
        raise ValueError("Duplicate development job")
    env = dict(os.environ, PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    status = "complete"
    for block in frozen["blocks"]:
        pending = [spec for spec in block["jobs"] if spec["id"] not in records]
        # Conservative fixed admission based on the per-worker watchdog, not optimistic mean runtime.
        upper = sum(spec["upper_seconds"] for spec in pending)
        if pending and (not admit(budget.remaining(), upper, config["analysis_reserve_seconds"]) or
                        budget.data.get("worker_cpu_charged_seconds", 0) + upper >
                        config["maximum_worker_cpu_seconds"]):
            status = "budget_admission_pause"
            break
        for spec in block["jobs"]:
            path = OUTPUT / "raw" / f"{spec['id']}.json.gz"
            if spec["id"] in records:
                if sha256(path.read_bytes()).hexdigest() != records[spec["id"]]["sha256"]:
                    raise ValueError("Saved development raw hash changed")
                verify_raw(frozen, spec, load_json(path))
                continue
            if path.exists():
                raise ValueError("Unmanifested raw evidence; no silent retry")
            execution = budget.execute(spec["id"], [sys.executable, "-u", "-m", "scripts.run_final_cpu_development",
                              "--worker", str(spec["index"]), spec["method"], spec["variant"]],
                              spec["upper_seconds"], env=env, reserve=config["analysis_reserve_seconds"])
            if execution is None or execution["status"] != "complete":
                status = "worker_incomplete_preserved"
                break
            raw = load_json(path)
            verify_raw(frozen, spec, raw)
            budget.data["worker_cpu_charged_seconds"] = (budget.data.get("worker_cpu_charged_seconds", 0) +
                                                          raw["worker_cpu_seconds"])
            budget.flush()
            records[spec["id"]] = dict(id=spec["id"], index=spec["index"], method=spec["method"],
                                       variant=spec["variant"], raw=path.relative_to(ROOT).as_posix(),
                                       sha256=sha256(path.read_bytes()).hexdigest(), execution=execution)
            manifest.update(status="partial", records=list(records.values()), completed_runs=len(records),
                            planned_runs=120)
            save_json(manifest_path, manifest)
            print(f"development {len(records)}/120 {spec['id']} served="
                  f"{raw['result']['metrics']['customers_served']}", flush=True)
        if status != "complete":
            break
    manifest.update(status=status, records=list(records.values()), completed_runs=len(records), planned_runs=120)
    save_json(manifest_path, manifest)
    print(f"Development {status}: {len(records)}/120; charged wall {budget.data['charged_seconds']:.1f}/21600 s",
          flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--worker", nargs=3, metavar=("INDEX", "METHOD", "VARIANT"))
    args = parser.parse_args()
    if args.worker:
        worker(int(args.worker[0]), args.worker[1], args.worker[2])
    elif args.freeze:
        print(f"Frozen {len(freeze()['blocks'])} balanced development cases / 120 runs")
    else:
        run()
