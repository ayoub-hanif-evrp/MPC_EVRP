"""Independently audited paired analysis with base-instance uncertainty."""

import argparse
from collections import defaultdict
from hashlib import sha256
from statistics import mean, median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evrp.audit import decode_result
from evrp.experiments import audit_result, prepare
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.analyze_alns_recovery_screen import _interval
from scripts.run_desaulniers_pilot import family_of
from scripts.run_publication_campaign import configuration, options, verify


def analyze(path):
    _, config, output = configuration(path)
    if len(config["methods"]) != 2 or len(config["variants"]) != 1:
        raise ValueError("Paired analyzer requires two methods and one shared variant")
    frozen = load_json(output / "protocol.json")
    manifest = load_json(output / "manifest.json")
    expected = len(config["cases"]) * 2
    if (manifest["status"] != "complete" or manifest["completed_runs"] != expected or
            manifest["planned_runs"] != expected or manifest["protocol_identifier"] != identifier(frozen)
            or frozen["scientific"]["design"] != config):
        raise ValueError("Incomplete or mismatched paired campaign")
    indexed, latencies = {}, defaultdict(list)
    for row in manifest["records"]:
        key = row["case_index"], row["method"]
        if key in indexed:
            raise ValueError("Duplicate paired campaign key")
        raw_path = ROOT / row["raw"]
        if sha256(raw_path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Paired raw SHA-256 mismatch")
        raw = load_json(raw_path)
        verify(raw, frozen, frozen["scientific"]["cases"][row["case_index"]],
               row["method"], row["variant"])
        case = config["cases"][row["case_index"]]
        instance, _, scenario, _ = prepare(case[0], options(config, case, row["method"], row["variant"]))
        result = decode_result(raw)
        independent = audit_result(result, instance, scenario)
        if not all(independent.values()) or independent != row["independent_audit"]:
            raise ValueError("Paired raw failed independent physical replay")
        if raw["metrics"] != row["metrics"]:
            raise ValueError("Manifest metrics differ from raw evidence")
        indexed[key] = raw
        latencies[row["method"]].extend(d["optimization_latency_seconds"] for d in raw["decisions"]
                                        if d.get("optimization_latency_seconds") is not None)
    old_name, new_name = config["methods"]
    pairs, clusters = [], defaultdict(lambda: [0, 0, 0, 0])
    parent_clusters = defaultdict(lambda: [0, 0, 0, 0])
    for index, case in enumerate(config["cases"]):
        old_raw, new_raw = indexed[index, old_name], indexed[index, new_name]
        old, new = old_raw["metrics"], new_raw["metrics"]
        size = frozen["scientific"]["cases"][index]["customers"]
        row = dict(instance=case[0], dod=case[1], seed=case[2], size=size,
                   family=family_of(case[0]), old=old["customers_served"], new=new["customers_served"],
                   old_full=int(old["complete_service"]), new_full=int(new["complete_service"]),
                   old_seconds=old["worker_wall_seconds"], new_seconds=new["worker_wall_seconds"],
                   old_distance=old["total_distance"], new_distance=new["total_distance"],
                   old_evs=old["vehicles_activated"], new_evs=new["vehicles_activated"],
                   old_charge_time=old["total_charging_time"], new_charge_time=new["total_charging_time"],
                   guard_rejections=sum(d.get("optimizer", {}).get("diagnostics", {}).get(
                       "coverage_guard_rejections", 0) for d in new_raw["decisions"] if d.get("optimizer")))
        row["delta"] = row["new"] - row["old"]
        pairs.append(row)
        cluster = clusters[case[0]]
        for k, value in enumerate((row["delta"], size, row["new_full"] - row["old_full"], 1)):
            cluster[k] += value
            parent_clusters[case[0].rsplit("_", 1)[0]][k] += value
    grouped = list(clusters.values())
    service_ci = _interval(grouped, [c[0] for c in grouped], [c[1] for c in grouped])
    full_ci = _interval(grouped, [c[2] for c in grouped], [c[3] for c in grouped], seed=20261024)
    parents = list(parent_clusters.values())
    parent_service_ci = _interval(parents, [c[0] for c in parents], [c[1] for c in parents])
    parent_full_ci = _interval(parents, [c[2] for c in parents], [c[3] for c in parents], seed=20261024)
    total = sum(p["size"] for p in pairs)
    summary = dict(study=config["study"], role=config["role"], scenarios=len(pairs),
                   base_instances=len(clusters), customer_opportunities=total,
                   original=old_name, enhanced=new_name,
                   original_service=sum(p["old"] for p in pairs) / total,
                   enhanced_service=sum(p["new"] for p in pairs) / total,
                   service_delta=sum(p["delta"] for p in pairs) / total,
                   service_ci=service_ci, complete_ci=full_ci,
                   parent_instances=len(parents), parent_service_ci=parent_service_ci,
                   parent_complete_ci=parent_full_ci,
                   original_complete=mean(p["old_full"] for p in pairs),
                   enhanced_complete=mean(p["new_full"] for p in pairs),
                   wins=sum(p["delta"] > 0 for p in pairs), ties=sum(p["delta"] == 0 for p in pairs),
                   losses=sum(p["delta"] < 0 for p in pairs),
                   worker_time_median_ratio=median(p["new_seconds"] / p["old_seconds"] for p in pairs),
                   guard_rejections=sum(p["guard_rejections"] for p in pairs),
                   latency={method: dict(decisions=len(times), mean=mean(times),
                            p95=float(np.quantile(times, .95)), maximum=max(times))
                            for method, times in latencies.items()})
    if "selection_rule" in config:
        rule = config["selection_rule"]
        hundred_gain = sum(p["delta"] for p in pairs if p["size"] == 100)
        checks = dict(service_interval=service_ci[0] > rule["service_clustered_95_ci_lower_above"],
                      complete_service=(summary["enhanced_complete"] - summary["original_complete"] >=
                                        rule["complete_service_change_at_least"]),
                      hundred_customer_service=hundred_gain >= rule["total_100_customer_service_change_at_least"],
                      physical_and_information_audits=True,
                      decision_budget=all(v["maximum"] <= rule["maximum_decision_seconds"] + 1e-6
                                          for v in summary["latency"].values()))
        summary["selection_checks"] = checks
        summary["promotion_eligible"] = all(checks.values())
    save_json(output / "analysis.json", dict(summary=summary, pairs=pairs))
    paper = output / "paper"
    table = ["# Matched service results", "",
             "| Method | Customers served % | Complete scenarios % |", "| --- | ---: | ---: |",
             f"| {old_name} | {100*summary['original_service']:.2f} | {100*summary['original_complete']:.2f} |",
             f"| {new_name} | {100*summary['enhanced_service']:.2f} | {100*summary['enhanced_complete']:.2f} |"]
    writable_path(paper / "service.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    by_group = ["# Service by size, family and dynamicity", "",
                "| Group | Value | Scenarios | Old service % | New service % | Old / new complete |",
                "| --- | --- | ---: | ---: | ---: | --- |"]
    for field in ("size", "family", "dod"):
        for value in sorted({p[field] for p in pairs}):
            subset = [p for p in pairs if p[field] == value]
            denominator = sum(p["size"] for p in subset)
            by_group.append(f"| {field} | {value} | {len(subset)} | "
                            f"{100*sum(p['old'] for p in subset)/denominator:.2f} | "
                            f"{100*sum(p['new'] for p in subset)/denominator:.2f} | "
                            f"{sum(p['old_full'] for p in subset)} / {sum(p['new_full'] for p in subset)} |")
    writable_path(paper / "strata.md").write_text("\n".join(by_group) + "\n", encoding="utf-8")
    detailed = ["# Paired scenarios", "",
                "| Instance | DoD | Seed | Old | New | Change | Worker seconds old / new | Guard rejections |",
                "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |"]
    detailed.extend(f"| {p['instance']} | {p['dod']} | {p['seed']} | {p['old']} | {p['new']} | "
                    f"{p['delta']:+d} | {p['old_seconds']:.1f} / {p['new_seconds']:.1f} | "
                    f"{p['guard_rejections']} |" for p in pairs)
    writable_path(paper / "paired_scenarios.md").write_text("\n".join(detailed) + "\n", encoding="utf-8")
    common = [p for p in pairs if p["old_full"] and p["new_full"]]
    efficiency = ["# Conditional operational efficiency", "",
                  f"Common complete-service scenarios: {len(common)}/{len(pairs)}.", "",
                  "Distance, EV and charging comparisons below include only scenarios",
                  "where both methods served every customer.", ""]
    if common:
        efficiency += ["| Measure | Original mean | Enhanced mean |", "| --- | ---: | ---: |"]
        for label, old_key, new_key in (("Distance", "old_distance", "new_distance"),
                                        ("EVs", "old_evs", "new_evs"),
                                        ("Charging time", "old_charge_time", "new_charge_time")):
            efficiency.append(f"| {label} | {mean(p[old_key] for p in common):.2f} | "
                              f"{mean(p[new_key] for p in common):.2f} |")
    writable_path(paper / "conditional_efficiency.md").write_text("\n".join(efficiency) + "\n", encoding="utf-8")
    runtime = ["# Decision runtime", "",
               "| Method | Decisions | Mean s | p95 s | Max s |", "| --- | ---: | ---: | ---: | ---: |"]
    runtime.extend(f"| {method} | {values['decisions']} | {values['mean']:.4f} | "
                   f"{values['p95']:.4f} | {values['maximum']:.4f} |"
                   for method, values in summary["latency"].items())
    writable_path(paper / "runtime.md").write_text("\n".join(runtime) + "\n", encoding="utf-8")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for method, times in latencies.items():
        sorted_times = np.sort(times)
        ax.step(sorted_times, np.arange(1, len(times) + 1) / len(times), where="post", label=method)
    ax.axvline(5, color="#b44345", linestyle="--", label="Five-second limit")
    ax.set(xlabel="End-to-end optimization decision latency (s)", ylabel="Empirical cumulative probability",
           ylim=(0, 1.01))
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(writable_path(paper / "runtime_ecdf.png"), dpi=300)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(range(len(pairs)), [p["delta"] for p in pairs],
           color=["#267a66" if p["delta"] > 0 else "#b44345" for p in pairs])
    ax.axhline(0, color="#30363d", linewidth=.8)
    ax.set(xlabel="Paired development scenario index", ylabel="Enhanced minus original customers served")
    fig.tight_layout()
    fig.savefig(writable_path(paper / "paired_service.png"), dpi=300)
    plt.close(fig)
    lines = [f"# {config['study']}", "", f"Design role: **{config['role']}**.",
             f"Completed and independently audited: {expected}/{expected} runs on {len(pairs)} matched",
             f"scenarios from {len(clusters)} base instances. All decisions meet five seconds.", "",
             f"Customer-weighted service: {100*summary['original_service']:.2f}% original versus "
             f"{100*summary['enhanced_service']:.2f}% enhanced. Paired change "
             f"{100*summary['service_delta']:+.2f} percentage points, base-instance bootstrap 95% CI "
             f"[{100*service_ci[0]:+.2f}, {100*service_ci[1]:+.2f}].", "",
             f"Complete service: {100*summary['original_complete']:.2f}% versus "
             f"{100*summary['enhanced_complete']:.2f}%; paired 95% CI "
             f"[{100*full_ci[0]:+.2f}, {100*full_ci[1]:+.2f}] percentage points.", "",
             f"Scenario service wins/ties/losses: {summary['wins']}/{summary['ties']}/{summary['losses']}. "
             f"Median whole-worker time ratio: {summary['worker_time_median_ratio']:.2f}x. "
             f"Equal-service best-update guard rejections: {summary['guard_rejections']}.", "",
             "Intervals resample complete base-instance clusters, retaining all associated seeds",
             "and dynamicity levels. Development intervals are exploratory and do not justify",
             "claims on unseen instances. Raw traces, negative cases and manifests are retained.", "",
             f"Underlying-parent sensitivity: {len(parents)} parent cases, service 95% CI "
             f"[{100*parent_service_ci[0]:+.2f}, {100*parent_service_ci[1]:+.2f}] and complete-service CI "
             f"[{100*parent_full_ci[0]:+.2f}, {100*parent_full_ci[1]:+.2f}] percentage points. "
             "This groups size variants of the same parent case together. The original "
             "file-clustered selection rule remains the predeclared rule.", "",
             "Paper tables are Markdown; figures are PNG at 300 dpi under `paper/`.", ""]
    if "selection_rule" in config:
        lines += [f"Predeclared promotion rule satisfied: **{summary['promotion_eligible']}**.", "",
                  "| Selection check | Passed |", "| --- | --- |"]
        lines.extend(f"| {name} | {passed} |" for name, passed in summary["selection_checks"].items())
        lines += [""]
    writable_path(output / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    analyze(parser.parse_args().config)
