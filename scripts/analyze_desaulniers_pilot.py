"""Summarize only complete, audited Desaulniers MP development-pilot pairs."""

from hashlib import sha256

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.storage import ROOT, load_json
from scripts.run_desaulniers_pilot import OUTPUT


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |",
                      *("| " + " | ".join(map(str, row)) + " |" for row in rows)])


def analyze():
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    records = manifest["records"]
    if manifest["status"] != "pilot_complete" or len(records) != manifest["expected_records"] != 15:
        raise ValueError("Complete three-size, five-method pilot required")
    if len({(r["scenario_id"], r["method"]) for r in records}) != 15:
        raise ValueError("Duplicate or missing paired pilot result")
    by_size = {size: {} for size in (25, 50, 100)}
    for row in records:
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError(f"Pilot raw checksum mismatch: {path}")
        raw = load_json(path)
        meta, metrics = raw["metadata"], raw["metrics"]
        if (meta["dataset_sha256"] != protocol["dataset_sha256"] or
                meta["source_sha256"] != protocol["source_sha256"] or
                meta["charging_policy"] != "MP" or not meta["isolated_worker"] or
                not all(meta["independent_audit"].values()) or
                any(metrics[key] != 0 for key in ("hidden_information_violations",
                      "battery_violations", "capacity_violations", "time_window_violations")) or
                metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                metrics["customers_served"] != row["customers_served"] or
                row["method"] in by_size[row["size"]]):
            raise ValueError(f"Pilot audit or identity mismatch: {path}")
        by_size[row["size"]][row["method"]] = dict(
            row, total_charging_time=metrics["total_charging_time"])
    if any(set(group) != set(protocol["methods"]) or
           len({row["scenario_id"] for row in group.values()}) != 1 or
           len({row["k_ref"] for row in group.values()}) != 1
           for group in by_size.values()):
        raise ValueError("Pilot methods are not paired on identical scenarios and fleets")

    headings = ["Size", "Method", "Served", "Complete", "EVs", "Distance",
                "Charge visits", "Charge time", "Mean decision s", "p95 decision s",
                "Max decision s", "Worker s"]
    rows = []
    for size, group in by_size.items():
        for method in protocol["methods"]:
            row = group[method]
            rows.append((size, method, f"{row['customers_served']}/{size}",
                         "yes" if row["complete_service"] else "no", row["vehicles_activated"],
                         f"{row['total_distance']:.2f}", row["charging_visits"],
                         f"{row['total_charging_time']:.2f}",
                         f"{row['mean_optimization_latency']:.3f}",
                         f"{row['p95_optimization_latency']:.3f}",
                         f"{row['max_optimization_latency']:.3f}",
                         f"{row['worker_wall_seconds']:.1f}"))
    figures = OUTPUT / "figures"
    figures.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = {"MPC_COMPLETION": "#555d63", "MPC_MCTS": "#306b83",
              "MPC_ALNS": "#b44c35", "MPC_HGS": "#758c31", "MPC_ACS": "#9070a5"}
    for method in protocol["methods"]:
        ax.plot([25, 50, 100], [100 * by_size[size][method]["customers_served"] / size
                               for size in (25, 50, 100)], marker="o", label=method.removeprefix("MPC_"),
                color=colors[method])
    ax.set_xticks([25, 50, 100])
    ax.set_ylim(0, 101)
    ax.set_xlabel("Customers in instance")
    ax.set_ylabel("Customers served (%)")
    ax.set_title("Desaulniers MP development pilot (one C1 scenario per size)")
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(figures / "pilot_service_by_size.png", dpi=300)
    plt.close(fig)
    details = ["# Desaulniers MP Development Pilot", "",
               "These are **development engineering checks**, not a final holdout or a "
               "statistical ranking. Each size has one C1 instance, DoD 0.25 and seed 0; "
               "all five methods receive the same dynamic scenario and K_ref. The published "
               "full-charge reference is used offline under the more permissive MP policy, "
               "never as an online route or objective baseline.", "",
               table(headings, rows), "",
               "[PNG: service by size](figures/pilot_service_by_size.png)", "",
               "All 15 workers were isolated and independently replay-audited. Every recorded "
               "battery, capacity, time-window, and hidden-information violation count is zero; "
               "each maximum decision latency is at most five seconds. Distance and EV count "
               "must be compared conditionally on equal service, not ranked unconditionally "
               "when methods serve different customers.", "",
               "Fresh-process isolation does not imply an idle machine. Other user jobs were "
               "active during this pilot, so the worker/latency measurements are not isolated "
               "real-time benchmarks and should not support a quality-versus-compute claim.", "",
               f"Dataset fingerprint: `{protocol['dataset_sha256']}`. "
               f"Source fingerprint: `{protocol['source_sha256']}`.", "",
               "Reproduce with `python -m scripts.run_desaulniers_pilot` followed by "
               "`python -m scripts.analyze_desaulniers_pilot`. The runner reuses only raw "
               "files whose manifest SHA-256 matches and rejects protocol drift.", ""]
    (OUTPUT / "SUMMARY.md").write_text("\n".join(details), encoding="utf-8")
    return rows


if __name__ == "__main__":
    analyze()
