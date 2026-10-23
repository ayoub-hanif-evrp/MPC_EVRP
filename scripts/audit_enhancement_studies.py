"""Replay all completed development evidence without rewriting old studies."""

from hashlib import sha256

from evrp.audit import decode_result
from evrp.experiments import audit_result, load_config, prepare
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts import run_desaulniers_campaign as development


OUTPUT = ROOT / "results/desaulniers/publication_development/audits"


def study_directories():
    roots = (ROOT / "results/desaulniers/enhancement_development",
             ROOT / "results/desaulniers/publication_development")
    for root in roots:
        for path in sorted(root.glob("*/manifest.json")):
            manifest = load_json(path)
            if not manifest.get("records") or not all("raw" in r for r in manifest["records"]):
                continue
            if manifest.get("status") != "complete":
                raise ValueError(f"Incomplete development evidence: {path.parent}")
            yield path.parent


def audit():
    config = load_config(development.CONFIG)
    scenarios, studies = {}, []
    for directory in study_directories():
        protocol = load_json(directory / "protocol.json")
        manifest = load_json(directory / "manifest.json")
        source = protocol.get("source_sha256", protocol.get("scientific", {}).get("source_sha256"))
        if (not source or manifest["protocol_identifier"] != identifier(protocol) or
                manifest["completed_runs"] != manifest["planned_runs"] or
                len(manifest["records"]) != manifest["planned_runs"]):
            raise ValueError(f"Development protocol/completeness mismatch: {directory}")
        seen = set()
        for row in manifest["records"]:
            key = row["instance"], row["dynamicity"], row["seed"]
            if key not in scenarios:
                scenarios[key] = prepare(row["instance"], development.options(
                    config, *key, "MPC_COMPLETION"))[:3]
            instance, reference, scenario = scenarios[key]
            path = (ROOT / row["raw"]).resolve()
            if (not path.is_relative_to((directory / "raw").resolve()) or
                    sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
                raise ValueError(f"Development raw SHA-256/path mismatch: {path}")
            raw = load_json(path)
            meta, metrics = raw["metadata"], raw["metrics"]
            protocol_keys = ("campaign_protocol_identifier", "pilot_protocol_identifier", "protocol_identifier")
            if (not any(meta.get(key) == identifier(protocol) for key in protocol_keys) or
                    "method" in row and meta["algorithm"] != row["method"] or
                    raw["effective_config"]["total_planning_time_limit"] != 5.0):
                raise ValueError("Development raw protocol, method or configured budget mismatch")
            for variant_key in ("campaign_variant", "dispatch_variant", "decoder_variant", "variant"):
                if variant_key in meta and meta[variant_key] != row["variant"]:
                    raise ValueError("Development raw/manifest variant mismatch")
            run = (*key, meta["algorithm"], row.get("variant", ""))
            if run in seen:
                raise ValueError(f"Duplicate development run: {directory} {run}")
            seen.add(run)
            if (meta["instance"] != row["instance"] or meta["scenario_seed"] != row["seed"] or
                    meta["source_sha256"] != source or
                    not (meta["scenario_identifier"] == row["scenario_id"] == scenario.identifier) or
                    not (meta["K_ref"] == row["k_ref"] == reference.fleet_size) or
                    not meta["isolated_worker"] or
                    metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                    any(metrics[v] for v in ("battery_violations", "capacity_violations", "time_window_violations",
                                              "duplicate_service_violations", "hidden_information_violations"))):
                raise ValueError(f"Development identity, physical or deadline mismatch: {path}")
            independent = audit_result(decode_result(raw), instance, scenario)
            if (not all(independent.values()) or independent != meta["independent_audit"] or
                    independent != row["independent_audit"]):
                raise ValueError(f"Development independent physical replay failed: {path}")
            expected = row.get("metrics", row)
            if any(metrics[key] != value for key, value in expected.items() if key in metrics):
                raise ValueError("Development manifest metrics differ from raw evidence")
        record = dict(study=directory.relative_to(ROOT).as_posix(), runs=len(seen),
                      all_independent_audits_passed=True, source_sha256=source,
                      protocol_identifier=identifier(protocol),
                      manifest_sha256=sha256((directory / "manifest.json").read_bytes()).hexdigest())
        studies.append(record)
        print(f"Audited {directory.name}: {len(seen)} raw runs", flush=True)
    save_json(OUTPUT / "enhancement_integrity.json", dict(studies=studies,
              audited_runs=sum(row["runs"] for row in studies)))
    lines = ["# Enhancement development integrity", "",
             "All completed studies below passed raw SHA-256/protocol checks, paired",
             "scenario/fleet identity, independent physical replay, duplicate/future",
             "information checks, and the five-second decision budget.", "",
             "| Study | Audited runs | Source SHA-256 |", "| --- | ---: | --- |"]
    lines.extend(f"| {row['study']} | {row['runs']} | {row['source_sha256']} |" for row in studies)
    writable_path(OUTPUT / "ENHANCEMENT_INTEGRITY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return studies


if __name__ == "__main__":
    audit()
