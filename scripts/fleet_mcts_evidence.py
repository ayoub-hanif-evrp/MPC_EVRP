"""Inventory and independently audit every fleet-MCTS static development run."""

import argparse
import hashlib
import json
from pathlib import Path

from evrp.audit import audit_record


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results/fleet_mcts_static/runs"
MANIFEST = ROOT / "docs/fleet_mcts_static_manifest.json"
TABLE = ROOT / "docs/fleet_mcts_static_table.md"
INSTANCES = {"c101_21", "c201_21", "r101_21", "r201_21", "rc101_21", "rc201_21"}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entry(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    identity = raw["identity"]
    if (identity["instance"] not in INSTANCES or identity["algorithm"] != "FLEET_MPC_MCTS"
            or identity["requested_config"].get("dynamicity") != 0):
        raise ValueError(f"Unexpected run in static campaign: {path}")
    errors = audit_record(raw)
    metrics = raw["metrics"]
    return {
        "result_file": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "status": raw["status"],
        "audit_errors": errors,
        "instance": identity["instance"],
        "algorithm": identity["algorithm"],
        "run_id": identity["run_id"],
        "git_commit": identity["git_commit"],
        "source_hash": identity["source_sha256"],
        "scenario_hash": identity["scenario_hash"],
        "config_hash": raw["provenance"]["requested_configuration_hash"],
        "served": metrics.get("customers_served"),
        "evs": metrics.get("vehicles_activated"),
        "distance": metrics.get("total_distance"),
        "planning_seconds": metrics.get("total_planning_time"),
        "p95_event_seconds": metrics.get("p95_planning_time"),
        "max_event_seconds": metrics.get("maximum_planning_time"),
        "tree_improvements": metrics.get("fleet_mcts_tree_improvements"),
        "deadline_overrun_rate": metrics.get("total_deadline_overrun_rate"),
        "unserved": raw.get("unserved_customers", []),
    }


def render(manifest):
    lines = ["# Fleet-MCTS static development attempts", "",
             "Generated from `fleet_mcts_static_manifest.json`. Every JSON run in the static",
             "campaign directory is included; each completed file is independently audited.",
             "No dynamic or holdout cases were run.", "",
             "| Source prefix | Instance | Status/audit | Served | EVs | Distance | Planning s | p95 s | Max s | Unserved |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    def number(value):
        return "-" if value is None else f"{value:.2f}"
    for row in manifest["runs"]:
        audit = "pass" if not row["audit_errors"] else "fail"
        lines.append(f"| `{row['source_hash'][:10]}` | {row['instance']} | {row['status']}/{audit} | "
                     f"{row['served'] if row['served'] is not None else '-'} | "
                     f"{row['evs'] if row['evs'] is not None else '-'} | "
                     f"{number(row['distance'])} | {number(row['planning_seconds'])} | "
                     f"{number(row['p95_event_seconds'])} | {number(row['max_event_seconds'])} | "
                     f"{', '.join(row['unserved']) or '-'} |")
    groups = {}
    for row in manifest["runs"]:
        groups.setdefault((row["source_hash"], row["config_hash"]), []).append(row)
    passed = any({row["instance"] for row in group} == INSTANCES and len(group) == 6
                 and all(row["served"] == 100 and row["status"] == "completed"
                         and not row["audit_errors"] for row in group)
                 for group in groups.values())
    lines += ["", ("Static six-instance gate: PASS." if passed else
                   "Static six-instance gate: FAIL; no single source/configuration serves 100/100 on all six."), ""]
    return "\n".join(lines)


def build():
    files = sorted(RUNS.glob("*.json"))
    if not files:
        raise ValueError("No fleet-MCTS static results found")
    return {"schema_version": 1, "runs": [entry(path) for path in files]}


def verify(manifest):
    files = {path.relative_to(ROOT).as_posix() for path in RUNS.glob("*.json")}
    listed = {row["result_file"] for row in manifest["runs"]}
    if manifest["schema_version"] != 1 or files != listed or len(listed) != len(manifest["runs"]):
        raise ValueError("Static campaign manifest omits or duplicates a run")
    for row in manifest["runs"]:
        if entry(ROOT / row["result_file"]) != row:
            raise ValueError(f"Changed static evidence: {row['result_file']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        verify(manifest)
        if TABLE.read_text(encoding="utf-8") != render(manifest):
            raise ValueError("Static table differs from manifest")
        print(f"Verified {len(manifest['runs'])} independently audited static runs")
        return
    manifest = build()
    verify(manifest)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    TABLE.write_text(render(manifest), encoding="utf-8")
    print(f"Inventoried {len(manifest['runs'])} independently audited static runs")


if __name__ == "__main__":
    main()
