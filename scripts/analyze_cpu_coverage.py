"""Independent replay of the complete six-family original/cache comparison."""

from collections import defaultdict
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evrp.audit import decode_result
from evrp.experiments import audit_result
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.complete_cpu_coverage import DEVELOPMENT, OUTPUT, PAPER, digest, verify_record
from scripts.run_final_cpu_development import verify_raw
from scripts.run_final_cpu_replication import archived_case


def bootstrap_ratio(pairs, numerator, denominator, seed=20261028):
    """Ratio of sums, resampling the independent parents as paired blocks."""
    groups = defaultdict(list)
    for row in pairs:
        groups[row["parent"]].append(row)
    totals = np.asarray([(sum(row[numerator] for row in group), sum(row[denominator] for row in group))
                         for group in groups.values()], dtype=float)
    if not len(totals) or (totals[:, 1] <= 0).any():
        raise ValueError("A ratio needs nonempty paired parents and positive denominators")
    draws = np.random.default_rng(seed).integers(0, len(totals), (10000, len(totals)))
    selected = totals[draws].sum(axis=1)
    low, high = np.percentile(selected[:, 0] / selected[:, 1], (2.5, 97.5))
    return dict(value=float(totals[:, 0].sum() / totals[:, 1].sum()),
                low=float(low), high=float(high), parents=len(totals))


def analyze():
    from scripts.render_final_cpu_paper import METHODS, LABELS, write_table, save_figure

    frozen = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    parent = load_json(DEVELOPMENT / "protocol.json")
    old_manifest = load_json(DEVELOPMENT / "manifest.json")
    if (manifest["status"] != "complete" or manifest["completed_runs"] != 15 or
            manifest["protocol_identifier"] != identifier(frozen) or
            digest(DEVELOPMENT / "manifest.json") != frozen["parent_manifest_sha256"] or
            identifier(parent) != frozen["parent_protocol"] or
            len({row["id"] for row in manifest["records"]}) != 15):
        raise ValueError("Incomplete or inconsistent CPU coverage")
    inputs = {index: archived_case(info) for index, info in enumerate(parent["selected"])}
    data = {}
    audits = []
    original_specs = {job["id"]: job for block in parent["blocks"] for job in block["jobs"]}
    for row in old_manifest["records"]:
        if row["variant"] not in ("original", "cpu"):
            continue
        path = ROOT / row["raw"]
        raw = load_json(path)
        if digest(path) != row["sha256"]:
            raise ValueError("Inherited original/cache raw hash changed")
        verify_raw(parent, original_specs[row["id"]], raw)
        instance, _, scenario = inputs[row["index"]]
        if not all(audit_result(decode_result(raw["result"]), instance, scenario).values()):
            raise ValueError("Inherited original/cache physical audit failed")
        data[row["index"], row["method"], row["variant"]] = raw
        audits.append(dict(raw=row["raw"], sha256=row["sha256"], physical_replay=True))
    specs = {job["id"]: job for job in frozen["jobs"]}
    for row in manifest["records"]:
        path = ROOT / row["raw"]
        raw = load_json(path)
        if digest(path) != row["sha256"] or path != OUTPUT / "raw" / f"{row['id']}.json.gz":
            raise ValueError("CPU coverage raw path/hash mismatch")
        verify_record(frozen, specs[row["id"]], raw)
        job = specs[row["id"]]
        if digest(ROOT / job["baseline"]) != job["baseline_sha256"]:
            raise ValueError("Frozen matching baseline changed")
        data[row["index"], row["method"], "cpu"] = raw
        audits.append(dict(raw=row["raw"], sha256=row["sha256"], physical_replay=True))
    if len(data) != 60:
        raise ValueError("Six-family CPU comparison requires 60 original/cache records")
    pairs = []
    for index, info in enumerate(parent["selected"]):
        for method in METHODS:
            left, right = data[index, method, "original"], data[index, method, "cpu"]
            lm, rm = left["result"]["metrics"], right["result"]["metrics"]
            matched = set(left["result"]["unserved_customers"]) == set(right["result"]["unserved_customers"])
            pairs.append(dict(parent=info["instance"].split("_", 1)[0], family=info["family"],
                              size=info["size"], method=method, original=lm["customers_served"],
                              cached=rm["customers_served"], delta=rm["customers_served"]-lm["customers_served"],
                              complete_original=int(lm["complete_service"]), complete_cached=int(rm["complete_service"]),
                              original_cpu=left["worker_cpu_seconds"], cached_cpu=right["worker_cpu_seconds"],
                              original_wall=left["worker_wall_seconds"], cached_wall=right["worker_wall_seconds"],
                              same_set=matched,
                              distance_delta=rm["total_distance"]-lm["total_distance"] if matched else None))
    summary = []
    for method in METHODS:
        rows = [row for row in pairs if row["method"] == method]
        cpu = bootstrap_ratio(rows, "cached_cpu", "original_cpu")
        total = sum(row["size"] for row in rows)
        matched = [row["distance_delta"] for row in rows if row["same_set"]]
        summary.append(dict(method=method, pairs=len(rows), total=total,
                            original_served=sum(row["original"] for row in rows),
                            cached_served=sum(row["cached"] for row in rows),
                            original_complete=sum(row["complete_original"] for row in rows),
                            cached_complete=sum(row["complete_cached"] for row in rows),
                            gains=sum(row["delta"] > 0 for row in rows), losses=sum(row["delta"] < 0 for row in rows),
                            cpu_ratio=cpu, same_set_pairs=len(matched),
                            matched_distance_mean=mean(matched) if matched else None))
    note = ("Exploratory development: six parents, one per family, two per size, DoD 0.5 seed 3; "
            "30 original/cache pairs. Original raw and 15 earlier CPU runs are reused; 15 missing-family "
            "CPU runs were preregistered separately. Sequential shared-machine timings were obtained "
            "at different dates; ratios are observations, not controlled hardware speedups. "
            "CPU intervals resample six parent blocks (10,000 draws, seed 20261028). "
            "Distance differences use identical served-customer sets only. Historical cache regressions "
            "remain evidence against a universal service-preservation claim.")
    write_table("cpu_six_family_pairs",
                ["Parent", "Family", "Customers", "Method", "Original served", "Cache served", "Served delta",
                 "Original complete", "Cache complete", "Original CPU s", "Cache CPU s", "Original wall s",
                 "Cache wall s", "Identical served set", "Conditional distance delta"],
                [[row["parent"], row["family"], row["size"], LABELS[row["method"]], row["original"], row["cached"],
                  row["delta"], row["complete_original"], row["complete_cached"],
                  *[f"{row[key]:.3f}" for key in ("original_cpu", "cached_cpu", "original_wall", "cached_wall")],
                  row["same_set"], f"{row['distance_delta']:.3f}" if row["same_set"] else "NA"] for row in pairs], note)
    write_table("cpu_six_family_summary",
                ["Method", "Pairs", "Original served/total", "Cache served/total", "Original complete",
                 "Cache complete", "Gains", "Losses", "Cache/original CPU ratio", "95% parent interval",
                 "Identical-set n", "Mean conditional distance delta"],
                [[LABELS[row["method"]], row["pairs"], f"{row['original_served']}/{row['total']}",
                  f"{row['cached_served']}/{row['total']}", row["original_complete"], row["cached_complete"],
                  row["gains"], row["losses"], f"{row['cpu_ratio']['value']:.3f}",
                  f"[{row['cpu_ratio']['low']:.3f}, {row['cpu_ratio']['high']:.3f}]", row["same_set_pairs"],
                  f"{row['matched_distance_mean']:.3f}" if row["same_set_pairs"] else "NA"] for row in summary], note)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    labels = [LABELS[row["method"]] for row in summary]
    axes[0].bar(labels, [row["cached_served"]-row["original_served"] for row in summary], color="#216e83")
    axes[0].scatter(range(5), [row["cached_served"]-row["original_served"] for row in summary], color="#216e83", zorder=3)
    if all(row["cached_served"] == row["original_served"] for row in summary):
        axes[0].set(ylim=(-1, 1), yticks=(-1, 0, 1))
    axes[0].axhline(0, color="#333333", linewidth=.8)
    axes[0].set(ylabel="Served-customer change (6 paired parents)", title="Cache minus original service")
    values = np.asarray([row["cpu_ratio"]["value"] for row in summary])
    lows = np.asarray([row["cpu_ratio"]["low"] for row in summary])
    highs = np.asarray([row["cpu_ratio"]["high"] for row in summary])
    axes[1].errorbar(range(5), values, yerr=[values-lows, highs-values], fmt="o", color="#218462", capsize=4)
    axes[1].set_xticks(range(5), labels)
    axes[1].axhline(1, color="#333333", linewidth=.8, linestyle="--")
    axes[1].set(ylabel="Cache / original worker CPU", title="Exploratory parent-cluster intervals")
    for ax in axes:
        ax.tick_params(axis="x", labelrotation=20)
    save_figure("15_cpu_six_family_coverage", fig)
    budget = load_json(OUTPUT / "budget.json")
    report = dict(status="complete", raw_records=60, new_runs=15, pairs=30, parents=6,
                  prior_accounting=frozen["prior_accounting"], charged_seconds=budget["charged_seconds"],
                  attempted_cpu_seconds=sum(job["cpu_seconds"] for job in budget["jobs"]),
                  summary=summary, audit=audits, protocol_sha256=digest(OUTPUT / "protocol.json"),
                  manifest_sha256=digest(OUTPUT / "manifest.json"), promotion="not_promoted")
    save_json(OUTPUT / "analysis.json", report)
    total_delta = sum(row["delta"] for row in pairs)
    losses = sum(row["delta"] < 0 for row in pairs)
    text = ("# Six-family CPU-cache development coverage\n\n" + note + "\n\n"
            f"Independent replay passed for all 60 records (45 reused and 15 new). "
            f"Aggregate service change: {total_delta:+d}; paired service losses: {losses}/30. "
            "No independently confirmed enhancement is claimed. Fixed-work equality does not guarantee "
            "the same explored candidates or executed actions under a wall-clock limit.\n\n"
            "The original methods remain the selected publication configuration. This supplement "
            "closes the CPU component's family coverage gap and retains unfavorable results.\n\n"
            "[Paired cases](tables/cpu_six_family_pairs.md), "
            "[method summaries](tables/cpu_six_family_summary.md), "
            "[service and CPU figure](figures/15_cpu_six_family_coverage.png).\n")
    writable_path(PAPER / "CPU_COVERAGE.md").write_text(text, encoding="utf-8")
    return report


if __name__ == "__main__":
    report = analyze()
    print(f"Audited CPU comparison: {report['raw_records']} records, {report['pairs']} pairs")
