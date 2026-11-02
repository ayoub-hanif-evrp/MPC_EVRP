"""Versioned ten-run original-method pilot; no large-campaign execution path."""

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from math import ceil
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter, process_time
import traceback
import xml.etree.ElementTree as ET

from evrp.audit import decode_result
from evrp.experiments import audit_result, load_config, simulation_config
from evrp.instance import load_instance
from evrp.reference import ReferenceConfig, ReferenceSchedule, published_full_reference
from evrp.scenario import generate
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json, verify_text_digest
from scripts.experiments.paths import artifact_path
from scripts.experiments.design_balanced_benchmark import FAMILIES, POLICIES, SIZES, family
from scripts.performance_budget import HardBudget, admit
from scripts.run_final_cpu_replication import archived_case


STUDY = "mpc_reliability_v1"
OUTPUT = ROOT / "results/research_v2" / STUDY
METHODS = ("MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS")
PILOT_CASES = ("c101_21_25", "r101_21_100")
DOD, SEED = .75, 7301
PILOT_LIMIT = 7200
SETUP, RESERVE = 300, 600
EXPOSURE = ROOT / "results/research_v2/balanced_evaluation_v1/validation/exposure_inventory_final.json"
REFERENCES = ROOT / "results/desaulniers/targeted_service_v1/reference_inventory.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def source_files():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__),
        ROOT / "scripts/performance_budget.py", ROOT / "scripts/experiments/paths.py",
        ROOT / "configs/paper_controller.yaml"]
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


def exclusive(path, data):
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def original_options(method):
    if method not in METHODS:
        raise ValueError("Pilot permits exactly the original five methods")
    base = load_config(ROOT / "configs/paper_controller.yaml")
    return dict(base, algorithm=method, dynamicity=DOD, scenario_seed=SEED,
                diagnostics=False, trace_level="summary", total_planning_time_limit=5.,
                engineering_watchdog_seconds=900., **dict.fromkeys(POLICIES, "original"))


def shared_configs():
    configs = {m: asdict(simulation_config(original_options(m))) for m in METHODS}
    first = configs[METHODS[0]]
    for method, config in configs.items():
        differences = {key for key in first if first[key] != config[key]}
        if differences != ({"algorithm"} if method != METHODS[0] else set()):
            raise ValueError("Original methods differ beyond optimizer identity")
        if config["total_planning_time_limit"] != 5 or any(config[k] != "original" for k in POLICIES):
            raise ValueError("Pilot changed original settings")
    return configs


def prepare_case(name):
    benchmark = ROOT / "data/opre.2016.1535-sm-data/instances/instances_format_1" / (name + ".txt")
    instance = load_instance(benchmark)
    inventory = load_json(REFERENCES)
    row = next(r for r in inventory["rows"] if r["instance"] == name)
    if not row["physical_witness"] or row["instance_sha256"] != instance.sha256:
        raise ValueError("Reference is missing or bound to another benchmark")
    if row.get("artifact"):
        path = ROOT / row["artifact"]
        verify_text_digest(path, row["artifact_sha256"])
        reference = ReferenceSchedule.load(path, instance)
    else:
        reference = published_full_reference(instance, ReferenceConfig())
        if reference is None:
            raise ValueError("Reference search is forbidden in this pilot")
        variant = reference.provenance.split("_")[1]
        path = ROOT / "data/opre.2016.1535-sm-data/solutions" / variant / ("solution" + name)
    if reference.identifier != row["reference_id"]:
        raise ValueError("Reference canonical identity changed")
    scenario = generate(instance, reference, SEED, DOD, "exact_count")
    if any(dict(scenario.customer_release_times)[c] > t + 1e-8
           for c, t in reference.predecessor_departures.items()):
        raise ValueError("Reference dispatch precedes a customer release")
    info = dict(instance=name, parent=name.split("_")[0], family=family(name.split("_")[0]),
                size=len(instance.customers), benchmark=benchmark.relative_to(ROOT).as_posix(),
                instance_sha256=instance.sha256, k_ref=reference.fleet_size,
                reference_source=path.relative_to(ROOT).as_posix(), reference_sha256=digest(path),
                reference_id=reference.identifier, scenario=asdict(scenario),
                scenario_id=scenario.identifier, scenario_sha256=identifier(asdict(scenario)))
    return info, instance, reference, scenario


def historical_records():
    """Yield exact bytes and frozen specs for the primary plus replication cohorts."""
    for study in ("robustness_v3", "final_cpu_paper_v1"):
        directory = ROOT / "results/desaulniers" / study
        protocol = load_json(directory / "protocol.json")
        manifest = load_json(directory / "manifest.json")
        if manifest["protocol_identifier"] != identifier(protocol) or manifest["status"] != "complete":
            raise ValueError("Historical source cohort is incomplete or its protocol changed")
        for row in manifest["records"]:
            path = ROOT / row["raw"]
            actual = digest(path)
            if actual != row.get("raw_sha256", row.get("sha256")):
                raise ValueError("Historical raw hash mismatch")
            raw = load_json(path)
            payload = raw.get("result", raw)
            yield study, protocol, row, raw, payload, actual, path.stat().st_size


def timing_model():
    observations = []
    for study, _, row, raw, result, sha, size_bytes in historical_records():
        meta, metrics = result["metadata"], result["metrics"]
        if meta["algorithm"] not in METHODS or not meta.get("isolated_worker"):
            raise ValueError("Timing source is not an original isolated worker")
        observations.append(dict(method=meta["algorithm"], size=metrics["number_of_customers"]
            if "number_of_customers" in metrics else meta["number_of_customers"],
            wall=raw.get("worker_wall_seconds", metrics.get("worker_wall_seconds")),
            cpu=raw.get("worker_cpu_seconds", metrics.get("worker_cpu_seconds")),
            bytes=size_bytes, source=row["raw"], sha256=sha, study=study))
    strata = []
    for size in SIZES:
        for method in METHODS:
            rows = [r for r in observations if (r["size"], r["method"]) == (size, method)]
            walls = [r["wall"] for r in rows if r["wall"] is not None]
            cpus = [r["cpu"] for r in rows if r["cpu"] is not None]
            if not walls or not cpus or any(v <= 0 for v in walls + cpus):
                raise ValueError("Missing measured wall/CPU timing stratum")
            cap = ceil(max(60, 2 * max(walls) + 60, 2 * max(cpus) + 60))
            strata.append(dict(size=size, method=method, cap_seconds=cap,
                wall_samples=len(walls), cpu_samples=len(cpus), max_wall=max(walls), max_cpu=max(cpus),
                storage_cap=max(65536, 2 * max(r["bytes"] for r in rows)) + 65536))
    return dict(strata=strata, samples=len(observations), source_identifier=identifier(observations),
                source_manifests={study: digest(ROOT / "results/desaulniers" / study / "manifest.json")
                                  for study in ("robustness_v3", "final_cpu_paper_v1")})


def jobs_for(cases, model, prefix="pilot"):
    table = {(r["size"], r["method"]): r for r in model["strata"]}
    jobs = []
    for index, case in enumerate(cases):
        order = METHODS if index % 2 == 0 else tuple(reversed(METHODS))
        for method in order:
            cost = table[case["size"], method]
            jobs.append(dict(id=f"{prefix}_{index}_{method}", case_index=index, method=method,
                             upper_seconds=cost["cap_seconds"], storage_cap=cost["storage_cap"]))
    return jobs


def allowance(jobs, limit=PILOT_LIMIT, storage_limit=256 * 1024**2):
    upper = SETUP + RESERVE + sum(j["upper_seconds"] + 2 for j in jobs)
    storage = 16 * 1024**2 + sum(j["storage_cap"] for j in jobs)
    return dict(admitted=upper <= limit and storage <= storage_limit, wall_limit_seconds=limit,
                worker_cpu_limit_seconds=limit, upper_seconds=upper, setup_seconds=SETUP,
                validation_reserve_seconds=RESERVE, storage_limit_bytes=storage_limit,
                storage_estimate_bytes=storage,
                rule="2x maximum matching isolated historical wall/measured CPU +60 s, floor60; no clipping; max(wall,CPU) charged; no automatic retry")


def design():
    configs = shared_configs()
    cases = [prepare_case(name)[0] for name in PILOT_CASES]
    model = timing_model()
    jobs = jobs_for(cases, model)
    exposure = load_json(EXPOSURE)
    eligible = {fam: sorted(p for p, row in exposure["dataset_parents"].items()
                           if row["family"] == fam and row["all_references_and_dynamicity_valid"])
                for fam in FAMILIES}
    if any(len(names) < 3 for names in eligible.values()):
        raise ValueError("Even the proposed exposed-parent size panel is incomplete")
    future_parents = [p for fam in FAMILIES for p in eligible[fam][:3]]
    future_cases = [prepare_case(f"{p}_21_{size}")[0] for p in future_parents for size in SIZES]
    future_jobs = jobs_for(future_cases, model, prefix="future")
    return dict(study=STUDY, role="exposed-development correctness pilot, not a confirmatory test",
                case_selection="Fixed c101_21_25 plus first R1 100-customer parent; sizes/families chosen before new outcomes, no performance ranking",
                scenario_seed=SEED, target_dod=DOD, algorithm_seed=0, configs=configs, cases=cases, jobs=jobs,
                pilot_budget=allowance(jobs), timing_model=model,
                full_future_design=dict(role="candidate exploratory comparison on exposed parents; never launched here",
                    selected_parents=future_parents, independent_parent_groups=18, benchmark_files=54,
                    jobs=future_jobs, optimizer_executions=270, cases=future_cases,
                    budget=allowance(future_jobs, limit=12 * 3600, storage_limit=1024**3),
                    exposure_inventory_sha256=digest(EXPOSURE), untouched_parents=0,
                    readiness="BLOCKED for untouched confirmation; exposed extension needs separate approval and budget",
                    estimand="Equal-weight mean across 18 parent differences, each the equal-weight mean across sizes25/50/100; paired contrasts vs Completion plus ALNS-HGS",
                    uncertainty="20000 family-stratified parent bootstrap draws seed7302, 95% descriptive CIs; carry sizes together; exploratory multiplicity and small family samples disclosed",
                    cost_comparability="Operations/distance only on matched actual served customer sets; no epoch pseudo-replication"),
                source_files=source_files(), source_sha256=identifier(source_files()),
                source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                execution="sequential one worker, fixed threads, isolated processes; machine load not certified",
                no_enhanced_variants=True, no_automatic_retry=True)


def audit_history():
    path = artifact_path(STUDY, "validation", "historical_replay.json")
    from scripts.audit_frozen_studies import source_evidence
    source = source_evidence("robustness_v3")
    cache, rows = {}, []
    for study, protocol, row, _, raw, sha, _ in historical_records():
        if study == "final_cpu_paper_v1":
            info = protocol["selected"][row["index"]]
            key = study, row["index"]
            if key not in cache:
                cache[key] = archived_case(info)
            instance, reference, scenario = cache[key]
        else:
            key = study, row["instance"], row["dynamicity"], row["seed"]
            if key not in cache:
                instance = load_instance(ROOT / "data/opre.2016.1535-sm-data/instances/instances_format_1" / (row["instance"] + ".txt"))
                reference = published_full_reference(instance, ReferenceConfig())
                if reference is None:
                    raise ValueError("Historical reference unavailable; construction forbidden")
                scenario = generate(instance, reference, row["seed"], row["dynamicity"])
                cache[key] = instance, reference, scenario
            instance, reference, scenario = cache[key]
        meta = raw["metadata"]
        if (meta["algorithm"] != row["method"] or meta["instance_sha256"] != instance.sha256 or
                meta["scenario_identifier"] != scenario.identifier or meta["K_ref"] != reference.fleet_size or
                raw["metrics"]["max_optimization_latency"] > 5 + 1e-6):
            raise ValueError("Historical identity/five-second audit failed")
        checks = audit_result(decode_result(raw), instance, scenario)
        if not all(checks.values()):
            raise ValueError("Historical physical/information replay failed")
        rows.append(dict(raw=row["raw"], sha256=sha, study=study, method=row["method"], checks=checks,
                         max_latency=raw["metrics"]["max_optimization_latency"]))
        if len(rows) % 100 == 0:
            print(f"historical physical replay {len(rows)}/510", flush=True)
    if Counter(r["study"] for r in rows) != Counter(robustness_v3=450, final_cpu_paper_v1=60):
        raise ValueError("Historical audit cohort count changed")
    exclusive(path, dict(all_passed=True, completed=len(rows), rows=rows, source_evidence=source,
                         physics_sha256=identifier({name: digest(ROOT / name) for name in
                             ("evrp/instance.py", "evrp/model.py", "evrp/reference.py", "evrp/scenario.py", "evrp/observation.py")})))
    print(f"Historical replay: {len(rows)}/510 passed")


def freeze():
    path = artifact_path(STUDY, "validation", "protocol.json")
    planned = design()
    if not planned["pilot_budget"]["admitted"] or len(planned["jobs"]) != 10:
        raise ValueError("Ten-run pilot exceeds its bounded allowance")
    tests = OUTPUT / "validation/tests.xml"
    suites = list(ET.parse(tests).getroot().iter("testsuite"))
    if not suites or sum(int(s.attrib["tests"]) for s in suites) < 1 or any(
            int(s.attrib.get("failures", 0)) + int(s.attrib.get("errors", 0)) for s in suites):
        raise ValueError("Full tests must pass before pilot freeze")
    history = OUTPUT / "validation/historical_replay.json"
    historical = load_json(history)
    if not historical["all_passed"] or historical["completed"] != 510:
        raise ValueError("Historical independent replay gate did not pass")
    planned["validation"] = dict(tests_sha256=digest(tests), tests=sum(int(s.attrib["tests"]) for s in suites),
                                historical_replay_sha256=digest(history))
    exclusive(path, dict(protocol=planned, protocol_identifier=identifier(planned)))
    print(f"Frozen 2 scenarios / 10 original-method runs; cap {planned['pilot_budget']['upper_seconds']}/{PILOT_LIMIT} seconds")


def frozen():
    data = load_json(OUTPUT / "validation/protocol.json")
    planned = data["protocol"]
    if data["protocol_identifier"] != identifier(planned) or source_files() != planned["source_files"]:
        raise ValueError("Pilot protocol or scientific source changed")
    if set(planned["configs"]) != set(METHODS):
        raise ValueError("Pilot method set changed")
    return data


def verify_result(data, spec, raw):
    planned = data["protocol"]
    info = planned["cases"][spec["case_index"]]
    result = raw["result"]
    meta = result["metadata"]
    if (raw["id"] != spec["id"] or raw["protocol_identifier"] != data["protocol_identifier"] or
            raw["config_sha256"] != identifier(planned["configs"][spec["method"]]) or
            meta["source_sha256"] != planned["source_sha256"] or meta["algorithm"] != spec["method"] or
            meta["scenario_identifier"] != info["scenario_id"] or meta["K_ref"] != info["k_ref"] or
            identifier(result["effective_config"]) != identifier(planned["configs"][spec["method"]]) or
            result["metrics"]["max_optimization_latency"] > 5 + 1e-6 or not all(raw["audit"].values())):
        raise ValueError("Pilot result violates frozen identity/config/audit gates")


def worker(index, method):
    data = frozen()
    planned = data["protocol"]
    spec = next(j for j in planned["jobs"] if (j["case_index"], j["method"]) == (index, method))
    path = OUTPUT / "raw" / (spec["id"] + ".json.gz")
    if path.exists():
        raise FileExistsError("Never overwrite a saved pilot outcome")
    started, cpu = perf_counter(), process_time()
    try:
        expected = planned["cases"][index]
        info, instance, reference, scenario = prepare_case(expected["instance"])
        if identifier(info) != identifier(expected):
            raise ValueError("Pilot benchmark/reference/scenario inputs changed")
        config = simulation_config(original_options(method))
        result = EventDrivenSimulator(instance, scenario, config).run()
        checks = audit_result(result, instance, scenario)
        if not all(checks.values()) or result.metrics["max_optimization_latency"] > 5 + 1e-6:
            raise ValueError("Pilot independent feasibility/information/five-second audit failed")
        result.metadata.update(source_sha256=planned["source_sha256"],
                               protocol_identifier=data["protocol_identifier"],
                               independent_audit=checks, sequential_worker=True,
                               timing_scope="single supervised worker; external machine load not certified")
        raw = dict(id=spec["id"], protocol_identifier=data["protocol_identifier"],
                   config_sha256=identifier(asdict(config)), audit=checks, result=asdict(result),
                   worker_wall_seconds=perf_counter() - started, worker_cpu_seconds=process_time() - cpu)
        verify_result(data, spec, raw)
        save_json(path, raw)
    except Exception as error:
        exclusive(OUTPUT / "failures" / (spec["id"] + ".json"), dict(
            id=spec["id"], protocol_identifier=data["protocol_identifier"],
            source_sha256=planned["source_sha256"], error_type=type(error).__name__,
            message=str(error), traceback=traceback.format_exc(),
            wall_seconds=perf_counter() - started, cpu_seconds=process_time() - cpu))
        raise


def _run_pilot():
    data = frozen()
    planned = data["protocol"]
    if not planned["pilot_budget"]["admitted"]:
        raise ValueError("Pilot budget was not admitted")
    budget = HardBudget(OUTPUT, PILOT_LIMIT)
    if not budget.path.exists():
        budget.data.update(charged_seconds=SETUP, worker_cpu_charged_seconds=0.)
        budget.flush()
    manifest_path = OUTPUT / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else dict(
        status="partial", protocol_identifier=data["protocol_identifier"], records=[])
    if manifest["protocol_identifier"] != data["protocol_identifier"]:
        raise ValueError("Manifest belongs to another pilot")
    saved = {row["id"]: row for row in manifest["records"]}
    if len(saved) != len(manifest["records"]):
        raise ValueError("Duplicate pilot evidence")
    env = dict(os.environ, PYTHONHASHSEED="0")
    env.update({key: "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    status = "complete"
    for index in range(2):
        block = [job for job in planned["jobs"] if job["case_index"] == index]
        pending = [job for job in block if job["id"] not in saved]
        cap = sum(job["upper_seconds"] + 2 for job in pending)
        if pending and (not admit(budget.remaining(), cap, RESERVE) or
                        budget.data["worker_cpu_charged_seconds"] + cap + RESERVE > PILOT_LIMIT):
            status = "budget_admission_pause"
            break
        for spec in block:
            path = OUTPUT / "raw" / (spec["id"] + ".json.gz")
            if spec["id"] in saved:
                if digest(path) != saved[spec["id"]]["sha256"]:
                    raise ValueError("Saved raw bytes changed")
                verify_result(data, spec, load_json(path))
                continue
            if path.exists():
                raise ValueError("Unmanifested raw outcome; preserve and review, never rerun")
            record = budget.execute(spec["id"], [sys.executable, "-u", "-m", __spec__.name,
                "--worker", str(index), spec["method"]], spec["upper_seconds"], env=env, reserve=RESERVE)
            if record is None or record["status"] != "complete":
                status = "failure_preserved_no_retry"
                failure = OUTPUT / "failures" / (spec["id"] + ".supervisor.json")
                exclusive(failure, dict(job=spec, execution=record, protocol_identifier=data["protocol_identifier"]))
                break
            raw = load_json(path)
            verify_result(data, spec, raw)
            budget.data["worker_cpu_charged_seconds"] += raw["worker_cpu_seconds"]
            budget.flush()
            saved[spec["id"]] = dict(id=spec["id"], method=spec["method"], case_index=index,
                                    raw=path.relative_to(ROOT).as_posix(), sha256=digest(path), execution=record)
            manifest.update(status="partial", records=list(saved.values()), completed_runs=len(saved), planned_runs=10)
            save_json(manifest_path, manifest)
            print(f"pilot {len(saved)}/10 {planned['cases'][index]['instance']} {spec['method']} "
                  f"served={raw['result']['metrics']['customers_served']} wall={record['elapsed_seconds']:.1f}s", flush=True)
            if sum(p.stat().st_size for p in OUTPUT.rglob("*") if p.is_file()) > planned["pilot_budget"]["storage_limit_bytes"]:
                status = "storage_limit_pause"
                break
        if status != "complete":
            break
    manifest.update(status=status, records=list(saved.values()), completed_runs=len(saved), planned_runs=10)
    save_json(manifest_path, manifest)
    budget.flush()
    print(f"Pilot {status}: {len(saved)}/10; charged {budget.data['charged_seconds']:.1f}/{PILOT_LIMIT}s", flush=True)


def run_pilot():
    frozen()
    lock = OUTPUT / "supervisor.lock"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with lock.open("x", encoding="ascii") as stream:
        stream.write(str(os.getpid()))
    try:
        _run_pilot()
    finally:
        lock.unlink()


def report():
    data = frozen()
    planned = data["protocol"]
    manifest = load_json(OUTPUT / "manifest.json")
    rows, served_sets = [], {}
    for saved in manifest["records"]:
        spec = next(j for j in planned["jobs"] if j["id"] == saved["id"])
        path = ROOT / saved["raw"]
        if digest(path) != saved["sha256"]:
            raise ValueError("Cannot analyze altered pilot evidence")
        raw = load_json(path)
        verify_result(data, spec, raw)
        info, instance, reference, scenario = prepare_case(planned["cases"][spec["case_index"]]["instance"])
        physical = audit_result(decode_result(raw["result"]), instance, scenario)
        if physical != raw["audit"] or not all(physical.values()):
            raise ValueError("Saved pilot failed independent second replay")
        result = raw["result"]
        metrics = result["metrics"]
        served = sorted(s["served"] for s in result["steps"] if s["served"])
        served_sets[spec["case_index"], spec["method"]] = served
        charging = [s for s in result["steps"] if s["action"]["kind"] == "charge"]
        rows.append(dict(id=spec["id"], instance=info["instance"], parent=info["parent"],
            case_index=spec["case_index"], method=spec["method"], served=len(served), size=info["size"],
            complete=len(served) == info["size"], distance=metrics["total_distance"],
            charging_time=sum(s["after"]["charging_time"] - s["before"]["charging_time"] for s in charging),
            charging_visits=len(charging), charged_energy=sum(s["energy_charged"] for s in charging),
            travel_energy=sum(s["before"]["battery"] + s["energy_charged"] - s["after"]["battery"] for s in result["steps"]),
            evs=metrics["vehicles_activated"], wall=raw["worker_wall_seconds"], cpu=raw["worker_cpu_seconds"],
            max_latency=metrics["max_optimization_latency"], deadline_events=metrics["total_deadline_events"],
            validated_fallbacks=metrics["deadline_fallback_count"],
            initialization_fallbacks=metrics["optimizer_initialization_fallbacks"], audit_passed=True,
            physical_violations=sum(metrics.get(k, 0) for k in ("battery_violations", "capacity_violations",
                "time_window_violations", "duplicate_service_violations", "hidden_information_violations"))))
    totals = {method: sum(r["served"] for r in rows if r["method"] == method) for method in METHODS}
    full = manifest["status"] == "complete" and len(rows) == 10
    winners = [m for m in METHODS if totals[m] == max(totals.values())] if full else []
    comparable = {str(i): len({identifier(served_sets[i, m]) for m in METHODS if (i, m) in served_sets}) == 1
                  and all((i, m) in served_sets for m in METHODS) for i in range(2)}
    output = dict(status=manifest["status"], completed=len(rows), planned=10, records=rows,
                  winners_by_customer_service=winners, totals_served=totals,
                  operating_metrics_comparable_across_all_five=comparable,
                  protocol_identifier=data["protocol_identifier"],
                  no_population_superiority_claim=True, budget=load_json(OUTPUT / "budget.json"))
    exclusive(artifact_path(STUDY, "validation", "pilot_results.json"), output)
    lines = ["# Original five-method correctness pilot", "",
        f"Status: {manifest['status']}; {len(rows)}/10 runs. Two preselected exposed development scenarios,",
        "target DoD .75, seed7301. This pilot cannot establish population superiority.", "",
        "| Instance | Method | Served | EVs | Wall s | CPU s | Max decision s | Deadline events | Audit |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    lines.extend(f"| {r['instance']} | {r['method']} | {r['served']}/{r['size']} | {r['evs']} | "
                 f"{r['wall']:.2f} | {r['cpu']:.2f} | {r['max_latency']:.3f} | {r['deadline_events']} | pass |" for r in rows)
    lines += ["", f"Highest total customer service on these two cases only: {', '.join(winners) or 'incomplete panel'}.",
              "", "## Operating metrics", "",
              "Individual operating measurements below are descriptive. Compare or rank them only",
              "within scenarios with identical served sets. Full served-set comparison is in JSON.", "",
              "| Instance | Method | Distance | Charge time | Charge visits | Charged energy | Travel energy |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    lines.extend(f"| {r['instance']} | {r['method']} | {r['distance']:.2f} | {r['charging_time']:.2f} | "
                 f"{r['charging_visits']} | {r['charged_energy']:.2f} | {r['travel_energy']:.2f} |" for r in rows)
    lines += ["", "## Limits", "", "Original ALNS/HGS/ACS still have their preserved expired-initialization edge defect.",
              "The separately named ALNS safe-initialization correction was not substituted into this pilot.",
              "A deadline event is not automatically a failed physical plan; validated fallback counts are retained.",
              "Timing is sequential-worker timing, not certification of an otherwise idle machine.",
              "The full future panel is exposed and exceeds the default budget; it was not launched.", ""]
    path = artifact_path(STUDY, "validation", "RESULTS.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))
    print(f"Independent pilot replay: {len(rows)}/10; observed service leaders {winners}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--audit-history", action="store_true")
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--run-pilot", action="store_true")
    action.add_argument("--report", action="store_true")
    action.add_argument("--worker", nargs=2, metavar=("INDEX", "METHOD"))
    args = parser.parse_args()
    if args.audit_history:
        audit_history()
    elif args.freeze:
        freeze()
    elif args.run_pilot:
        run_pilot()
    elif args.report:
        report()
    elif args.worker:
        worker(int(args.worker[0]), args.worker[1])
    else:
        planned = design()
        print(json.dumps(dict(cases=list(PILOT_CASES), methods=list(METHODS), pilot_budget=planned["pilot_budget"],
            future_parents=planned["full_future_design"]["selected_parents"],
            future_budget=planned["full_future_design"]["budget"],
            full_benchmark_readiness=planned["full_future_design"]["readiness"]), indent=2))


if __name__ == "__main__":
    main()
