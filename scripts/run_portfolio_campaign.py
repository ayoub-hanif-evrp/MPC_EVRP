"""Run only the 66 already-inspected development scenarios for MPC optimizers."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from itertools import product

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json


CONFIG_PATH = ROOT / "configs" / "portfolio_development.yaml"
OUTPUT = ROOT / "results" / "portfolio" / "development"


def cases(config):
    for prefix in ("old_development", "consumed_holdout"):
        yield from product(config[f"{prefix}_instances"],
                           config[f"{prefix}_dynamicity"],
                           config[f"{prefix}_seeds"])


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py"))
    return identifier({str(p.relative_to(ROOT)).replace("\\", "/"): p.read_text(encoding="utf-8")
                       for p in paths})


def run(case_limit=None, methods=None):
    study = load_config(CONFIG_PATH)
    base = load_config(ROOT / study["base_controller"])
    selected = tuple(methods or study["methods"])
    if not set(selected) <= set(study["methods"]):
        raise ValueError("Unknown development method")
    if study["total_planning_time_limit"] != 5.0:
        raise ValueError("Development comparison requires a five-second decision limit")
    scenarios = list(cases(study))
    if len(scenarios) != 66 or len(set(scenarios)) != 66:
        raise ValueError("Expected exactly 66 inspected development scenarios")
    if case_limit is not None:
        scenarios = scenarios[:case_limit]
    code_hash = source_hash()
    config_hash = sha256(CONFIG_PATH.read_bytes()).hexdigest()
    controller_hash = sha256((ROOT / study["base_controller"]).read_bytes()).hexdigest()
    manifest_path = OUTPUT / "manifest.json"
    prior = load_json(manifest_path)["records"] if manifest_path.exists() else []
    records = {(row["scenario_id"], row["method"]): row for row in prior
               if row["source_sha256"] == code_hash and row["protocol_sha256"] == config_hash
               and row["controller_sha256"] == controller_hash}
    for index, (name, dod, seed) in enumerate(scenarios, 1):
        options = dict(base, scenario_seed=seed, dynamicity=dod,
                       total_planning_time_limit=study["total_planning_time_limit"],
                       diagnostics=False, trace_level="summary")
        instance, reference, scenario, _ = prepare(name, options)
        for method in selected:
            effective = dict(options, algorithm=method)
            identity = identifier(dict(instance_sha256=instance.sha256,
                                       scenario=scenario.identifier, method=method,
                                       code=code_hash, config=config_hash,
                                       controller=controller_hash, effective=effective))
            path = OUTPUT / "raw" / f"{name}_{dod:.2f}_{seed}_{method}_{identity[:12]}.json.gz"
            if path.exists():
                saved = load_json(path)
                if saved["metadata"]["scenario_identifier"] != scenario.identifier or saved[
                        "metadata"]["algorithm"] != method:
                    raise ValueError(f"Stale development record: {path}")
                metrics = saved["metrics"]
            else:
                result = EventDrivenSimulator(instance, scenario, simulation_config(effective)).run()
                audit_result(result, instance, scenario)
                save_json(path, asdict(result))
                metrics = result.metrics
            digest = sha256(path.read_bytes()).hexdigest()
            row = dict(instance=name, instance_sha256=instance.sha256, dynamicity=dod,
                       scenario_seed=seed, scenario_id=scenario.identifier, method=method,
                       raw=str(path.relative_to(ROOT)).replace("\\", "/"), raw_sha256=digest,
                       customers_served=metrics["customers_served"],
                       complete_service=metrics["complete_service"],
                       vehicles_activated=metrics["vehicles_activated"],
                       total_distance=metrics["total_distance"],
                       mean_optimization_latency=metrics["mean_optimization_latency"],
                       p95_optimization_latency=metrics["p95_optimization_latency"],
                       max_optimization_latency=metrics["max_optimization_latency"],
                       source_sha256=code_hash, protocol_sha256=config_hash,
                       controller_sha256=controller_hash)
            records[(scenario.identifier, method)] = row
            print(f"{index}/{len(scenarios)} {name} DoD={dod} seed={seed} {method} "
                  f"served={row['customers_served']} max_s={row['max_optimization_latency']:.3f}",
                  flush=True)
            ordered = sorted(records.values(), key=lambda item: (
                item["instance"], item["dynamicity"], item["scenario_seed"], item["method"]))
            save_json(manifest_path, dict(
                status="development_complete" if len(ordered) == 66 * len(study["methods"])
                else "development_incomplete", expected_scenarios=66,
                expected_records=66 * len(study["methods"]), records=ordered))
    return list(records.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-limit", type=int, help="Run the first N paired development scenarios")
    parser.add_argument("--methods", nargs="+", help="Subset of the four comparison methods")
    args = parser.parse_args()
    run(args.case_limit, args.methods)
