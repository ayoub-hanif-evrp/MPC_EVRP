"""Summarize the source-frozen, paired dispatch development pilot."""

from collections import defaultdict
from hashlib import sha256
from statistics import mean

from evrp.storage import ROOT, load_json, writable_path
from scripts.run_enhancement_development import OUTPUT, VARIANTS, METHODS, CASES


def analyze():
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    if (manifest["status"] != "complete" or manifest["completed_runs"] !=
            manifest["planned_runs"] != len(CASES) * len(METHODS) * len(VARIANTS)):
        raise ValueError("Dispatch pilot incomplete")
    pairs = defaultdict(dict)
    for row in manifest["records"]:
        raw_path = ROOT / row["raw"]
        if sha256(raw_path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError(f"Raw SHA-256 mismatch: {raw_path}")
        raw = load_json(raw_path)
        if (not all(row["independent_audit"].values()) or
                raw["metadata"]["source_sha256"] != protocol["source_sha256"] or
                raw["metadata"]["pilot_protocol_identifier"] != manifest["protocol_identifier"] or
                raw["metrics"]["max_optimization_latency"] > 5.0 + 1e-6):
            raise ValueError(f"Audit, provenance, or budget failure: {raw_path}")
        key = row["instance"], row["dynamicity"], row["seed"], row["method"]
        if row["variant"] in pairs[key]:
            raise ValueError(f"Duplicate pilot variant: {key}")
        pairs[key][row["variant"]] = row
    lines = ["# Depot-window waiting: development mechanism pilot", "",
             "This is a **selected-case development pilot**, not independent evaluation. "
             "The three cases were chosen for historical ALNS service losses before the "
             "new variants ran. Both policies used the same observable scenario, fixed "
             "fleet, service-first objective, five-second budget, and independent replay.", "",
             "| Instance | DoD | Method | Original | Depot wait | Paired change | "
             "Original / wait max latency (s) |",
             "| --- | ---: | --- | ---: | ---: | ---: | --- |"]
    changes = defaultdict(list)
    for key in sorted(pairs):
        variants = pairs[key]
        if set(variants) != set(VARIANTS):
            raise ValueError(f"Unpaired pilot scenario: {key}")
        original, delayed = (variants[v] for v in VARIANTS)
        if original["scenario_id"] != delayed["scenario_id"] or original["k_ref"] != delayed["k_ref"]:
            raise ValueError(f"Scenario/fleet changed within pair: {key}")
        change = delayed["customers_served"] - original["customers_served"]
        changes[key[3]].append(change)
        lines.append(f"| {key[0]} | {key[1]} | {key[3]} | "
                     f"{original['customers_served']}/{original['size']} | "
                     f"{delayed['customers_served']}/{delayed['size']} | {change:+d} | "
                     f"{original['max_optimization_latency']:.3f} / "
                     f"{delayed['max_optimization_latency']:.3f} |")
    lines += ["", "## Interpretation", ""]
    for method in METHODS:
        values = changes[method]
        lines.append(f"- {method}: changes {', '.join(f'{value:+d}' for value in values)}; "
                     f"mean {mean(values):+.2f} customers per selected case.")
    lines += ["", "The result is mixed and too small/selected for inferential claims. "
             "The policy remains optional and is not the default. It must not be "
             "described as an established improvement or selected using historical "
             "robustness/final outcomes. No new final holdout was opened.", ""]
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    analyze()
