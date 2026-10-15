"""Audited paired analysis for the five-method development comparison."""

import argparse
import csv
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from random import Random
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evrp.experiments import load_config
from evrp.storage import ROOT, load_json, save_json
from scripts.run_portfolio_campaign import CONFIG_PATH, OUTPUT, source_hash


def family(name):
    return name.split("_")[0].rstrip("0123456789").upper()


def paired_bootstrap(values, draws=5000, seed=0):
    if not values:
        return None
    rng = Random(seed)
    n = len(values)
    samples = sorted(mean(values[rng.randrange(n)] for _ in range(n))
                     for _ in range(draws))
    return [samples[int(0.025 * draws)], samples[int(0.975 * draws)]]


def _write_csv(path, rows):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(allow_incomplete=False):
    study = load_config(CONFIG_PATH)
    methods = tuple(study["methods"])
    manifest = load_json(OUTPUT / "manifest.json")
    records = manifest["records"]
    expected = 66 * len(methods)
    if len(records) != expected and not allow_incomplete:
        raise ValueError(f"Development grid incomplete: {len(records)}/{expected}")
    code = source_hash()
    protocol = sha256(CONFIG_PATH.read_bytes()).hexdigest()
    controller = sha256((ROOT / study["base_controller"]).read_bytes()).hexdigest()
    grouped = {}
    latencies = {method: [] for method in methods}
    controller_wall = {method: 0.0 for method in methods}
    for row in records:
        if (row["source_sha256"], row["protocol_sha256"], row["controller_sha256"]) != (
                code, protocol, controller):
            raise ValueError("Mixed code or protocol versions in development manifest")
        if not row.get("isolated_worker") or not row.get("independent_audit"):
            raise ValueError("Non-isolated or unaudited development record")
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError(f"Raw evidence hash mismatch: {path}")
        raw = load_json(path)
        if not all(raw["metadata"].get("independent_audit", {}).values()):
            raise ValueError("Independent audit missing or failed")
        if row["max_optimization_latency"] > 5.0 + 1e-6:
            raise ValueError("Decision latency exceeded five seconds")
        if any(raw["metrics"][name] for name in (
                "hidden_information_violations", "time_window_violations",
                "battery_violations", "capacity_violations")):
            raise ValueError("Physical or information-boundary violation")
        run_latencies = [decision["optimization_latency_seconds"]
                         for decision in raw["decisions"]
                         if decision.get("optimization_latency_seconds") is not None]
        if not run_latencies:
            raise ValueError("Missing per-decision optimization latencies")
        if not np.isclose(mean(run_latencies), row["mean_optimization_latency"], atol=1e-6):
            raise ValueError("Decision trace disagrees with reported mean latency")
        if not np.isclose(max(run_latencies), row["max_optimization_latency"], atol=1e-6):
            raise ValueError("Decision trace disagrees with reported maximum latency")
        latencies[row["method"]].extend(run_latencies)
        controller_wall[row["method"]] += raw["metrics"]["complete_instance_wall_clock_seconds"]
        key = (row["instance"], row["dynamicity"], row["scenario_seed"])
        if row["method"] in grouped.setdefault(key, {}):
            raise ValueError("Duplicate method in a paired scenario")
        grouped[key][row["method"]] = row
    paired = {key: runs for key, runs in grouped.items() if set(runs) == set(methods)}
    if not allow_incomplete and len(paired) != 66:
        raise ValueError(f"Expected 66 fully paired scenarios, got {len(paired)}")
    for runs in paired.values():
        if len({row["scenario_id"] for row in runs.values()}) != 1 or len({
                row["instance_sha256"] for row in runs.values()}) != 1:
            raise ValueError("Paired scenario or instance hashes differ")
    # The first two characters distinguish clustered, random, and mixed families;
    # the instance prefix also carries the 1/2 subtype.
    scopes = [("overall", lambda key: True)] + [
        (f"family_{name}", lambda key, name=name: family(key[0]) == name)
        for name in ("C", "R", "RC")]
    scopes += [(f"family_{name}", lambda key, name=name: key[0].lower().startswith(name.lower()))
               for name in ("C1", "C2", "R1", "R2", "RC1", "RC2")]
    scopes += [(f"dod_{dod:.2f}", lambda key, dod=dod: key[1] == dod)
               for dod in (0.25, 0.5, 0.75)]
    comparisons = []
    for scope, selector in scopes:
        keys = [key for key in paired if selector(key)]
        for left, right in combinations(methods, 2):
            deltas = [paired[key][left]["customers_served"] - paired[key][right]["customers_served"]
                      for key in keys]
            equal_service = [key for key in keys if paired[key][left]["customers_served"] ==
                             paired[key][right]["customers_served"]]
            ev_deltas = [paired[key][left]["vehicles_activated"] -
                         paired[key][right]["vehicles_activated"] for key in equal_service]
            equal_ev = [key for key in equal_service if paired[key][left]["vehicles_activated"] ==
                        paired[key][right]["vehicles_activated"]]
            distance_deltas = [paired[key][left]["total_distance"] -
                               paired[key][right]["total_distance"] for key in equal_ev]
            comparisons.append(dict(scope=scope, left=left, right=right, n=len(keys),
                                    service_diff=mean(deltas) if deltas else None,
                                    service_ci=paired_bootstrap(deltas),
                                    service_wins=sum(delta > 0 for delta in deltas),
                                    service_ties=sum(delta == 0 for delta in deltas),
                                    service_losses=sum(delta < 0 for delta in deltas),
                                    complete_rate_diff=(mean(
                                        int(paired[key][left]["complete_service"])
                                        - int(paired[key][right]["complete_service"])
                                        for key in keys) if keys else None),
                                    equal_service_n=len(equal_service),
                                    ev_diff_equal_service=mean(ev_deltas) if ev_deltas else None,
                                    equal_service_ev_n=len(equal_ev),
                                    distance_diff_equal_service_ev=(mean(distance_deltas)
                                                                    if distance_deltas else None)))
    runtime = []
    for method in methods:
        rows = [row for row in records if row["method"] == method]
        if rows:
            times = latencies[method]
            runtime.append(dict(method=method, n=len(rows), decision_epochs=len(times),
                                mean_decision_seconds=mean(times),
                                median_decision_seconds=float(np.median(times)),
                                p95_decision_seconds=float(np.percentile(times, 95)),
                                max_decision_seconds=max(times),
                                total_controller_wall_seconds=controller_wall[method],
                                worker_wall_seconds=sum(row["worker_wall_seconds"] for row in rows),
                                fraction_decisions_within_five_seconds=mean(
                                    elapsed <= 5.0 for elapsed in times)))
    report = dict(status="complete_development" if len(paired) == 66 else "incomplete_development",
                  scenarios=len(paired), records=len(records), expected_records=expected,
                  comparisons=comparisons, runtime=runtime)
    out = OUTPUT / "analysis"
    save_json(out / "paired_analysis.json", report)
    _write_csv(out / "paired_comparisons.csv", [{**row, "service_ci": str(row["service_ci"])}
                                                for row in comparisons])
    _write_csv(out / "runtime.csv", runtime)
    if paired:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        means = [mean(paired[key][method]["customers_served"] for key in paired)
                 for method in methods]
        ax.bar([method.replace("MPC_", "") for method in methods], means,
               color=["#6b7280", "#2563eb", "#0f766e", "#ca8a04", "#b45309"])
        ax.set_ylabel("Mean customers served")
        ax.set_ylim(0, 100)
        ax.set_title("Paired development scenarios" if len(paired) == 66
                     else "Incomplete development pilot")
        fig.tight_layout()
        fig.savefig(out / "service_by_optimizer.png", dpi=180)
        plt.close(fig)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    result = analyze(args.allow_incomplete)
    print(result["status"], result["scenarios"], result["records"])
