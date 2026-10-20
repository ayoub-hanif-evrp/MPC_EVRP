"""Run the frozen Desaulniers campaigns and analyses unattended, in order."""

import ctypes
from datetime import datetime, timezone
import os
import subprocess
import sys
import traceback

from evrp.storage import ROOT, save_json, writable_path


OUTPUT = ROOT / "results/desaulniers"
STATUS = OUTPUT / "pipeline_status.json"
LOG = OUTPUT / "pipeline.log"
STAGES = (
    ("development", "scripts.run_desaulniers_campaign"),
    ("development_analysis", "scripts.analyze_desaulniers_campaign"),
    ("final_holdout", "scripts.run_desaulniers_final"),
    ("final_analysis", "scripts.analyze_desaulniers_final"),
)


def now():
    return datetime.now(timezone.utc).isoformat()


def run():
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
    try:
        with writable_path(LOG).open("a", encoding="utf-8", buffering=1) as log:
            for stage, module in STAGES:
                save_json(STATUS, dict(stage=stage, state="running", started_utc=now(),
                                       pipeline_pid=os.getpid()))
                log.write(f"\n[{now()}] START {stage}: {module}\n")
                result = subprocess.run([sys.executable, "-u", "-m", module],
                                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                if result.returncode:
                    log.write(f"[{now()}] FAILED {stage}: exit {result.returncode}\n")
                    save_json(STATUS, dict(stage=stage, state="failed", finished_utc=now(),
                                           exit_code=result.returncode, pipeline_pid=os.getpid(),
                                           log=LOG.relative_to(ROOT).as_posix()))
                    return result.returncode
                log.write(f"[{now()}] COMPLETE {stage}\n")
            save_json(STATUS, dict(stage="all", state="complete", finished_utc=now(),
                                   pipeline_pid=os.getpid(), log=LOG.relative_to(ROOT).as_posix()))
            return 0
    except Exception:
        save_json(STATUS, dict(stage="pipeline", state="failed", finished_utc=now(),
                               pipeline_pid=os.getpid(), traceback=traceback.format_exc()))
        raise
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    sys.exit(run())
