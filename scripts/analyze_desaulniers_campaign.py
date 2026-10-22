"""Audit complete development evidence and summarize matched MP outcomes."""

from collections import defaultdict
from hashlib import sha256
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.experiments import load_config
from evrp.storage import ROOT, identifier, load_json, writable_path
from scripts.run_desaulniers_campaign import CONFIG, OUTPUT, METHODS, protocol
from scripts.run_desaulniers_pilot import VIOLATIONS


def _table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def analyze(frozen=None, output=OUTPUT, complete_status="development_complete"):
    frozen = frozen if frozen is not None else protocol(load_config(CONFIG))
    manifest = load_json(output / "manifest.json")
    if manifest["status"] != complete_status:
        raise ValueError("Campaign is incomplete; no paper summary will be rendered")
    records = manifest["records"]
    excluded = manifest["ineligible"]
    scenarios = {(r["instance"], dod, seed) for r in frozen["selected"]
                 for dod in frozen["dynamicities"] for seed in frozen["scenario_seeds"]}
    excluded_keys = {(r["instance"], r["dynamicity"], r["seed"]) for r in excluded}
    if (manifest["protocol_identifier"] != identifier(frozen) or
            manifest["planned_runs"] != len(scenarios) * len(METHODS) or
            not excluded_keys <= scenarios or len(excluded_keys) != len(excluded) or
            any((r["instance"], r["dynamicity"], r["seed"]) not in scenarios - excluded_keys
                for r in records) or
            len(records) + len(excluded) * len(METHODS) != manifest["planned_runs"] or
            len(records) != len({(r["instance"], r["dynamicity"], r["seed"], r["method"])
                                 for r in records})):
        raise ValueError("Development manifest has missing or duplicated method keys")
    if not records:
        raise ValueError("No eligible audited scenarios")
    grouped = defaultdict(dict)
    complete_rows = []
    for row in records:
        path = ROOT / row["raw"]
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError(f"Missing or corrupted raw record: {path}")
        raw = load_json(path)
        metrics, meta = raw["metrics"], raw["metadata"]
        if (meta["source_sha256"] != frozen["source_sha256"] or
                meta["dataset_sha256"] != frozen["dataset_sha256"] or
                meta["charging_policy"] != "MP" or not meta["isolated_worker"] or
                not all(meta["independent_audit"].values()) or
                any(metrics[key] for key in VIOLATIONS) or
                metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                meta["scenario_identifier"] != row["scenario_id"] or
                meta["K_ref"] != row["k_ref"] or
                metrics["customers_served"] != row["customers_served"]):
            raise ValueError(f"Unaudited or inconsistent raw record: {path}")
        enriched = dict(row, customers=meta["number_of_customers"],
                        charging_visits=metrics["total_charging_visits"],
                        mean_latency=metrics["mean_optimization_latency"],
                        p95_latency=metrics["p95_optimization_latency"])
        key = row["instance"], row["dynamicity"], row["seed"]
        if row["method"] in grouped[key]:
            raise ValueError("Duplicate method in paired scenario")
        grouped[key][row["method"]] = enriched
        complete_rows.append(enriched)
    for key, methods in grouped.items():
        if set(methods) != METHODS:
            raise ValueError(f"Unpaired methods for {key}")
        if len({(row["scenario_id"], row["k_ref"], row["reference_identifier"],
                 row["instance_sha256"]) for row in methods.values()}) != 1:
            raise ValueError(f"Scenario or fleet mismatch for {key}")

    comparable = {key for key, methods in grouped.items()
                  if all(row["complete_service"] for row in methods.values())}

    def summarize(rows):
        n = len(rows)
        equal = [row for row in rows if (row["instance"], row["dynamicity"], row["seed"])
                 in comparable]
        return (n, f"{100 * sum(r['customers_served'] for r in rows) / sum(r['customers'] for r in rows):.2f}",
                f"{100 * sum(r['complete_service'] for r in rows) / n:.1f}",
                f"{mean(r['vehicles_activated'] for r in rows):.2f}",
                f"{mean(r['charging_visits'] for r in rows):.2f}",
                f"{mean(r['mean_latency'] for r in rows):.3f}",
                f"{max(r['max_optimization_latency'] for r in rows):.3f}",
                len(equal),
                f"{mean(r['vehicles_activated'] for r in equal):.2f}" if equal else "NA",
                f"{mean(r['total_distance'] for r in equal):.2f}" if equal else "NA")

    headers = ["Group", "Method", "N", "Served %", "Complete %", "EV mean",
               "Charge visits mean", "Mean decision s", "Max decision s",
               "Comparable N", "EV conditional", "Distance conditional"]

    def grouped_table(label, key_func):
        buckets = defaultdict(list)
        for row in complete_rows:
            buckets[(key_func(row), row["method"])].append(row)
        return _table(headers, [(label(group), method, *summarize(buckets[group, method]))
                                for group in sorted({key for key, _ in buckets})
                                for method in frozen["methods"]])

    pair_rows = []
    for method in frozen["methods"]:
        if method == "MPC_COMPLETION":
            continue
        diffs = [methods[method]["customers_served"] -
                 methods["MPC_COMPLETION"]["customers_served"]
                 for methods in grouped.values()]
        pair_rows.append((method, len(diffs), f"{mean(diffs):.2f}",
                          sum(x > 0 for x in diffs), sum(x == 0 for x in diffs),
                          sum(x < 0 for x in diffs)))

    final = complete_status == "final_complete"
    lines = [f"# Desaulniers MP {'final holdout' if final else 'development campaign'}", "",
             "Final holdout evidence. All included scenarios have five matched," if final else
             "Development evidence only. All included scenarios have five matched,",
             "isolated, independently audited methods and the same five-second",
             "decision budget. Ineligible target-DoD scenarios are excluded",
             "before optimizer comparison and counted separately.", "",
             *( ["The original final protocol stopped after 10 records on a replay-audit",
                  "floating-point timing defect. Its evidence is preserved separately;",
                  "all records here were rerun under an auditor-only erratum with",
                  "unchanged optimizers, objective, controller, scenarios, and budget.", ""]
                if final and frozen.get("audit_erratum") else [] ),
             f"Planned method runs: {manifest['planned_runs']}; audited runs: {len(records)}; "
             f"ineligible scenarios: {len(excluded)}.", "",
             "Conditional EV and distance use only scenarios where every method",
             "served all customers. Unconditional values must not be ranked when",
             "service differs. Shared-machine load can affect runtime.", "",
             "## Overall", "", grouped_table(lambda _: "All", lambda _: "All"), "",
             "## By size", "", grouped_table(str, lambda row: row["size"]), "",
             "## By family", "", grouped_table(str, lambda row: row["family"]), "",
             "## By target DoD", "", grouped_table(str, lambda row: row["dynamicity"]), "",
             "## Paired service change vs Completion", "",
             _table(["Method", "N", "Mean customers", "Wins", "Ties", "Losses"], pair_rows), "",
             "Reserved benchmark instances were fixed in the original protocol before final outcomes." if final else
             "No final holdout has been opened; these development outcomes are not",
             "" if final else "an unbiased final comparison.", ""]
    writable_path(output / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")

    fig, ax = plt.subplots(figsize=(9, 5))
    for method in frozen["methods"]:
        points = []
        for size in sorted(set(row["size"] for row in complete_rows)):
            rows = [row for row in complete_rows if row["size"] == size and row["method"] == method]
            points.append((size, 100 * sum(row["customers_served"] for row in rows) /
                           sum(row["customers"] for row in rows)))
        ax.plot([x for x, _ in points], [y for _, y in points], marker="o",
                label=method.removeprefix("MPC_"))
    ax.set(xlabel="Customers in instance", ylabel="Customers served (%)",
           title=f"Desaulniers MP {'final holdout' if final else 'development'} (matched scenarios)")
    ax.set_xticks(sorted(set(row["size"] for row in complete_rows)))
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(writable_path(output / "figures/service_by_size.png"), dpi=300)
    plt.close(fig)
    return grouped


if __name__ == "__main__":
    analyze()
