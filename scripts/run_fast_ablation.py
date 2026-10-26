"""Controlled 100-customer HGS/ACS component ablation; separate from frozen pilot."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter, process_time

from evrp.experiments import audit_result, simulation_config
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.fast_framework_worker import options as pilot_options
from scripts.performance_budget import HardBudget, admit
from scripts.performance_engineering_worker import load_case

OUTPUT = ROOT / "results/desaulniers/fast_framework_v1/ablation_1"
PILOT = ROOT / "results/desaulniers/fast_framework_v1/revision_1"
VARIANTS = {
    "original": {},
    "fast_only": {"proposal_cache_policy": "fast_framework_v1"},
    "adaptive_only": {"computation_policy": "adaptive_compute_v1"},
    "guard_only": {"first_action_policy": "service_guard_v1"},
    "combined": {"proposal_cache_policy": "fast_framework_v1",
                 "computation_policy": "adaptive_compute_v1",
                 "first_action_policy": "service_guard_v1"},
}
METHODS = ("MPC_HGS", "MPC_ACS")


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__),
        ROOT / "scripts/performance_budget.py", ROOT / "scripts/performance_engineering_worker.py",
        ROOT / "scripts/fast_framework_worker.py"]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths})


def options(protocol, method, variant):
    data = pilot_options(protocol["pilot_protocol"], 2, method, "original")
    data.update(VARIANTS[variant])
    return data


def freeze():
    path = OUTPUT / "protocol.json"
    if path.exists():
        protocol = load_json(path)
        if protocol["source_sha256"] != source_hash():
            raise ValueError("Frozen ablation source drift")
        return protocol
    if subprocess.run(["git", "status", "--porcelain", "--", "evrp", "scripts/run_fast_ablation.py"],
                      cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip():
        raise ValueError("Commit ablation source before freezing")
    pilot_protocol = load_json(PILOT / "protocol.json")
    pilot_budget = load_json(PILOT / "budget.json")
    if load_json(PILOT / "manifest.json")["status"] != "confirmation_not_promoted_pilot_service_regression":
        raise ValueError("Ablation only follows completed failed shared pilot gate")
    blocks = []
    for method in METHODS:
        original = load_json(PILOT / "raw" / f"pilot_2_{method}_original.json.gz")
        upper = max(45, 2 * original["worker_wall_seconds"] + 20)
        blocks.append(dict(method=method, jobs=[dict(id=f"{method}_{variant}", method=method,
                                                    variant=variant, upper_seconds=upper)
                                                 for variant in VARIANTS]))
    upper = sum(j["upper_seconds"] for block in blocks for j in block["jobs"])
    if upper + pilot_budget["charged_seconds"] + 120 > 7200:
        raise ValueError("Ablation preflight exceeds remaining two-hour development allowance")
    protocol = dict(source_sha256=source_hash(),
                    source_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                 capture_output=True, text=True, check=True).stdout.strip(),
                    pilot_protocol=pilot_protocol, prior_charge_seconds=pilot_budget["charged_seconds"],
                    upper_seconds=upper, blocks=blocks, case_index=2, fixed_python_hash_seed=0,
                    note="Controlled-seed component ablation on a seen development case, not a new holdout. "
                         "All methods preserve the original physics, controller, objective, and five-second maximum.")
    baseline = asdict(simulation_config(options(protocol, METHODS[0], "original")))
    for method in METHODS:
        for variant in VARIANTS:
            a = asdict(simulation_config(options(protocol, method, "original")))
            b = asdict(simulation_config(options(protocol, method, variant)))
            if {k for k in a if a[k] != b[k]} - {"proposal_cache_policy", "computation_policy", "first_action_policy"}:
                raise ValueError("Ablation changed common scientific parameters")
            if b["total_planning_time_limit"] != 5 or baseline["total_planning_time_limit"] != 5:
                raise ValueError("Five-second maximum changed")
    save_json(path, protocol)
    return protocol


def worker(method, variant):
    protocol = load_json(OUTPUT / "protocol.json")
    if protocol["source_sha256"] != source_hash() or method not in METHODS or variant not in VARIANTS:
        raise ValueError("Worker outside frozen ablation")
    path = OUTPUT / "raw" / f"{method}_{variant}.json.gz"
    if path.exists():
        raise ValueError("Raw evidence cannot be overwritten")
    started, cpu = perf_counter(), process_time()
    instance, scenario = load_case(protocol["pilot_protocol"], protocol["case_index"])
    config = simulation_config(options(protocol, method, variant))
    result = EventDrivenSimulator(instance, scenario, config).run()
    audit = audit_result(result, instance, scenario)
    if not all(audit.values()) or result.metrics["max_optimization_latency"] > 5 + 1e-6:
        save_json(OUTPUT / "failures" / f"{method}_{variant}.json.gz", asdict(result))
        raise ValueError("Independent physical/information/deadline audit failed")
    record = dict(protocol_identifier=identifier(protocol), source_sha256=source_hash(),
                  method=method, variant=variant, result=asdict(result), independent_audit=audit,
                  worker_wall_seconds=perf_counter()-started, worker_cpu_seconds=process_time()-cpu)
    save_json(path, record)


def verify(raw, protocol, job):
    expected = asdict(simulation_config(options(protocol, job["method"], job["variant"])))
    if (raw["protocol_identifier"] != identifier(protocol) or raw["source_sha256"] != source_hash() or
            raw["method"] != job["method"] or raw["variant"] != job["variant"] or
            identifier(raw["result"]["effective_config"]) != identifier(expected) or
            raw["result"]["metrics"]["max_optimization_latency"] > 5 + 1e-6 or
            not all(raw["independent_audit"].values())):
        raise ValueError("Invalid ablation result")


def report(protocol, manifest, budget):
    lines = ["# Controlled HGS/ACS component ablation", "",
             "This is an exploratory ablation on the seen r101_21_100 development scenario, "
             "not an independent final confirmation. Fresh workers use PYTHONHASHSEED=0, "
             "one native thread, identical scenario and source, and a five-second decision maximum.", "",
             f"Prior study charge carried: {protocol['prior_charge_seconds']:.2f} s. "
             f"Cumulative charge: {budget.data['charged_seconds']:.2f}/7200 s.", "",
             "| Method | Variant | Served | Complete | CPU s | Wall s | Max decision s | Replans | Early stops | Guard accepts |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for block in protocol["blocks"]:
        for job in block["jobs"]:
            record = next((r for r in manifest["records"] if r["id"] == job["id"]), None)
            if record is None:
                continue
            path = ROOT / record["raw"]
            if sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError("Ablation raw hash drift")
            raw = load_json(path)
            verify(raw, protocol, job)
            m, decisions = raw["result"]["metrics"], raw["result"]["decisions"]
            stops = sum(bool((d.get("adaptive_compute") or {}).get("stopped_early")) for d in decisions)
            guards = sum(bool((d.get("targeted_control") or {}).get("accepted")) for d in decisions)
            lines.append(f"| {job['method']} | {job['variant']} | {m['customers_served']} | "
                         f"{int(m['complete_service'])} | {raw['worker_cpu_seconds']:.2f} | "
                         f"{raw['worker_wall_seconds']:.2f} | {m['max_optimization_latency']:.2f} | "
                         f"{m['optimization_triggers']} | {stops} | {guards} |")
    lines += ["", "The original variant remains the benchmark. Single-factor variants isolate an optional "
              "component only in this one seed; search trajectories depend on the fixed deadline. "
              "A service loss rejects promotion regardless of CPU savings. "
              "The full frozen publication study is unchanged."]
    writable_path(OUTPUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    protocol = freeze()
    budget = HardBudget(OUTPUT, 7200)
    if not budget.path.exists():
        budget.data["charged_seconds"] = protocol["prior_charge_seconds"]
        budget.data["prior_revision_charge_seconds"] = protocol["prior_charge_seconds"]
        budget.flush()
    manifest_path = OUTPUT / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else dict(
        protocol_identifier=identifier(protocol), records=[], status="partial")
    if manifest["protocol_identifier"] != identifier(protocol):
        raise ValueError("Ablation manifest drift")
    records = {r["id"]: r for r in manifest["records"]}
    if len(records) != len(manifest["records"]):
        raise ValueError("Duplicate ablation record")
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env.update({k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    status = "complete"
    for block in protocol["blocks"]:
        pending = [j for j in block["jobs"] if j["id"] not in records]
        if pending and not admit(budget.remaining(), sum(j["upper_seconds"] for j in pending), 120):
            status = "budget_admission_pause"
            break
        for job in block["jobs"]:
            path = OUTPUT / "raw" / f"{job['id']}.json.gz"
            if job["id"] in records:
                if sha256(path.read_bytes()).hexdigest() != records[job["id"]]["sha256"]:
                    raise ValueError("Saved ablation raw changed")
                verify(load_json(path), protocol, job)
                continue
            if path.exists():
                raise ValueError("Unmanifested ablation raw: no automatic rerun")
            execution = budget.execute(job["id"], [sys.executable, "-u", "-m", "scripts.run_fast_ablation",
                                                   "--worker", job["method"], job["variant"]],
                                       job["upper_seconds"], env=env, reserve=120)
            if execution is None or execution["status"] != "complete":
                status = "worker_incomplete_preserved"
                break
            verify(load_json(path), protocol, job)
            records[job["id"]] = dict(id=job["id"], raw=path.relative_to(ROOT).as_posix(),
                                      sha256=sha256(path.read_bytes()).hexdigest(), execution=execution)
            manifest.update(records=list(records.values()), status="partial")
            save_json(manifest_path, manifest)
            print(f"{len(records)}/10 {job['id']} {execution['elapsed_seconds']:.2f}s", flush=True)
        if status == "worker_incomplete_preserved":
            break
    manifest.update(status=status, records=list(records.values()))
    save_json(manifest_path, manifest)
    budget.flush()
    report(protocol, manifest, budget)
    print(f"Ablation {status}; cumulative charge {budget.data['charged_seconds']:.2f}/7200 s", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=2)
    args = parser.parse_args()
    if args.worker:
        worker(*args.worker)
    else:
        lock = writable_path(OUTPUT / "execution.lock")
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()))
        try:
            main()
        finally:
            lock.unlink()
