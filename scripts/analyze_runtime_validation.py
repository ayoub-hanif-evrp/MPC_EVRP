"""Matched all-engine validation of explicit runtime safety/coordination switches."""

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
from scripts.run_publication_campaign import configuration, options, verify


CONFIG = "configs/publication_runtime_validation_v1.yaml"


def analyze():
    _, config, output = configuration(CONFIG)
    frozen = load_json(output / "protocol.json")
    manifest = load_json(output / "manifest.json")
    total = len(config["cases"]) * len(config["methods"]) * len(config["variants"])
    if (manifest["status"] != "complete" or manifest["completed_runs"] != total or
            manifest["planned_runs"] != total or manifest["protocol_identifier"] != identifier(frozen)):
        raise ValueError("Runtime validation is incomplete")
    indexed, latencies = {}, defaultdict(list)
    for row in manifest["records"]:
        key = row["case_index"], row["method"], row["variant"]
        if key in indexed:
            raise ValueError("Duplicate runtime validation key")
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Runtime raw hash mismatch")
        raw = load_json(path)
        verify(raw, frozen, frozen["scientific"]["cases"][row["case_index"]], row["method"], row["variant"])
        case = config["cases"][row["case_index"]]
        instance, _, scenario, _ = prepare(case[0], options(config, case, row["method"], row["variant"]))
        result = decode_result(raw)
        checks = audit_result(result, instance, scenario)
        if not all(checks.values()) or checks != row["independent_audit"] or raw["metrics"] != row["metrics"]:
            raise ValueError("Runtime validation independent replay/metric mismatch")
        indexed[key] = row
        latencies[row["method"], row["variant"]].extend(
            d["optimization_latency_seconds"] for d in raw["decisions"]
            if d.get("optimization_latency_seconds") is not None)
    summaries, details = {}, []
    opportunities = sum(int(case[0].rsplit("_", 1)[1]) for case in config["cases"])
    for method in config["methods"]:
        original, guarded, ratios = [], [], []
        for index, case in enumerate(config["cases"]):
            old = indexed[index, method, "original"]
            new = indexed[index, method, "guarded"]
            if old["scenario_id"] != new["scenario_id"] or old["k_ref"] != new["k_ref"]:
                raise ValueError("Runtime validation scenario/fleet mismatch")
            a, b = old["metrics"], new["metrics"]
            original.append(a)
            guarded.append(b)
            ratios.append(b["worker_wall_seconds"] / a["worker_wall_seconds"])
            details.append(dict(method=method, instance=case[0], dod=case[1], seed=case[2],
                           size=int(case[0].rsplit("_", 1)[1]), old=a["customers_served"], new=b["customers_served"],
                           delta=b["customers_served"]-a["customers_served"],
                           old_full=int(a["complete_service"]), new_full=int(b["complete_service"]),
                           old_section_seconds=a["worker_wall_seconds"], new_section_seconds=b["worker_wall_seconds"],
                           old_process_seconds=old.get("process_wall_seconds"),
                           new_process_seconds=new.get("process_wall_seconds")))
        summaries[method] = dict(
            original_service=sum(row["customers_served"] for row in original) / opportunities,
            guarded_service=sum(row["customers_served"] for row in guarded) / opportunities,
            original_complete=mean(int(row["complete_service"]) for row in original),
            guarded_complete=mean(int(row["complete_service"]) for row in guarded),
            service_gain=sum(b["customers_served"]-a["customers_served"] for a, b in zip(original, guarded)),
            median_timed_section_ratio=median(ratios),
            original_coordination_solver_invocations=sum(row["coordination_solver_invocations"] for row in original),
            guarded_coordination_solver_invocations=sum(row["coordination_solver_invocations"] for row in guarded),
            guarded_forced_choices=sum(row["coordination_forced_choices"] for row in guarded),
            original_mean_latency=mean(latencies[method, "original"]),
            guarded_mean_latency=mean(latencies[method, "guarded"]),
            original_p95_latency=float(np.quantile(latencies[method, "original"], .95)),
            guarded_p95_latency=float(np.quantile(latencies[method, "guarded"], .95)),
            original_max_latency=max(latencies[method, "original"]),
            guarded_max_latency=max(latencies[method, "guarded"]),
            initialization_fallbacks=sum(row["optimizer_initialization_fallbacks"] for row in guarded))
    save_json(output / "analysis.json", dict(summary=summaries, pairs=details,
              independent_parent_cases=len({case[0].rsplit("_", 1)[0] for case in config["cases"]})))
    paper = output / "paper"
    lines = ["# Matched runtime implementation validation", "",
             f"All {total}/{total} separate-worker runs passed raw SHA-256 verification, exact scenario/fleet",
             "matching, independent physical replay, duplicate/future-information checks",
             "and the five-second decision limit. These are three development size",
             "variants of one parent case; results are descriptive implementation",
             "checks and carry no independent-instance generalization claim.", "",
             "The guarded variant enables validated-incumbent initialization fallback",
             "and exact forced retained-route coordination. Core search strategies,",
             "canonical objective, physics, fleets, releases and configured budgets match.", "",
             "Machine-load policy: " + config["machine_load_methodology"] + ".",
             "Process isolation does not imply an otherwise idle computer. Runtime",
             "ratios are descriptive shared-machine observations, not hardware benchmarks.", "",
             "| Method | Original service % | Guarded service % | Original complete % | Guarded complete % | Customer change |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for method, row in summaries.items():
        lines.append(f"| {method} | {100*row['original_service']:.2f} | {100*row['guarded_service']:.2f} | "
                     f"{100*row['original_complete']:.2f} | {100*row['guarded_complete']:.2f} | {row['service_gain']:+d} |")
    lines += ["", "| Method | Mean decision s old / guarded | p95 s old / guarded | Max s old / guarded | Timed-section median ratio |",
              "| --- | --- | --- | --- | ---: |"]
    for method, row in summaries.items():
        lines.append(f"| {method} | {row['original_mean_latency']:.4f} / {row['guarded_mean_latency']:.4f} | "
                     f"{row['original_p95_latency']:.4f} / {row['guarded_p95_latency']:.4f} | "
                     f"{row['original_max_latency']:.4f} / {row['guarded_max_latency']:.4f} | "
                     f"{row['median_timed_section_ratio']:.2f}x |")
    lines += ["", "| Method | Coordination solver calls old / guarded | Forced choices | Initialization fallbacks |",
              "| --- | --- | ---: | ---: |"]
    lines.extend(f"| {method} | {row['original_coordination_solver_invocations']} / "
                 f"{row['guarded_coordination_solver_invocations']} | {row['guarded_forced_choices']} | "
                 f"{row['initialization_fallbacks']} |" for method, row in summaries.items())
    lines += ["", "Search may execute a different number of iterations under the same",
              "wall-clock limit when coordination overhead changes. Consequently this",
              "small sample does not establish a general service improvement or",
              "noninferiority claim. Synthetic deadline tests separately exercise the",
              "initialization fallback even when it is not triggered in these runs.", "",
              "`worker_wall_seconds` measures simulation plus independent audit inside",
              "the worker; the separate parent process timer includes startup and",
              "preparation. Neither is an optimization-decision latency.", ""]
    report = "\n".join(lines) + "\n"
    writable_path(output / "RESULTS.md").write_text(report, encoding="utf-8")
    writable_path(paper / "method_results.md").write_text(report, encoding="utf-8")
    rows = ["# Results by size on matched development cases", "",
            "| Method | Size | Original | Guarded | Customer change | Original / guarded complete |",
            "| --- | ---: | ---: | ---: | ---: | --- |"]
    rows.extend(f"| {row['method']} | {row['size']} | {row['old']} | {row['new']} | "
                f"{row['delta']:+d} | {row['old_full']} / {row['new_full']} |" for row in details)
    writable_path(paper / "size_results.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    fig, axes = plt.subplots(2, 3, figsize=(11, 6), sharex=True, sharey=True)
    for ax, method in zip(axes.flat, config["methods"]):
        for variant in config["variants"]:
            values = np.sort(latencies[method, variant])
            ax.step(values, np.arange(1, len(values)+1)/len(values), where="post", label=variant)
        ax.axvline(5, color="#b44345", linestyle="--", linewidth=.8)
        ax.set_xscale("log")
        ax.set(xlim=(1e-4, 6), ylim=(0, 1.01), title=method.replace("MPC_", ""))
        ax.legend(fontsize=8)
    axes.flat[-1].axis("off")
    fig.supxlabel("Optimization-decision latency (s, logarithmic axis)")
    fig.supylabel("Empirical cumulative probability")
    fig.tight_layout()
    fig.savefig(writable_path(paper / "runtime_ecdf.png"), dpi=300)
    plt.close(fig)
    return summaries


if __name__ == "__main__":
    print(analyze())
