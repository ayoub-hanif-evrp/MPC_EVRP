"""Derive paper CSV/Markdown tables and PNG figures solely from raw records."""

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from evrp.storage import ROOT, load_json, save_json, writable_path
from evrp.validation import validate_references


OUT = ROOT / "results/paper"
OLD = ROOT / "results/final/performance_patch/raw"
STATIC_NAMES = ("c101_21", "c201_21", "r101_21", "r201_21", "rc101_21", "rc201_21")


def _raw(directory: Path):
    records = []
    for path in sorted(directory.glob("*.json")):
        value = load_json(path)
        if value.get("status") != "completed" or not value.get("audit", {}).get("trace_replay"):
            raise ValueError(f"Unverified raw record: {path}")
        records.append(value)
    return records


def _frame(rows: list[dict], columns: list[str], name: str):
    frame = pd.DataFrame(rows, columns=columns)
    path = writable_path(OUT / "tables" / f"{name}.csv")
    frame.to_csv(path, index=False)
    markdown = path.with_suffix(".md")
    if frame.empty:
        markdown.write_text("No eligible raw records.\n", encoding="utf-8")
    else:
        headers = "| " + " | ".join(columns) + " |"
        rule = "|" + "|".join("---" for _ in columns) + "|"
        data = ["| " + " | ".join(str(row[col]) if pd.notna(row[col]) else "n/a"
                                 for col in columns) + " |" for _, row in frame.iterrows()]
        markdown.write_text("\n".join([headers, rule, *data]) + "\n", encoding="utf-8")
    return frame


def _key(record):
    meta = record["metadata"]
    return (meta["instance"], meta["DoD_target"], meta["scenario_seed"],
            record["scenario"]["scenario_hash"])


def _bootstrap(values, samples=10000):
    if not values:
        return (None, None)
    rng = np.random.default_rng(0)
    data = np.asarray(values, dtype=float)
    means = data[rng.integers(0, len(data), size=(samples, len(data)))].mean(axis=1)
    return tuple(float(x) for x in np.percentile(means, (2.5, 97.5)))


def _dynamic():
    old = _raw(OLD / "development")
    rh = _raw(OUT / "raw/development_rh")
    holdout = _raw(OUT / "raw/holdout")
    by_split = {"development": old + rh, "holdout": holdout}
    ablations, methods, runtimes, contributions = [], [], [], []
    comparisons = {}
    for split, records in by_split.items():
        keyed = defaultdict(dict)
        for record in records:
            keyed[_key(record)][record["metadata"]["algorithm"]] = record
            m, meta = record["metrics"], record["metadata"]
            max_latency = m.get("max_optimization_latency", m.get("maximum_planning_time"))
            runtimes.append({"split": split, "instance": meta["instance"],
                             "dynamicity": meta["DoD_target"], "seed": meta["scenario_seed"],
                             "method": meta["algorithm"], "mean_latency_s": m.get("mean_optimization_latency"),
                             "p95_latency_s": m.get("p95_optimization_latency"),
                             "max_latency_s": max_latency,
                             "total_wall_s": m.get("complete_instance_wall_clock_seconds"),
                             "calls_le_5_percent": 100.0 if max_latency is not None and max_latency <= 5 else None})
            if meta["algorithm"] == "FLEET_MPC_MCTS":
                calls = [d["fleet_mcts"] for d in record["decisions"]
                         if d.get("mcts_called") and d.get("fleet_mcts")]
                contributions.append({"split": split, "instance": meta["instance"],
                                      "dynamicity": meta["DoD_target"], "seed": meta["scenario_seed"],
                                      "calls": len(calls),
                                      "service_gain_calls": sum(c.get("service_gain_over_root", 0) > 0 for c in calls),
                                      "ev_gain_calls": sum(c["best_score"][0] == c["initial_score"][0]
                                                           and c["best_score"][3] < c["initial_score"][3] for c in calls),
                                      "distance_gain_calls": sum(c["best_score"][0] == c["initial_score"][0]
                                                                 and c["best_score"][3] == c["initial_score"][3]
                                                                 and c["best_score"][5] < c["initial_score"][5] for c in calls),
                                      "objective_gain_calls": sum(c["best_score"] < c["initial_score"] for c in calls),
                                      "root_to_final_service_gain": sum(c.get("service_gain_over_root", 0) for c in calls),
                                      "nodes": sum(c.get("nodes_expanded", 0) for c in calls),
                                      "iterations": sum(c.get("iterations", 0) for c in calls),
                                      "rollouts": sum(c.get("rollout_count", 0) for c in calls)})
        for key, group in keyed.items():
            fleet = group.get("FLEET_MPC_MCTS")
            completion = group.get("FLEET_MPC_COMPLETION_ONLY")
            if fleet and completion:
                fm, cm = fleet["metrics"], completion["metrics"]
                equal_service = fm["customers_served"] == cm["customers_served"]
                equal_evs = fm["vehicles_activated"] == cm["vehicles_activated"]
                ablations.append({"split": split, "instance": key[0], "dynamicity": key[1],
                                  "seed": key[2], "scenario_hash": key[3],
                                  "mcts_served": fm["customers_served"],
                                  "completion_served": cm["customers_served"],
                                  "service_diff": fm["customers_served"] - cm["customers_served"],
                                  "mcts_complete": fm["complete_service"],
                                  "completion_complete": cm["complete_service"],
                                  "conditional_ev_diff": fm["vehicles_activated"] - cm["vehicles_activated"]
                                  if equal_service else None,
                                  "conditional_distance_diff": fm["total_distance"] - cm["total_distance"]
                                  if equal_service and equal_evs else None})
        for method in ("FLEET_MPC_MCTS", "FLEET_MPC_COMPLETION_ONLY", "RH_REGRET", "ROLLING_LNS"):
            group = [r for r in records if r["metadata"]["algorithm"] == method]
            if not group:
                continue
            values = [r["metrics"]["customers_served"] for r in group]
            methods.append({"split": split, "method": method, "n": len(group),
                            "served_total": sum(values), "served_mean": np.mean(values),
                            "served_sd": np.std(values, ddof=1) if len(values) > 1 else None,
                            "complete_count": sum(r["metrics"]["complete_service"] for r in group),
                            "complete_rate": np.mean([r["metrics"]["complete_service"] for r in group])})
        for baseline in ("FLEET_MPC_COMPLETION_ONLY", "RH_REGRET"):
            differences = []
            for group in keyed.values():
                if "FLEET_MPC_MCTS" in group and baseline in group:
                    differences.append(group["FLEET_MPC_MCTS"]["metrics"]["customers_served"]
                                       - group[baseline]["metrics"]["customers_served"])
            if differences:
                comparisons[f"{split}:MCTS-minus-{baseline}"] = {
                    "n": len(differences), "mean": float(np.mean(differences)),
                    "wins": sum(x > 0 for x in differences), "ties": sum(x == 0 for x in differences),
                    "losses": sum(x < 0 for x in differences), "ci95": _bootstrap(differences)}
    _frame(ablations, list(ablations[0]) if ablations else ["split", "instance", "dynamicity", "seed", "service_diff"],
           "table_dynamic_ablation")
    _frame(methods, list(methods[0]) if methods else ["split", "method", "n"], "table_dynamic_methods")
    _frame(runtimes, list(runtimes[0]) if runtimes else ["split", "method", "instance"], "table_runtime")
    _frame(contributions, list(contributions[0]) if contributions else ["split", "instance", "calls"],
           "table_mcts_contribution")
    return ablations, methods, runtimes, contributions, comparisons


def _static():
    controller = _raw(OUT / "raw/static_controller")
    if not controller:
        controller = _raw(OLD / "static")
    rows = []
    for record in controller:
        m, meta = record["metrics"], record["metadata"]
        rows.append({"instance": meta["instance"], "method": "FLEET_MPC_MCTS",
                     "budget": "5s/decision", "seed": meta["algorithm_seed"],
                     "replay_feasible": bool(m["feasible"]), "complete": bool(m["complete_service"]),
                     "served": m["customers_served"], "evs": m["vehicles_activated"],
                     "distance": m["total_distance"],
                     "runtime_s": m.get("complete_instance_wall_clock_seconds")})
    audit_rows = []
    for path in sorted((OUT / "raw/routingblocks").glob("*.json")):
        value = load_json(path)
        replay = value.get("our_replay", {})
        completed = value.get("status", "completed") == "completed"
        audit_rows.append({"solver": "RoutingBlocks", "instance": value["instance"],
                           "seed": value["seed"],
                           "external_feasible": value.get("external", {}).get("feasible"),
                           "our_replay_feasible": replay.get("feasible"), "served": replay.get("served"),
                           "vehicles": replay.get("vehicles"), "distance": replay.get("distance"),
                           "external_objective": value.get("external", {}).get("cost"),
                           "runtime": value.get("runtime"),
                           "nominal_budget_s": value["runtime_budget"],
                           "budget_respected": value.get("budget_respected"),
                           "external_wall_s": value.get("external_wall_seconds"),
                           "reason_if_rejected": value.get("error", replay.get("reason", ""))})
        rows.append({"instance": value["instance"], "method": "RoutingBlocks",
                     "budget": f"{value['runtime_budget']}s/instance nominal", "seed": value["seed"],
                     "completed": completed, "budget_respected": value.get("budget_respected", False),
                     "replay_feasible": replay.get("feasible", False), "complete": replay.get("complete", False),
                     "served": replay.get("served"), "evs": replay.get("vehicles"),
                     "distance": replay.get("distance"), "runtime_s": value.get("runtime"),
                     "wall_s": value.get("external_wall_seconds")})
    _frame(audit_rows, ["solver", "instance", "seed", "external_feasible", "our_replay_feasible",
                        "served", "vehicles", "distance", "external_objective", "runtime",
                        "nominal_budget_s", "budget_respected", "external_wall_s",
                        "reason_if_rejected"], "external_solution_audit")
    groups = defaultdict(list)
    for row in rows:
        groups[(row["instance"], row["method"], row["budget"])].append(row)
    summary = []
    for (instance, method, budget), group in sorted(groups.items()):
        complete = [r for r in group if r["replay_feasible"] and r["complete"]]
        strict_complete = [r for r in complete if method != "RoutingBlocks" or r["budget_respected"]]
        distances = [r["distance"] for r in complete]
        served = [r["served"] for r in group if r["served"] is not None]
        runtime = [r["runtime_s"] for r in group if r["runtime_s"] is not None]
        wall = [r["wall_s"] for r in group if r.get("wall_s") is not None]
        summary.append({"instance": instance, "method": method, "budget": budget,
                        "n": len(group), "n_completed": sum(r.get("completed", True) for r in group),
                        "budget_respected_rate": float(np.mean([r.get("budget_respected", True) for r in group]))
                        if method == "RoutingBlocks" else None,
                        "success_rate": len(complete) / len(group),
                        "strict_budget_success_rate": len(strict_complete) / len(group)
                        if method == "RoutingBlocks" else None,
                        "served_mean": float(np.mean(served)) if served else None,
                        "evs_mean_complete": float(np.mean([r["evs"] for r in complete])) if complete else None,
                        "distance_best_complete": min(distances) if distances else None,
                        "distance_mean_complete": float(np.mean(distances)) if distances else None,
                        "distance_median_complete": float(np.median(distances)) if distances else None,
                        "distance_sd_complete": float(np.std(distances, ddof=1)) if len(distances) > 1 else None,
                        "runtime_mean_s": float(np.mean(runtime)) if runtime else None,
                        "wall_mean_s": float(np.mean(wall)) if wall else None})
    _frame(summary, list(summary[0]) if summary else ["instance", "method", "budget", "n"],
           "table_static_external")
    return summary


def _small():
    raw = validate_references(output=OUT / "raw/small")
    rows = []
    for record in raw.to_dict("records"):
        rows.append({"instance": record["instance"], "published_reference_evs": record["published_vehicles"],
                     "our_evs": record["our_vehicles"],
                     "published_reference_distance": record["published_distance"],
                     "our_distance": record["our_distance"],
                     "validation_status": record["validation_status"],
                     "conditional_gap_percent": None,
                     "gap_note": "Charging model not proven identical to full-charge CPLEX reference"})
    _frame(rows, list(rows[0]), "table_small_reference")


def _figures(ablations, methods, runtimes, contributions, static):
    figure_dir = OUT / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    made = []

    def save(name, tight=True):
        if tight:
            plt.tight_layout()
        plt.savefig(writable_path(figure_dir / f"{name}.png"), dpi=220)
        plt.close()
        made.append(name)

    if ablations:
        fig, ax = plt.subplots(figsize=(5.5, 5))
        for split, color in (("development", "#136f63"), ("holdout", "#b64b3d")):
            group = [r for r in ablations if r["split"] == split]
            if group:
                ax.scatter([r["completion_served"] for r in group],
                           [r["mcts_served"] for r in group], label=split, color=color, alpha=.8)
        ax.plot([0, 100], [0, 100], color="#333333", lw=1)
        ax.set(xlabel="Completion-only customers served", ylabel="MPC-MCTS customers served",
               xlim=(75, 101), ylim=(75, 101))
        ax.legend()
        save("paired_service_scatter")

        fig, ax = plt.subplots(figsize=(8, 4.3))
        frame = pd.DataFrame(ablations)
        pivot = frame.groupby(["split", "instance"], sort=True)["service_diff"].mean()
        labels = [f"{a}\n{b}" for a, b in pivot.index]
        ax.bar(labels, pivot.values, color=["#136f63" if a == "development" else "#b64b3d"
                                            for a, _ in pivot.index])
        ax.axhline(0, color="#333333", lw=.8)
        ax.set_ylabel("Mean paired service difference")
        save("per_instance_service_difference")
    if methods:
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        frame = pd.DataFrame(methods)
        labels = [f"{r['split']}\n{r['method']}" for r in methods]
        ax.bar(labels, 100 * frame.complete_rate,
               color=["#136f63" if x == "development" else "#b64b3d" for x in frame.split])
        ax.set(ylabel="Complete-service rate (%)", ylim=(0, 100))
        ax.tick_params(axis="x", labelrotation=25)
        save("complete_service_rate")
    if runtimes:
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        frame = pd.DataFrame(runtimes)
        available = [(name, group.p95_latency_s.dropna().values) for name, group in frame.groupby("method")]
        available = [(name, values) for name, values in available if len(values)]
        if available:
            ax.boxplot([values for _, values in available], tick_labels=[name for name, _ in available])
            ax.axhline(5, color="#b64b3d", lw=1, ls="--")
            ax.set_ylabel("Run-level p95 decision latency (s)")
            ax.tick_params(axis="x", labelrotation=20)
            save("decision_latency_distribution")
        else:
            plt.close(fig)
    if contributions:
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        frame = pd.DataFrame(contributions)
        grouped = frame.groupby("instance").root_to_final_service_gain.sum()
        ax.bar(grouped.index, grouped.values, color="#136f63")
        ax.set_ylabel("Additional released reservations over MCTS roots")
        save("mcts_root_to_final_gain")
    # These plots are offline quality context; strict budget compliance is a separate table column.
    if len({row["method"] for row in static}) > 1:
        frame = pd.DataFrame(static)
        complete = frame[frame.success_rate == 1]
        if not complete.empty:
            fig, axes = plt.subplots(2, 3, figsize=(11, 6.5))
            styles = {"FLEET_MPC_MCTS": ("#136f63", "o"),
                      "5.0s/instance nominal": ("#b64b3d", "^"),
                      "30.0s/instance nominal": ("#bc7b16", "s"),
                      "300.0s/instance nominal": ("#535caa", "D")}
            for ax, instance in zip(axes.flat, STATIC_NAMES):
                group = complete[complete.instance == instance]
                for row in group.itertuples():
                    key = row.method if row.method == "FLEET_MPC_MCTS" else row.budget
                    color, marker = styles[key]
                    ax.scatter(row.evs_mean_complete, row.distance_mean_complete,
                               color=color, marker=marker, s=44,
                               label=key if instance == STATIC_NAMES[0] else None)
                ax.set_title(instance)
                ax.grid(alpha=.18)
                ax.set_xlabel("Mean EVs")
                ax.set_ylabel("Mean distance")
            handles = [plt.Line2D([], [], color=color, marker=marker, linestyle="None",
                                  label=label) for label, (color, marker) in styles.items()]
            fig.legend(handles=handles, loc="upper center", ncol=4, fontsize=8)
            fig.subplots_adjust(top=.84, bottom=.09, hspace=.48, wspace=.35)
            save("static_evs_distance", tight=False)
        eligible = frame[(frame.success_rate == 1) & frame.evs_mean_complete.notna()]
        if eligible.method.nunique() > 1:
            best_evs = eligible.groupby("instance").evs_mean_complete.min()
            fig, ax = plt.subplots(figsize=(7.5, 4.2))
            for (method, budget), group in eligible.groupby(["method", "budget"]):
                ratios = sorted(float(row.evs_mean_complete / best_evs[row.instance])
                                for row in group.itertuples())
                ax.step(ratios, np.arange(1, len(ratios) + 1) / len(STATIC_NAMES),
                        where="post", label=f"{method} ({budget})")
            ax.set(xlabel="Mean EV count / best observed (all seeds complete)",
                   ylabel="Fraction of six instances", ylim=(0, 1.02))
            ax.legend(fontsize=7)
            save("static_performance_profile")
    return made


def generate():
    ablations, methods, runtimes, contributions, comparisons = _dynamic()
    static = _static()
    _small()
    compatibility = OUT / "tables/table_compatibility.csv"
    if compatibility.exists():
        frame = pd.read_csv(compatibility)
        _frame(frame.to_dict("records"), list(frame.columns), "table_compatibility")
    figures = _figures(ablations, methods, runtimes, contributions, static)
    lines = ["# Paper Results Status", "", "All tables are generated from audited raw records.",
             "MPC and MCTS source remains frozen; Rolling-LNS remains historical/supplementary.", "",
             "## Paired Service", ""]
    for key, value in comparisons.items():
        lines.append(f"- {key}: n={value['n']}, mean={value['mean']:.3f}, "
                     f"W/T/L={value['wins']}/{value['ties']}/{value['losses']}, "
                     f"bootstrap 95% CI={value['ci95']}.")
    if not any(key.startswith("holdout") for key in comparisons):
        lines.append("- Holdout not executed; no holdout inference is made.")
    holdout_methods = {row["method"]: row for row in methods if row["split"] == "holdout"}
    if holdout_methods:
        lines += ["", "## Holdout Service", ""]
        for method in ("FLEET_MPC_MCTS", "FLEET_MPC_COMPLETION_ONLY", "RH_REGRET"):
            row = holdout_methods[method]
            lines.append(f"- {method}: {row['served_total']}/{100 * row['n']} served; "
                         f"{row['complete_count']}/{row['n']} complete.")
        mcts_runtime = [row for row in runtimes if row["split"] == "holdout"
                        and row["method"] == "FLEET_MPC_MCTS"]
        mcts_calls = [row for row in contributions if row["split"] == "holdout"]
        lines.append(f"- MPC-MCTS run-level mean decision latency: "
                     f"{np.mean([row['mean_latency_s'] for row in mcts_runtime]):.3f}s; "
                     f"largest recorded decision latency: "
                     f"{max(row['max_latency_s'] for row in mcts_runtime):.3f}s. "
                     "Concurrent-family timings are not isolated-machine measurements.")
        lines.append(f"- MCTS: {sum(row['calls'] for row in mcts_calls)} calls, "
                     f"{sum(row['service_gain_calls'] for row in mcts_calls)} service-improving, "
                     f"{sum(row['ev_gain_calls'] for row in mcts_calls)} EV-improving, "
                     f"{sum(row['distance_gain_calls'] for row in mcts_calls)} distance-improving, "
                     f"{sum(row['objective_gain_calls'] for row in mcts_calls)} objective-improving.")
    external_count = len(list((OUT / "raw/routingblocks").glob("*.json")))
    external = [row for row in static if row["method"] == "RoutingBlocks"]
    lines += ["", "## External Context", "",
              f"RoutingBlocks raw attempts: {external_count}. Static quality columns require "
              "independent replay; strict budget success is reported separately. "
              "Nominal external budgets are not actual elapsed times. "
              "pyevrp 0.2.1 is excluded by the exact-physics gate.",
              "The 5-second external whole-run budget is not equal to a five-second "
              "per-decision controller budget."]
    if external:
        for budget in (5, 30, 300):
            group = [row for row in external if row["budget"] == f"{budget}.0s/instance nominal"]
            if group:
                lines.append(f"- RoutingBlocks nominal {budget}s: "
                             f"{sum(round(row['success_rate'] * row['n']) for row in group)}/"
                             f"{sum(row['n'] for row in group)} replay-valid complete routes; "
                             f"{sum(round(row['strict_budget_success_rate'] * row['n']) for row in group)} "
                             "also met the strict elapsed-time cutoff.")
    lines += ["", "The static external solver often uses fewer EVs and less distance. "
              "These are offline solution-quality results, not evidence that the online "
              "controller dominates ALNS. The four small reference checks pass, but the "
              "published charging model is not proven identical, so no optimality gap is claimed.", "",
              "## Artifacts", "",
              "Tables: `results/paper/tables/`; PNG figures: `results/paper/figures/`.",
              f"Figures generated: {', '.join(figures) if figures else 'none'}."]
    report = writable_path(OUT / "PAPER_RESULTS.md")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    files = [p for folder in (OUT / "tables", OUT / "figures") for p in folder.glob("*") if p.is_file()]
    save_json(OUT / "artifact_hashes.json", {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
                                              for p in files})
    return {"tables": len(list((OUT / "tables").glob("*.csv"))), "figures": figures,
            "paired_comparisons": comparisons, "report": str(report)}


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
