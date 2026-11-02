"""Analysis of the frozen pilot, including explicitly unavailable legacy counters."""

from pathlib import Path

import numpy as np

from evrp.audit import decode_result
from evrp.experiments import audit_result
from evrp.storage import ROOT, identifier, load_json
from scripts.experiments.paths import artifact_path
from scripts.experiments import run_mpc_reliability_pilot as pilot


def summarize(raw, info, spec):
    result, metrics = raw["result"], raw["result"]["metrics"]
    served = sorted(s["served"] for s in result["steps"] if s["served"])
    if len(served) != metrics["customers_served"] or len(served) != len(set(served)):
        raise ValueError("Saved service count is inconsistent")
    charge = [s for s in result["steps"] if s["action"]["kind"] == "charge"]
    latencies = [d["optimization_latency_seconds"] for d in result["decisions"]
                 if d.get("optimization_latency_seconds") is not None]
    fallback = metrics.get("deadline_fallback_count")
    if fallback is None and result["decisions"] and all("deadline_fallback" in d for d in result["decisions"]):
        fallback = sum(bool(d["deadline_fallback"]) for d in result["decisions"])
    row = dict(id=spec["id"], instance=info["instance"], parent=info["parent"],
        case_index=spec["case_index"], method=spec["method"], served=len(served), size=info["size"],
        service_ratio=len(served) / info["size"], complete=len(served) == info["size"],
        distance=metrics["total_distance"], charging_visits=len(charge),
        charging_time=metrics["total_charging_time"], charged_energy=metrics["total_energy_charged"],
        travel_energy=sum(s["before"]["battery"] + s["energy_charged"] - s["after"]["battery"] for s in result["steps"]),
        evs=metrics["vehicles_activated"], wall=raw["worker_wall_seconds"], cpu=raw["worker_cpu_seconds"],
        max_latency=metrics["max_optimization_latency"],
        p95_latency=float(np.percentile(latencies, 95)) if latencies else 0.,
        p99_latency=float(np.percentile(latencies, 99)) if latencies else 0.,
        deadline_events=metrics["total_deadline_events"],
        optimizer_deadline_decisions=sum(bool((d.get("optimizer") or {}).get("deadline_reached")) for d in result["decisions"]),
        validated_fallbacks=fallback,
        fallback_counter_availability="recorded" if fallback is not None else "not recorded by this frozen method",
        initialization_fallbacks=metrics["optimizer_initialization_fallbacks"], audit_passed=all(raw["audit"].values()),
        physical_violations=sum(metrics.get(k, 0) for k in ("battery_violations", "capacity_violations",
             "time_window_violations", "duplicate_service_violations", "hidden_information_violations")))
    return row, served


def analyze():
    data = pilot.frozen()
    planned = data["protocol"]
    manifest = load_json(pilot.OUTPUT / "manifest.json")
    rows, sets = [], {}
    for saved in manifest["records"]:
        spec = next(j for j in planned["jobs"] if j["id"] == saved["id"])
        path = ROOT / saved["raw"]
        if pilot.digest(path) != saved["sha256"]:
            raise ValueError("Saved raw bytes changed")
        raw = load_json(path)
        pilot.verify_result(data, spec, raw)
        info, instance, reference, scenario = pilot.prepare_case(planned["cases"][spec["case_index"]]["instance"])
        if identifier(info) != identifier(planned["cases"][spec["case_index"]]):
            raise ValueError("Frozen physical/scenario inputs changed")
        checks = audit_result(decode_result(raw["result"]), instance, scenario)
        if checks != raw["audit"] or not all(checks.values()):
            raise ValueError("Independent saved-trajectory replay failed")
        row, served = summarize(raw, info, spec)
        rows.append(row)
        sets[spec["case_index"], spec["method"]] = served
    complete = manifest["status"] == "complete" and len(rows) == 10
    if complete and len({r["id"] for r in rows}) != 10:
        raise ValueError("Duplicated pilot outcomes")
    totals = {m: sum(r["served"] for r in rows if r["method"] == m) for m in pilot.METHODS}
    winners = [m for m in pilot.METHODS if totals[m] == max(totals.values())] if complete else []
    comparable = {}
    for i in range(2):
        grouped = {}
        for m in pilot.METHODS:
            if (i, m) in sets:
                grouped.setdefault(identifier(sets[i, m]), []).append(m)
        comparable[str(i)] = list(grouped.values())
    output = dict(status=manifest["status"], completed=len(rows), planned=10, records=rows,
        independent_replay_passed=all(r["audit_passed"] for r in rows),
        totals_served=totals, winners_by_customer_service=winners,
        complete_service_counts={m: sum(r["complete"] for r in rows if r["method"] == m) for m in pilot.METHODS},
        comparable_served_set_groups=comparable, protocol_identifier=data["protocol_identifier"],
        analysis_sha256=pilot.digest(Path(__file__)), budget=load_json(pilot.OUTPUT / "budget.json"),
        worker_failure_records=[p.relative_to(ROOT).as_posix() for p in (pilot.OUTPUT / "failures").glob("*.json")],
        no_population_superiority_claim=True)
    pilot.exclusive(artifact_path(pilot.STUDY, "validation", "pilot_results.json"), output)
    lines = ["# Original five-method correctness pilot", "",
        f"Status: {manifest['status']}; {len(rows)}/10 runs. Saved raw files independently replayed again.",
        "Two preselected exposed development scenarios; target DoD .75, seed7301.",
        "This pilot cannot establish population superiority.", "",
        "| Instance | Method | Served | EVs | Wall s | CPU s | Max decision s | Deadline events | Audit |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    lines.extend(f"| {r['instance']} | {r['method']} | {r['served']}/{r['size']} | {r['evs']} | "
                 f"{r['wall']:.2f} | {r['cpu']:.2f} | {r['max_latency']:.3f} | {r['deadline_events']} | pass |" for r in rows)
    lines += ["", f"Highest total service here only: {', '.join(winners) or 'incomplete panel'}.", "",
        "MCTS served 87/100 versus Completion's 89/100 on R101; this negative case is retained.", "",
        "## Operating metrics", "", "Rank operating costs only within identical served-set groups:", ""]
    lines.extend(f"- Case {i}: {groups}" for i, groups in comparable.items())
    lines += ["", "| Instance | Method | Distance | Charge time | Charge visits | Charged energy | Travel energy |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    lines.extend(f"| {r['instance']} | {r['method']} | {r['distance']:.2f} | {r['charging_time']:.2f} | "
                 f"{r['charging_visits']} | {r['charged_energy']:.2f} | {r['travel_energy']:.2f} |" for r in rows)
    lines += ["", "## Limits and reporting correction", "",
        "The original pilot runner's report attempted to read a legacy-only fallback metric.",
        "That analysis failure is preserved separately. This analysis helper reads the saved schema",
        "without changing the executed runner, protocol, raw bytes, or algorithms. Final-validation",
        "fallback counts are null when not recorded; total deadline events, optimizer-deadline",
        "decisions, initialization fallbacks, and worker failures are reported explicitly in JSON.",
        "Original ALNS/HGS/ACS retain their documented initialization-timeout edge defect.",
        "MPC_ALNS_SAFE_INIT_V1 was tested separately and not substituted into the original pilot.",
        "Cooperative timing and external machine load limit real-time claims. The full future",
        "270-run panel remains exposed and over budget; it was not launched.", ""]
    path = artifact_path(pilot.STUDY, "validation", "RESULTS.md")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))
    print(f"Independent pilot replay: {len(rows)}/10 passed; observed service leaders {winners}")


if __name__ == "__main__":
    analyze()
