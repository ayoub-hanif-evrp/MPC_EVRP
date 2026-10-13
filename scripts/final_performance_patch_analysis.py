"""Generate audited, service-first final-patch development tables."""

import csv
from collections import Counter
from hashlib import sha256
import json
from statistics import mean

from evrp.experiments import source_fingerprint
from evrp.storage import ROOT
from scripts.final_performance_patch_campaign import RAW, completed


OUT = ROOT / "results" / "final" / "performance_patch"
FLEET = "FLEET_MPC_MCTS"
LNS = "ROLLING_LNS"
NO_TREE = "FLEET_MPC_COMPLETION_ONLY"


def search_summary(record):
    calls = [decision["fleet_mcts"] for decision in record["decisions"]
             if decision.get("fleet_mcts")]
    service = sum(call["final_uncovered"] < call["root_uncovered"] for call in calls)
    objective = sum(call["best_score"] < call["seed_score"] and
                    call["final_uncovered"] == call["root_uncovered"] for call in calls)
    equal_full = [call for call in calls if call["seed_score"][0] ==
                  call["best_score"][0] == 0]
    ev_gain = sum(call["best_score"][3] < call["seed_score"][3]
                  for call in equal_full)
    distance_gain = sum(call["best_score"][3] == call["seed_score"][3] and
                        call["best_score"][5] < call["seed_score"][5]
                        for call in equal_full)
    rollouts = sum(call["rollout_count"] for call in calls)
    service_calls = [call for call in calls if call["root_uncovered"] > 0]
    screens = sum(call["screened_insertions"] for call in service_calls)
    service_decodes = sum(call["exact_decoded_options"] for call in service_calls)
    decodes = sum(call["exact_decoded_options"] for call in calls)
    hits = sum(call["screen_cache_hits"] for call in calls)
    lookups = sum(call["screen_cache_lookups"] for call in calls)
    return dict(mcts_calls=len(calls), service_gain_calls=service,
                equal_service_objective_gain_calls=objective,
                equal_full_service_ev_gain_calls=ev_gain,
                equal_full_service_equal_ev_distance_gain_calls=distance_gain,
                root_to_final_service_gain=sum(call["service_gain_over_root"] for call in calls),
                root_to_final_service_gain_mean=(mean(call["service_gain_over_root"]
                                                     for call in calls) if calls else 0),
                iterations=sum(call["iterations"] for call in calls),
                nodes=sum(call["nodes_expanded"] for call in calls),
                rollout_count=rollouts,
                mean_rollout_inserted=(sum(call["rollout_customers_completed"]
                                           for call in calls) / max(1, rollouts)),
                exact_decoder_calls=decodes, service_decoder_calls=service_decodes,
                screened_insertions=screens,
                screen_to_decode_ratio=screens / max(1, service_decodes),
                cache_hit_rate=hits / max(1, lookups),
                ejection_generated=sum(call["ejection_chains_generated"] for call in calls),
                ejection_feasible=sum(call["ejection_chains_feasible"] for call in calls),
                ejection_selected=sum(call["ejection_chains_selected"] for call in calls),
                mean_r_ctrl=(mean(call["best_components"]["control_risk"]
                                  for call in calls) if calls else 0),
                mean_r_flex=(mean(call["best_components"]["flexibility_risk"]
                                  for call in calls) if calls else 0))


def main():
    targeted = completed("targeted")
    static = completed("static")
    development = completed("development")
    if sum(record["metrics"]["customers_served"] for record in static) != 600:
        raise RuntimeError("Static gate is not 600/600")
    grouped = {}
    for record in development:
        key = (record["identity"]["instance"], record["identity"]["scenario_seed"])
        grouped.setdefault(key, {})[record["identity"]["algorithm"]] = record
    if len(grouped) != 12:
        raise RuntimeError("Expected 12 matched development scenarios")
    rows = []
    for (instance, seed), records in sorted(grouped.items()):
        if set(records) != {FLEET, LNS, NO_TREE}:
            raise RuntimeError("Incomplete algorithm triple")
        if len({record["identity"]["scenario_hash"] for record in records.values()}) != 1:
            raise RuntimeError("Unmatched scenario")
        f, l, n = (records[algorithm]["metrics"] for algorithm in (FLEET, LNS, NO_TREE))
        search = search_summary(records[FLEET])
        same_service = f["customers_served"] == l["customers_served"]
        same_ev = same_service and f["vehicles_activated"] == l["vehicles_activated"]
        rows.append(dict(instance=instance, seed=seed,
                         scenario_hash=records[FLEET]["identity"]["scenario_hash"],
                         fleet_served=f["customers_served"], lns_served=l["customers_served"],
                         completion_served=n["customers_served"],
                         fleet_minus_lns_service=f["customers_served"] - l["customers_served"],
                         fleet_minus_completion_service=(f["customers_served"] -
                                                         n["customers_served"]),
                         fleet_complete=f["complete_service"],
                         lns_complete=l["complete_service"],
                         completion_complete=n["complete_service"],
                         fleet_evs=f["vehicles_activated"], lns_evs=l["vehicles_activated"],
                         completion_evs=n["vehicles_activated"],
                         fleet_distance=f["total_distance"], lns_distance=l["total_distance"],
                         completion_distance=n["total_distance"],
                         conditional_ev_difference=(f["vehicles_activated"] - l["vehicles_activated"]
                                                    if same_service else ""),
                         conditional_distance_difference=(f["total_distance"] - l["total_distance"]
                                                          if same_ev else ""),
                         fleet_p95_latency=f["p95_optimization_latency"],
                         fleet_max_latency=f["max_optimization_latency"],
                         fleet_wall=f["complete_instance_wall_clock_seconds"],
                         lns_p95_latency=l["p95_optimization_latency"],
                         lns_max_latency=l["max_optimization_latency"],
                         lns_wall=l["complete_instance_wall_clock_seconds"],
                         completion_p95_latency=n["p95_optimization_latency"],
                         completion_max_latency=n["max_optimization_latency"],
                         completion_wall=n["complete_instance_wall_clock_seconds"],
                         **search))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "development_pairs.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    versus_lns = Counter("W" if row["fleet_minus_lns_service"] > 0 else
                         "L" if row["fleet_minus_lns_service"] < 0 else "T" for row in rows)
    versus_no_tree = Counter("W" if row["fleet_minus_completion_service"] > 0 else
                             "L" if row["fleet_minus_completion_service"] < 0 else "T" for row in rows)
    fleet_total = sum(row["fleet_served"] for row in rows)
    lns_total = sum(row["lns_served"] for row in rows)
    no_tree_total = sum(row["completion_served"] for row in rows)
    lines = ["# Final Performance Patch: Development Verdict", "",
             f"Frozen source SHA-256: `{source_fingerprint()}`; Git commit: `30e485d`.",
             "All 36 runs completed, passed independent trace audit, shared their paired",
             "scenario hashes, and stayed below five seconds per optimization call.",
             "The six-static prerequisite passed at 600/600. No holdout was run.", "",
             "## Primary Benchmark Outcomes", "",
             f"Service: Fleet MPC-MCTS **{fleet_total}/1200**, Rolling-LNS **{lns_total}/1200**, "
             f"completion-only **{no_tree_total}/1200**. Complete-instance rates: "
             f"{sum(row['fleet_complete'] for row in rows)}/12, "
             f"{sum(row['lns_complete'] for row in rows)}/12, and "
             f"{sum(row['completion_complete'] for row in rows)}/12, respectively.",
             f"Fleet vs Rolling-LNS service W/T/L: **{versus_lns['W']}/{versus_lns['T']}/{versus_lns['L']}**; "
             f"Fleet vs completion-only: **{versus_no_tree['W']}/{versus_no_tree['T']}/{versus_no_tree['L']}**.", "",
             "| Instance | Seed | Fleet | LNS | Completion | Fleet-LNS | Fleet-Completion | "
             "EVs F/L/C | Distance F/L/C | Conditional EV F-L | Conditional distance F-L |",
             "|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|"]
    for row in rows:
        ev = "/".join(str(row[key]) for key in ("fleet_evs", "lns_evs", "completion_evs"))
        distances = "/".join(f"{row[key]:.1f}" for key in (
            "fleet_distance", "lns_distance", "completion_distance"))
        conditional_ev = (str(row["conditional_ev_difference"])
                          if row["conditional_ev_difference"] != "" else "n/a")
        conditional_distance = (f"{row['conditional_distance_difference']:.1f}"
                                if row["conditional_distance_difference"] != "" else "n/a")
        lines.append(f"| {row['instance']} | {row['seed']} | {row['fleet_served']} | "
                     f"{row['lns_served']} | {row['completion_served']} | "
                     f"{row['fleet_minus_lns_service']:+d} | "
                     f"{row['fleet_minus_completion_service']:+d} | {ev} | "
                     f"{distances} | {conditional_ev} | {conditional_distance} |")
    lines.extend(["", "Raw EV and distance columns are descriptive only. The conditional EV",
                  "difference is shown only at equal service; the conditional distance",
                  "difference is shown only at equal service and equal activated EVs.", "",
                  "## Internal MPC Search Diagnostics", "",
                  "`R_CTRL` and `R_FLEX` are search guidance, not primary benchmark wins.",
                  "The root-to-final column counts additional released customers reserved",
                  "within MCTS calls, not extra physical services over the paired ablation.", "",
                  "| Instance | Seed | R_CTRL | R_FLEX | MCTS calls / service-gain calls | "
                  "Root-to-final gain | Equal-service objective / EV / distance gain calls | "
                  "Iterations / nodes | Rollouts / mean inserted | Screens / decodes | "
                  "Cache hit | p95 / max trigger s | Wall s |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in rows:
        gains = "/".join(str(row[key]) for key in (
            "equal_service_objective_gain_calls", "equal_full_service_ev_gain_calls",
            "equal_full_service_equal_ev_distance_gain_calls"))
        lines.append(f"| {row['instance']} | {row['seed']} | {row['mean_r_ctrl']:.3f} | "
                     f"{row['mean_r_flex']:.3f} | {row['mcts_calls']} / "
                     f"{row['service_gain_calls']} | {row['root_to_final_service_gain']} "
                     f"({row['root_to_final_service_gain_mean']:.2f}/call) | {gains} | "
                     f"{row['iterations']} / {row['nodes']} | {row['rollout_count']} / "
                     f"{row['mean_rollout_inserted']:.3f} | "
                     f"{row['screened_insertions']} / {row['service_decoder_calls']} "
                     f"({row['screen_to_decode_ratio']:.1f}:1) | "
                     f"{row['cache_hit_rate']:.1%} | "
                     f"{row['fleet_p95_latency']:.3f} / {row['fleet_max_latency']:.3f} | "
                     f"{row['fleet_wall']:.1f} |")
    lines.extend(["", "Across all Fleet calls, `EJECTION_CHAIN_2` generated "
                  f"{sum(row['ejection_generated'] for row in rows)} chains, found "
                  f"{sum(row['ejection_feasible'] for row in rows)} feasible chains, and "
                  f"selected {sum(row['ejection_selected'] for row in rows)} tree actions.",
                  "Screens/decodes and their ratio use service-phase MCTS calls only;",
                  "the CSV separately retains exact decoder calls over all MCTS calls.",
                  "The CSV contains per-case wall/p95/max timings for all three methods.", "",
                  "## Stop-Rule Verdict", "",
                  "**Strong development is not achieved.** Fleet MPC-MCTS improves service",
                  "over its shared-constructor completion-only ablation on multiple cases,",
                  "but serves 16 fewer customers than Rolling-LNS overall and loses service",
                  f"on {versus_lns['L']} of 12 matched scenarios. The static 600/600 success",
                  "therefore does not establish dynamic service competitiveness.",
                  "Per the absolute stop rule, no further algorithm tuning, secondary route",
                  "pool, or untouched holdout campaign is run. This is a limitation report,",
                  "not a positive final-paper performance claim. No optimality is claimed.",
                  "No figures were generated; no PDF artifacts were created.", ""])
    (OUT / "DEVELOPMENT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    manifest = dict(source_sha256=source_fingerprint(), git_commit="30e485d",
                    static_count=len(static), development_count=len(development),
                    records=[])
    for stage, records in (("targeted", targeted), ("static", static),
                           ("development", development)):
        current_names = {f"{record['identity']['instance']}_"
                         f"{record['identity']['algorithm']}_"
                         f"{record['identity']['run_id'][:20]}.json"
                         for record in records}
        for path in sorted((RAW / stage).glob("*.json")):
            if path.name not in current_names:
                continue
            manifest["records"].append(dict(path=str(path.relative_to(ROOT)).replace("\\", "/"),
                                            sha256=sha256(path.read_bytes()).hexdigest()))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                          encoding="utf-8")
    print(f"development: {fleet_total}/{lns_total}/{no_tree_total}, "
          f"Fleet-vs-LNS W/T/L={versus_lns['W']}/{versus_lns['T']}/{versus_lns['L']}, "
          "holdout=not run", flush=True)


if __name__ == "__main__":
    main()
