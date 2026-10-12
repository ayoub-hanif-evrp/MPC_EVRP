"""Audit and summarize the frozen risk-aware fleet development campaign."""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.audit import audit_record
from evrp.storage import ROOT, load_json


FINAL = ROOT / "results" / "final"
FROZEN_COMMIT = "6a1ab7ea1944a8f06665a72a3da3d90462a93f9b"
INSTANCES = ("c101_21", "c201_21", "r101_21", "r201_21", "rc101_21", "rc201_21")
FLEET = "FLEET_MPC_MCTS"
BASELINE = "ROLLING_LNS"


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_records(stage):
    records = []
    for path in sorted((FINAL / "raw" / stage).glob("*.json")):
        record = load_json(path)
        if record["identity"]["git_commit"] != FROZEN_COMMIT:
            if stage == "development":
                raise ValueError(f"Foreign development record: {path}")
            continue
        errors = audit_record(record)
        if errors or record["status"] != "completed":
            raise ValueError(f"Invalid {path}: {errors or record['status']}")
        records.append((path, record))
    expected = 6 if stage == "static" else 24
    if len(records) != expected:
        raise ValueError(f"Expected {expected} {stage} records, found {len(records)}")
    if len({record["identity"]["source_sha256"] for _, record in records}) != 1:
        raise ValueError(f"Mixed source hashes in {stage}")
    return records


def overrun_count(metrics):
    return round(metrics["total_deadline_overrun_rate"] * metrics["decision_epochs"])


def fleet_risk(record, field):
    values = [decision["fleet_mcts"]["best_components"][field]
              for decision in record["decisions"]
              if decision.get("fleet_mcts") and
              decision["fleet_mcts"]["best_components"]["unserved_customers"] == 0]
    return sum(values) / len(values) if values else None


def mean_defined(values):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def summarize():
    static = load_records("static")
    development = load_records("development")
    rows = []
    grouped = defaultdict(dict)
    for path, record in development:
        identity = record["identity"]
        key = (identity["instance"], identity["scenario_seed"])
        algorithm = identity["algorithm"]
        if algorithm in grouped[key]:
            raise ValueError(f"Duplicate pair member: {key} {algorithm}")
        grouped[key][algorithm] = (path, record)
    if set(grouped) != {(instance, seed) for instance in INSTANCES for seed in (0, 1)}:
        raise ValueError("Incomplete matched development grid")

    for instance in INSTANCES:
        for seed in (0, 1):
            pair = grouped[instance, seed]
            if set(pair) != {FLEET, BASELINE}:
                raise ValueError(f"Incomplete pair: {instance} seed {seed}")
            fleet = pair[FLEET][1]
            baseline = pair[BASELINE][1]
            if (fleet["identity"]["scenario_hash"] != baseline["identity"]["scenario_hash"]
                    or fleet["metadata"]["K_ref"] != baseline["metadata"]["K_ref"]):
                raise ValueError(f"Scenario/fleet mismatch: {instance} seed {seed}")
            if any(record["metadata"]["DoD_realized"] != 0.5 or
                   record["identity"]["algorithm_seed"] != 0
                   for record in (fleet, baseline)):
                raise ValueError(f"DoD/algorithm seed mismatch: {instance} seed {seed}")
            fm, bm = fleet["metrics"], baseline["metrics"]
            equal_service = fm["customers_served"] == bm["customers_served"]
            equal_fleet = fm["vehicles_activated"] == bm["vehicles_activated"]
            rows.append(dict(instance=instance, family=fleet["identity"]["family"], scenario_seed=seed,
                             K_ref=fleet["metadata"]["K_ref"], DoD_realized=0.5,
                             scenario_hash=fleet["identity"]["scenario_hash"],
                             fleet_served=fm["customers_served"], lns_served=bm["customers_served"],
                             service_delta=fm["customers_served"] - bm["customers_served"],
                             fleet_EV=fm["vehicles_activated"], lns_EV=bm["vehicles_activated"],
                             EV_delta_equal_service=(fm["vehicles_activated"] - bm["vehicles_activated"]
                                                     if equal_service else ""),
                             fleet_distance=fm["total_distance"], lns_distance=bm["total_distance"],
                             distance_delta_equal_service_EV=(fm["total_distance"] - bm["total_distance"]
                                                              if equal_service and equal_fleet else ""),
                             fleet_p95_seconds=fm["p95_planning_time"],
                             fleet_max_seconds=fm["maximum_planning_time"],
                             fleet_overrun_events=overrun_count(fm),
                             lns_p95_seconds=bm["p95_planning_time"],
                             lns_max_seconds=bm["maximum_planning_time"],
                             lns_overrun_events=overrun_count(bm),
                             fleet_mcts_iterations=fm["fleet_mcts_iterations"],
                             fleet_mcts_nodes=fm["fleet_mcts_nodes_expanded"],
                             fleet_mean_full_coverage_flex_risk=fleet_risk(fleet, "flexibility_risk"),
                             fleet_mean_full_coverage_operational_cost=fleet_risk(fleet, "operational_cost")))

    static_rows = [dict(instance=record["identity"]["instance"],
                        served=record["metrics"]["customers_served"],
                        EV=record["metrics"]["vehicles_activated"],
                        p95_seconds=record["metrics"]["p95_planning_time"],
                        max_seconds=record["metrics"]["maximum_planning_time"],
                        overrun_events=overrun_count(record["metrics"]),
                        audit="pass") for _, record in static]
    write_csv(FINAL / "summaries" / "static_summary.csv", static_rows)
    write_csv(FINAL / "summaries" / "development_pairs.csv", rows)
    write_csv(FINAL / "tables" / "development_pairs.csv", rows)
    write_csv(FINAL / "tables" / "static_validation.csv", static_rows)
    tex = [r"\begin{tabular}{lrrrr}", r"\hline",
           r"Instance & Seed & Fleet served & Rolling-LNS served & Difference \\", r"\hline"]
    tex.extend(f"{row['instance'].replace('_', r'\_')} & {row['scenario_seed']} & "
               f"{row['fleet_served']} & {row['lns_served']} & {row['service_delta']} \\\\"
               for row in rows)
    tex.extend([r"\hline", r"\end{tabular}"])
    (FINAL / "tables" / "development_service.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")

    service = [row["service_delta"] for row in rows]
    fleet_runs = [record for _, record in development if record["identity"]["algorithm"] == FLEET]
    baseline_runs = [record for _, record in development if record["identity"]["algorithm"] == BASELINE]
    family = {}
    for name in ("C1", "C2", "R1", "R2", "RC1", "RC2"):
        subset = [row for row in rows if row["family"] == name]
        family[name] = dict(fleet_served=sum(row["fleet_served"] for row in subset),
                            lns_served=sum(row["lns_served"] for row in subset),
                            wins=sum(row["service_delta"] > 0 for row in subset),
                            ties=sum(row["service_delta"] == 0 for row in subset),
                            losses=sum(row["service_delta"] < 0 for row in subset))
    equal_service_rows = [row for row in rows if row["EV_delta_equal_service"] != ""]
    equal_distance_rows = [row for row in rows if row["distance_delta_equal_service_EV"] != ""]
    latency = {}
    for name, records in (("fleet", fleet_runs), ("rolling_lns", baseline_runs)):
        latency[name] = dict(max_run_p95_seconds=max(r["metrics"]["p95_planning_time"] for r in records),
                             maximum_event_seconds=max(r["metrics"]["maximum_planning_time"] for r in records),
                             overrun_events=sum(overrun_count(r["metrics"]) for r in records),
                             decision_epochs=sum(r["metrics"]["decision_epochs"] for r in records))
    gate = dict(aggregate_unserved_no_worse=sum(row["fleet_served"] for row in rows) >=
                sum(row["lns_served"] for row in rows),
                wins_at_least_losses=sum(value > 0 for value in service) >= sum(value < 0 for value in service),
                multi_family_behavior=sum(any(row["service_delta"] >= 0 for row in rows
                                              if row["family"] in families)
                                          for families in (("C1", "C2"), ("R1", "R2"),
                                                           ("RC1", "RC2"))) >= 2,
                no_severe_fleet_collapse=min(row["fleet_served"] for row in rows) > 81,
                all_audits_pass=True,
                latency_within_five_seconds=all(row["fleet_max_seconds"] <= 5 and row["lns_max_seconds"] <= 5
                                                for row in rows))
    gate["passed"] = all(gate.values())
    summary = dict(frozen_git_commit=FROZEN_COMMIT,
                   source_sha256=development[0][1]["identity"]["source_sha256"],
                   static=dict(runs=len(static), served=sum(row["served"] for row in static_rows),
                               total_customers=600, all_audits_pass=True,
                               maximum_event_seconds=max(row["max_seconds"] for row in static_rows),
                               overrun_events=sum(row["overrun_events"] for row in static_rows)),
                   development=dict(pairs=len(rows), runs=len(development),
                                    fleet_served=sum(row["fleet_served"] for row in rows),
                                    lns_served=sum(row["lns_served"] for row in rows),
                                    total_customers_per_method=1200,
                                    wins=sum(value > 0 for value in service),
                                    ties=sum(value == 0 for value in service),
                                    losses=sum(value < 0 for value in service),
                                    fleet_min_served=min(row["fleet_served"] for row in rows),
                                    fleet_full_service_runs=sum(row["fleet_served"] == 100 for row in rows),
                                    lns_full_service_runs=sum(row["lns_served"] == 100 for row in rows),
                                    equal_service_pairs=len(equal_service_rows),
                                    EV_delta_equal_service=sum(row["EV_delta_equal_service"] for row in equal_service_rows),
                                    equal_service_equal_EV_pairs=len(equal_distance_rows),
                                    distance_delta_equal_service_EV=sum(
                                        row["distance_delta_equal_service_EV"] for row in equal_distance_rows),
                                    fleet_MCTS_iterations=sum(r["metrics"]["fleet_mcts_iterations"]
                                                              for r in fleet_runs),
                                    fleet_MCTS_nodes=sum(r["metrics"]["fleet_mcts_nodes_expanded"]
                                                         for r in fleet_runs),
                                    fleet_service_phase_seconds=sum(r["metrics"]["fleet_mcts_service_seconds"]
                                                                    for r in fleet_runs),
                                    fleet_full_phase_seconds=sum(r["metrics"]["fleet_mcts_full_seconds"]
                                                                 for r in fleet_runs),
                                    fleet_final_validation_seconds=sum(
                                        r["metrics"]["final_validation_seconds_total"] for r in fleet_runs),
                                    fleet_deadline_fallbacks=sum(r["metrics"]["deadline_fallback_count"]
                                                                 for r in fleet_runs),
                                    mean_full_coverage_flex_risk=mean_defined(
                                        row["fleet_mean_full_coverage_flex_risk"] for row in rows),
                                    mean_full_coverage_operational_cost=mean_defined(
                                        row["fleet_mean_full_coverage_operational_cost"] for row in rows),
                                    family=family, latency=latency), gate=gate,
                   holdout=dict(status="not_run", reason="Development gate failed"))
    (FINAL / "summaries" / "development_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    manifest = []
    for stage, records in (("static", static), ("development", development)):
        for path, record in records:
            manifest.append(dict(stage=stage, path=path.relative_to(ROOT).as_posix(),
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                 run_id=record["identity"]["run_id"],
                                 scenario_hash=record["identity"]["scenario_hash"],
                                 source_sha256=record["identity"]["source_sha256"],
                                 git_commit=record["identity"]["git_commit"], audit="pass"))
    (FINAL / "summaries" / "raw_sha256_manifest.json").write_text(
        json.dumps(dict(frozen_git_commit=FROZEN_COMMIT, records=manifest), indent=2) + "\n",
        encoding="utf-8")

    plot_rows = [dict(pair=f"{row['instance']} s{row['scenario_seed']}",
                      service_delta=row["service_delta"]) for row in rows]
    write_csv(FINAL / "figures" / "service_delta_source.csv", plot_rows)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    colors = ["#0d8068" if row["service_delta"] >= 0 else "#c44536" for row in plot_rows]
    ax.bar(range(len(rows)), service, color=colors)
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.set_xticks(range(len(rows)), [row["pair"] for row in plot_rows], rotation=55, ha="right")
    ax.set_ylabel("Fleet minus Rolling-LNS customers served")
    ax.set_title("Development service difference by matched scenario")
    fig.tight_layout()
    fig.savefig(FINAL / "figures" / "service_delta_by_pair.png", dpi=180)
    plt.close(fig)

    family_rows = [dict(family=name, fleet_served=values["fleet_served"],
                        lns_served=values["lns_served"]) for name, values in family.items()]
    write_csv(FINAL / "figures" / "service_by_family_source.csv", family_rows)
    fig, ax = plt.subplots(figsize=(8, 4))
    positions = range(len(family_rows))
    ax.bar([p - 0.2 for p in positions], [row["fleet_served"] for row in family_rows],
           width=0.4, color="#0d8068", label="Fleet MPC-MCTS")
    ax.bar([p + 0.2 for p in positions], [row["lns_served"] for row in family_rows],
           width=0.4, color="#c44536", label="Rolling-LNS")
    ax.set_xticks(list(positions), [row["family"] for row in family_rows])
    ax.set_ylim(0, 205)
    ax.set_ylabel("Customers served across two seeds (of 200)")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2)
    fig.tight_layout()
    fig.savefig(FINAL / "figures" / "service_by_family.png", dpi=180)
    plt.close(fig)
    return summary


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
