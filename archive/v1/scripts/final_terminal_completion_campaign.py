"""Run the last paper-track diagnostics and frozen matched campaign."""

import argparse
from collections import Counter
import subprocess

from evrp.audit import audit_record
from evrp.experiments import load_config, run_single, source_fingerprint
from evrp.storage import ROOT, load_json


CONFIG = ROOT / "configs" / "final_control_horizon.yaml"
FROZEN = load_config(CONFIG)
INSTANCES = tuple(FROZEN["instances"])
RAW = ROOT / "results" / "final" / "terminal_completion" / "raw"
BASE = {key: value for key, value in FROZEN.items() if key not in {"instances", "gate"}}
BASE["study"] = "fleet_mpc_terminal_completion_final"
DIAGNOSTICS = (("r101_21", 0), ("c201_21", 0), ("r201_21", 1))


def cases(stage):
    if stage == "diagnostic":
        for instance, seed in DIAGNOSTICS:
            yield instance, dict(BASE, algorithm="FLEET_MPC_MCTS", dynamicity=0.5,
                                 scenario_seed=seed)
    elif stage == "static":
        for instance in INSTANCES:
            yield instance, dict(BASE, algorithm="FLEET_MPC_MCTS", dynamicity=0.0,
                                 scenario_seed=0)
    elif stage == "development":
        for instance in INSTANCES:
            for seed in (0, 1):
                for algorithm in ("FLEET_MPC_MCTS", "ROLLING_LNS"):
                    yield instance, dict(BASE, algorithm=algorithm, dynamicity=0.5,
                                         scenario_seed=seed)
    else:
        raise ValueError(stage)


def run(stage):
    if stage == "development":
        static_paths = sorted((RAW / "static").glob("*.json"))
        if len(static_paths) != len(INSTANCES):
            raise RuntimeError("Development blocked: incomplete six-case static gate")
        static = [load_json(path) for path in static_paths]
        if (any(record["status"] != "completed" or audit_record(record)
                or record["metrics"]["customers_served"] != 100
                or record["metrics"]["max_optimization_latency"] > 5.0
                or record["identity"]["source_sha256"] != source_fingerprint()
                for record in static)
                or {record["identity"]["instance"] for record in static} != set(INSTANCES)):
            raise RuntimeError("Development blocked: six-case static gate failed")
        if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
            raise RuntimeError("Development blocked: source/config/tests are not frozen")
    failures = []
    for index, (instance, config) in enumerate(cases(stage), 1):
        path = run_single(instance, config, RAW / stage, resume=True)
        record = load_json(path)
        errors = audit_record(record) if record["status"] == "completed" else [record.get("error")]
        metrics = record.get("metrics", {})
        print(f"{stage} {index} {instance} seed={config['scenario_seed']} "
              f"{config['algorithm']} status={record['status']} "
              f"served={metrics.get('customers_served')} audit={not bool(errors)} "
              f"wall={metrics.get('complete_instance_wall_clock_seconds')} "
              f"p95={metrics.get('p95_optimization_latency')} "
              f"max={metrics.get('max_optimization_latency')}", flush=True)
        if stage == "diagnostic" and record["status"] == "completed":
            calls = [d["fleet_mcts"] for d in record["decisions"] if d.get("fleet_mcts")]
            reasons = Counter(reason for d in record["decisions"]
                              for reason in (d.get("optimization_trigger_reason") or "").split(",")
                              if reason)
            rollouts = sum(c["rollout_count"] for c in calls)
            print(dict(released=len(record["scenario"]["customer_release_times"]),
                       served=metrics["customers_served"],
                       triggers=metrics["optimization_triggers"], reasons=dict(reasons),
                       root_uncovered=sum(c["root_uncovered"] for c in calls),
                       root_completion_uncovered=sum(c["completed_root_uncovered"] for c in calls),
                       final_uncovered=sum(c["final_uncovered"] for c in calls),
                       service_gain=sum(c["service_gain_over_root"] for c in calls),
                       simulations=sum(c["iterations"] for c in calls),
                       mean_customers_completed_per_rollout=(
                           sum(c["rollout_customers_completed"] for c in calls) / rollouts
                           if rollouts else 0),
                       maximum_rollout_residual=max((c["maximum_rollout_residual"]
                                                     for c in calls), default=0)), flush=True)
        if errors:
            failures.append((str(path), errors))
        if (stage == "static" and record["status"] == "completed"
                and (metrics["customers_served"] != 100
                     or metrics["max_optimization_latency"] > 5.0)):
            raise RuntimeError(f"Static gate failed at {instance}: stopping remaining cases")
    if failures:
        raise RuntimeError(f"{len(failures)} {stage} runs failed: {failures}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("diagnostic", "static", "development"))
    run(parser.parse_args().stage)
