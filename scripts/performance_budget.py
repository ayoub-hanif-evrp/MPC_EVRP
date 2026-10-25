"""Hard, persistent sequential experiment accounting and paired-block admission."""

from datetime import datetime, timezone
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
from time import perf_counter, process_time, sleep

from evrp.storage import ROOT, load_json, save_json, writable_path


def admit(remaining, block_upper_seconds, reserve=180):
    return block_upper_seconds > 0 and remaining >= block_upper_seconds + reserve


def process_cpu(process):
    if os.name != "nt":
        return None
    times = [wintypes.FILETIME() for _ in range(4)]
    get_times = ctypes.windll.kernel32.GetProcessTimes
    get_times.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)]*4
    get_times.restype = wintypes.BOOL
    if not get_times(wintypes.HANDLE(int(process._handle)), *(ctypes.byref(t) for t in times)):
        return None
    return sum(((t.dwHighDateTime << 32) | t.dwLowDateTime) for t in times[2:])/1e7


class HardBudget:
    def __init__(self, directory, limit=7200):
        self.directory = Path(directory)
        self.path = self.directory/"budget.json"
        if self.path.exists():
            self.data = load_json(self.path)
            if self.data["limit_seconds"] != limit:
                raise ValueError("Cannot extend a frozen compute allowance")
        else:
            self.data = dict(limit_seconds=limit, charged_seconds=0.0, jobs=[],
                             policy="Charge max(worker elapsed, worker CPU); no automatic retry; hard per-job and campaign limits")
        self.invocation_started = perf_counter()
        self.initial_charge = self.data["charged_seconds"]
        self.last_cpu = process_time()

    def remaining(self):
        # Include orchestration and idle time within this invocation, as well as worker CPU.
        elapsed_charge = self.initial_charge + perf_counter()-self.invocation_started
        pending_cpu = max(0,process_time()-self.last_cpu)
        return max(0.0, self.data["limit_seconds"]-max(elapsed_charge, self.data["charged_seconds"]+pending_cpu))

    def flush(self):
        now = process_time()
        pending_cpu = max(0,now-self.last_cpu)
        self.data["charged_seconds"] += pending_cpu
        self.data["orchestration_cpu_seconds"] = self.data.get("orchestration_cpu_seconds",0)+pending_cpu
        self.last_cpu = now
        save_json(self.path, self.data)

    def execute(self, job_id, command, upper_seconds, *, env=None, reserve=180):
        old = next((j for j in self.data["jobs"] if j["id"] == job_id), None)
        if old:
            if old["status"] != "complete":
                raise ValueError("Prior failed/interrupted job is preserved; automatic retry is forbidden")
            return old
        if not admit(self.remaining(), upper_seconds+2, reserve):
            return None
        log = writable_path(self.directory/"logs"/f"{job_id}.log")
        record = dict(id=job_id, command=command, upper_seconds=upper_seconds, status="running",
                      started_utc=datetime.now(timezone.utc).isoformat(), log=log.relative_to(ROOT).as_posix())
        self.data["jobs"].append(record)
        self.flush()
        started, cpu, interrupted = perf_counter(), 0.0, None
        allowance = min(upper_seconds, self.remaining()-reserve-2)
        with log.open("xb") as stream:
            process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, env=env)
            record["pid"] = process.pid
            self.flush()
            try:
                while process.poll() is None:
                    observed = process_cpu(process)
                    if observed is not None:
                        cpu = observed
                    elapsed = perf_counter()-started
                    if max(elapsed, cpu) >= allowance or self.remaining() <= reserve:
                        interrupted = "Hard worker/campaign allowance exhausted; result remains incomplete"
                        process.kill()
                        break
                    sleep(.05)
                process.wait()
                observed = process_cpu(process)
                if observed is not None:
                    cpu = observed
            except BaseException:
                interrupted = "Supervisor interrupted; owned worker terminated and evidence preserved"
                process.kill()
                process.wait()
                record["status"] = "interrupted"
                raise
            finally:
                elapsed = perf_counter()-started
                charge = max(elapsed, cpu)
                self.data["charged_seconds"] += charge
                record.update(elapsed_seconds=elapsed, cpu_seconds=cpu if os.name == "nt" else None,
                              cpu_to_wall=cpu/elapsed if os.name == "nt" and elapsed else None,
                              returncode=process.returncode,
                              status="incomplete" if interrupted else "complete" if process.returncode == 0 else "failed",
                              reason=interrupted)
                self.flush()
        return record
