"""Audit and summarize the paired decoder development pilot."""

from collections import defaultdict
from hashlib import sha256

from evrp.storage import ROOT, load_json, writable_path
from scripts.run_decoder_development import CASES, METHODS, OUTPUT, VARIANTS


def analyze():
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    if (manifest["status"] != "complete" or manifest["completed_runs"] !=
            manifest["planned_runs"] != len(CASES) * len(METHODS) * len(VARIANTS)):
        raise ValueError("Decoder pilot incomplete")
    pairs = defaultdict(dict)
    for row in manifest["records"]:
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError(f"Decoder raw SHA-256 mismatch: {path}")
        raw = load_json(path)
        if (not all(row["independent_audit"].values()) or
                raw["metadata"]["source_sha256"] != protocol["source_sha256"] or
                raw["metadata"]["protocol_identifier"] != manifest["protocol_identifier"] or
                raw["metrics"]["max_optimization_latency"] > 5.0 + 1e-6):
            raise ValueError(f"Decoder audit, provenance, or budget failure: {path}")
        key = row["instance"], row["dynamicity"], row["seed"], row["method"]
        if row["variant"] in pairs[key]:
            raise ValueError(f"Duplicate decoder run: {key}")
        pairs[key][row["variant"]] = row
    lines = ["# Continuous charging decoder: development pilot", "",
             "This is a small **selected-case development ablation**, not independent "
             "evaluation. Both variants used the same released requests, K_ref, common "
             "objective, original dispatch policy, and five-second decision limit. "
             "Every raw trace has a manifest SHA-256 and independent plant replay.", "",
             "| Instance | DoD | Method | Original | LP fallback | Change | "
             "Worker time original / LP (s) | Max decision latency original / LP (s) |",
             "| --- | ---: | --- | ---: | ---: | ---: | --- | --- |"]
    changes = defaultdict(list)
    time_ratios = defaultdict(list)
    for key in sorted(pairs):
        variants = pairs[key]
        if set(variants) != set(VARIANTS):
            raise ValueError(f"Unpaired decoder run: {key}")
        original, enhanced = (variants[variant] for variant in VARIANTS)
        if original["scenario_id"] != enhanced["scenario_id"] or original["k_ref"] != enhanced["k_ref"]:
            raise ValueError(f"Scenario or fleet changed: {key}")
        delta = enhanced["customers_served"] - original["customers_served"]
        changes[key[3]].append(delta)
        time_ratios[key[3]].append(enhanced["worker_wall_seconds"] /
                                   original["worker_wall_seconds"])
        lines.append(f"| {key[0]} | {key[1]} | {key[3]} | "
                     f"{original['customers_served']}/{original['size']} | "
                     f"{enhanced['customers_served']}/{enhanced['size']} | {delta:+d} | "
                     f"{original['worker_wall_seconds']:.1f} / "
                     f"{enhanced['worker_wall_seconds']:.1f} | "
                     f"{original['max_optimization_latency']:.3f} / "
                     f"{enhanced['max_optimization_latency']:.3f} |")
    lines += ["", "## Decision", ""]
    for method in METHODS:
        values = changes[method]
        ratios = time_ratios[method]
        lines.append(f"- {method}: paired service changes "
                     f"{', '.join(f'{value:+d}' for value in values)}; "
                     f"worker-time ratios {', '.join(f'{ratio:.2f}x' for ratio in ratios)}.")
    lines += ["", "The LP fallback solves a synthetic fixed-charge-target miss, but "
             "the first-decision ALNS loss probe found no LP-only insertion witness on "
             "these development traces. This end-to-end pilot does not support "
             "adopting it as the default. A bounded decoder failure does not prove "
             "physical infeasibility. No new final holdout was opened.", ""]
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    analyze()
