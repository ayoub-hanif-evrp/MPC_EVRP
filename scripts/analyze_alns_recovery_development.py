"""Audit and summarize the selected-case ALNS recovery development pilot."""

from collections import defaultdict
from hashlib import sha256
from statistics import mean, median

from evrp.storage import ROOT, load_json, writable_path
from scripts.run_alns_recovery_development import CASES, OUTPUT, VARIANTS


def analyze():
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    if (manifest["status"] != "complete" or manifest["completed_runs"] !=
            manifest["planned_runs"] != len(CASES) * len(VARIANTS)):
        raise ValueError("ALNS recovery pilot incomplete")
    pairs = defaultdict(dict)
    for row in manifest["records"]:
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError(f"Recovery raw SHA-256 mismatch: {path}")
        raw = load_json(path)
        if (not all(row["independent_audit"].values()) or
                raw["metadata"]["source_sha256"] != protocol["source_sha256"] or
                raw["metadata"]["protocol_identifier"] != manifest["protocol_identifier"] or
                raw["metrics"]["max_optimization_latency"] > 5.0 + 1e-6):
            raise ValueError(f"Recovery audit, provenance, or budget failure: {path}")
        key = row["instance"], row["dynamicity"], row["seed"]
        if row["variant"] in pairs[key]:
            raise ValueError(f"Duplicate recovery run: {key}")
        pairs[key][row["variant"]] = row
    lines = ["# ALNS recovery v2: selected development pilot", "",
             "Six **seen, loss-selected** scenarios, not a representative sample or "
             "independent evaluation. Original ALNS and Recovery V2 ran in isolated "
             "processes with the original decoder, original dispatch policy, identical "
             "scenarios/K_ref, unchanged objective, and five-second decisions. "
             "Every raw trace has a manifest hash and independent replay.", "",
             "| Instance | DoD | Original | Recovery v2 | Change | "
             "Worker time original / v2 (s) | Max decision latency original / v2 (s) |",
             "| --- | ---: | ---: | ---: | ---: | --- | --- |"]
    deltas, ratios = [], []
    for key in sorted(pairs):
        variants = pairs[key]
        if set(variants) != set(VARIANTS):
            raise ValueError(f"Unpaired recovery scenario: {key}")
        original, enhanced = (variants[variant] for variant in VARIANTS)
        if original["scenario_id"] != enhanced["scenario_id"] or original["k_ref"] != enhanced["k_ref"]:
            raise ValueError(f"Scenario or fleet changed: {key}")
        delta = enhanced["customers_served"] - original["customers_served"]
        deltas.append(delta)
        ratios.append(enhanced["worker_wall_seconds"] / original["worker_wall_seconds"])
        lines.append(f"| {key[0]} | {key[1]} | "
                     f"{original['customers_served']}/{original['size']} | "
                     f"{enhanced['customers_served']}/{enhanced['size']} | {delta:+d} | "
                     f"{original['worker_wall_seconds']:.1f} / "
                     f"{enhanced['worker_wall_seconds']:.1f} | "
                     f"{original['max_optimization_latency']:.3f} / "
                     f"{enhanced['max_optimization_latency']:.3f} |")
    lines += ["", f"Net paired gain: {sum(deltas):+d} customers over {len(deltas)} "
             f"selected scenarios; mean change {mean(deltas):+.2f}. "
             f"Median worker-time ratio {median(ratios):.2f}x.", "",
             "This pilot supports further **balanced development screening**, not "
             "selection or final-paper superiority claims. The 25-customer regression "
             "and runtime costs must remain visible. No independent holdout was opened.", ""]
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    analyze()
