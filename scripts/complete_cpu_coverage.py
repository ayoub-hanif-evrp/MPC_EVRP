"""Prospective missing-family CPU-cache comparison with a mission-wide allowance."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter, process_time

from evrp.audit import decode_result
from evrp.experiments import audit_result, simulation_config
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json
from scripts.performance_budget import HardBudget, admit
from scripts.run_final_cpu_development import OUTPUT as DEVELOPMENT, run_options, source_hash
from scripts.run_final_cpu_replication import archived_case


OUTPUT = DEVELOPMENT / "cpu_coverage"
PAPER = ROOT / "results/desaulniers/final_cpu_paper_v1"
INDICES = (1, 3, 5)
WALL_LIMIT = 8 * 3600
CPU_LIMIT = 12 * 3600
RESERVE = 300


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def prior_accounting():
    """Count every attempted worker, including the preserved technical timeout."""
    rows = []
    for directory in (PAPER, DEVELOPMENT, DEVELOPMENT / "technical_extension"):
        path = directory / "budget.json"
        budget = load_json(path)
        if any(job["status"] == "running" for job in budget["jobs"]):
            raise ValueError("Another final-mission worker is still running")
        cpu = sum(job["cpu_seconds"] if job.get("cpu_seconds") is not None
                  else job["elapsed_seconds"] for job in budget["jobs"])
        rows.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=digest(path),
                         charged_seconds=budget["charged_seconds"], worker_cpu_seconds=cpu,
                         attempts=len(budget["jobs"])))
    path = ROOT / "results/desaulniers/two_worker_probe_v1/manifest.json"
    probe = load_json(path)
    if probe["status"] != "complete":
        raise ValueError("Technical probe is not complete")
    rows.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=digest(path),
                     charged_seconds=probe["total_elapsed_seconds"],
                     worker_cpu_seconds=sum(row["cpu_seconds"] for mode in probe["modes"].values()
                                            for row in mode["results"]), attempts=4))
    return rows


def allowances(accounting):
    wall = WALL_LIMIT - sum(row["charged_seconds"] for row in accounting)
    cpu = CPU_LIMIT - sum(row["worker_cpu_seconds"] for row in accounting)
    if wall <= 0 or cpu <= 0:
        raise ValueError("The final mission compute allowance is exhausted")
    return min(wall, cpu, 4200.0)


def scientific_hash():
    return identifier(dict(inherited_source=source_hash(), runner=digest(Path(__file__))))


def freeze():
    path = OUTPUT / "protocol.json"
    accounting = prior_accounting()
    parent = load_json(DEVELOPMENT / "protocol.json")
    manifest = load_json(DEVELOPMENT / "manifest.json")
    if parent["source_sha256"] != source_hash() or manifest["completed_runs"] != 120:
        raise ValueError("The completed source-frozen development study is required")
    if path.exists():
        frozen = load_json(path)
        if (frozen["source_sha256"] != scientific_hash() or frozen["prior_accounting"] != accounting or
                frozen["parent_protocol"] != identifier(parent) or
                frozen["parent_manifest_sha256"] != digest(DEVELOPMENT / "manifest.json")):
            raise ValueError("CPU coverage source or prior evidence drift")
        return frozen
    if (OUTPUT / "raw").exists() and any((OUTPUT / "raw").iterdir()):
        raise ValueError("Unregistered CPU coverage evidence exists")
    jobs = []
    for index in INDICES:
        for method in parent["config"]["methods"]:
            original = next(row for row in manifest["records"] if row["index"] == index
                            and row["method"] == method and row["variant"] == "original")
            baseline_path = ROOT / original["raw"]
            if digest(baseline_path) != original["sha256"]:
                raise ValueError("Original development raw changed")
            baseline = load_json(baseline_path)
            jobs.append(dict(id=f"cpu_{index}_{method}", index=index, method=method,
                             baseline=original["raw"], baseline_sha256=original["sha256"],
                             upper_seconds=min(900.0, max(60.0, 2 * baseline["worker_wall_seconds"] + 30))))
    limit = allowances(accounting)
    if not admit(limit, sum(job["upper_seconds"] + 2 for job in jobs), RESERVE):
        raise ValueError("The entire 15-run block cannot fit the remaining mission allowance")
    frozen = dict(study="final_cpu_missing_family_coverage_v1", stage="exploratory_development",
                  source_sha256=scientific_hash(), parent_protocol=identifier(parent),
                  parent_manifest_sha256=digest(DEVELOPMENT / "manifest.json"),
                  source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                        text=True).strip(),
                  jobs=jobs, prior_accounting=accounting, maximum_charged_seconds=limit,
                  mission_wall_limit_seconds=WALL_LIMIT, mission_cpu_limit_seconds=CPU_LIMIT,
                  hypothesis="The existing incremental CPU cache saves worker CPU while preserving service "
                             "on the three families omitted from the component ablation.",
                  analysis="Report all 30 original/cache pairs across six parents, all five methods, "
                           "customer-weighted service, complete service, paired service losses, "
                           "same-served-set distance and CPU ratios. Original raw is reused byte-for-byte.",
                  interpretation="Exploratory coverage only. Existing historical cache service regressions "
                                 "remain part of the evidence and preclude a universal safety or promotion "
                                 "claim. No outcome-driven selection, rerun, or new holdout follows.",
                  execution="Sequential workers; one numerical thread; shared-machine timings; "
                            "five-second MPC limit; no optimizer changes; whole-block admission; "
                            "no automatic retry; all failed attempts retained.")
    save_json(path, frozen)
    return frozen


def verify_record(frozen, job, raw, *, replay=True):
    parent = load_json(DEVELOPMENT / "protocol.json")
    info = parent["selected"][job["index"]]
    result = raw["result"]
    meta = result["metadata"]
    if (raw["job_id"] != job["id"] or raw["protocol_identifier"] != identifier(frozen) or
            raw["source_sha256"] != frozen["source_sha256"] or
            meta["algorithm"] != job["method"] or meta["scenario_identifier"] != info["scenario_id"] or
            meta["reference_schedule_identifier"] != info["reference_id"] or meta["K_ref"] != info["k_ref"] or
            result["metrics"]["max_optimization_latency"] > 5.0 + 1e-6):
        raise ValueError("CPU coverage identity, fleet, or decision-budget mismatch")
    if replay:
        instance, _, scenario = archived_case(info)
        if not all(audit_result(decode_result(result), instance, scenario).values()):
            raise ValueError("CPU coverage physical/information replay failed")


def worker(job_id):
    frozen = freeze()
    job = next(job for job in frozen["jobs"] if job["id"] == job_id)
    path = OUTPUT / "raw" / f"{job_id}.json.gz"
    if path.exists():
        raise ValueError("Never overwrite saved CPU coverage evidence")
    parent = load_json(DEVELOPMENT / "protocol.json")
    info = parent["selected"][job["index"]]
    started, cpu = perf_counter(), process_time()
    instance, _, scenario = archived_case(info)
    options = run_options(parent["config"], info["instance"], job["method"], "cpu")
    options["study"] = frozen["study"]
    result = EventDrivenSimulator(instance, scenario, simulation_config(options)).run()
    raw = dict(job_id=job_id, source_sha256=frozen["source_sha256"],
               protocol_identifier=identifier(frozen), result=asdict(result),
               worker_wall_seconds=perf_counter() - started, worker_cpu_seconds=process_time() - cpu)
    verify_record(frozen, job, raw)
    save_json(path, raw)


def run():
    frozen = freeze()
    budget = HardBudget(OUTPUT, frozen["maximum_charged_seconds"])
    path = OUTPUT / "manifest.json"
    manifest = load_json(path) if path.exists() else dict(protocol_identifier=identifier(frozen), records=[])
    if manifest["protocol_identifier"] != identifier(frozen):
        raise ValueError("CPU coverage manifest protocol drift")
    records = {row["id"]: row for row in manifest["records"]}
    if len(records) != len(manifest["records"]) or not set(records) <= {job["id"] for job in frozen["jobs"]}:
        raise ValueError("Duplicate or unplanned CPU coverage record")
    pending = [job for job in frozen["jobs"] if job["id"] not in records]
    if pending and not admit(budget.remaining(), sum(job["upper_seconds"] + 2 for job in pending), RESERVE):
        raise ValueError("The remaining fixed block cannot fit; no workers started")
    env = dict(os.environ, PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    for job in frozen["jobs"]:
        raw_path = OUTPUT / "raw" / f"{job['id']}.json.gz"
        if job["id"] in records:
            if digest(raw_path) != records[job["id"]]["sha256"]:
                raise ValueError("Saved CPU coverage raw hash changed")
            verify_record(frozen, job, load_json(raw_path))
            continue
        if raw_path.exists():
            raise ValueError("Unmanifested CPU coverage record; inspect before any retry")
        execution = budget.execute(job["id"], [sys.executable, "-u", "-m",
                                   "scripts.complete_cpu_coverage", "--worker", job["id"]],
                                   job["upper_seconds"], env=env, reserve=RESERVE)
        if execution is None or execution["status"] != "complete":
            manifest.update(status="incomplete_evidence_preserved", completed_runs=len(records), planned_runs=15)
            save_json(path, manifest)
            raise RuntimeError("CPU coverage worker incomplete; its evidence is preserved")
        raw = load_json(raw_path)
        verify_record(frozen, job, raw)
        records[job["id"]] = dict(id=job["id"], index=job["index"], method=job["method"],
                                  raw=raw_path.relative_to(ROOT).as_posix(), sha256=digest(raw_path),
                                  execution=execution)
        manifest.update(status="complete" if len(records) == 15 else "partial",
                        records=list(records.values()), completed_runs=len(records), planned_runs=15)
        save_json(path, manifest)
        print(f"CPU coverage {len(records)}/15 {job['id']} served="
              f"{raw['result']['metrics']['customers_served']}", flush=True)
    print(f"CPU coverage complete: {len(records)}/15", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    elif args.freeze:
        protocol = freeze()
        print(f"Frozen {len(protocol['jobs'])} CPU coverage jobs; allowance "
              f"{protocol['maximum_charged_seconds']:.1f} seconds")
    else:
        run()
