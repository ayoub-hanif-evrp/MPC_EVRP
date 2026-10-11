"""Freeze and verify the single-seed fleet-LNS development evidence."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "f37b8ac6e7c332a5784a845ebad1870c7b87c1d8d608c601c68e67155485d6b7"
HYBRID_SOURCE = "0ef7219ac6c578bdd8134809cfbdfb9d65958464b7cae4170c7af4d879336c5d"
INSTANCES = ("c101_21", "c201_21", "r101_21", "r201_21", "rc101_21", "rc201_21")
STATIC = ROOT / "results/fleet_lns_static/runs"
DYNAMIC = ROOT / "results/fleet_lns_development/runs"
HYBRID_STATIC = ROOT / "results/fleet_lns_hybrid_static/runs"
MANIFEST = ROOT / "docs/fleet_lns_evidence_manifest.json"
TABLES = ROOT / "docs/fleet_lns_evidence_tables.md"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path, raw, source=SOURCE):
    identity = raw["identity"]
    if raw["status"] != "completed" or not all(raw["audit"].values()):
        raise ValueError(f"Unusable evidence: {path}")
    if identity["source_sha256"] != source or raw["provenance"]["source_sha256"] != source:
        raise ValueError(f"Source mismatch: {path}")
    metrics = raw["metrics"]
    return {
        "instance": identity["instance"],
        "algorithm": identity["algorithm"],
        "scenario_hash": identity["scenario_hash"],
        "source_hash": source,
        "config_hash": raw["provenance"]["requested_configuration_hash"],
        "run_id": identity["run_id"],
        "result_file": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "status": raw["status"],
        "customers_served": metrics["customers_served"],
        "vehicles_activated": metrics["vehicles_activated"],
        "total_distance": metrics["total_distance"],
        "total_planning_time": metrics["total_planning_time"],
        "maximum_planning_time": metrics["maximum_planning_time"],
    }


def select(directory, instance, algorithm, dynamicity, source=SOURCE):
    matches = []
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        identity = raw.get("identity", {})
        requested = identity.get("requested_config", {})
        if (identity.get("instance") == instance and identity.get("algorithm") == algorithm
                and identity.get("source_sha256") == source
                and requested.get("dynamicity") == dynamicity):
            matches.append((path, raw))
    if len(matches) != 1:
        raise ValueError(f"Expected one {instance}/{algorithm}/DoD {dynamicity} run, found {len(matches)}")
    return record(*matches[0], source=source)


def build_manifest():
    static = [select(STATIC, name, "ROLLING_ALNS", 0.0) for name in INSTANCES]
    dynamic = [select(DYNAMIC, name, algorithm, 0.5) for name in INSTANCES
               for algorithm in ("ROLLING_ALNS", "MPC_MCTS_ALNS")]
    hybrid_static_partial = [select(HYBRID_STATIC, name, "MPC_MCTS_LNS", 0.0,
                                    source=HYBRID_SOURCE) for name in INSTANCES[:3]]
    for index in range(0, len(dynamic), 2):
        if dynamic[index]["scenario_hash"] != dynamic[index + 1]["scenario_hash"]:
            raise ValueError(f"Unmatched scenario: {dynamic[index]['instance']}")
    return {"schema_version": 2, "source_hash": SOURCE,
            "hybrid_static_source_hash": HYBRID_SOURCE, "static": static, "dynamic": dynamic,
            "hybrid_static_partial": hybrid_static_partial}


def verify(manifest):
    if (manifest["source_hash"] != SOURCE or manifest["hybrid_static_source_hash"] != HYBRID_SOURCE
            or len(manifest["static"]) != 6 or len(manifest["dynamic"]) != 12
            or len(manifest["hybrid_static_partial"]) != 3):
        raise ValueError("Unexpected evidence manifest")
    for entry in manifest["static"] + manifest["dynamic"] + manifest["hybrid_static_partial"]:
        path = ROOT / entry["result_file"]
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"Changed result file: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        source = HYBRID_SOURCE if entry in manifest["hybrid_static_partial"] else SOURCE
        if record(path, raw, source=source) != entry:
            raise ValueError(f"Changed result metadata: {path}")
    for name in INSTANCES:
        static = [r for r in manifest["static"] if r["instance"] == name]
        pair = [r for r in manifest["dynamic"] if r["instance"] == name]
        if (len(static) != 1 or len(pair) != 2 or
                {r["algorithm"] for r in pair} != {"ROLLING_ALNS", "MPC_MCTS_ALNS"} or
                pair[0]["scenario_hash"] != pair[1]["scenario_hash"]):
            raise ValueError(f"Incomplete or unmatched evidence: {name}")
    if [r["instance"] for r in manifest["hybrid_static_partial"]] != list(INSTANCES[:3]):
        raise ValueError("Unexpected partial hybrid-static selection")


def winner(rolling, hybrid):
    for key, reason in (("customers_served", "service"), ("vehicles_activated", "EVs"),
                        ("total_distance", "distance")):
        a, b = rolling[key], hybrid[key]
        if a != b:
            better = "Hybrid" if (b > a if key == "customers_served" else b < a) else "Rolling"
            return f"{better}: {reason}"
    return "Tie"


def render_tables(manifest):
    lines = ["# Fleet-LNS evidence tables", "",
             "Generated from `fleet_lns_evidence_manifest.json` by `scripts/fleet_lns_evidence.py`.",
             "The ALNS algorithm IDs are historical labels; these methods use non-adaptive LNS.",
             "", "## Static", "",
             "| Instance | Served | EVs | Distance | Planning s | Max event s |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in manifest["static"]:
        lines.append(f"| {row['instance']} | {row['customers_served']} | {row['vehicles_activated']} | "
                     f"{row['total_distance']:.2f} | {row['total_planning_time']:.2f} | "
                     f"{row['maximum_planning_time']:.2f} |")
    lines += ["", "## Hybrid static check (partial)", "",
              "The first three `MPC_MCTS_LNS` static runs completed. `r201_21` was interrupted",
              "after a 30-minute wall-time cutoff; `rc101_21` and `rc201_21` were not started.",
              "This is not a six-instance pass.", "",
              "| Instance | Served | EVs | Distance | Planning s | Max event s |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in manifest["hybrid_static_partial"]:
        lines.append(f"| {row['instance']} | {row['customers_served']} | {row['vehicles_activated']} | "
                     f"{row['total_distance']:.2f} | {row['total_planning_time']:.2f} | "
                     f"{row['maximum_planning_time']:.2f} |")
    lines += ["", "## Matched dynamic development (DoD 0.5, seeds 0)", "",
              "Each cell is `served / EVs / distance / total planning seconds`.", "",
              "| Instance | Rolling LNS | MPC-MCTS-LNS | Lexicographic winner |",
              "| --- | --- | --- | --- |"]
    def cell(row):
        return (f"{row['customers_served']} / {row['vehicles_activated']} / "
                f"{row['total_distance']:.2f} / {row['total_planning_time']:.2f}")
    for name in INSTANCES:
        pair = {r["algorithm"]: r for r in manifest["dynamic"] if r["instance"] == name}
        rolling, hybrid = pair["ROLLING_ALNS"], pair["MPC_MCTS_ALNS"]
        lines.append(f"| {name} | {cell(rolling)} | {cell(hybrid)} | {winner(rolling, hybrid)} |")
    totals = {algorithm: sum(r["customers_served"] for r in manifest["dynamic"]
                             if r["algorithm"] == algorithm)
              for algorithm in ("ROLLING_ALNS", "MPC_MCTS_ALNS")}
    lines += ["", f"Total service: Rolling LNS {totals['ROLLING_ALNS']}/600; "
              f"MPC-MCTS-LNS {totals['MPC_MCTS_ALNS']}/600.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Verify frozen files and generated tables")
    args = parser.parse_args()
    if args.verify:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        verify(manifest)
        if TABLES.read_text(encoding="utf-8") != render_tables(manifest):
            raise ValueError("Generated tables differ from frozen manifest")
        print("Fleet-LNS evidence manifest and tables verified")
        return
    manifest = build_manifest()
    verify(manifest)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    TABLES.write_text(render_tables(manifest), encoding="utf-8")
    print(f"Froze {len(manifest['static'])} rolling static, {len(manifest['dynamic'])} dynamic, "
          f"and {len(manifest['hybrid_static_partial'])} partial hybrid static runs")


if __name__ == "__main__":
    main()
