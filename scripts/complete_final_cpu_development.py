"""Explicit technical continuation after a too-short whole-worker watchdog."""

import argparse
from hashlib import sha256
import os
import subprocess
import sys

from evrp.storage import ROOT, identifier, load_json, save_json
from scripts.performance_budget import HardBudget, admit
from scripts.run_final_cpu_development import OUTPUT, source_hash, verify_raw


EXT = OUTPUT / "technical_extension"
WATCHDOG = 900.0
RESERVE = 300.0


def freeze():
    original = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    budget = load_json(OUTPUT / "budget.json")
    path = EXT / "protocol.json"
    if path.exists():
        saved = load_json(path)
        if (saved["original_protocol_identifier"] != identifier(original) or
                saved["original_source_sha256"] != source_hash() or
                saved["failed_log_sha256"] != sha256(
                    (ROOT / budget["jobs"][-1]["log"]).read_bytes()).hexdigest() or
                not set(row["id"] for row in manifest["records"]) <=
                {spec["id"] for block in original["blocks"] for spec in block["jobs"]}):
            raise ValueError("Technical continuation source/evidence drift")
        return saved
    if (original["source_sha256"] != source_hash() or
            manifest["protocol_identifier"] != identifier(original) or
            manifest["status"] != "worker_incomplete_preserved" or
            manifest["completed_runs"] != 112 or
            budget["limit_seconds"] != original["config"]["maximum_wall_seconds"] or
            budget["jobs"][-1]["status"] != "incomplete" or
            budget["jobs"][-1]["reason"] !=
            "Hard worker/campaign allowance exhausted; result remains incomplete"):
        raise ValueError("The specific preserved technical timeout is absent")
    specs = [spec for block in original["blocks"] for spec in block["jobs"]]
    completed = {row["id"] for row in manifest["records"]}
    pending = [spec for spec in specs if spec["id"] not in completed]
    if len(pending) != 8 or pending[0]["id"] != budget["jobs"][-1]["id"]:
        raise ValueError("Unexpected pending development jobs")
    for spec in pending:
        if (OUTPUT / "raw" / f"{spec['id']}.json.gz").exists():
            raise ValueError("Unmanifested raw result; stop before correction")
    failed_log = ROOT / budget["jobs"][-1]["log"]
    remaining_wall = original["config"]["maximum_wall_seconds"] - budget["charged_seconds"]
    remaining_cpu = original["config"]["maximum_worker_cpu_seconds"] - budget.get(
        "worker_cpu_charged_seconds", 0)
    if (not admit(remaining_wall, WATCHDOG * len(pending), RESERVE) or
            remaining_cpu < WATCHDOG * len(pending)):
        raise ValueError("Correction cannot fit within original compute allowance")
    frozen = dict(purpose="technical_timeout_correction_no_scientific_changes",
                  original_protocol_identifier=identifier(original),
                  original_source_sha256=original["source_sha256"],
                  pending=[dict(spec, corrected_upper_seconds=WATCHDOG) for spec in pending],
                  failed_job_id=pending[0]["id"], failed_log_sha256=sha256(failed_log.read_bytes()).hexdigest(),
                  original_budget_sha256=sha256((OUTPUT / "budget.json").read_bytes()).hexdigest(),
                  original_manifest_sha256=sha256((OUTPUT / "manifest.json").read_bytes()).hexdigest(),
                  original_charged_wall_seconds=budget["charged_seconds"],
                  original_charged_cpu_seconds=budget.get("worker_cpu_charged_seconds", 0),
                  remaining_wall_seconds=remaining_wall, remaining_cpu_seconds=remaining_cpu,
                  watchdog_seconds=WATCHDOG,
                  change="Only whole-worker supervisor timeout; same source, scenarios, fleet, "
                         "objective, five-second decision cap and fixed pending jobs",
                  source_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                capture_output=True, text=True, check=True).stdout.strip())
    save_json(path, frozen)
    return frozen


def run():
    frozen = freeze()
    original = load_json(OUTPUT / "protocol.json")
    manifest_path = OUTPUT / "manifest.json"
    manifest = load_json(manifest_path)
    records = {row["id"]: row for row in manifest["records"]}
    budget = HardBudget(EXT, frozen["remaining_wall_seconds"])
    env = dict(os.environ, PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    if not admit(budget.remaining(), WATCHDOG * sum(spec["id"] not in records
                                                    for spec in frozen["pending"]), RESERVE):
        raise ValueError("Remaining correction block no longer fits hard budget")
    for spec in frozen["pending"]:
        if spec["id"] in records:
            path = ROOT / records[spec["id"]]["raw"]
            if sha256(path.read_bytes()).hexdigest() != records[spec["id"]]["sha256"]:
                raise ValueError("Corrected raw hash drift")
            verify_raw(original, spec, load_json(path))
            continue
        path = OUTPUT / "raw" / f"{spec['id']}.json.gz"
        if path.exists():
            raise ValueError("Never overwrite an unmanifested raw result")
        job = "technical_retry_" + spec["id"]
        execution = budget.execute(job, [sys.executable, "-u", "-m", "scripts.run_final_cpu_development",
                              "--worker", str(spec["index"]), spec["method"], spec["variant"]],
                              WATCHDOG, env=env, reserve=RESERVE)
        if execution is None or execution["status"] != "complete":
            raise RuntimeError(f"Technical continuation stopped; preserved {job} evidence")
        raw = load_json(path)
        verify_raw(original, spec, raw)
        cumulative_cpu = frozen["original_charged_cpu_seconds"] + budget.data.get(
            "worker_cpu_charged_seconds", 0) + raw["worker_cpu_seconds"]
        if cumulative_cpu > frozen["original_charged_cpu_seconds"] + frozen["remaining_cpu_seconds"]:
            raise ValueError("Original cumulative worker CPU allowance exceeded")
        budget.data["worker_cpu_charged_seconds"] = budget.data.get(
            "worker_cpu_charged_seconds", 0) + raw["worker_cpu_seconds"]
        budget.flush()
        records[spec["id"]] = dict(id=spec["id"], index=spec["index"], method=spec["method"],
                                   variant=spec["variant"], raw=path.relative_to(ROOT).as_posix(),
                                   sha256=sha256(path.read_bytes()).hexdigest(),
                                   execution=execution, technical_correction=identifier(frozen))
        manifest.update(status="technical_continuation" if len(records) < 120 else "complete",
                        records=list(records.values()), completed_runs=len(records), planned_runs=120,
                        technical_correction=identifier(frozen))
        save_json(manifest_path, manifest)
        print(f"technical continuation {len(records)}/120 {spec['id']} served="
              f"{raw['result']['metrics']['customers_served']}", flush=True)
    save_json(EXT / "completion.json", dict(status="complete", completed_runs=len(records),
              original_charged_wall_seconds=frozen["original_charged_wall_seconds"],
              correction_charged_wall_seconds=budget.data["charged_seconds"],
              total_charged_wall_seconds=frozen["original_charged_wall_seconds"] +
              budget.data["charged_seconds"], original_worker_cpu_seconds=frozen["original_charged_cpu_seconds"],
              correction_worker_cpu_seconds=budget.data.get("worker_cpu_charged_seconds", 0)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        print(f"Frozen technical correction for {len(freeze()['pending'])} fixed jobs")
    else:
        run()
