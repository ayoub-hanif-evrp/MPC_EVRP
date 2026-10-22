"""Record machine and dependency context for a separately frozen study."""

from datetime import datetime, timezone
from importlib.metadata import version
import os
import platform
import subprocess
import sys

from evrp.storage import ROOT, load_json, save_json


PACKAGES = ("numpy", "scipy", "pandas", "matplotlib", "PyYAML", "pytest", "scikit-learn")


def record(study="robustness_v2"):
    if study not in {"robustness_v2", "robustness_pilot_v2", "robustness_v3"}:
        raise ValueError("Only new Desaulniers studies may receive environment records")
    directory = ROOT / "results/desaulniers" / study
    protocol = load_json(directory / "protocol.json")
    target = directory / "environment.json"
    if target.exists():
        raise ValueError("Environment evidence already exists; refusing overwrite")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    changed = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    save_json(target, dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
                           git_head=head, git_worktree_dirty=bool(changed),
                           python=sys.version, operating_system=platform.platform(),
                           cpu_model=platform.processor() or "not reported by platform",
                           logical_cpu_count=os.cpu_count(),
                           packages={name: version(name) for name in PACKAGES},
                           source_sha256=protocol["source_sha256"],
                           dataset_sha256=protocol["dataset_sha256"],
                           config_sha256=protocol["config_sha256"],
                           controller_sha256=protocol["controller_sha256"],
                           execution=protocol["execution"],
                           methods=protocol["methods"], dynamicities=protocol["dynamicities"],
                           scenario_seeds=protocol["scenario_seeds"],
                           decision_budget_seconds=protocol["total_planning_time_limit"]))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", choices=["robustness_v2", "robustness_pilot_v2",
                                            "robustness_v3"], default="robustness_v3")
    args = parser.parse_args()
    record(args.study)
