"""Inventory and independently audit risk-aware fleet-MCTS development evidence."""

import argparse
import hashlib
import json
from pathlib import Path

from evrp.audit import audit_record


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/risk_aware_fleet_manifest.json"
TABLE = ROOT / "docs/risk_aware_fleet_table.md"
INSTANCES = {"c101_21", "c201_21", "r101_21", "r201_21", "rc101_21", "rc201_21"}
RUN_DIRS = (
    "fleet_mcts_upgrade_dev",
    "fleet_mcts_upgrade_dev2",
    "fleet_mcts_risk_static",
    "fleet_mcts_upgrade_dev3",
    "fleet_mcts_upgrade_dev4",
    "fleet_mcts_risk_static_b695d12",
    "fleet_mcts_upgrade_dev5",
    "fleet_mcts_risk_final_static",
    "fleet_mcts_upgrade_dev6",
    "fleet_mcts_risk_bounded_static",
    "fleet_mcts_risk_dynamic_dev",
)


def files():
    return sorted(path for directory in RUN_DIRS
                  for path in (ROOT / "results" / directory).rglob("*.json"))


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def entry(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    scenario_path = Path(raw["scenario_path"])
    if not scenario_path.exists():
        local_scenario = ROOT / "results" / "scenarios" / scenario_path.name
        if not local_scenario.exists():
            raise ValueError(f"Missing scenario for {path}: {scenario_path.name}")
        raw["scenario_path"] = str(local_scenario)
    identity = raw["identity"]
    metrics = raw["metrics"]
    campaign = path.relative_to(ROOT / "results").parts[0]
    if identity["instance"] not in INSTANCES or identity["algorithm"] not in {
            "FLEET_MPC_MCTS", "ROLLING_LNS"}:
        raise ValueError(f"Unexpected run: {path}")
    return dict(result_file=path.relative_to(ROOT).as_posix(), sha256=digest(path),
                campaign=campaign, status=raw["status"], audit_errors=audit_record(raw),
                instance=identity["instance"], algorithm=identity["algorithm"],
                scenario_seed=identity["scenario_seed"], dynamicity=identity["requested_config"]["dynamicity"],
                run_id=identity["run_id"], git_commit=identity["git_commit"],
                source_hash=identity["source_sha256"], scenario_hash=identity["scenario_hash"],
                config_hash=raw["provenance"]["requested_configuration_hash"],
                served=metrics.get("customers_served"), vehicles=metrics.get("vehicles_activated"),
                distance=metrics.get("total_distance"), planning_seconds=metrics.get("total_planning_time"),
                p95_seconds=metrics.get("p95_planning_time"), max_seconds=metrics.get("maximum_planning_time"),
                deadline_overrun_rate=metrics.get("total_deadline_overrun_rate"),
                unserved=raw.get("unserved_customers", []))


def gates(rows):
    static = [row for row in rows if row["campaign"] == "fleet_mcts_risk_bounded_static"]
    static_pass = (len(static) == 6 and {r["instance"] for r in static} == INSTANCES
                   and len({(r["git_commit"], r["source_hash"], r["config_hash"]) for r in static}) == 1
                   and all(r["status"] == "completed" and r["served"] == 100
                           and r["dynamicity"] == 0 and not r["audit_errors"] for r in static))
    dynamic = [row for row in rows if row["campaign"] == "fleet_mcts_risk_dynamic_dev"]
    pairs = {}
    for row in dynamic:
        pairs.setdefault((row["instance"], row["scenario_seed"]), []).append(row)
    valid_pairs = {}
    for key, group in pairs.items():
        by_algorithm = {row["algorithm"]: row for row in group}
        if (len(group) != 2 or set(by_algorithm) != {"FLEET_MPC_MCTS", "ROLLING_LNS"}
                or len({(r["git_commit"], r["source_hash"], r["scenario_hash"])
                        for r in group}) != 1
                or any(r["status"] != "completed" or r["dynamicity"] != 0.5
                       or r["audit_errors"] for r in group)):
            continue
        valid_pairs[key] = by_algorithm
    fleet = sum(group["FLEET_MPC_MCTS"]["served"] for group in valid_pairs.values())
    baseline = sum(group["ROLLING_LNS"]["served"] for group in valid_pairs.values())
    wins = sum(group["FLEET_MPC_MCTS"]["served"] > group["ROLLING_LNS"]["served"]
               for group in valid_pairs.values())
    losses = sum(group["FLEET_MPC_MCTS"]["served"] < group["ROLLING_LNS"]["served"]
                 for group in valid_pairs.values())
    return dict(static_pass=static_pass, static_served=sum(r["served"] or 0 for r in static),
                dynamic_pairs=len(valid_pairs), dynamic_planned_pairs=12,
                fleet_served=fleet, rolling_lns_served=baseline,
                service_wins=wins, service_losses=losses,
                dynamic_gate_pass=(len(valid_pairs) == 12 and fleet >= baseline and wins > losses))


def build():
    rows = [entry(path) for path in files()]
    return dict(schema_version=1, runs=rows, gates=gates(rows))


def verify(manifest):
    current = build()
    if manifest != current:
        raise ValueError("Risk-aware evidence inventory, hashes, audits, or gates changed")


def render(manifest):
    rows = [row for row in manifest["runs"] if row["campaign"] in {
        "fleet_mcts_risk_bounded_static", "fleet_mcts_risk_dynamic_dev"}]
    lines = ["# Risk-aware Fleet MPC-MCTS development", "",
             "Generated from `risk_aware_fleet_manifest.json`; all listed raw records are",
             "SHA-256 bound and independently trace-audited. Earlier attempts are retained",
             "in the manifest. No holdout run was made.", "",
             "| Stage | Instance | Seed | Algorithm | Served | EVs | Distance | Planning s | p95 s | Max s | Audit |",
             "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in rows:
        number = lambda value: "-" if value is None else f"{value:.2f}"
        stage = "static" if row["dynamicity"] == 0 else "DoD 0.5"
        lines.append(f"| {stage} | {row['instance']} | {row['scenario_seed']} | {row['algorithm']} | "
                     f"{row['served']} | {row['vehicles']} | {number(row['distance'])} | "
                     f"{number(row['planning_seconds'])} | {number(row['p95_seconds'])} | "
                     f"{number(row['max_seconds'])} | {'pass' if not row['audit_errors'] else 'fail'} |")
    gate = manifest["gates"]
    lines += ["", f"Static gate: {'PASS' if gate['static_pass'] else 'FAIL'} "
              f"({gate['static_served']}/600).",
              f"Dynamic gate: {'PASS' if gate['dynamic_gate_pass'] else 'FAIL'}; "
              f"{gate['dynamic_pairs']}/{gate['dynamic_planned_pairs']} pairs run; "
              f"Fleet {gate['fleet_served']} versus Rolling-LNS {gate['rolling_lns_served']} "
              f"customers served, {gate['service_wins']} service wins and "
              f"{gate['service_losses']} losses.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        verify(manifest)
        if TABLE.read_text(encoding="utf-8") != render(manifest):
            raise ValueError("Risk-aware table differs from verified manifest")
    else:
        manifest = build()
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        TABLE.write_text(render(manifest), encoding="utf-8")
    print(f"Verified {len(manifest['runs'])} audited risk-aware runs; "
          f"static={'PASS' if manifest['gates']['static_pass'] else 'FAIL'}, "
          f"dynamic={'PASS' if manifest['gates']['dynamic_gate_pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
