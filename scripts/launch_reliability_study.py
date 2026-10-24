"""Unattended supervisor: progress, logs, temporary awake request, no retuning."""

from datetime import datetime, timezone
import ctypes
import json
import os
import subprocess
import sys
from time import monotonic, sleep

from evrp.storage import ROOT, load_json, save_json, writable_path
from scripts.analyze_reliability_study import report
from scripts.run_reliability_study import OUTPUT, source_hash


def snapshot(pid, supervisor_pid, state):
    stages = {}
    for stage in ("development", "holdout"):
        path = OUTPUT/stage/"manifest.json"
        if path.exists():
            value = load_json(path)
            stages[stage] = dict(completed=value["completed_runs"], planned=value["planned_runs"],
                                 status=value["status"], maximum_decision=max(
                                     r["metrics"]["max_optimization_latency"] for r in value["records"]),
                                 all_audits=all(all(r["independent_audit"].values()) for r in value["records"]))
    result = dict(updated_utc=datetime.now(timezone.utc).isoformat(), runner_pid=pid,
                  supervisor_pid=supervisor_pid, state=state, stages=stages,
                  log="results/desaulniers/reliability_v2/run.log")
    save_json(OUTPUT/"progress.json", result)
    return result


def main():
    protocol = load_json(OUTPUT/"development/protocol.json")
    if protocol["source_sha256"] != source_hash():
        raise ValueError("Cannot launch a source-drifted campaign")
    lock = writable_path(OUTPUT/"execution.lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(dict(supervisor_pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat()), stream)
    child = None
    awake = os.name == "nt"
    try:
        if awake:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        with writable_path(OUTPUT/"run.log").open("ab", buffering=0) as log:
            child = subprocess.Popen([sys.executable, "-u", "-m", "scripts.run_reliability_study"],
                                     cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            attempt = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            save_json(OUTPUT/"execution_attempts"/f"{attempt}.json", dict(runner_pid=child.pid,
                      supervisor_pid=os.getpid(), source_sha256=source_hash(),
                      maximum_campaign_hours=protocol["config"]["maximum_campaign_hours"],
                      timing_conditions=protocol["timing_conditions"],
                      temporary_system_awake=awake, display_awake=False))
            print(f"Started monitored runner PID {child.pid}", flush=True)
            previous, last_progress, last_report = None, monotonic(), 0
            while child.poll() is None:
                value = snapshot(child.pid, os.getpid(), "running")
                count = sum(v["completed"] for v in value["stages"].values())
                if count != previous:
                    last_progress, previous = monotonic(), count
                if monotonic()-last_progress > 40*60:
                    print("No new record for 40 minutes. Inspect run.log and the recorded runner tree; no automatic rerun or deletion.", flush=True)
                    last_progress = monotonic()
                if monotonic()-last_report > 300:
                    report("Prospective campaign running under the frozen protocol. Partial results are not final evidence.")
                    last_report = monotonic()
                sleep(30)
            value = snapshot(child.pid, os.getpid(), "exited")
            development = value["stages"].get("development", {})
            state = "failed" if child.returncode else "paused"
            analysis = OUTPUT/"development/analysis.json"
            if child.returncode == 0 and development.get("status") == "complete" and analysis.exists():
                promoted = load_json(analysis)["selection"]["promoted"]
                if promoted is None or (OUTPUT/"holdout/analysis.json").exists():
                    state = "complete"
            snapshot(child.pid, os.getpid(), state)
            if child.returncode:
                report("Execution stopped with an error. Preserve the log, failures and saved evidence; no silent reruns.")
            print(f"Monitored study {state}; return code {child.returncode}", flush=True)
            return child.returncode
    finally:
        if awake:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        if child is None or child.poll() is not None:
            lock.unlink()


if __name__ == "__main__":
    sys.exit(main())
