"""Independently audit and summarize the balanced development ALNS screen."""

from collections import defaultdict
from hashlib import sha256
from statistics import mean, median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evrp.storage import ROOT, load_json, writable_path
from scripts.run_alns_recovery_screen import OUTPUT, VARIANTS, cases
from scripts.run_desaulniers_pilot import family_of


def _interval(pairs, values, denominator, seed=20261023):
    rng = np.random.default_rng(seed)
    samples = []
    n = len(pairs)
    for _ in range(20000):
        indices = rng.integers(0, n, n)
        samples.append(sum(values[i] for i in indices) /
                       sum(denominator[i] for i in indices))
    return tuple(float(x) for x in np.quantile(samples, [0.025, 0.975]))


def analyze():
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    if (manifest["status"] != "complete" or manifest["completed_runs"] !=
            manifest["planned_runs"] != len(cases()) * len(VARIANTS)):
        raise ValueError("Balanced ALNS screen incomplete")
    pairs = defaultdict(dict)
    for row in manifest["records"]:
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError(f"Balanced screen raw SHA-256 mismatch: {path}")
        raw = load_json(path)
        if (not all(row["independent_audit"].values()) or
                raw["metadata"]["source_sha256"] != protocol["source_sha256"] or
                raw["metadata"]["protocol_identifier"] != manifest["protocol_identifier"] or
                raw["metrics"]["max_optimization_latency"] > 5.0 + 1e-6):
            raise ValueError(f"Balanced screen audit, provenance, or budget failure: {path}")
        key = row["instance"], row["dynamicity"], row["seed"]
        if row["variant"] in pairs[key]:
            raise ValueError(f"Duplicate balanced screen run: {key}")
        pairs[key][row["variant"]] = row
    records = []
    for key in sorted(pairs):
        variants = pairs[key]
        if set(variants) != set(VARIANTS):
            raise ValueError(f"Unpaired balanced screen scenario: {key}")
        original, enhanced = (variants[variant] for variant in VARIANTS)
        if original["scenario_id"] != enhanced["scenario_id"] or original["k_ref"] != enhanced["k_ref"]:
            raise ValueError(f"Scenario or fleet changed within pair: {key}")
        records.append(dict(instance=key[0], family=family_of(key[0]), size=original["size"],
                            old=original["customers_served"], new=enhanced["customers_served"],
                            delta=enhanced["customers_served"]-original["customers_served"],
                            full_delta=int(enhanced["complete_service"])-int(original["complete_service"]),
                            old_full=original["complete_service"], new_full=enhanced["complete_service"],
                            old_time=original["worker_wall_seconds"],
                            new_time=enhanced["worker_wall_seconds"],
                            old_latency=original["max_optimization_latency"],
                            new_latency=enhanced["max_optimization_latency"]))
    sizes = [row["size"] for row in records]
    deltas = [row["delta"] for row in records]
    full_deltas = [row["full_delta"] for row in records]
    service_ci = _interval(records, deltas, sizes)
    complete_ci = _interval(records, full_deltas, [1] * len(records), seed=20261024)
    old_served = sum(row["old"] for row in records)
    new_served = sum(row["new"] for row in records)
    total = sum(sizes)
    ratios = [row["new_time"] / row["old_time"] for row in records]
    lines = ["# ALNS recovery v2: balanced development screen", "",
             "This 18-instance screen is **development data**, not an independent final holdout. "
             "It crosses six Desaulniers families and sizes 25/50/100 at DoD 0.75, seed 0. "
             "Original and recovery ALNS use identical scenario hashes, fixed K_ref, "
             "original decoder/dispatch, common objective, and five-second decisions. "
             "All 36 isolated raw runs passed independent replay and SHA-256 checks.", "",
             f"Customer-weighted service: {old_served}/{total} ({100*old_served/total:.2f}%) "
             f"original versus {new_served}/{total} ({100*new_served/total:.2f}%) recovery; "
             f"paired change {100*(new_served-old_served)/total:+.2f} percentage points, "
             f"instance-bootstrap 95% interval "
             f"[{100*service_ci[0]:+.2f}, {100*service_ci[1]:+.2f}].", "",
             f"Complete scenarios: {sum(r['old_full'] for r in records)}/18 original versus "
             f"{sum(r['new_full'] for r in records)}/18 recovery; paired change "
             f"{100*mean(full_deltas):+.1f} percentage points, "
             f"instance-bootstrap 95% interval "
             f"[{100*complete_ci[0]:+.1f}, {100*complete_ci[1]:+.1f}].", "",
             f"Worker-time median ratio: {median(ratios):.2f}x; total "
             f"{sum(r['old_time'] for r in records):.1f}s original versus "
             f"{sum(r['new_time'] for r in records):.1f}s recovery. "
             "These are isolated whole-run times, not a change to the five-second "
             "per-decision budget.", "",
             "## Paired instances", "",
             "| Instance | Family | Size | Original | Recovery v2 | Change | "
             "Whole-run time old / v2 (s) | Max decision latency old / v2 (s) |",
             "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |"]
    for row in records:
        lines.append(f"| {row['instance']} | {row['family']} | {row['size']} | "
                     f"{row['old']} | {row['new']} | {row['delta']:+d} | "
                     f"{row['old_time']:.1f} / {row['new_time']:.1f} | "
                     f"{row['old_latency']:.3f} / {row['new_latency']:.3f} |")
    lines += ["", "## By size", "",
             "| Size | Scenarios | Original service | Recovery service | Paired change | Complete old / v2 |",
             "| ---: | ---: | ---: | ---: | ---: | ---: |"]
    for size in (25, 50, 100):
        group = [row for row in records if row["size"] == size]
        lines.append(f"| {size} | {len(group)} | {sum(r['old'] for r in group)} | "
                     f"{sum(r['new'] for r in group)} | {sum(r['delta'] for r in group):+d} | "
                     f"{sum(r['old_full'] for r in group)} / {sum(r['new_full'] for r in group)} |")
    lines += ["", "## By family", "",
             "| Family | Scenarios | Paired customers gained |", "| --- | ---: | ---: |"]
    for family in ("C1", "C2", "R1", "R2", "RC1", "RC2"):
        group = [row for row in records if row["family"] == family]
        lines.append(f"| {family} | {len(group)} | {sum(r['delta'] for r in group):+d} |")
    lines += ["", "The bootstrap resamples **base instances**, not decisions or customers. "
             "Intervals are exploratory: one seed and one DoD per instance, with no "
             "multiplicity-adjusted confirmatory claim. Neither this screen nor the "
             "selected pilot may be used to tune on historical holdouts.", ""]
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    fig, ax = plt.subplots(figsize=(9, 6))
    ordered = sorted(records, key=lambda row: (row["delta"], row["instance"]))
    bars = ax.barh([row["instance"] for row in ordered],
                   [row["delta"] for row in ordered],
                   color=["#267a66" if row["delta"] > 0 else
                          "#b44345" if row["delta"] < 0 else "#8b949e" for row in ordered])
    ax.axvline(0, color="#30363d", linewidth=0.8)
    ax.set_xlabel("Paired customers served: Recovery v2 minus original")
    ax.set_title("Development screen, DoD 0.75 (18 base instances)")
    ax.bar_label(bars, labels=[f"{row['delta']:+d}" for row in ordered], padding=3)
    fig.tight_layout()
    fig.savefig(writable_path(OUTPUT / "paired_service_by_instance.png"), dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    analyze()
