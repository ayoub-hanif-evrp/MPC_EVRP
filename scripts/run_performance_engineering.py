"""Predeclared two-hour engineering pilot; never resumes Reliability V2 or opens holdout."""

import argparse
from hashlib import sha256
from pathlib import Path
import os
import shutil
import subprocess
import sys
from time import perf_counter

from evrp.experiments import load_config, simulation_config
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.performance_budget import HardBudget, admit
from scripts.performance_engineering_worker import OUTPUT, load_case, options
from scripts.run_desaulniers_campaign import CONFIG as BASE_CONFIG, options as baseline_options

CONFIG = ROOT/"configs/performance_engineering_v1.yaml"
ARCHIVE = ROOT/"results/desaulniers/targeted_service_v1"


def source_hash():
    paths = sorted((ROOT/"evrp").rglob("*.py")) + [Path(__file__), CONFIG,
        ROOT/"scripts/performance_engineering_worker.py", ROOT/"scripts/performance_budget.py",
        ROOT/"scripts/run_desaulniers_campaign.py", ROOT/"scripts/run_desaulniers_pilot.py",
        ROOT/"configs/paper_controller.yaml", BASE_CONFIG]
    return identifier({p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in paths})


def archive_input(row, kind):
    source = ROOT/row["artifact"]
    if sha256(source.read_bytes()).hexdigest() != row["sha256"]:
        raise ValueError("Historical exact input hash changed")
    target = writable_path(OUTPUT/"inputs"/kind/source.name)
    if target.exists():
        if target.read_bytes() != source.read_bytes():
            raise ValueError("New input archive conflict")
    else:
        shutil.copyfile(source, target)
    return dict(path=target.relative_to(ROOT).as_posix(), sha256=row["sha256"])


def job(kind, index, method, variant, upper):
    return dict(id=f"{kind}_{index}_{method}_{variant}", kind=kind, case_index=index,
                method=method, variant=variant, upper_seconds=upper)


def make_blocks(config, historical):
    blocks = []
    for i, _ in enumerate(config["cases"]):
        blocks.append(dict(id=f"micro_{i}", stage="engineering", jobs=[
            job("micro", i, "MPC_COMPLETION", v, config["micro_upper_seconds"]) for v in config["micro_variants"]]))
        for kind in ("profile", "allocation"):
            blocks.append(dict(id=f"{kind}_{i}", stage="engineering", jobs=[
                job(kind, i, "MPC_COMPLETION", v, config[f"{kind}_upper_seconds"]) for v in config["variants"]]))
        for method in config["methods"][1:]:
            blocks.append(dict(id=f"optimizer_profile_{i}_{method}",stage="engineering",jobs=[
                job("optimizer_profile",i,method,v,config["optimizer_profile_upper_seconds"]) for v in config["variants"]]))
    for i, case in enumerate(config["cases"]):
        for j, method in enumerate(config["methods"]):
            value = historical[i, method]["seconds"]
            upper = max(config["worker_floor_seconds"], config["historical_cost_factor"]*value+
                        config["worker_startup_margin_seconds"])
            variants = config["variants"] if (i+j) % 2 == 0 else list(reversed(config["variants"]))
            blocks.append(dict(id=f"pilot_{i}_{method}", stage="pilot", jobs=[
                job("pilot", i, method, v, upper) for v in variants]))
    return blocks


def freeze():
    config = load_config(CONFIG)
    if config["maximum_total_seconds"] > 7200 or not config["no_automatic_holdout"]:
        raise ValueError("User authorized a two-hour engineering study only, with no automatic holdout")
    path = OUTPUT/"protocol.json"
    if path.exists():
        result = load_json(path)
        if result["source_sha256"] != source_hash() or result["config"] != config:
            raise ValueError("Frozen performance source or protocol drift")
        return result
    scientific = ["evrp", str(CONFIG.relative_to(ROOT)), "scripts/run_performance_engineering.py",
                  "scripts/performance_engineering_worker.py", "scripts/performance_budget.py"]
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *scientific],
                      cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip():
        raise ValueError("Commit scientific source before freezing the reproducible engineering protocol")
    old_protocol = load_json(ARCHIVE/"development/protocol.json")
    previous = old_protocol["scientific"]
    inputs = previous["inputs"]
    raw_manifest = load_json(ARCHIVE/"development/manifest.json")
    historical_manifest = load_json(ROOT/"results/desaulniers/development_campaign/manifest.json")
    cases, historical = [], {}
    for i, case in enumerate(config["cases"]):
        index, old = next((j,r) for j,r in enumerate(previous["cases"]) if r["case"] == case)
        reference = next(r for r in inputs if r["kind"] == "reference_schedules" and r["identifier"] == old["reference_id"]
                         and r["instance"] == case[0])
        scenario = next(r for r in inputs if r["kind"] == "scenarios" and r["identifier"] == old["scenario_id"])
        corpus_raw = next(r for r in raw_manifest["records"] if r["case_index"] == index and
                          r["method"] == "MPC_COMPLETION" and r["variant"] == "original")
        cases.append(dict(case=case, instance_sha256=old["instance_sha256"], scenario_id=old["scenario_id"],
                          reference_id=old["reference_id"], k_ref=old["k_ref"],
                          scenario=archive_input(scenario,"scenarios"), reference=archive_input(reference,"references"),
                          micro_raw=dict(path=corpus_raw["raw"],sha256=corpus_raw["raw_sha256"]),
                          base_options=baseline_options(load_config(BASE_CONFIG), *case, "MPC_COMPLETION")))
        for method in config["methods"]:
            row = next(r for r in historical_manifest["records"] if r["instance"] == case[0] and
                       r["dynamicity"] == case[1] and r["seed"] == case[2] and r["method"] == method)
            raw = ROOT/row["raw"]
            if sha256(raw.read_bytes()).hexdigest() != row["raw_sha256"]:
                raise ValueError("Historical cost evidence changed")
            result = load_json(raw)
            if result["metadata"]["scenario_identifier"] != old["scenario_id"]:
                raise ValueError("Historical cost estimate is not the identical input")
            historical[i, method] = dict(seconds=result["metrics"]["worker_wall_seconds"],
                                         raw=row["raw"],sha256=row["raw_sha256"])
    blocks = make_blocks(config, historical)
    estimate = sum(j["upper_seconds"] for b in blocks for j in b["jobs"])+config["final_report_reserve_seconds"]
    if estimate > config["maximum_total_seconds"]:
        save_json(OUTPUT/"admission_refused.json",dict(estimated_upper_seconds=estimate,
                  allowance=config["maximum_total_seconds"],reason="Oversized campaign; explicit new authorization is required"))
        raise ValueError("Planned job upper allowances exceed authorized budget; no workers launched")
    result = dict(config=config, cases=cases, blocks=blocks, source_sha256=source_hash(),
                  source_commit=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),
                  historical_costs=[dict(case_index=k[0],method=k[1],**v) for k,v in historical.items()],
                  planned_jobs=sum(len(b["jobs"]) for b in blocks), planned_simulations=30,
                  estimated_upper_seconds_including_report=estimate,
                  notes="Three previously seen development parents, not a new paper holdout. "
                        "Full original engine parameters and five seconds unchanged. Paired order alternates. "
                        "Profiles/allocation are separate from unprofiled pilot outcomes. No early-stop or event-suppression policy.")
    for i in range(len(cases)):
        for method in config["methods"]:
            baseline=simulation_config(options(result,i,method,"original"))
            if baseline.parallel_agents or baseline.total_planning_time_limit!=5:
                raise ValueError("Workers must be sequential with the original five-second limit")
            from dataclasses import asdict
            for variant in config["micro_variants"]:
                other=simulation_config(options(result,i,method,variant))
                a,b=asdict(baseline),asdict(other)
                if {k for k in a if a[k]!=b[k]}-{"proposal_cache_policy"}:
                    raise ValueError("Performance variant changed algorithm, physics, objective or budget")
    save_json(path, result)
    return result


def raw_path(job_id):
    return OUTPUT/"raw"/f"{job_id}.json.gz"


def verify_raw(raw, protocol, spec):
    if (raw["protocol_identifier"] != identifier(protocol) or raw["job_id"] != spec["id"] or
            raw["variant"] != spec["variant"] or raw["case_index"] != spec["case_index"]):
        raise ValueError("Worker identity outside protocol")
    if spec["kind"] in {"pilot","profile"}:
        r, info = raw["result"], protocol["cases"][spec["case_index"]]
        expected = simulation_config(options(protocol,spec["case_index"],spec["method"],spec["variant"]))
        from dataclasses import asdict
        if (identifier(r["effective_config"]) != identifier(asdict(expected)) or
                r["metadata"]["scenario_identifier"] != info["scenario_id"] or r["metadata"]["K_ref"] != info["k_ref"] or
                r["metrics"]["max_optimization_latency"] > 5+1e-6 or not all(r["metadata"]["independent_audit"].values())):
            raise ValueError("Scientific, budget or independent audit violation")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze",action="store_true")
    parser.add_argument("--stage",choices=("engineering","pilot","all"),default="all")
    args = parser.parse_args()
    protocol = freeze()
    if args.freeze:
        return print(f"Frozen {protocol['planned_jobs']} jobs: 30 unprofiled pilot simulations plus bounded diagnostics; upper allowances {protocol['estimated_upper_seconds_including_report']:.1f}/7200 s")
    budget = HardBudget(OUTPUT, protocol["config"]["maximum_total_seconds"])
    manifest_path = OUTPUT/"manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else dict(protocol_identifier=identifier(protocol),records=[],status="partial")
    if manifest["protocol_identifier"] != identifier(protocol):
        raise ValueError("Performance manifest drift")
    records = {r["id"]:r for r in manifest["records"]}
    if len(records) != len(manifest["records"]):
        raise ValueError("Duplicate recorded job")
    env = dict(os.environ)
    env.update({k:"1" for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS")})
    status = "complete"
    for block in protocol["blocks"]:
        if args.stage != "all" and block["stage"] != args.stage:
            continue
        if block["stage"] == "pilot":
            for i in range(len(protocol["cases"])):
                checks = []
                for variant in protocol["config"]["micro_variants"]:
                    job_id = f"micro_{i}_MPC_COMPLETION_{variant}"
                    if job_id not in records:
                        raise ValueError("Pilot requires all predeclared correctness microbenchmarks")
                    checks.append([p["checksum"] for p in load_json(raw_path(job_id))["fixed_work"]["phases"]])
                if any(v != checks[0] for v in checks[1:]):
                    raise ValueError("Fixed-work mathematical mismatch: pilot must not launch")
        pending = [j for j in block["jobs"] if j["id"] not in records]
        if pending and not admit(budget.remaining(),sum(j["upper_seconds"] for j in pending),protocol["config"]["final_report_reserve_seconds"]):
            status = "budget_admission_pause"
            print(f"Refused block {block['id']}: insufficient remaining complete-block allowance",flush=True)
            break
        for spec in block["jobs"]:
            job_id = spec["id"]
            path = raw_path(job_id)
            if job_id in records:
                if sha256(path.read_bytes()).hexdigest() != records[job_id]["sha256"]:
                    raise ValueError("Saved raw changed")
                verify_raw(load_json(path),protocol,spec)
                continue
            if path.exists():
                raise ValueError("Unmanifested evidence preserved; no silent rerun")
            command = [sys.executable,"-u","-m","scripts.performance_engineering_worker",spec["kind"],
                       str(spec["case_index"]),spec["method"],spec["variant"]]
            execution = budget.execute(job_id,command,spec["upper_seconds"],env=env,
                                       reserve=protocol["config"]["final_report_reserve_seconds"])
            if execution is None or execution["status"] != "complete":
                status = "incomplete_preserved"
                break
            raw = load_json(path)
            verify_raw(raw,protocol,spec)
            records[job_id] = dict(id=job_id,kind=spec["kind"],case_index=spec["case_index"],method=spec["method"],
                                   variant=spec["variant"],raw=path.relative_to(ROOT).as_posix(),
                                   sha256=sha256(path.read_bytes()).hexdigest(), execution=execution)
            manifest.update(records=list(records.values()),completed_jobs=len(records),planned_jobs=protocol["planned_jobs"],status="partial")
            save_json(manifest_path,manifest)
            print(f"{len(records)}/{protocol['planned_jobs']} {job_id}: {execution['elapsed_seconds']:.2f}s, CPU {execution['cpu_seconds']}",flush=True)
        if status == "incomplete_preserved":
            break
    if args.stage == "engineering" and status == "complete":
        status = "engineering_complete_pilot_not_started"
    manifest.update(status=status,records=list(records.values()),completed_jobs=len(records),planned_jobs=protocol["planned_jobs"])
    save_json(manifest_path,manifest)
    budget.flush()
    # Final audit/render is itself a budgeted child, not unbounded work after the cap.
    result = budget.execute("final_report_"+str(len(records)),[sys.executable,"-u","-m","scripts.report_performance_engineering"],
                            protocol["config"]["final_report_reserve_seconds"],env=env,reserve=0)
    if result is None or result["status"] != "complete":
        print("Reporting allowance exhausted or reporting failed; preserved evidence remains available",flush=True)
    print(f"Performance study {status}; charged {budget.data['charged_seconds']:.2f}s of 7200; no holdout or Reliability V2 restart",flush=True)


if __name__ == "__main__":
    lock=writable_path(OUTPUT/"execution.lock")
    descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    with os.fdopen(descriptor,"w",encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    try:
        main()
    finally:
        lock.unlink()
