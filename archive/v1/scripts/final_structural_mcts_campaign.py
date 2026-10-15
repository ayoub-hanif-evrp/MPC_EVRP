"""Run the predeclared structural-rollout paper campaign in gate order."""

import argparse
import subprocess
from collections import Counter

from evrp.audit import audit_record
from evrp.experiments import load_config, run_single, source_fingerprint
from evrp.storage import ROOT, load_json


CONFIG = ROOT / "configs" / "final_structural_mcts.yaml"
FROZEN = load_config(CONFIG)
INSTANCES = tuple(FROZEN["instances"])
HOLDOUT_INSTANCES = ("c109_21", "c208_21", "r112_21", "r211_21", "rc108_21", "rc208_21")
BASE = {key: value for key, value in FROZEN.items() if key != "instances"}
RAW = ROOT / "results" / "final" / "structural_rollout" / "raw"
DIAGNOSTICS = (("c101_21", 0.0, 0), ("r101_21", 0.5, 0),
               ("r201_21", 0.5, 1), ("c201_21", 0.5, 0))


def cases(stage):
    if stage == "diagnostic":
        for instance, dynamicity, seed in DIAGNOSTICS:
            yield instance, dict(BASE, algorithm="FLEET_MPC_MCTS", dynamicity=dynamicity,
                                 scenario_seed=seed)
    elif stage == "static":
        for instance in INSTANCES:
            yield instance, dict(BASE, algorithm="FLEET_MPC_MCTS", dynamicity=0.0,
                                 scenario_seed=0)
    elif stage in {"development", "ablation"}:
        algorithms = (("FLEET_MPC_MCTS", "ROLLING_LNS") if stage == "development"
                      else ("FLEET_MPC_COMPLETION_ONLY",))
        for instance in INSTANCES:
            for seed in (0, 1):
                for algorithm in algorithms:
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
        raise ValueError(stage)


def current_records(stage):
    source = source_fingerprint()
    records = []
    for path in sorted((RAW / stage).glob("*.json")):
        record = load_json(path)
        if record.get("identity", {}).get("source_sha256") == source:
            records.append(record)
    return records


def require_completed(stage, expected):
    records = current_records(stage)
    keys = [(r["identity"]["instance"], r["identity"]["scenario_seed"],
             r["identity"]["algorithm"], r["requested_config"]["dynamicity"]) for r in records]
    if len(records) != len(expected) or set(keys) != set(expected):
        raise RuntimeError(f"{stage} gate blocked: missing or duplicate current-source records")
    if any(r["status"] != "completed" or audit_record(r)
           or r["metrics"]["max_optimization_latency"] > 5.0 for r in records):
        raise RuntimeError(f"{stage} gate blocked: failed run, audit, or latency")
    return records


def preflight(stage):
    if stage == "static":
        expected = [(instance, seed, "FLEET_MPC_MCTS", dynamicity)
                    for instance, dynamicity, seed in DIAGNOSTICS]
        records = require_completed("diagnostic", expected)
        served = {(r["identity"]["instance"], r["identity"]["scenario_seed"]):
                  r["metrics"]["customers_served"] for r in records}
        if (served["c101_21", 0] != 100 or served["r101_21", 0] < 90
                or served["r201_21", 1] < 90 or served["c201_21", 0] < 99):
            raise RuntimeError("Static gate blocked: four diagnostics did not meet engineering sanity")
    if stage in {"development", "ablation", "holdout"}:
        expected = [(instance, 0, "FLEET_MPC_MCTS", 0.0) for instance in INSTANCES]
        static = require_completed("static", expected)
        if sum(r["metrics"]["customers_served"] for r in static) != 600:
            raise RuntimeError("Development blocked: static service below 600/600")
        if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                   cwd=ROOT).strip():
            raise RuntimeError("Development blocked: tracked source/config/tests are not frozen")
    if stage in {"ablation", "holdout"}:
        expected = [(instance, seed, algorithm, 0.5) for instance in INSTANCES
                    for seed in (0, 1) for algorithm in ("FLEET_MPC_MCTS", "ROLLING_LNS")]
        require_completed("development", expected)
    if stage == "holdout":
        raise RuntimeError("Holdout requires a separately documented positive development verdict")


def run(stage):
    preflight(stage)
    for index, (instance, config) in enumerate(cases(stage), 1):
        path = run_single(instance, config, RAW / stage, resume=True)
        record = load_json(path)
        errors = audit_record(record) if record["status"] == "completed" else [record.get("error")]
        metrics = record.get("metrics", {})
        print(f"{stage} {index} {instance} DoD={config['dynamicity']} seed={config['scenario_seed']} "
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
                       triggers=metrics["optimization_triggers"], reasons=dict(reasons),
                       retained_service=sum(d["retained_service"] for d in record["decisions"] if d["mcts_called"]),
                       constructed_service=sum(d["constructor_service"] for d in record["decisions"] if d["mcts_called"]),
                       best_service=sum(d["best_service_after_search"] for d in record["decisions"] if d["mcts_called"]),
                       constructor_seconds=metrics["constructor_seconds_total"],
                       mcts_seconds=sum(c["elapsed"] for c in calls),
                       iterations=sum(c["iterations"] for c in calls),
                       nodes=sum(c["nodes_expanded"] for c in calls),
                       rollouts=rollouts,
                       mean_rollout_inserted=(sum(c["rollout_customers_completed"] for c in calls) / rollouts
                                              if rollouts else 0),
                       max_rollout_residual=max((c["maximum_rollout_residual"] for c in calls), default=0),
                       screened_evs_per_customer=(sum(c["screened_vehicle_evaluations"] for c in calls) /
                                                  max(1, sum(c["screened_customer_count"] for c in calls))),
                       exact_decodes=sum(c["exact_decoded_options"] for c in calls),
                       service_improvements=sum(c["service_improvements"] for c in calls),
                       objective_only_improvements=sum(c["objective_only_improvements"] for c in calls)), flush=True)
        if errors:
            raise RuntimeError(f"{stage} run failed: {path}: {errors}")
        if stage == "static" and metrics["customers_served"] != 100:
            raise RuntimeError(f"Static service gate failed at {instance}; stopping")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("diagnostic", "static", "development", "ablation", "holdout"))
    run(parser.parse_args().stage)
