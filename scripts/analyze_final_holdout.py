"""Audit and analyze the complete preregistered final MPC holdout."""

from hashlib import sha256
from itertools import combinations, product
from statistics import mean

import numpy as np

from evrp.storage import ROOT, load_json, save_json
from scripts.analyze_portfolio_development import (_write_csv, family_subtype,
                                                   mechanism_record, paired_bootstrap,
                                                   plot_development, summarize_mechanisms)
from scripts.run_final_holdout import (JSON_OUTPUT, OUTPUT, VIOLATIONS,
                                       validated_protocol)
from scripts.shadow_portfolio import OUTPUT as SHADOW


def analyze():
    protocol = validated_protocol()
    manifest = load_json(OUTPUT / "manifest.json")
    methods = tuple(protocol["methods"])
    expected = 54 * len(methods)
    protocol_hash = sha256(JSON_OUTPUT.read_bytes()).hexdigest()
    if (manifest["status"] != "final_complete" or len(manifest["records"]) != expected or
            manifest["expected_records"] != expected or
            manifest["source_sha256"] != protocol["source_sha256"] or
            manifest["protocol_sha256"] != protocol_hash):
        raise ValueError("Final holdout manifest is incomplete or differs from preregistration")
    selected = {row["instance"] for row in protocol["selected"].values()}
    expected_cases = set(product(selected, protocol["dynamicity"], protocol["seeds"]))
    grouped = {}
    latencies = {method: [] for method in methods}
    controller_wall = {method: 0.0 for method in methods}
    mechanism_decisions = []
    for row in manifest["records"]:
        if (row["source_sha256"] != protocol["source_sha256"] or
                row["protocol_sha256"] != protocol_hash or
                row["controller_sha256"] != protocol["controller_sha256"] or
                row["runner_sha256"] != protocol["holdout_runner_sha256"] or
                not row["isolated_worker"] or not row["independent_audit"]):
            raise ValueError("Final row has mixed provenance or missing isolation/audit")
        key = (row["instance"], row["dynamicity"], row["scenario_seed"])
        if key not in expected_cases or row["method"] not in methods:
            raise ValueError("Final row was not preregistered")
        runs = grouped.setdefault(key, {})
        if row["method"] in runs:
            raise ValueError("Duplicate final method for scenario")
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Final raw SHA-256 mismatch")
        raw = load_json(path)
        metadata, metrics = raw["metadata"], raw["metrics"]
        if (metadata["algorithm"] != row["method"] or
                metadata["instance"] != row["instance"] or
                metadata["instance_sha256"] != row["instance_sha256"] or
                metadata["scenario_identifier"] != row["scenario_id"] or
                metadata["K_ref"] != row["k_ref"] or
                not metadata.get("isolated_worker") or
                not metadata.get("independent_audit") or
                not all(metadata["independent_audit"].values()) or
                any(metrics[name] != 0 for name in VIOLATIONS) or
                metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                metrics["customers_served"] != row["customers_served"] or
                metrics["complete_service"] != row["complete_service"] or
                metrics["vehicles_activated"] != row["vehicles_activated"] or
                not np.isclose(metrics["total_distance"], row["total_distance"])):
            raise ValueError("Final raw run failed an independent audit check")
        times = [decision["optimization_latency_seconds"] for decision in raw["decisions"]
                 if decision.get("optimization_latency_seconds") is not None]
        if (not times or not np.isclose(mean(times), row["mean_optimization_latency"], atol=1e-6)
                or not np.isclose(max(times), row["max_optimization_latency"], atol=1e-6)):
            raise ValueError("Final decision trace disagrees with timing summary")
        latencies[row["method"]].extend(times)
        controller_wall[row["method"]] += metrics["complete_instance_wall_clock_seconds"]
        for decision in raw["decisions"]:
            record = mechanism_record(row, decision)
            if record is not None:
                mechanism_decisions.append(record)
        runs[row["method"]] = row
    if set(grouped) != expected_cases or any(set(runs) != set(methods) for runs in grouped.values()):
        raise ValueError("Final study lacks 54 fully paired scenarios")
    for runs in grouped.values():
        if (len({row["scenario_id"] for row in runs.values()}) != 1 or
                len({row["instance_sha256"] for row in runs.values()}) != 1 or
                len({row["k_ref"] for row in runs.values()}) != 1):
            raise ValueError("Methods did not share identical final scenarios")

    scopes = {"overall": lambda key: True}
    for family in ("C1", "C2", "R1", "R2", "RC1", "RC2"):
        scopes[f"family_{family}"] = lambda key, family=family: family_subtype(key[0]) == family
    for dod in protocol["dynamicity"]:
        scopes[f"dod_{dod:.2f}"] = lambda key, dod=dod: key[1] == dod
    service = []
    comparisons = []
    for scope, includes in scopes.items():
        keys = [key for key in grouped if includes(key)]
        for method in methods:
            service.append(dict(scope=scope, method=method, scenarios=len(keys),
                                mean_customers_served=mean(grouped[key][method]["customers_served"]
                                                           for key in keys),
                                complete_service_rate=mean(int(grouped[key][method]["complete_service"])
                                                           for key in keys)))
        for left, right in combinations(methods, 2):
            deltas = [grouped[key][left]["customers_served"] -
                      grouped[key][right]["customers_served"] for key in keys]
            equal_service = [key for key in keys if grouped[key][left]["customers_served"] ==
                             grouped[key][right]["customers_served"]]
            ev_deltas = [grouped[key][left]["vehicles_activated"] -
                         grouped[key][right]["vehicles_activated"] for key in equal_service]
            equal_ev = [key for key in equal_service if grouped[key][left]["vehicles_activated"] ==
                        grouped[key][right]["vehicles_activated"]]
            distance_deltas = [grouped[key][left]["total_distance"] -
                               grouped[key][right]["total_distance"] for key in equal_ev]
            comparisons.append(dict(scope=scope, left=left, right=right, n=len(keys),
                                    service_diff=mean(deltas), service_ci=paired_bootstrap(deltas),
                                    service_wins=sum(value > 0 for value in deltas),
                                    service_ties=sum(value == 0 for value in deltas),
                                    service_losses=sum(value < 0 for value in deltas),
                                    complete_rate_diff=mean(
                                        int(grouped[key][left]["complete_service"]) -
                                        int(grouped[key][right]["complete_service"]) for key in keys),
                                    equal_service_n=len(equal_service),
                                    ev_diff_equal_service=mean(ev_deltas) if ev_deltas else None,
                                    equal_service_ev_n=len(equal_ev),
                                    distance_diff_equal_service_ev=(mean(distance_deltas)
                                                                    if distance_deltas else None)))
    runtime = []
    for method in methods:
        values = latencies[method]
        rows = [row for row in manifest["records"] if row["method"] == method]
        runtime.append(dict(method=method, scenarios=len(rows), decision_epochs=len(values),
                            mean_decision_seconds=mean(values),
                            median_decision_seconds=float(np.median(values)),
                            p95_decision_seconds=float(np.percentile(values, 95)),
                            max_decision_seconds=max(values),
                            fraction_decisions_within_five_seconds=mean(value <= 5.0 for value in values),
                            total_controller_wall_seconds=controller_wall[method],
                            worker_wall_seconds=sum(row["worker_wall_seconds"] for row in rows)))
    mechanism_summary, operator_summary = summarize_mechanisms(mechanism_decisions)
    shadow = load_json(SHADOW / "sbs_vbs_gate.json")
    report = dict(status="complete_final_holdout", scenarios=54, records=expected,
                  source_sha256=protocol["source_sha256"], protocol_sha256=protocol_hash,
                  service=service, comparisons=comparisons, runtime=runtime,
                  mechanism_summary=mechanism_summary, operator_summary=operator_summary,
                  shadow_summary=shadow)
    out = OUTPUT / "analysis"
    save_json(out / "final_analysis.json", report)
    architecture = [dict(method=method, embedded_search=method.replace("MPC_", ""),
                         common_constructor=True, objective="J_A/J_B",
                         budget_seconds=5.0) for method in methods]
    _write_csv(out / "table1_architecture.csv", architecture)
    _write_csv(out / "table2_overall_service.csv", [row for row in service if row["scope"] == "overall"])
    overall_comparisons = [row for row in comparisons if row["scope"] == "overall"]
    _write_csv(out / "table3_completion_comparisons.csv", [
        {**row, "service_ci": str(row["service_ci"])} for row in overall_comparisons
        if row["left"] == "MPC_COMPLETION"])
    _write_csv(out / "table4_optimizer_comparisons.csv", [
        {**row, "service_ci": str(row["service_ci"])} for row in overall_comparisons
        if row["left"] != "MPC_COMPLETION"])
    _write_csv(out / "table5_conditional_evs_distance.csv", [
        dict(scope=row["scope"], left=row["left"], right=row["right"],
             equal_service_n=row["equal_service_n"], ev_diff_equal_service=row["ev_diff_equal_service"],
             equal_service_ev_n=row["equal_service_ev_n"],
             distance_diff_equal_service_ev=row["distance_diff_equal_service_ev"])
        for row in overall_comparisons])
    _write_csv(out / "table6_runtime.csv", runtime)
    _write_csv(out / "table7_family.csv", [row for row in service if row["scope"].startswith("family_")])
    _write_csv(out / "table8_dynamicity.csv", [row for row in service if row["scope"].startswith("dod_")])
    _write_csv(out / "table9_mechanisms.csv", mechanism_summary)
    _write_csv(out / "table9_operator_detail.csv", operator_summary)
    _write_csv(out / "table10_shadow.csv", [dict(sbs=shadow["sbs"],
                                             snapshots=shadow["snapshots"],
                                             sbs_planned_customers_served=shadow[
                                                 "sbs_planned_customers_served"],
                                             vbs_planned_customers_served=shadow[
                                                 "vbs_planned_customers_served"],
                                             vbs_minus_sbs_served=shadow["vbs_minus_sbs_served"],
                                             vbs_service_win_fraction=shadow["vbs_service_win_fraction"],
                                             portfolio_gate_passed=shadow["portfolio_gate_passed"])])
    plot_development(out, methods, service, comparisons, latencies, operator_summary)
    return report


if __name__ == "__main__":
    result = analyze()
    print(result["status"], result["scenarios"], result["records"])
