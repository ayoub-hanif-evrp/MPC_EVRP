"""Read-only, independently audited report for the bounded hybrid pilot."""

from collections import Counter, defaultdict
from hashlib import sha256
from math import sqrt
from pathlib import Path
from statistics import mean

from evrp.audit import decode_result
from evrp.experiments import audit_result
from evrp.instance import energy, travel_time
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.hybrid_acceleration_worker import OUTPUT
from scripts.performance_engineering_worker import load_case
from scripts.run_hybrid_acceleration import source_hash, verify


def table(headers, rows):
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"] + [
        "| " + " | ".join(str(value) for value in row) + " |" for row in rows]


def number(value, digits=2):
    return "n/a" if value is None else f"{value:.{digits}f}"


def features(raw, instance, execution):
    result = raw["result"]
    metrics = result["metrics"]
    customers = {customer.id: customer for customer in instance.customers}
    steps = result["steps"]
    final_times = {}
    loads = Counter()
    margins = []
    total_travel = total_energy = 0.0
    for step in steps:
        before, after = step["before"], step["after"]
        final_times[after["id"]] = max(final_times.get(after["id"], 0), after["time"])
        if step["distance"]:
            a, b = instance.geometry.by_id[before["location"]["id"]], instance.geometry.by_id[after["location"]["id"]]
            total_travel += travel_time(a, b, instance.infrastructure.parameters)
            total_energy += energy(a, b, instance.infrastructure.parameters)
        if step["served"] is not None:
            loads[after["id"]] += 1
            margins.append(customers[step["served"]].due - step["service_start"])
    fleet = [loads[k] for k in sorted(final_times)]
    balance = sqrt(mean((count - mean(fleet)) ** 2 for count in fleet)) if fleet else 0.0
    decisions = result["decisions"]
    latencies = [row["optimization_latency_seconds"] for row in decisions
                 if row.get("optimization_latency_seconds") is not None]
    quality = [row.get("quality_control") or {} for row in decisions]
    recovery = [row.get("recovery_control") or {} for row in decisions]
    counts = raw["measurements"]["counts"]
    memo = Counter()
    for row in decisions:
        memo.update(row.get("proposal_memo", {}).get("incremental_counts", {}))
    return dict(served=metrics["customers_served"], total=len(instance.customers),
                complete=bool(metrics["complete_service"]),
                served_ids=tuple(sorted(customers.keys() - set(result["unserved_customers"]))),
                distance=metrics["total_distance"], travel_time=total_travel,
                completion_time=max(final_times.values(), default=0.0),
                charging_time=metrics["total_charging_time"], energy_charged=metrics["total_energy_charged"],
                travel_energy=total_energy, waiting_time=metrics["total_waiting_time"],
                activated=metrics["vehicles_activated"], workload_std=balance,
                margin_min=min(margins) if margins else None,
                margin_mean=mean(margins) if margins else None,
                cpu=execution.get("cpu_seconds"), wall=execution["elapsed_seconds"],
                optimizations=len(latencies), latency_mean=mean(latencies) if latencies else 0.0,
                latency_p95=sorted(latencies)[min(len(latencies)-1, int(.95*(len(latencies)-1)))] if latencies else 0.0,
                latency_max=max(latencies, default=0.0),
                distinct_route_decodes=counts.get("distinct_route_decodes_within_problem", 0),
                route_build_requests=counts.get("route_build_requests", 0),
                compiled_batches=counts.get("compiled_screen_batches", 0),
                compiled_proven_late=counts.get("compiled_screen_proven_late", 0),
                quality_eligible=sum(bool(row.get("eligible")) for row in quality),
                quality_accepted=sum(bool(row.get("accepted")) for row in quality),
                recovery_eligible=sum(bool(row.get("eligible")) for row in recovery),
                recovery_accepted=sum(bool(row.get("accepted")) for row in recovery),
                memo_hits=sum(row.get("proposal_memo", {}).get("hits", 0) for row in decisions),
                transition_hits=memo.get("transition_hits", 0))


def build():
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    budget = load_json(OUTPUT / "budget.json")
    benchmark_path = OUTPUT / "kernel_benchmark.json"
    benchmark = load_json(benchmark_path)
    if (protocol["source_sha256"] != source_hash() or
            protocol["benchmark_sha256"] != sha256(benchmark_path.read_bytes()).hexdigest() or
            manifest["protocol_identifier"] != identifier(protocol)):
        raise ValueError("Frozen source, benchmark, or manifest changed")
    specs = {spec["id"]: spec for block in protocol["blocks"] for spec in block["jobs"]}
    records = {}
    raw = {}
    prepared = {}
    measures = {}
    for row in manifest["records"]:
        if row["id"] in records or row["id"] not in specs:
            raise ValueError("Duplicate or unplanned worker")
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Raw worker bytes changed")
        data = load_json(path)
        spec = specs[row["id"]]
        if row["execution"]["status"] != "complete" or data["method"] != spec["method"]:
            raise ValueError("Worker did not complete as planned")
        verify(data, protocol, spec)
        if spec["kind"] == "scenario":
            index = spec["case_index"]
            if index not in prepared:
                prepared[index] = load_case(protocol, index)
            instance, scenario = prepared[index]
            meta = data["result"]["metadata"]
            case = protocol["cases"][index]
            if (meta["source_sha256"] != protocol["source_sha256"] or
                    meta["reference_schedule_identifier"] != case["reference_id"] or
                    meta["instance_sha256"] != case["instance_sha256"] or
                    meta["scenario_seed"] != case["case"][2] or
                    meta["DoD_target"] != case["case"][1]):
                raise ValueError("Scenario identity differs from frozen protocol")
            audit = audit_result(decode_result(data["result"]), instance, scenario)
            if not all(audit.values()) or audit != meta["independent_audit"]:
                raise ValueError("Independent disk replay failed")
            measures[row["id"]] = features(data, instance, row["execution"])
        records[row["id"]] = row
        raw[row["id"]] = data
    pairs = []
    detail = []
    for index, case in enumerate(protocol["cases"]):
        for method in protocol["config"]["methods"]:
            variant = "compiled_cpu_v1" if index < 3 else "quality_recovery_v1"
            keys = [f"scenario_{index}_{method}_{v}" for v in ("original", variant)]
            for key in keys:
                if key in measures:
                    detail.append((case["case"], method, key.rsplit("_", 1)[-1], raw[key]["variant"], measures[key]))
            if all(key in measures for key in keys):
                original, new = (measures[key] for key in keys)
                if raw[keys[0]]["result"]["metadata"]["scenario_identifier"] != raw[keys[1]]["result"]["metadata"]["scenario_identifier"]:
                    raise ValueError("Unpaired scenario")
                pairs.append(dict(index=index, case=case["case"], method=method, variant=variant,
                                  original=original, enhanced=new,
                                  equal_service=original["served_ids"] == new["served_ids"]))
    lines = ["# Hybrid GPU/CPU acceleration and service-first development pilot", "",
             f"Status: {manifest['status']}; {len(records)}/{len(specs)} workers; {len(pairs)}/25 full-scenario pairs.",
             f"Frozen execution commit: `{protocol['source_commit']}`. Source SHA-256: `{protocol['source_sha256']}`.",
             "These are previously generated development parents, not an independent final test. Historical paper results remain untouched.",
             "All five MPC engines retain the same original physical simulator, fixed fleet, objective, and five-second decision cap. Enhancements are opt-in.", "",
             "## Hardware and kernel screen", "",
             "RTX A2000 12GB, NVIDIA driver 596.71, CUDA runtime 13.2; Windows, Python 3.12.10; isolated CuPy 14.2.0 and Numba 0.68 environment.",
             "The GPU benchmark includes host/device transfer and synchronization; it does not beat compiled CPU at observed insertion-batch sizes. No GPU context is used in the full MPC runs: GPU processing time and workload utilization are 0/not applicable, not missing speedups.",
             "The hybrid dispatcher therefore selects compiled CPU on this workstation. The original Python path remains the fallback if Numba is absent.",
             f"Standalone benchmark: `kernel_benchmark.json` (SHA-256 `{protocol['benchmark_sha256']}`).", "",
             "## Fixed-work checks", ""]
    micro_rows = []
    for index in range(3):
        key = f"micro_{index}_MPC_COMPLETION_compiled_cpu_v1"
        if key in raw:
            variants = raw[key]["micro"]["variants"]
            micro_rows.append([protocol["cases"][index]["case"][0],
                               variants["original"]["screened_insertions"],
                               variants["compiled_cpu_v1"]["compiled_batches"],
                               variants["compiled_cpu_v1"]["proven_late"],
                               number(variants["original"]["seconds"], 5),
                               number(variants["compiled_cpu_v1"]["seconds"], 5),
                               "identical" if variants["original"]["checksum"] == variants["compiled_cpu_v1"]["checksum"] else "DIFFERENT"])
    lines += table(["Case", "Screened gaps", "Compiled batches", "Proven late", "Python s", "Compiled s", "Objective/options"], micro_rows)
    lines += ["", "## End-to-end paired results", "",
              "Stage B compares original against opt-in compiled CPU plus the existing incremental screen/cache. Stage C independently compares original against opt-in quality/recovery; it does not combine Stage B and C.",
              "Alternating pair order, fresh sequential workers, one numerical-library thread per worker. Timings are shared-machine observations.", ""]
    summary_rows = []
    for stage, index_range in (("B", range(3)), ("C", range(3, 5))):
        for method in protocol["config"]["methods"]:
            group = [row for row in pairs if row["index"] in index_range and row["method"] == method]
            if not group:
                continue
            total = sum(row["original"]["total"] for row in group)
            summary_rows.append([stage, method, len(group),
                f"{sum(r['original']['served'] for r in group)}/{total}",
                f"{sum(r['enhanced']['served'] for r in group)}/{total}",
                f"{sum(r['original']['complete'] for r in group)}/{len(group)}",
                f"{sum(r['enhanced']['complete'] for r in group)}/{len(group)}",
                number(sum(r["original"]["wall"] for r in group)),
                number(sum(r["enhanced"]["wall"] for r in group)),
                number(sum(r["original"]["cpu"] or 0 for r in group)),
                number(sum(r["enhanced"]["cpu"] or 0 for r in group)),
                sum(r["equal_service"] for r in group)])
    lines += table(["Stage", "Method", "Pairs", "Original served", "Enhanced served", "Original complete", "Enhanced complete", "Original wall s", "Enhanced wall s", "Original CPU s", "Enhanced CPU s", "Equal-service pairs"], summary_rows)
    lines += ["", "### Every paired case", ""]
    lines += table(["Stage", "Case", "DoD", "Method", "Served O/E", "Complete O/E", "Wall s O/E", "CPU s O/E", "Distance O/E (only equal-service)", "Equal served IDs"],
        [["B" if r["index"] < 3 else "C", r["case"][0], r["case"][1], r["method"],
          f"{r['original']['served']}/{r['enhanced']['served']}",
          f"{int(r['original']['complete'])}/{int(r['enhanced']['complete'])}",
          f"{number(r['original']['wall'])}/{number(r['enhanced']['wall'])}",
          f"{number(r['original']['cpu'])}/{number(r['enhanced']['cpu'])}",
          f"{number(r['original']['distance'])}/{number(r['enhanced']['distance'])}" if r["equal_service"] else "not comparable",
          "yes" if r["equal_service"] else "no"] for r in pairs])
    lines += ["", "## Full operational measurements", "",
              "Travel energy is exact physical arc energy; charged energy is separately reported. Fleet workload balance is the standard deviation of customer service counts across active/known vehicles. Completion is the latest vehicle event time.",
              "Distance, travel, energy, waiting, and charging comparisons are meaningful only when the served-customer identities match; see the paired table.", ""]
    lines += table(["Case", "Method", "Variant", "Served", "Distance", "Travel time", "Completion", "Charge time", "Charged energy", "Travel energy", "Wait time", "EVs", "Load SD", "TW margin min/mean"],
        [[case[0], method, variant, f"{f['served']}/{f['total']}", number(f["distance"]),
          number(f["travel_time"]), number(f["completion_time"]), number(f["charging_time"]),
          number(f["energy_charged"]), number(f["travel_energy"]), number(f["waiting_time"]),
          f["activated"], number(f["workload_std"]),
          f"{number(f['margin_min'])}/{number(f['margin_mean'])}"] for case, method, _, variant, f in detail])
    lines += ["", "## Computation, deadlines, and interventions", "",
              "Route decode counts are per-problem distinct keys summed across decision problems, not globally unique routes. GPU time is zero in full workers.", ""]
    lines += table(["Case", "Method", "Variant", "Wall s", "CPU s", "Optimizations", "Latency mean/p95/max s", "Route decodes", "Route builds", "Compiled batches/proven late", "Quality eligible/accepted", "Recovery eligible/accepted"],
        [[case[0], method, variant, number(f["wall"]), number(f["cpu"]), f["optimizations"],
          f"{number(f['latency_mean'],3)}/{number(f['latency_p95'],3)}/{number(f['latency_max'],3)}",
          f["distinct_route_decodes"], f["route_build_requests"],
          f"{f['compiled_batches']}/{f['compiled_proven_late']}",
          f"{f['quality_eligible']}/{f['quality_accepted']}",
          f"{f['recovery_eligible']}/{f['recovery_accepted']}"] for case, method, _, variant, f in detail])
    regressions = [r for r in pairs if r["enhanced"]["served"] < r["original"]["served"]]
    improvements = [r for r in pairs if r["enhanced"]["served"] > r["original"]["served"]]
    equal = [r for r in pairs if r["equal_service"]]
    shorter = [r for r in equal if r["enhanced"]["distance"] < r["original"]["distance"] - .01]
    lines += ["", "## Scientific interpretation", "",
              f"Across {len(pairs)} matched pairs: {len(improvements)} service gains, {len(regressions)} service losses, "
              f"{len(equal)} equal-served-set pairs, and {len(shorter)} shorter-distance results among the latter.",
              "A fixed-work compiled screen can match exact proposals yet change a deadline-limited search trajectory; end-to-end service and time, not micro speed, govern promotion.",
              "The optional quality policy uses explicit risk tolerances and physical replay. It is a separate policy, not a rewrite of the historical lexicographic objective. Its intervention counts above establish whether it actually changed decisions.",
              "Two structurally preselected Stage C development parents are too few to support a repeatable complete-service claim. No enhanced variant is promoted automatically; original remains default.",
              "Every saved full scenario was independently replayed from disk against the original physical/information auditor and passed the five-second decision maximum.",
              f"Charged compute before report worker: {budget['charged_seconds']:.2f}/7200 s; 300 s setup charge and 120 s report reserve. Consult `budget.json` for the final report charge.",
              "The stopped Reliability V2 evidence was not resumed; no new final holdout was opened.", "",
              "## Reproduction", "", "```powershell",
              ".\\.venv-accel\\Scripts\\python.exe -m pytest -q",
              ".\\.venv-accel\\Scripts\\python.exe -m scripts.run_hybrid_acceleration --freeze",
              ".\\.venv-accel\\Scripts\\python.exe -u -m scripts.run_hybrid_acceleration",
              ".\\.venv-accel\\Scripts\\python.exe -m scripts.report_hybrid_acceleration",
              "```", "",
              "Use the frozen source commit and the recorded environment. Completed raw files are hash-checked and never regenerated by the runner; failed jobs require an explicit revision, not a silent retry."]
    writable_path(OUTPUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    save_json(OUTPUT / "analysis.json", dict(status=manifest["status"], protocol_identifier=identifier(protocol),
        source_sha256=protocol["source_sha256"], records=len(records), pairs=pairs,
        independent_disk_audits=len(measures), service_gains=len(improvements),
        service_losses=len(regressions), equal_service_pairs=len(equal),
        shorter_distance_equal_service=len(shorter)))
    print(f"Audited {len(measures)} full scenarios; {len(pairs)} matched pairs", flush=True)


if __name__ == "__main__":
    build()
