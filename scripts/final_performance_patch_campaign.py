"""Run the final performance patch in targeted, static, then development gates."""

import argparse
import subprocess

from evrp.audit import audit_record
from evrp.experiments import load_config, run_single, source_fingerprint
from evrp.storage import ROOT, load_json


FROZEN = load_config(ROOT / "configs" / "final_structural_mcts.yaml")
INSTANCES = tuple(FROZEN["instances"])
BASE = {key: value for key, value in FROZEN.items() if key != "instances"}
RAW = ROOT / "results" / "final" / "performance_patch" / "raw"


def cases(stage):
    if stage == "targeted":
        for instance in ("c201_21", "c101_21"):
            yield instance, dict(BASE, algorithm="FLEET_MPC_MCTS",
                                 dynamicity=0.0, scenario_seed=0)
    elif stage == "static":
        for instance in INSTANCES:
            yield instance, dict(BASE, algorithm="FLEET_MPC_MCTS",
                                 dynamicity=0.0, scenario_seed=0)
    elif stage == "development":
        for instance in INSTANCES:
            for seed in (0, 1):
                for algorithm in ("FLEET_MPC_MCTS", "ROLLING_LNS",
                                  "FLEET_MPC_COMPLETION_ONLY"):
                    yield instance, dict(BASE, algorithm=algorithm,
                                         dynamicity=0.5, scenario_seed=seed)
    else:
        raise ValueError(stage)


def completed(stage):
    source = source_fingerprint()
    records = [load_json(path) for path in sorted((RAW / stage).glob("*.json"))]
    records = [record for record in records
               if record.get("identity", {}).get("source_sha256") == source]
    expected = list(cases(stage))
    keys = {(record["identity"]["instance"], record["identity"]["algorithm"],
             record["identity"]["scenario_seed"])
            for record in records}
    wanted = {(instance, config["algorithm"], config["scenario_seed"])
              for instance, config in expected}
    if len(records) != len(expected) or keys != wanted:
        raise RuntimeError(f"{stage}: missing or duplicate current-source records")
    for record in records:
        if record["status"] != "completed" or audit_record(record):
            raise RuntimeError(f"{stage}: failed status or audit")
        if record["metrics"]["max_optimization_latency"] >= 5.0:
            raise RuntimeError(f"{stage}: five-second event budget exceeded")
    return records


def preflight(stage):
    if stage == "static":
        targeted = completed("targeted")
        if any(record["metrics"]["customers_served"] != 100 for record in targeted):
            raise RuntimeError("Targeted static 200/200 gate failed")
    elif stage == "development":
        static = completed("static")
        if sum(record["metrics"]["customers_served"] for record in static) != 600:
            raise RuntimeError("Six-static 600/600 gate failed")
        if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                   cwd=ROOT).strip():
            raise RuntimeError("Source must be committed before development")


def run(stage):
    preflight(stage)
    for index, (instance, config) in enumerate(cases(stage), 1):
        path = run_single(instance, config, RAW / stage, resume=True)
        record = load_json(path)
        metrics = record.get("metrics", {})
        errors = audit_record(record) if record["status"] == "completed" else [record.get("error")]
        print(f"{stage} {index} {instance} seed={config['scenario_seed']} "
              f"{config['algorithm']} status={record['status']} "
              f"served={metrics.get('customers_served')} audit={not bool(errors)} "
              f"wall={metrics.get('complete_instance_wall_clock_seconds')} "
              f"max_call={metrics.get('max_optimization_latency')}", flush=True)
        if stage == "targeted" and record["status"] == "completed":
            decision = record["decisions"][0]
            mcts = decision.get("fleet_mcts") or {}
            print(dict(released=len(decision["available"]),
                       constructor_coverage=decision["constructor_service"],
                       constructor_ms=round(decision["constructor_seconds"] * 1000, 2),
                       screened_insertions=decision["constructor_screened_insertions"],
                       exact_decoder_calls=decision["constructor_exact_decoder_calls"],
                       zero_option_after_constructor=decision["constructor_zero_option_customers"],
                       mcts_service_improvements=mcts.get("service_improvements"),
                       ejection_generated=mcts.get("ejection_chains_generated"),
                       ejection_feasible=mcts.get("ejection_chains_feasible"),
                       ejection_selected=mcts.get("ejection_chains_selected"),
                       final_root_coverage=decision["best_service_after_search"]), flush=True)
        if errors or metrics.get("max_optimization_latency", float("inf")) >= 5.0:
            raise RuntimeError(f"{stage} run failed: {path}: {errors}")
        if stage in {"targeted", "static"} and metrics["customers_served"] != 100:
            raise RuntimeError(f"Static service gate failed at {instance}; stopping")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("targeted", "static", "development"))
    run(parser.parse_args().stage)
