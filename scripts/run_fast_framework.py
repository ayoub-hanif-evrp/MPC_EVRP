"""Resumable, paired, strictly bounded development study; never opens a holdout."""

import argparse
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys

from evrp.experiments import load_config, simulation_config
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.performance_budget import HardBudget, admit
from scripts.fast_framework_worker import OUTPUT, options
from scripts.run_desaulniers_campaign import CONFIG as BASE_CONFIG, options as baseline_options

CONFIG = ROOT / "configs/fast_framework_v1.yaml"
PREVIOUS = ROOT / "results/desaulniers/performance_engineering_v1"
ARCHIVE = ROOT / "results/desaulniers/targeted_service_v1/development/protocol.json"
HISTORICAL = ROOT / "results/desaulniers/development_campaign/manifest.json"


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__),
        ROOT / "scripts/fast_framework_worker.py", ROOT / "scripts/report_fast_framework.py",
        ROOT / "scripts/performance_budget.py", ROOT / "scripts/performance_engineering_worker.py",
        ROOT / "scripts/run_desaulniers_campaign.py", CONFIG, BASE_CONFIG]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths})


def _archived_input(rows, case, kind, key):
    row = next(r for r in rows if r["kind"] == kind and r["identifier"] == key and r["instance"] == case)
    path = ROOT / row["artifact"]
    if sha256(path.read_bytes()).hexdigest() != row["sha256"]:
        raise ValueError("Archived development input drift")
    return dict(path=row["artifact"], sha256=row["sha256"])


def freeze():
    config = load_config(CONFIG)
    if config["maximum_total_seconds"] != 7200 or not config["no_automatic_holdout"]:
        raise ValueError("This study cannot exceed two hours or open a holdout")
    path = OUTPUT / "protocol.json"
    if path.exists():
        protocol = load_json(path)
        if protocol["source_sha256"] != source_hash() or protocol["config"] != config:
            raise ValueError("Frozen source or protocol drift")
        return protocol
    scientific_paths = ["evrp", "configs/fast_framework_v1.yaml", "scripts/run_fast_framework.py",
                        "scripts/fast_framework_worker.py", "scripts/report_fast_framework.py"]
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *scientific_paths],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout
    if dirty.strip():
        raise ValueError("Commit scientific implementation before freezing development protocol")
    previous = load_json(PREVIOUS / "protocol.json")
    old_manifest = load_json(PREVIOUS / "manifest.json")
    archive = load_json(ARCHIVE)["scientific"]
    history = load_json(HISTORICAL)["records"]
    cases = list(previous["cases"])
    # Prespecified additional development parents, selected by family and smallest size only.
    for name in ("r201_21_25", "rc101_21_25"):
        old = next(r for r in archive["cases"] if r["case"] == [name, .25, 0])
        cases.append(dict(case=old["case"], instance_sha256=old["instance_sha256"],
                          scenario_id=old["scenario_id"], reference_id=old["reference_id"],
                          k_ref=old["k_ref"],
                          scenario=_archived_input(archive["inputs"], name, "scenarios", old["scenario_id"]),
                          reference=_archived_input(archive["inputs"], name, "reference_schedules", old["reference_id"]),
                          base_options=baseline_options(load_config(BASE_CONFIG), name, .25, 0, "MPC_COMPLETION")))
    blocks = []
    for i in config["cases"]:
        blocks.append(dict(stage="micro", id=f"micro_{i}", jobs=[dict(
            id=f"micro_{i}_MPC_COMPLETION_enhanced", kind="micro", case_index=i,
            method="MPC_COMPLETION", variant="enhanced", upper_seconds=45)]))
    for i in range(len(cases)):
        for j, method in enumerate(config["methods"]):
            if i < 3:
                evidence = next(r["execution"]["elapsed_seconds"] for r in old_manifest["records"]
                                if r["kind"] == "pilot" and r["case_index"] == i and
                                r["method"] == method and r["variant"] == "original")
            else:
                name, dod, seed = cases[i]["case"]
                row = next(r for r in history if r["instance"] == name and
                           r["dynamicity"] == dod and r["seed"] == seed and r["method"] == method)
                raw = ROOT / row["raw"]
                if sha256(raw.read_bytes()).hexdigest() != row["raw_sha256"]:
                    raise ValueError("Historical admission evidence drift")
                evidence = load_json(raw)["metrics"]["worker_wall_seconds"]
            upper = max(45, 2 * evidence + 20)
            stage = "pilot" if i < 3 else "confirmation"
            variants = config["variants"] if (i + j) % 2 == 0 else list(reversed(config["variants"]))
            blocks.append(dict(stage=stage, id=f"{stage}_{i}_{method}", jobs=[dict(
                id=f"pilot_{i}_{method}_{v}", kind="pilot", case_index=i,
                method=method, variant=v, upper_seconds=upper) for v in variants]))
    estimate = sum(j["upper_seconds"] for b in blocks for j in b["jobs"]) + config["report_reserve_seconds"]
    if estimate > 7200:
        save_json(OUTPUT / "admission_refused.json", dict(upper_seconds=estimate, allowance_seconds=7200))
        raise ValueError("Preflight upper bounds exceed authorized compute")
    protocol = dict(config=config, cases=cases, common=previous["config"]["common"],
                    blocks=blocks, source_sha256=source_hash(),
                    source_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                 capture_output=True, text=True, check=True).stdout.strip(),
                    estimated_upper_seconds_including_report=estimate,
                    notes="Three seen pilot cases; two preselected additional development parents. "
                          "Not a final holdout. Shared machine; sequential fresh process; one native thread. "
                          "All methods receive identical shared evaluator, stopping rule, and guard. "
                          "MCTS-only skip-blocked correction is separately identified.")
    from dataclasses import asdict
    for i in range(len(cases)):
        for method in config["methods"]:
            a = asdict(simulation_config(options(protocol, i, method, "original")))
            b = asdict(simulation_config(options(protocol, i, method, "enhanced")))
            differences = {k for k in a if a[k] != b[k]}
            if differences - {"proposal_cache_policy", "computation_policy", "first_action_policy", "mcts_rollout_policy"}:
                raise ValueError("Enhanced variant changes frozen scientific parameters")
            if a["total_planning_time_limit"] != 5 or b["total_planning_time_limit"] != 5:
                raise ValueError("Five-second decision cap changed")
    save_json(path, protocol)
    return protocol


def verify(raw, protocol, job):
    if (raw["protocol_identifier"] != identifier(protocol) or raw["job_id"] != job["id"] or
            raw["method"] != job["method"] or raw["variant"] != job["variant"]):
        raise ValueError("Worker identity drift")
    if job["kind"] == "micro":
        x = raw["fixed_work"]
        if x["original"]["checksum"] != x["enhanced"]["checksum"] or not all(
                row["independent_replay"] for row in x.values()):
            raise ValueError("Fixed-work equivalence failed")
    else:
        result, case = raw["result"], protocol["cases"][job["case_index"]]
        from dataclasses import asdict
        expected = simulation_config(options(protocol, job["case_index"], job["method"], job["variant"]))
        if (identifier(result["effective_config"]) != identifier(asdict(expected)) or
                result["metadata"]["scenario_identifier"] != case["scenario_id"] or
                result["metadata"]["K_ref"] != case["k_ref"] or
                result["metrics"]["max_optimization_latency"] > 5 + 1e-6 or
                not all(result["metadata"]["independent_audit"].values())):
            raise ValueError("Physical, information, configuration or deadline violation")


def evidence_supports_confirmation(protocol, records):
    from statistics import mean
    deltas, original_cpu, enhanced_cpu = [], [], []
    for i in range(3):
        for method in protocol["config"]["methods"]:
            pair = [records.get(f"pilot_{i}_{method}_{v}") for v in protocol["config"]["variants"]]
            if None in pair:
                return False, "incomplete_pilot"
            raw = [load_json(ROOT / p["raw"]) for p in pair]
            a, b = (next(x for x in raw if x["variant"] == v) for v in ("original", "enhanced"))
            deltas.append((method, i, b["result"]["metrics"]["customers_served"] -
                           a["result"]["metrics"]["customers_served"]))
            original_cpu.append(a["worker_cpu_seconds"])
            enhanced_cpu.append(b["worker_cpu_seconds"])
    if any(delta < 0 for _, _, delta in deltas):
        return False, "pilot_service_regression"
    if sum(enhanced_cpu) > .9 * sum(original_cpu) and not any(delta > 0 for _, _, delta in deltas):
        return False, "no_credible_speed_or_service_gain"
    return True, "pilot_noninferior_with_gain"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    protocol = freeze()
    if args.freeze:
        return print(f"Frozen {sum(len(b['jobs']) for b in protocol['blocks'])} jobs; "
                     f"upper bound {protocol['estimated_upper_seconds_including_report']:.1f}/7200 seconds")
    budget = HardBudget(OUTPUT, 7200)
    manifest_path = OUTPUT / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else dict(
        protocol_identifier=identifier(protocol), records=[], status="partial")
    if manifest["protocol_identifier"] != identifier(protocol):
        raise ValueError("Manifest/protocol mismatch")
    records = {r["id"]: r for r in manifest["records"]}
    if len(records) != len(manifest["records"]):
        raise ValueError("Duplicate manifest record")
    env = dict(os.environ)
    env.update({k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    status = "complete"
    for block in protocol["blocks"]:
        if block["stage"] == "confirmation":
            approved, reason = evidence_supports_confirmation(protocol, records)
            if not approved:
                status = "confirmation_not_promoted_" + reason
                break
        if block["stage"] == "pilot" and not all(f"micro_{i}_MPC_COMPLETION_enhanced" in records for i in range(3)):
            raise ValueError("Pilot requires all fixed-work audits")
        pending = [j for j in block["jobs"] if j["id"] not in records]
        if pending and not admit(budget.remaining(), sum(j["upper_seconds"] for j in pending),
                                 protocol["config"]["report_reserve_seconds"]):
            status = "budget_admission_pause"
            break
        for job in block["jobs"]:
            path = OUTPUT / "raw" / f"{job['id']}.json.gz"
            if job["id"] in records:
                if sha256(path.read_bytes()).hexdigest() != records[job["id"]]["sha256"]:
                    raise ValueError("Saved raw changed")
                verify(load_json(path), protocol, job)
                continue
            if path.exists():
                raise ValueError("Unmanifested raw evidence: no automatic rerun")
            command = [sys.executable, "-u", "-m", "scripts.fast_framework_worker", job["kind"],
                       str(job["case_index"]), job["method"], job["variant"]]
            execution = budget.execute(job["id"], command, job["upper_seconds"], env=env,
                                       reserve=protocol["config"]["report_reserve_seconds"])
            if execution is None or execution["status"] != "complete":
                status = "worker_incomplete_preserved"
                break
            raw = load_json(path)
            verify(raw, protocol, job)
            records[job["id"]] = dict(id=job["id"], kind=job["kind"], case_index=job["case_index"],
                                      method=job["method"], variant=job["variant"],
                                      raw=path.relative_to(ROOT).as_posix(),
                                      sha256=sha256(path.read_bytes()).hexdigest(), execution=execution)
            manifest.update(records=list(records.values()), status="partial")
            save_json(manifest_path, manifest)
            print(f"{len(records)}/{sum(len(b['jobs']) for b in protocol['blocks'])} "
                  f"{job['id']} {execution['elapsed_seconds']:.2f}s", flush=True)
        if status == "worker_incomplete_preserved":
            break
    manifest.update(records=list(records.values()), status=status)
    save_json(manifest_path, manifest)
    budget.flush()
    report_id = f"report_{len(records)}"
    result = budget.execute(report_id, [sys.executable, "-u", "-m", "scripts.report_fast_framework"],
                            protocol["config"]["report_reserve_seconds"], env=env, reserve=0)
    if result is None or result["status"] != "complete":
        print("Report worker did not finish; evidence is preserved", flush=True)
    print(f"Study {status}; charged {budget.data['charged_seconds']:.2f}/7200 s", flush=True)


if __name__ == "__main__":
    lock = writable_path(OUTPUT / "execution.lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    try:
        main()
    finally:
        lock.unlink()
