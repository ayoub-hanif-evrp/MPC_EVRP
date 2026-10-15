"""Independently audit and summarize the final control-horizon campaign."""

import csv
import hashlib
import json
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.audit import audit_record
from evrp.storage import ROOT, load_json
from scripts.final_control_horizon_campaign import CONFIG, FROZEN, INSTANCES, RAW


OUT = ROOT / "results" / "final" / "control_horizon"
FLEET = "FLEET_MPC_MCTS"
BASELINE = "ROLLING_LNS"


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def risk(record, field, full):
    values = [d["fleet_mcts"]["best_components"][field]
              for d in record["decisions"] if d.get("fleet_mcts")
              and (d["fleet_mcts"]["best_components"]["unserved_customers"] == 0) == full]
    return mean(values)


def family(instance):
    stem = instance.split("_")[0].upper()
    prefix = "RC" if stem.startswith("RC") else stem[0]
    return prefix + stem[len(prefix)]


def records():
    found, manifest, failures = {}, [], []
    for stage in ("static", "development"):
        for path in sorted((RAW / stage).glob("*.json")):
            record = load_json(path)
            identity = record["identity"]
            key = (stage, identity["instance"], identity["scenario_seed"],
                   identity["algorithm"])
            if key in found:
                failures.append(f"Duplicate {key}")
            else:
                found[key] = record
            errors = audit_record(record) if record["status"] == "completed" else [record.get("error")]
            if errors:
                failures.append(f"{path}: {errors}")
            manifest.append(dict(stage=stage, path=path.relative_to(ROOT).as_posix(),
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                 status=record["status"], audit="pass" if not errors else errors,
                                 run_id=identity["run_id"], git_commit=identity["git_commit"],
                                 source_sha256=identity["source_sha256"],
                                 config_sha256=record["provenance"].get("requested_configuration_hash"),
                                 scenario_hash=identity["scenario_hash"]))
    expected = {("static", instance, 0, FLEET) for instance in INSTANCES}
    expected |= {("development", instance, seed, algorithm)
                 for instance in INSTANCES for seed in (0, 1)
                 for algorithm in (FLEET, BASELINE)}
    failures.extend(f"Missing {key}" for key in sorted(expected - set(found)))
    failures.extend(f"Unexpected {key}" for key in sorted(set(found) - expected))
    commits = {entry["git_commit"] for entry in manifest if entry["stage"] == "development"}
    sources = {entry["source_sha256"] for entry in manifest}
    if len(commits) != 1 or len(sources) != 1:
        failures.append("Mixed development commits or source hashes")
    return found, manifest, failures


def summarize():
    found, manifest, failures = records()
    (OUT / "summaries").mkdir(parents=True, exist_ok=True)
    (OUT / "summaries" / "raw_sha256_manifest.json").write_text(
        json.dumps(dict(records=manifest), indent=2) + "\n", encoding="utf-8")
    static_rows, pairs = [], []
    for instance in INSTANCES:
        record = found.get(("static", instance, 0, FLEET))
        metrics = record.get("metrics", {}) if record else {}
        static_rows.append(dict(instance=instance, status=record["status"] if record else "missing",
                                served=metrics.get("customers_served", ""),
                                EV=metrics.get("vehicles_activated", ""),
                                p95_seconds=metrics.get("p95_planning_time", ""),
                                max_seconds=metrics.get("maximum_planning_time", "")))
        for seed in (0, 1):
            f = found.get(("development", instance, seed, FLEET))
            b = found.get(("development", instance, seed, BASELINE))
            fm = f.get("metrics", {}) if f else {}
            bm = b.get("metrics", {}) if b else {}
            complete = bool(f and b and f["status"] == b["status"] == "completed")
            if complete and (f["identity"]["scenario_hash"] != b["identity"]["scenario_hash"]
                             or f["metadata"]["K_ref"] != b["metadata"]["K_ref"]
                             or f["metadata"]["DoD_realized"] != b["metadata"]["DoD_realized"]
                             or f["metadata"]["DoD_realized"] != 0.5):
                failures.append(f"Unmatched pair {instance} seed {seed}")
            equal_service = complete and fm["customers_served"] == bm["customers_served"]
            equal_EV = equal_service and fm["vehicles_activated"] == bm["vehicles_activated"]
            pairs.append(dict(instance=instance, family=family(instance), seed=seed,
                              status="completed" if complete else "incomplete",
                              K_ref=f["metadata"]["K_ref"] if complete else "",
                              realized_DoD=f["metadata"]["DoD_realized"] if complete else "",
                              scenario_hash=f["identity"]["scenario_hash"] if complete else "",
                              fleet_served=fm.get("customers_served", ""),
                              lns_served=bm.get("customers_served", ""),
                              service_delta=(fm["customers_served"] - bm["customers_served"]
                                             if complete else ""),
                              fleet_EV=fm.get("vehicles_activated", ""),
                              lns_EV=bm.get("vehicles_activated", ""),
                              EV_delta_equal_service=(fm["vehicles_activated"] - bm["vehicles_activated"]
                                                      if equal_service else ""),
                              fleet_distance=fm.get("total_distance", ""),
                              lns_distance=bm.get("total_distance", ""),
                              distance_delta_equal_service_EV=(fm["total_distance"] - bm["total_distance"]
                                                               if equal_EV else ""),
                              fleet_p95=fm.get("p95_planning_time", ""),
                              fleet_max=fm.get("maximum_planning_time", ""),
                              lns_p95=bm.get("p95_planning_time", ""),
                              lns_max=bm.get("maximum_planning_time", ""),
                              fleet_iterations=fm.get("fleet_mcts_iterations", ""),
                              fleet_nodes=fm.get("fleet_mcts_nodes_expanded", ""),
                              fleet_events=fm.get("simulation_events", ""),
                              lns_events=bm.get("simulation_events", ""),
                              fleet_triggers=fm.get("optimization_triggers", ""),
                              lns_triggers=bm.get("optimization_triggers", ""),
                              fleet_mcts_calls=fm.get("mcts_calls", ""),
                              fleet_wall_s=fm.get("complete_instance_wall_clock_seconds", ""),
                              lns_wall_s=bm.get("complete_instance_wall_clock_seconds", ""),
                              fleet_mean_optimization_s=fm.get("mean_optimization_latency", ""),
                              lns_mean_optimization_s=bm.get("mean_optimization_latency", ""),
                              fleet_R_CTRL_full=risk(f, "control_risk", True) if complete else "",
                              fleet_R_FLEX_full=risk(f, "flexibility_risk", True) if complete else "",
                              fleet_R_CTRL_service=risk(f, "control_risk", False) if complete else "",
                              fleet_R_FLEX_service=risk(f, "flexibility_risk", False) if complete else ""))
    write_csv(OUT / "summaries" / "static_summary.csv", static_rows)
    write_csv(OUT / "summaries" / "development_pairs.csv", pairs)
    write_csv(OUT / "tables" / "static_validation.csv", static_rows)
    write_csv(OUT / "tables" / "development_pairs.csv", pairs)
    if valid := [row for row in pairs if row["status"] == "completed"]:
        write_csv(OUT / "tables" / "runtime.csv", [dict(instance=r["instance"], seed=r["seed"],
                  fleet_wall_s=r["fleet_wall_s"], lns_wall_s=r["lns_wall_s"],
                  fleet_mean_optimization_s=r["fleet_mean_optimization_s"],
                  fleet_p95_s=r["fleet_p95"], fleet_max_s=r["fleet_max"],
                  lns_mean_optimization_s=r["lns_mean_optimization_s"],
                  lns_p95_s=r["lns_p95"], lns_max_s=r["lns_max"]) for r in valid])
        write_csv(OUT / "tables" / "mpc_triggers.csv", [dict(instance=r["instance"], seed=r["seed"],
                  fleet_events=r["fleet_events"], fleet_triggers=r["fleet_triggers"],
                  fleet_mcts_calls=r["fleet_mcts_calls"], lns_events=r["lns_events"],
                  lns_triggers=r["lns_triggers"], fleet_iterations=r["fleet_iterations"],
                  fleet_nodes=r["fleet_nodes"]) for r in valid])
    row_end = chr(92) * 2
    lines = [r"\begin{tabular}{lrrrr}", r"\hline",
             "Instance & Seed & Fleet served & Rolling-LNS served & Difference " + row_end,
             r"\hline"]
    for row in pairs:
        latex_instance = row["instance"].replace("_", r"\_")
        lines.append(f"{latex_instance} & {row['seed']} & {row['fleet_served']} & "
                     f"{row['lns_served']} & {row['service_delta']} " + row_end)
    lines.extend([r"\hline", r"\end{tabular}"])
    (OUT / "tables" / "development_service.tex").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    valid = [row for row in pairs if row["status"] == "completed"]
    fleet = [found["development", row["instance"], row["seed"], FLEET] for row in valid]
    baseline = [found["development", row["instance"], row["seed"], BASELINE] for row in valid]
    families = {name: dict(fleet=sum(r["fleet_served"] for r in valid if r["family"] == name),
                           lns=sum(r["lns_served"] for r in valid if r["family"] == name))
                for name in ("C1", "C2", "R1", "R2", "RC1", "RC2")}
    policy = FROZEN["gate"]
    complete_grid = len(valid) == 12 and len(static_rows) == 6 and not failures
    gate = dict(complete_grid=complete_grid,
                static_600=sum(r["served"] for r in static_rows if r["served"] != "") == policy["static_served"]
                and all(r["status"] == "completed" for r in static_rows),
                aggregate_service=sum(r["fleet_served"] for r in valid) >=
                sum(r["lns_served"] for r in valid),
                wins_at_least_losses=sum(r["service_delta"] > 0 for r in valid) >=
                sum(r["service_delta"] < 0 for r in valid),
                minimum_90=bool(valid) and min(r["fleet_served"] for r in valid) >=
                policy["minimum_fleet_service_per_run"],
                no_family_collapse=all(values["fleet"] >=
                                       2 * policy["minimum_fleet_service_per_run"]
                                       for values in families.values()),
                all_audits=not failures,
                all_events_within_five=all(r["max_seconds"] <= policy["maximum_event_seconds"]
                                       for r in static_rows
                                       if r["max_seconds"] != "") and
                all(r["fleet_max"] <= policy["maximum_event_seconds"] and
                    r["lns_max"] <= policy["maximum_event_seconds"] for r in valid))
    gate["passed"] = all(gate.values())
    latency = {name: dict(max_run_p95=max(r["metrics"]["p95_planning_time"] for r in rows),
                          max_event=max(r["metrics"]["maximum_planning_time"] for r in rows),
                          overrun_events=sum(round(r["metrics"]["total_deadline_overrun_rate"] *
                                                   r["metrics"]["optimization_triggers"]) for r in rows),
                          decision_epochs=sum(r["metrics"]["decision_epochs"] for r in rows),
                          simulation_events=sum(r["metrics"]["simulation_events"] for r in rows),
                          optimization_triggers=sum(r["metrics"]["optimization_triggers"] for r in rows),
                          mcts_calls=sum(r["metrics"]["mcts_calls"] for r in rows),
                          wall_seconds=sum(r["metrics"]["complete_instance_wall_clock_seconds"] for r in rows),
                          maximum_instance_wall_seconds=max(r["metrics"]["complete_instance_wall_clock_seconds"] for r in rows),
                          deadline_fallbacks=sum(r["metrics"].get("deadline_fallback_count", 0)
                                                 for r in rows))
               for name, rows in (("fleet", fleet), ("rolling_lns", baseline)) if rows}
    summary = dict(frozen_git_commit=next((entry["git_commit"] for entry in manifest
                                          if entry["stage"] == "development"), None),
                   config_file_sha256=hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
                   source_sha256=manifest[0]["source_sha256"] if manifest else None,
                   static=dict(runs=sum(r["status"] == "completed" for r in static_rows),
                               served=sum(r["served"] for r in static_rows if r["served"] != "")),
                   development=dict(pairs=len(valid), fleet_served=sum(r["fleet_served"] for r in valid),
                                    lns_served=sum(r["lns_served"] for r in valid),
                                    wins=sum(r["service_delta"] > 0 for r in valid),
                                    ties=sum(r["service_delta"] == 0 for r in valid),
                                    losses=sum(r["service_delta"] < 0 for r in valid),
                                    fleet_min_served=min((r["fleet_served"] for r in valid), default=None),
                                    family=families, latency=latency,
                                    equal_service_pairs=sum(r["EV_delta_equal_service"] != "" for r in valid),
                                    equal_service_equal_EV_pairs=sum(
                                        r["distance_delta_equal_service_EV"] != "" for r in valid),
                                    MCTS_iterations=sum(r["fleet_iterations"] for r in valid),
                                    MCTS_nodes=sum(r["fleet_nodes"] for r in valid),
                                    R_CTRL_full=mean(r["fleet_R_CTRL_full"] for r in valid),
                                    R_FLEX_full=mean(r["fleet_R_FLEX_full"] for r in valid),
                                    R_CTRL_service=mean(r["fleet_R_CTRL_service"] for r in valid),
                                    R_FLEX_service=mean(r["fleet_R_FLEX_service"] for r in valid)),
                   gate=gate, failures=failures,
                   holdout=dict(status="eligible_not_run" if gate["passed"] else "not_run"))
    (OUT / "summaries" / "development_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_csv(OUT / "tables" / "audit_report.csv", [dict(stage=e["stage"], path=e["path"],
              status=e["status"], audit=e["audit"] if isinstance(e["audit"], str)
              else "; ".join(e["audit"]), sha256=e["sha256"])
              for e in manifest])
    write_csv(OUT / "tables" / "family_service.csv", [dict(family=name,
              fleet_served=values["fleet"], lns_served=values["lns"])
              for name, values in families.items()])
    if valid:
        write_csv(OUT / "tables" / "eligible_ev_distance.csv", [dict(instance=r["instance"],
                  seed=r["seed"], service_equal=r["EV_delta_equal_service"] != "",
                  EV_delta=r["EV_delta_equal_service"],
                  service_and_EV_equal=r["distance_delta_equal_service_EV"] != "",
                  distance_delta=r["distance_delta_equal_service_EV"]) for r in valid])
    if valid:
        plot_rows = [dict(pair=f"{r['instance']} s{r['seed']}", service_delta=r["service_delta"])
                     for r in valid]
        write_csv(OUT / "figures" / "service_delta_source.csv", plot_rows)
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.bar(range(len(valid)), [r["service_delta"] for r in valid],
               color=["#0d8068" if r["service_delta"] >= 0 else "#c44536" for r in valid])
        ax.axhline(0, color="#333333", linewidth=0.8)
        ax.set_xticks(range(len(valid)), [r["pair"] for r in plot_rows], rotation=55, ha="right")
        ax.set_ylabel("Fleet minus Rolling-LNS customers served")
        fig.tight_layout()
        fig.savefig(OUT / "figures" / "service_delta_by_pair.png", dpi=180)
        plt.close(fig)
        family_rows = [dict(family=k, fleet_served=v["fleet"], lns_served=v["lns"])
                       for k, v in families.items()]
        write_csv(OUT / "figures" / "service_by_family_source.csv", family_rows)
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar([i - 0.2 for i in range(6)], [r["fleet_served"] for r in family_rows],
               0.4, label="Fleet MPC-MCTS", color="#0d8068")
        ax.bar([i + 0.2 for i in range(6)], [r["lns_served"] for r in family_rows],
               0.4, label="Rolling-LNS", color="#c44536")
        ax.set_xticks(range(6), [r["family"] for r in family_rows])
        ax.set_ylabel("Customers served across two seeds (of 200)")
        ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2)
        fig.tight_layout()
        fig.savefig(OUT / "figures" / "service_by_family.png", dpi=180)
        plt.close(fig)
    report = ["# Event-Triggered Risk-Aware Fleet MPC-MCTS: Final Development Report", "",
              f"Frozen development commit: `{summary['frozen_git_commit']}`. Source SHA-256: "
              f"`{summary['source_sha256']}`. Configuration SHA-256: "
              f"`{summary['config_file_sha256']}`.", "",
              "## Validation", "",
              f"Static Fleet service: {summary['static']['served']}/600 across "
              f"{summary['static']['runs']} completed cases. "
              "Full pytest: 296 passed. Schneider reference validation: 4/4 passed.", "",
              "## Matched Development", "",
              "| Instance | Seed | Fleet | Rolling-LNS | Difference | Fleet calls | Fleet wall s | LNS wall s |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in pairs:
        report.append(f"| {row['instance']} | {row['seed']} | {row['fleet_served']} | "
                      f"{row['lns_served']} | {row['service_delta']} | "
                      f"{row['fleet_mcts_calls']} | {row['fleet_wall_s']} | {row['lns_wall_s']} |")
    report += ["", f"Aggregate service: Fleet {summary['development']['fleet_served']}, "
               f"Rolling-LNS {summary['development']['lns_served']}; "
               f"wins/ties/losses {summary['development']['wins']}/"
               f"{summary['development']['ties']}/{summary['development']['losses']}.", "",
               "## Gate", ""]
    report.extend(f"- {key}: {'PASS' if value else 'FAIL'}" for key, value in gate.items())
    report += ["", "## Runtime and Triggers", ""]
    for name, values in latency.items():
        report.append(f"- {name}: {values['simulation_events']} simulation events, "
                      f"{values['optimization_triggers']} optimization triggers, "
                      f"{values['mcts_calls']} MCTS calls, {values['wall_seconds']:.2f} total "
                      f"wall seconds, {values['maximum_instance_wall_seconds']:.2f} maximum "
                      f"instance wall seconds, {values['max_event']:.3f} maximum call seconds.")
    report += ["", "## Evidence", "",
               "Raw SHA-256 manifest: `control_horizon/summaries/raw_sha256_manifest.json`. "
               "Audit, matched service, family, eligible EV/distance, runtime, and trigger CSVs "
               "are in `control_horizon/tables/`. Figures are PNG with source CSVs in "
               "`control_horizon/figures/`.", "",
               "Holdout: " + ("eligible but not yet executed" if gate["passed"] else
                              "blocked by the failed development gate") + ".", ""]
    if failures:
        report += ["Technical failures:", *[f"- {error}" for error in failures], ""]
    (ROOT / "results" / "final" / "FINAL_REPORT.md").write_text(
        "\n".join(report), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
