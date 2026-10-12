"""Run the preregistered control-horizon static/development grid."""

import argparse
import hashlib

from evrp.audit import audit_record
from evrp.experiments import load_config, run_single, source_fingerprint, git_commit
from evrp.storage import ROOT, load_json


CONFIG = ROOT / "configs" / "final_control_horizon.yaml"
FROZEN = load_config(CONFIG)
INSTANCES = tuple(FROZEN["instances"])
HOLDOUT_INSTANCES = ("c109_21", "c208_21", "r112_21", "r211_21", "rc108_21", "rc208_21")
RAW = ROOT / "results" / "final" / "control_horizon" / "raw"
BASE = {key: value for key, value in FROZEN.items() if key not in {"instances", "gate"}}


def cases(stage):
    if stage == "static":
        for instance in INSTANCES:
            yield instance, dict(BASE, algorithm="FLEET_MPC_MCTS", dynamicity=0.0,
                                 scenario_seed=0)
    elif stage == "development":
        for instance in INSTANCES:
            for seed in (0, 1):
                for algorithm in ("FLEET_MPC_MCTS", "ROLLING_LNS"):
                    yield instance, dict(BASE, algorithm=algorithm, dynamicity=0.5,
                                         scenario_seed=seed)
    elif stage == "holdout":
        for instance in HOLDOUT_INSTANCES:
            for dynamicity in (0.25, 0.5, 0.75):
                for seed in (0, 1, 2):
                    for algorithm in ("RH_REGRET", "ROLLING_LNS", "FLEET_MPC_MCTS"):
                        yield instance, dict(BASE, algorithm=algorithm, dynamicity=dynamicity,
                                             scenario_seed=seed)
    else:
        raise ValueError(f"Unknown stage: {stage}")


def run(stage, only_instance=None):
    if stage == "holdout":
        summary_path = ROOT / "results" / "final" / "control_horizon" / "summaries" / "development_summary.json"
        if not summary_path.exists():
            raise RuntimeError("Holdout blocked: no development gate")
        summary = load_json(summary_path)
        if (not summary["gate"]["passed"] or summary["frozen_git_commit"] != git_commit()
                or summary["source_sha256"] != source_fingerprint()
                or summary["config_file_sha256"] != hashlib.sha256(CONFIG.read_bytes()).hexdigest()):
            raise RuntimeError("Holdout blocked: development gate failed or freeze changed")
    failures = []
    for index, (instance, config) in enumerate(cases(stage), 1):
        if only_instance is not None and instance != only_instance:
            continue
        path = run_single(instance, config, RAW / stage, resume=True)
        record = load_json(path)
        errors = audit_record(record) if record["status"] == "completed" else [record.get("error")]
        if errors:
            failures.append((str(path), errors))
        print(f"{stage} {index}: {instance} seed={config['scenario_seed']} "
              f"{config['algorithm']} status={record['status']} "
              f"served={record.get('metrics', {}).get('customers_served')} "
              f"audit={'PASS' if not errors else 'FAIL'} path={path}", flush=True)
        metrics = record.get("metrics", {})
        if record["status"] == "completed":
            print(f"events={metrics.get('simulation_events')} triggers={metrics.get('optimization_triggers')} "
                  f"mcts_calls={metrics.get('mcts_calls')} "
                  f"wall_s={metrics.get('complete_instance_wall_clock_seconds')} "
                  f"optimization_max_s={metrics.get('max_optimization_latency')}", flush=True)
    if failures:
        raise RuntimeError(f"{len(failures)} {stage} runs failed: {failures}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("static", "development", "holdout"))
    parser.add_argument("--instance", choices=INSTANCES + HOLDOUT_INSTANCES)
    args = parser.parse_args()
    run(args.stage, args.instance)
