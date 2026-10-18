"""Audited paired analysis for the five-method development comparison."""

import argparse
import csv
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from random import Random
import re
from statistics import mean
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evrp.experiments import load_config
from evrp.storage import ROOT, load_json, save_json
from scripts.run_portfolio_campaign import CONFIG_PATH, OUTPUT, source_hash


def family(name):
    return name.split("_")[0].rstrip("0123456789").upper()


def family_subtype(name):
    match = re.fullmatch(r"(rc|c|r)([12])\d{2}_21", name, re.IGNORECASE)
    if not match:
        raise ValueError(f"Unexpected benchmark instance name: {name}")
    return (match.group(1) + match.group(2)).upper()


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


MECHANISM_FIELDS = {
    "MPC_MCTS": ("iterations", "nodes_expanded", "service_improvements",
                 "objective_only_improvements", "service_gain_over_root",
                 "exact_decoded_options", "ejection_chains_generated",
                 "ejection_chains_selected", "rollout_count"),
    "MPC_ALNS": ("iterations", "accepted_moves", "improving_moves",
                 "exact_decoder_calls"),
    "MPC_HGS": ("generations", "crossovers", "educated", "population_size",
                "diversity", "root_service_insertions", "offspring_service_insertions",
                "exact_decoder_calls"),
    "MPC_ACS": ("ants_completed", "complete_service_ants", "pheromone_updates",
                "service_improvements_over_constructor",
                "objective_improvements_at_equal_service", "exact_decoder_calls"),
}


def mechanism_record(row, decision):
    diagnostics = (decision.get("optimizer") or {}).get("diagnostics") or {}
    method = row["method"]
    if not diagnostics or method not in MECHANISM_FIELDS:
        return None
    metrics = {key: value for key in MECHANISM_FIELDS[method]
               if isinstance((value := diagnostics.get(key)), (int, float))}
    if (decision.get("constructor_service") is not None and
            decision.get("best_service_after_search") is not None):
        metrics["service_gain_over_constructor"] = max(
            0, decision["best_service_after_search"] - decision["constructor_service"])
    counts = {}
    weights = {}
    if method == "MPC_MCTS":
        metrics["root_control_alternatives"] = len(diagnostics.get("root_control_statistics", {}))
        metrics["keep_constructor_selected"] = int(
            diagnostics.get("selected_root_control") == "KEEP_CONSTRUCTOR")
        selected = diagnostics.get("selected_root_control")
        root_stats = diagnostics.get("root_control_statistics", {})
        if selected in root_stats:
            metrics["selected_root_visits"] = root_stats[selected]["visits"]
        for key in ("rollout_policy_usage", "rollout_policy_improvements"):
            counts[key] = diagnostics.get(key, {})
        counts["root_control_selection"] = {
            "KEEP_CONSTRUCTOR" if metrics["keep_constructor_selected"] else "OTHER_CONTROL": 1}
    elif method == "MPC_ALNS":
        for key in ("destroy_counts", "repair_counts"):
            counts[key] = diagnostics.get(key, {})
        for key in ("destroy_weights", "repair_weights"):
            weights[key] = diagnostics.get(key, {})
    elif method == "MPC_ACS":
        times = diagnostics.get("best_improvement_times", [])
        metrics["best_improvements"] = len(times)
        if times:
            metrics["first_best_improvement_seconds"] = min(times)
            metrics["last_best_improvement_seconds"] = max(times)
    return dict(method=method, family=family(row["instance"]),
                subtype=family_subtype(row["instance"]),
                dynamicity=row["dynamicity"], metrics=metrics, counts=counts,
                weights=weights)


def summarize_mechanisms(records):
    scopes = {"overall": lambda record: True}
    for subtype in ("C1", "C2", "R1", "R2", "RC1", "RC2"):
        scopes[f"family_{subtype}"] = lambda record, subtype=subtype: record["subtype"] == subtype
    for dod in (0.25, 0.5, 0.75):
        scopes[f"dod_{dod:.2f}"] = lambda record, dod=dod: record["dynamicity"] == dod
    summary = []
    operators = []
    for scope, includes in scopes.items():
        for method in MECHANISM_FIELDS:
            selected = [record for record in records if record["method"] == method and includes(record)]
            if not selected:
                continue
            fields = sorted({key for record in selected for key in record["metrics"]})
            for key in fields:
                values = [record["metrics"][key] for record in selected if key in record["metrics"]]
                summary.append(dict(scope=scope, method=method, calls=len(selected),
                                    metric=key, recorded_calls=len(values), total=sum(values),
                                    mean_per_recorded_call=mean(values)))
            for kind in ("counts", "weights"):
                names = sorted({key for record in selected for key in record[kind]})
                for name in names:
                    labels = sorted({label for record in selected
                                     for label in record[kind].get(name, {})})
                    for label in labels:
                        values = [record[kind][name][label] for record in selected
                                  if label in record[kind].get(name, {})]
                        operators.append(dict(scope=scope, method=method, kind=kind,
                                              diagnostic=name, label=label,
                                              recorded_calls=len(values), total=sum(values),
                                              mean_per_recorded_call=mean(values)))
    return summary, operators


def plot_development(out, methods, service, comparisons, latencies, operators):
    labels = ["MPC + Completion" if method == "MPC_COMPLETION" else
              method.replace("MPC_", "MPC + ") for method in methods]
    palette = ("#59636e", "#2474a6", "#12806a", "#bd7b13", "#a14851", "#755199")
    overall = {row["method"]: row for row in service if row["scope"] == "overall"}

    fig, ax = plt.subplots(figsize=(10, 3.7))
    ax.text(0.5, 0.88, "Observable fleet state + released requests", ha="center", fontsize=12)
    ax.annotate("Event-triggered MPC: common constructor", (0.5, 0.69),
                ha="center", fontsize=12, fontweight="bold")
    for index, (label, color) in enumerate(zip(labels, palette)):
        x = (index + 0.5) / len(methods)
        ax.text(x, 0.43, label, ha="center", va="center", color="white",
                bbox=dict(facecolor=color, edgecolor="none", boxstyle="round,pad=0.4"))
        ax.plot([0.5, x], [0.64, 0.49], color="#84919a", lw=1)
        ax.plot([x, 0.5], [0.35, 0.23], color="#84919a", lw=1)
    ax.text(0.5, 0.13, "Exact EV validation  |  execute first control  |  observe next event",
            ha="center", fontsize=11)
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "mpc_architecture.png", dpi=220)
    plt.close(fig)

    def bars(filename, metric, ylabel, ylim=None):
        fig, ax = plt.subplots(figsize=(8.5, 4.5))
        values = [overall[method][metric] for method in methods]
        ax.bar(labels, values, color=palette)
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", labelrotation=25)
        if ylim:
            ax.set_ylim(*ylim)
        fig.tight_layout()
        fig.savefig(out / filename, dpi=220)
        plt.close(fig)

    bars("service_by_optimizer.png", "mean_customers_served", "Mean customers served")
    bars("complete_service_by_optimizer.png", "complete_service_rate",
         "Complete-service fraction", (0, 1))

    baseline = methods[0]
    rows = [row for row in comparisons if row["scope"] == "overall" and
            row["left"] == baseline]
    if rows:
        fig, ax = plt.subplots(figsize=(8.5, 4.5))
        positions = np.arange(len(rows))
        effects = [-row["service_diff"] for row in rows]
        lower = [effect + row["service_ci"][1] for effect, row in zip(effects, rows)]
        upper = [-row["service_ci"][0] - effect for effect, row in zip(effects, rows)]
        ax.errorbar(effects, positions, xerr=[lower, upper], fmt="o", capsize=4,
                    color="#2474a6")
        ax.axvline(0, color="#59636e", lw=1)
        ax.set_yticks(positions, [row["right"].replace("MPC_", "MPC + ") for row in rows])
        ax.set_xlabel("Mean paired customers served over MPC + Completion (95% bootstrap CI)")
        fig.tight_layout()
        fig.savefig(out / "paired_service_over_completion.png", dpi=220)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    for method, label, color in zip(methods, labels, palette):
        values = [next(row["mean_customers_served"] for row in service
                       if row["scope"] == f"dod_{dod:.2f}" and row["method"] == method)
                  for dod in (0.25, 0.5, 0.75)]
        ax.plot((0.25, 0.5, 0.75), values, marker="o", label=label, color=color)
    ax.set(xlabel="Degree of dynamicity", ylabel="Mean customers served", xticks=(0.25, 0.5, 0.75))
    ax.legend(ncol=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "service_by_dynamicity.png", dpi=220)
    plt.close(fig)

    families = ("C1", "C2", "R1", "R2", "RC1", "RC2")
    matrix = np.array([[next(row["mean_customers_served"] for row in service
                             if row["scope"] == f"family_{group}" and row["method"] == method)
                        for method in methods] for group in families])
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    image = ax.imshow(matrix, aspect="auto", cmap="YlGnBu", vmin=0, vmax=100)
    ax.set_xticks(range(len(methods)), labels, rotation=25, ha="right")
    ax.set_yticks(range(len(families)), families)
    for i in range(len(families)):
        for j in range(len(methods)):
            ax.text(j, i, f"{matrix[i, j]:.1f}", ha="center", va="center",
                    color="white" if matrix[i, j] > 65 else "black", fontsize=9)
    fig.colorbar(image, ax=ax, label="Mean customers served")
    fig.tight_layout()
    fig.savefig(out / "family_optimizer_heatmap.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.boxplot([latencies[method] for method in methods], showfliers=False,
               medianprops=dict(color="#a14851"))
    ax.set_xticks(range(1, len(methods) + 1), labels)
    ax.axhline(5, color="#a14851", linestyle="--", label="5-second limit")
    ax.set_ylabel("Optimization decision latency (seconds)")
    ax.tick_params(axis="x", labelrotation=25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "decision_latency_distribution.png", dpi=220)
    plt.close(fig)

    usage = {row["label"]: row["total"] for row in operators if
             row["scope"] == "overall" and row["method"] == "MPC_MCTS" and
             row["diagnostic"] == "rollout_policy_usage"}
    improvements = {row["label"]: row["total"] for row in operators if
                    row["scope"] == "overall" and row["method"] == "MPC_MCTS" and
                    row["diagnostic"] == "rollout_policy_improvements"}
    if usage:
        policies = ("CRITICAL_REGRET", "EARLIEST_DEADLINE", "RESERVE_PRESERVING")
        rates = [improvements.get(policy, 0) / max(1, usage.get(policy, 0)) for policy in policies]
        fig, ax = plt.subplots(figsize=(8.5, 4.5))
        ax.bar([name.replace("_", " ").title() for name in policies], rates,
               color=("#2474a6", "#12806a", "#bd7b13"))
        ax.set_ylabel("Recorded improvements per rollout")
        fig.tight_layout()
        fig.savefig(out / "mcts_rollout_policy_contribution.png", dpi=220)
        plt.close(fig)


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
    k_refs = {}
    latencies = {method: [] for method in methods}
    controller_wall = {method: 0.0 for method in methods}
    optimizer_diagnostics = {method: defaultdict(list) for method in methods}
    policy_totals = {method: defaultdict(lambda: defaultdict(int)) for method in methods}
    mechanism_decisions = []
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
        if (not raw["metadata"].get("independent_audit") or
                not all(raw["metadata"]["independent_audit"].values())):
            raise ValueError("Independent audit missing or failed")
        if (raw["metadata"]["instance"] != row["instance"] or
                raw["metadata"]["instance_sha256"] != row["instance_sha256"] or
                raw["metadata"]["scenario_identifier"] != row["scenario_id"] or
                raw["metadata"]["algorithm"] != row["method"] or
                raw["metadata"]["K_ref"] <= 0):
            raise ValueError("Development raw instance, scenario, method, or K_ref mismatch")
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
        for decision in raw["decisions"]:
            mechanism = mechanism_record(row, decision)
            if mechanism is not None:
                mechanism_decisions.append(mechanism)
            optimizer = decision.get("optimizer") or {}
            diagnostics = optimizer.get("diagnostics") or {}
            for key, value in diagnostics.items():
                if key in ("rollout_policy_usage", "rollout_policy_improvements"):
                    for policy, count in value.items():
                        policy_totals[row["method"]][key][policy] += count
                elif key in ("rollout_count", "service_improvements",
                             "objective_only_improvements", "nodes_expanded", "iterations",
                             "exact_decoded_options", "exact_decoder_calls", "elapsed",
                             "service_gain_over_root", "selected_root_control"):
                    if key == "selected_root_control":
                        optimizer_diagnostics[row["method"]]["constructor_control_selected"].append(
                            int(value == "KEEP_CONSTRUCTOR"))
                    elif isinstance(value, (int, float)):
                        optimizer_diagnostics[row["method"]][key].append(value)
        key = (row["instance"], row["dynamicity"], row["scenario_seed"])
        if key in k_refs and k_refs[key] != raw["metadata"]["K_ref"]:
            raise ValueError("Methods used different reference fleet sizes")
        k_refs[key] = raw["metadata"]["K_ref"]
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
    service = []
    for scope, selector in scopes:
        keys = [key for key in paired if selector(key)]
        for method in methods:
            if keys:
                service.append(dict(scope=scope, method=method, scenarios=len(keys),
                                    mean_customers_served=mean(
                                        paired[key][method]["customers_served"] for key in keys),
                                    complete_service_rate=mean(
                                        int(paired[key][method]["complete_service"]) for key in keys)))
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
    diagnostics_report = {}
    for method in methods:
        diagnostics_report[method] = dict(
            measured_decisions=max((len(values) for values in optimizer_diagnostics[method].values()),
                                   default=0),
            numeric={key: dict(total=sum(values), mean_per_recorded_decision=mean(values),
                               recorded_decisions=len(values))
                     for key, values in optimizer_diagnostics[method].items()},
            policies={key: dict(values) for key, values in policy_totals[method].items()})
    mechanism_summary, operator_summary = summarize_mechanisms(mechanism_decisions)
    report = dict(status="complete_development" if len(paired) == 66 else "incomplete_development",
                  scenarios=len(paired), records=len(records), expected_records=expected,
                  service=service, comparisons=comparisons, runtime=runtime,
                  optimizer_diagnostics=diagnostics_report,
                  mechanism_summary=mechanism_summary, operator_summary=operator_summary)
    out = OUTPUT / "analysis"
    save_json(out / "paired_analysis.json", report)
    _write_csv(out / "paired_comparisons.csv", [{**row, "service_ci": str(row["service_ci"])}
                                                for row in comparisons])
    _write_csv(out / "service_summary.csv", service)
    _write_csv(out / "runtime.csv", runtime)
    _write_csv(out / "mechanism_summary.csv", mechanism_summary)
    _write_csv(out / "operator_summary.csv", operator_summary)
    if len(paired) == 66:
        plot_development(out, methods, service, comparisons, latencies, operator_summary)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    result = analyze(args.allow_incomplete)
    print(result["status"], result["scenarios"], result["records"])
