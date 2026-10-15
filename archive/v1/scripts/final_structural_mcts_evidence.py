"""Inventory and independently audit the stopped structural-rollout campaign."""

import argparse
import hashlib
import json

from evrp.audit import audit_record
from evrp.experiments import source_fingerprint
from evrp.storage import ROOT, load_json


RAW = ROOT / "results" / "final" / "structural_rollout" / "raw"
MANIFEST = ROOT / "docs" / "structural_rollout_manifest.json"


def build():
    source = source_fingerprint()
    records = []
    for path in sorted(RAW.glob("*/*.json")):
        result = load_json(path)
        errors = audit_record(result)
        if errors:
            raise ValueError(f"Independent audit failed for {path}: {errors}")
        identity = result["identity"]
        metrics = result["metrics"]
        records.append(dict(stage=path.parent.name,
                            role="final_method" if identity["source_sha256"] == source
                            else "intermediate_diagnostic",
                            path=path.relative_to(ROOT).as_posix(),
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            instance=identity["instance"],
                            scenario_seed=identity["scenario_seed"],
                            scenario_hash=identity["scenario_hash"],
                            algorithm=identity["algorithm"],
                            customers_served=metrics["customers_served"],
                            source_sha256=identity["source_sha256"],
                            base_git_commit=identity["git_commit"],
                            planner_objective_version=identity["planner_objective_version"],
                            search_policy_version=identity["search_policy_version"]))
    final = [r for r in records if r["role"] == "final_method"]
    if (len(records) != 10 or len(final) != 6
            or sum(r["stage"] == "diagnostic" for r in final) != 4
            or sum(r["stage"] == "static" for r in final) != 2):
        raise ValueError("Unexpected stopped-campaign record set")
    return dict(schema_version=1, status="stopped_static_gate_failed",
                objective_version="service-activation-distance-v2",
                planner_objective_version="risk-control-flex-service-v1",
                search_policy_version="fleet-mcts-structural-rollout-v2",
                final_source_sha256=source, records=records)


def main(verify):
    manifest = build()
    serialized = json.dumps(manifest, indent=2) + "\n"
    if verify:
        if not MANIFEST.exists() or MANIFEST.read_text(encoding="utf-8") != serialized:
            raise ValueError("Manifest differs from independently audited raw records")
    else:
        MANIFEST.write_text(serialized, encoding="utf-8")
    print(f"{'Verified' if verify else 'Recorded'} {len(manifest['records'])} audited raw runs; "
          "final static gate FAIL")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    main(parser.parse_args().verify)
