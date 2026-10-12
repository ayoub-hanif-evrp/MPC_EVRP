"""Run the preregistered control-horizon static/development grid."""

import argparse

from evrp.audit import audit_record
from evrp.experiments import load_config, run_single
from evrp.storage import ROOT, load_json


CONFIG = ROOT / "configs" / "final_control_horizon.yaml"
FROZEN = load_config(CONFIG)
INSTANCES = tuple(FROZEN["instances"])
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
    else:
        raise ValueError(f"Unknown stage: {stage}")


def run(stage):
    failures = []
    for index, (instance, config) in enumerate(cases(stage), 1):
        path = run_single(instance, config, RAW / stage, resume=True)
        record = load_json(path)
        errors = audit_record(record) if record["status"] == "completed" else [record.get("error")]
        if errors:
            failures.append((str(path), errors))
        print(f"{stage} {index}: {instance} seed={config['scenario_seed']} "
              f"{config['algorithm']} status={record['status']} "
              f"served={record.get('metrics', {}).get('customers_served')} "
              f"audit={'PASS' if not errors else 'FAIL'} path={path}", flush=True)
    if failures:
        raise RuntimeError(f"{len(failures)} {stage} runs failed: {failures}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("static", "development"))
    run(parser.parse_args().stage)
