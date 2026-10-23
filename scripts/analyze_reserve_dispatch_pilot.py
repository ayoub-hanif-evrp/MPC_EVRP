"""Verify and report the selected-case reserve-dispatch pilot."""

from collections import defaultdict
from hashlib import sha256
from statistics import median

from evrp.audit import decode_result
from evrp.experiments import audit_result, load_config, prepare
from evrp.storage import ROOT, load_json, writable_path
from scripts import run_desaulniers_campaign as development
from scripts import run_reserve_dispatch_pilot as pilot


def analyze():
    frozen = pilot.protocol(load_config(development.CONFIG))
    manifest = load_json(pilot.OUTPUT / "manifest.json")
    expected = len(pilot.CASES) * len(pilot.METHODS) * len(pilot.VARIANTS)
    if (manifest["status"] != "complete" or manifest["completed_runs"] != expected or
            manifest["planned_runs"] != expected or
            manifest["protocol_identifier"] != pilot.identifier(frozen)):
        raise ValueError("Reserve pilot incomplete or protocol mismatch")
    indexed = {}
    config = load_config(development.CONFIG)
    for row in manifest["records"]:
        key = (row["instance"], row["dynamicity"], row["seed"], row["method"], row["variant"])
        if key in indexed:
            raise ValueError("Duplicate reserve pilot run")
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Reserve pilot raw SHA-256 mismatch")
        raw = load_json(path)
        result = decode_result(raw)
        instance, reference, scenario, _ = prepare(row["instance"],
            pilot.options(config, row["instance"], row["dynamicity"], row["seed"],
                          row["method"], row["variant"]))
        audit = audit_result(result, instance, scenario)
        if (not all(audit.values()) or audit != row["independent_audit"] or
                row["scenario_id"] != scenario.identifier or row["k_ref"] != reference.fleet_size or
                raw["metadata"]["source_sha256"] != frozen["source_sha256"] or
                result.metrics["max_optimization_latency"] > 5.0 + 1e-6):
            raise ValueError(f"Reserve pilot audit failed: {key}")
        indexed[key] = (row, result.metrics)
    lines = ["# Bounded depot-reserve development pilot", "",
             "This is a **loss-selected development pilot**, not independent evaluation.",
             "Original and reserve variants used identical scenarios, fixed K_ref,",
             "original optimizer and decoder, unchanged service-first objective, and",
             "five-second decision limit. All 12 raw traces passed SHA-256 verification",
             "and independent physical/information-boundary replay.", "",
             "| Instance | Method | Original service | Reserve service | Change | Complete old / reserve | Worker s old / reserve | Triggers old / reserve | Max decision s old / reserve |",
             "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |"]
    aggregate = defaultdict(list)
    for name, dod, seed in pilot.CASES:
        for method in pilot.METHODS:
            old, old_metrics = indexed[name, dod, seed, method, "original"]
            new, new_metrics = indexed[name, dod, seed, method, "depot_slack_reserve_v2"]
            if old["scenario_id"] != new["scenario_id"] or old["k_ref"] != new["k_ref"]:
                raise ValueError("Unpaired reserve pilot scenario")
            delta = new["customers_served"] - old["customers_served"]
            aggregate[method].append(delta)
            lines.append(f"| {name}, DoD {dod} | {method} | {old['customers_served']} | "
                         f"{new['customers_served']} | {delta:+d} | "
                         f"{int(old['complete_service'])} / {int(new['complete_service'])} | "
                         f"{old['worker_wall_seconds']:.1f} / {new['worker_wall_seconds']:.1f} | "
                         f"{old_metrics['optimization_triggers']} / {new_metrics['optimization_triggers']} | "
                         f"{old['max_optimization_latency']:.3f} / "
                         f"{new['max_optimization_latency']:.3f} |")
    lines += ["", "## Decision", ""]
    for method, changes in aggregate.items():
        lines.append(f"- {method}: paired changes {', '.join(f'{d:+d}' for d in changes)}; "
                     f"total {sum(changes):+d}, median {median(changes):+.1f} customers.")
    lines += ["", "The reserve policy is **not promoted**. Its negative and mixed service",
              "results do not justify a new final holdout. These selected cases do",
              "not estimate generalization; no old final/robustness data were used",
              "to select the policy or its pilot cases.", ""]
    writable_path(pilot.OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    return aggregate


if __name__ == "__main__":
    analyze()
