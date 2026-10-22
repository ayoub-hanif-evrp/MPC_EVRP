"""Read-only, independent replay of the corrected Desaulniers final evidence."""

from collections import defaultdict
from hashlib import sha256

from evrp.audit import decode_result
from evrp.experiments import audit_result, load_config, prepare
from evrp.storage import ROOT, identifier, load_json, writable_path
from scripts.run_desaulniers_final import CONFIG, OUTPUT, options, selected_instances, source_hash
from scripts.run_desaulniers_pilot import dataset_hash, VIOLATIONS


REPORT = ROOT / "results/desaulniers/validation/final_integrity.md"


def verify():
    config = load_config(CONFIG)
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    original = load_json(ROOT / "results/desaulniers/final_holdout/manifest.json")
    methods = config["methods"]
    cases = selected_instances(config)
    expected = {(c["instance"], dod, seed, method)
                for c in cases for dod in config["dynamicities"]
                for seed in config["scenario_seeds"] for method in methods}
    rows = manifest["records"]
    keys = [(r["instance"], r["dynamicity"], r["seed"], r["method"]) for r in rows]
    if (manifest["status"] != "final_complete" or manifest["planned_runs"] != 270 or
            manifest["completed_runs"] != 270 or manifest["ineligible"] or
            len(keys) != len(set(keys)) or set(keys) != expected or
            manifest["protocol_identifier"] != identifier(protocol) or
            protocol["source_sha256"] != source_hash() or
            protocol["dataset_sha256"] != dataset_hash() or
            protocol["config_sha256"] != sha256(CONFIG.read_bytes()).hexdigest() or
            protocol["selected"] != cases or
            protocol["methods"] != methods):
        raise ValueError("Frozen protocol, dataset, selection, or manifest mismatch")
    grouped = defaultdict(dict)
    scenarios = {}
    for index, row in enumerate(rows, 1):
        key = row["instance"], row["dynamicity"], row["seed"]
        if key not in scenarios:
            instance, reference, scenario, _ = prepare(
                row["instance"], options(config, *key, "MPC_COMPLETION"))
            scenarios[key] = instance, reference, scenario
        instance, reference, scenario = scenarios[key]
        path = (ROOT / row["raw"]).resolve()
        if not path.is_relative_to((OUTPUT / "raw").resolve()) or not path.is_file():
            raise ValueError(f"Missing or escaped raw path: {row['raw']}")
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError(f"Raw digest mismatch: {path}")
        raw = load_json(path)
        meta, metrics = raw["metadata"], raw["metrics"]
        if (meta["instance"] != row["instance"] or meta["algorithm"] != row["method"] or
                meta["scenario_seed"] != row["seed"] or
                meta["scenario_identifier"] != row["scenario_id"] != scenario.identifier or
                meta["reference_schedule_identifier"] != row["reference_identifier"] != reference.identifier or
                meta["instance_sha256"] != row["instance_sha256"] != instance.sha256 or
                meta["K_ref"] != row["k_ref"] != reference.fleet_size or
                meta["source_sha256"] != protocol["source_sha256"] or
                meta["dataset_sha256"] != protocol["dataset_sha256"] or
                not meta["isolated_worker"] or meta["charging_policy"] != "MP" or
                metrics["customers_served"] != row["customers_served"] or
                metrics["complete_service"] != row["complete_service"] or
                metrics["vehicles_activated"] != row["vehicles_activated"] or
                metrics["total_distance"] != row["total_distance"] or
                metrics["max_optimization_latency"] != row["max_optimization_latency"] or
                metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                any(metrics[v] for v in VIOLATIONS)):
            raise ValueError(f"Raw identity, outcome, feasibility, or budget mismatch: {path}")
        audit = audit_result(decode_result(raw), instance, scenario)
        if not all(audit.values()) or audit != meta["independent_audit"]:
            raise ValueError(f"Independent replay mismatch: {path}")
        grouped[key][row["method"]] = row
        if index % 25 == 0:
            print(f"replayed {index}/{len(rows)}", flush=True)
    if len(grouped) != 54 or any(set(group) != set(methods) for group in grouped.values()):
        raise ValueError("Missing paired scenario methods")
    old_paths = {r["raw"] for r in original["records"]}
    if old_paths & {r["raw"] for r in rows}:
        raise ValueError("Original and corrected final raw evidence overlap")
    lines = ["# Corrected final-holdout integrity", "",
             f"Frozen protocol: `{identifier(protocol)}`.",
             f"Original partial campaign: {len(original['records'])} records, preserved separately.",
             f"Corrected campaign: {len(rows)}/270 raw files with matching SHA-256 digests.",
             f"Matched scenarios: {len(grouped)}/54 with all five methods and identical inputs.",
             "All raw traces independently decoded and replayed; all replay checks passed.",
             "All source/dataset/config identities, fixed fleets, recorded outcomes, and "
             "five-second decision maxima matched the manifest.", ""]
    writable_path(REPORT).write_text("\n".join(lines), encoding="utf-8")
    return len(rows)


if __name__ == "__main__":
    print(f"Verified {verify()} corrected final records")
