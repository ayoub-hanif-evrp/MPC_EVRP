"""Run only the committed, gate-checked final MPC holdout protocol."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from itertools import product
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import traceback

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json
from scripts.preregister_final_holdout import (BENCHMARK, FAMILIES, JSON_OUTPUT,
                                               OUTPUT as MARKDOWN)
from scripts.run_portfolio_campaign import CONFIG_PATH, OUTPUT as DEVELOPMENT, source_hash
from scripts.shadow_portfolio import OUTPUT as SHADOW


OUTPUT = ROOT / "results" / "final_study"
SCRIPT = Path(__file__)
VIOLATIONS = ("hidden_information_violations", "time_window_violations",
              "battery_violations", "capacity_violations")


def failure_path(raw_path):
    return OUTPUT / "failures" / f"{Path(raw_path).name}.failure.json"


def _committed(path):
    relative = path.relative_to(ROOT).as_posix()
    try:
        subprocess.run(["git", "cat-file", "-e", f"HEAD:{relative}"], cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["git", "diff", "--quiet", "HEAD", "--", relative], cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError as error:
        raise ValueError(f"Final protocol must be committed and unchanged: {relative}") from error


def validated_protocol():
    for path in (MARKDOWN, JSON_OUTPUT):
        if not path.exists():
            raise ValueError("Final holdout protocol has not been preregistered")
        _committed(path)
    protocol = load_json(JSON_OUTPUT)
    study = load_config(CONFIG_PATH)
    development = load_json(DEVELOPMENT / "manifest.json")
    development_analysis = load_json(DEVELOPMENT / "analysis" / "paired_analysis.json")
    shadow = load_json(SHADOW / "sbs_vbs_gate.json")
    shadow_manifest = load_json(SHADOW / "manifest.json")
    if (development["status"] != "development_complete" or
            len(development["records"]) != 330 or
            development_analysis["status"] != "complete_development" or
            development_analysis["scenarios"] != 66 or
            any(row["source_sha256"] != source_hash() for row in development["records"])):
        raise ValueError("Final holdout requires the complete final-source development grid")
    if (shadow["snapshots"] < 264 or shadow["portfolio_gate_passed"] or
            shadow_manifest["status"] != "shadow_complete"):
        raise ValueError("Final holdout requires a complete non-portfolio shadow decision")
    if (protocol["status"] != "preregistered_final_holdout" or
            protocol["source_sha256"] != source_hash() or
            protocol["controller_config"] != study["base_controller"] or
            protocol["controller_sha256"] !=
            sha256((ROOT / study["base_controller"]).read_bytes()).hexdigest() or
            protocol["development_protocol_sha256"] != sha256(CONFIG_PATH.read_bytes()).hexdigest() or
            protocol["holdout_runner_sha256"] != sha256(SCRIPT.read_bytes()).hexdigest() or
            protocol["shadow_selection_sha256"] !=
            sha256((SHADOW / "selection.json").read_bytes()).hexdigest() or
            shadow_manifest["selection_sha256"] != protocol["shadow_selection_sha256"] or
            protocol["shadow_gate_sha256"] !=
            sha256((SHADOW / "sbs_vbs_gate.json").read_bytes()).hexdigest() or
            protocol["methods"] != study["methods"] or
            protocol["dynamicity"] != [0.25, 0.5, 0.75] or
            protocol["seeds"] != [0, 1, 2] or
            set(protocol["selected"]) != set(FAMILIES) or
            study["total_planning_time_limit"] != 5.0):
        raise ValueError("Committed final protocol differs from frozen study conditions")
    for family in FAMILIES:
        selected = protocol["selected"][family]
        path = BENCHMARK / f"{selected['instance']}.txt"
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != selected["benchmark_sha256"]:
            raise ValueError(f"Selected benchmark changed: {family}")
    return protocol


def _options(protocol, method, dod, seed):
    base = load_config(ROOT / protocol["controller_config"])
    return dict(base, scenario_seed=seed, dynamicity=dod,
                total_planning_time_limit=5.0, diagnostics=False,
                trace_level="summary", algorithm=method)


def _validate_raw(raw, method, scenario, instance):
    metadata = raw["metadata"]
    metrics = raw["metrics"]
    if (metadata["algorithm"] != method or
            metadata["scenario_identifier"] != scenario.identifier or
            metadata["K_ref"] != scenario.fleet_size or
            not metadata.get("isolated_worker") or
            not metadata.get("independent_audit") or
            not all(metadata["independent_audit"].values()) or
            any(metrics[name] != 0 for name in VIOLATIONS) or
            metrics["max_optimization_latency"] > 5.0 + 1e-6):
        raise ValueError(f"Invalid final-holdout raw run: {instance.name} {method}")


def run_worker(name, dod, seed, method, output):
    protocol = validated_protocol()
    output = Path(output).resolve()
    if not output.is_relative_to((OUTPUT / "raw").resolve()) or output.exists():
        raise ValueError("Final worker output must be a new file under final_study/raw")
    if (name not in {row["instance"] for row in protocol["selected"].values()} or
            dod not in protocol["dynamicity"] or seed not in protocol["seeds"] or
            method not in protocol["methods"]):
        raise ValueError("Worker case is absent from committed final protocol")
    try:
        options = _options(protocol, method, dod, seed)
        started = perf_counter()
        instance, _, scenario, _ = prepare(name, options)
        result = EventDrivenSimulator(instance, scenario, simulation_config(options)).run()
        audit = audit_result(result, instance, scenario)
        if not all(audit.values()):
            raise AssertionError("Independent final-holdout audit failed")
        result.metadata["isolated_worker"] = True
        result.metadata["independent_audit"] = audit
        result.metrics["worker_wall_seconds"] = perf_counter() - started
        raw = asdict(result)
        _validate_raw(raw, method, scenario, instance)
        save_json(output, raw)
    except Exception as error:
        save_json(failure_path(output), dict(instance=name, dynamicity=dod, seed=seed,
                                                  method=method, source_sha256=source_hash(),
                                                  error_type=type(error).__name__,
                                                  error_message=str(error),
                                                  traceback=traceback.format_exc()))
        raise


def run():
    protocol = validated_protocol()
    protocol_hash = sha256(JSON_OUTPUT.read_bytes()).hexdigest()
    expected = len(FAMILIES) * len(protocol["dynamicity"]) * len(protocol["seeds"]) * len(protocol["methods"])
    manifest_path = OUTPUT / "manifest.json"
    prior = load_json(manifest_path)["records"] if manifest_path.exists() else []
    if prior and any(row["protocol_sha256"] != protocol_hash or
                     row["source_sha256"] != protocol["source_sha256"] for row in prior):
        raise ValueError("Final manifest contains a different protocol or source")
    records = {(row["scenario_id"], row["method"]): row for row in prior}
    if len(records) != len(prior):
        raise ValueError("Duplicate final-holdout records")
    for family in FAMILIES:
        name = protocol["selected"][family]["instance"]
        for dod, seed in product(protocol["dynamicity"], protocol["seeds"]):
            options = _options(protocol, protocol["methods"][0], dod, seed)
            instance, _, scenario, _ = prepare(name, options)
            for method in protocol["methods"]:
                effective = dict(options, algorithm=method)
                identity = identifier(dict(instance_sha256=instance.sha256,
                                           scenario=scenario.identifier, method=method,
                                           source=protocol["source_sha256"], protocol=protocol_hash,
                                           controller=protocol["controller_sha256"],
                                           runner=protocol["holdout_runner_sha256"],
                                           effective=effective))
                path = OUTPUT / "raw" / f"{name}_{dod:.2f}_{seed}_{method}_{identity[:12]}.json.gz"
                if failure_path(path).exists():
                    raise ValueError(f"Preserved final-run failure requires investigation: {path}")
                key = (scenario.identifier, method)
                if key in records and (records[key]["raw"] != path.relative_to(ROOT).as_posix()
                                       or not path.exists()):
                    raise ValueError("Previously recorded final raw file is missing or mismatched")
                if not path.exists():
                    subprocess.run([sys.executable, "-m", "scripts.run_final_holdout", "--worker",
                                    name, str(dod), str(seed), method, str(path)], cwd=ROOT, check=True)
                raw = load_json(path)
                _validate_raw(raw, method, scenario, instance)
                digest = sha256(path.read_bytes()).hexdigest()
                if key in records and records[key]["raw_sha256"] != digest:
                    raise ValueError("Previously opened final raw record changed")
                metrics = raw["metrics"]
                records[key] = dict(family=family, instance=name, instance_sha256=instance.sha256,
                                    dynamicity=dod, scenario_seed=seed,
                                    scenario_id=scenario.identifier, k_ref=scenario.fleet_size,
                                    method=method,
                                    raw=path.relative_to(ROOT).as_posix(), raw_sha256=digest,
                                    customers_served=metrics["customers_served"],
                                    complete_service=metrics["complete_service"],
                                    vehicles_activated=metrics["vehicles_activated"],
                                    total_distance=metrics["total_distance"],
                                    mean_optimization_latency=metrics["mean_optimization_latency"],
                                    p95_optimization_latency=metrics["p95_optimization_latency"],
                                    max_optimization_latency=metrics["max_optimization_latency"],
                                    worker_wall_seconds=metrics["worker_wall_seconds"],
                                    isolated_worker=True, independent_audit=True,
                                    source_sha256=protocol["source_sha256"],
                                    protocol_sha256=protocol_hash,
                                    controller_sha256=protocol["controller_sha256"],
                                    runner_sha256=protocol["holdout_runner_sha256"])
                ordered = sorted(records.values(), key=lambda row: (
                    row["family"], row["instance"], row["dynamicity"],
                    row["scenario_seed"], row["method"]))
                save_json(manifest_path, dict(status="final_complete" if len(ordered) == expected
                              else "final_incomplete", expected_scenarios=54,
                              expected_records=expected, protocol_sha256=protocol_hash,
                              source_sha256=protocol["source_sha256"], records=ordered))
                print(f"final {len(ordered)}/{expected} {name} DoD={dod} seed={seed} "
                      f"{method} served={metrics['customers_served']}", flush=True)
    return list(records.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=5, metavar=("INSTANCE", "DOD", "SEED", "METHOD", "OUTPUT"),
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        name, dod, seed, method, output = args.worker
        run_worker(name, float(dod), int(seed), method, output)
    else:
        run()
