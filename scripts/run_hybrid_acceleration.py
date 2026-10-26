"""Frozen, sequential, two-hour development campaign with paired-block admission."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys

from evrp.experiments import load_config, simulation_config
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.hybrid_acceleration_worker import OUTPUT, options
from scripts.performance_budget import HardBudget, admit
from scripts.run_desaulniers_campaign import CONFIG as BASE_CONFIG, options as baseline_options

CONFIG = ROOT / "configs/hybrid_acceleration_v1.yaml"
PREVIOUS = ROOT / "results/desaulniers/performance_engineering_v1"
ARCHIVE = ROOT / "results/desaulniers/targeted_service_v1/development/protocol.json"
HISTORICAL = ROOT / "results/desaulniers/development_campaign/manifest.json"


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__),
        ROOT / "scripts/hybrid_acceleration_worker.py", ROOT / "scripts/report_hybrid_acceleration.py",
        ROOT / "scripts/benchmark_hybrid_acceleration.py", ROOT / "scripts/performance_budget.py",
        ROOT / "scripts/performance_engineering_worker.py", ROOT / "scripts/run_desaulniers_campaign.py",
        CONFIG, BASE_CONFIG]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths})


def archived_input(rows, name, kind, key):
    row = next(r for r in rows if r["kind"] == kind and r["identifier"] == key and r["instance"] == name)
    if sha256((ROOT / row["artifact"]).read_bytes()).hexdigest() != row["sha256"]:
        raise ValueError("Archived input changed")
    return dict(path=row["artifact"], sha256=row["sha256"])


def job(kind, index, method, variant, upper):
    return dict(id=f"{kind}_{index}_{method}_{variant}", kind=kind,
                case_index=index, method=method, variant=variant, upper_seconds=upper)


def freeze():
    config = load_config(CONFIG)
    if config["maximum_total_seconds"] != 7200 or not config["no_automatic_holdout"]:
        raise ValueError("Only the authorized two-hour development study is allowed")
    path = OUTPUT / "protocol.json"
    if path.exists():
        protocol = load_json(path)
        if protocol["source_sha256"] != source_hash() or protocol["config"] != config:
            raise ValueError("Frozen source or protocol drift")
        return protocol
    scoped = ["evrp", "configs/hybrid_acceleration_v1.yaml", "scripts/run_hybrid_acceleration.py",
              "scripts/hybrid_acceleration_worker.py", "scripts/report_hybrid_acceleration.py",
              "scripts/benchmark_hybrid_acceleration.py"]
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *scoped],
                      cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip():
        raise ValueError("Commit scientific source before freezing protocol")
    benchmark_path = OUTPUT / "kernel_benchmark.json"
    benchmark = load_json(benchmark_path)
    if benchmark["source_sha256"] != sha256((ROOT / "scripts/benchmark_hybrid_acceleration.py").read_bytes()).hexdigest():
        raise ValueError("Kernel benchmark source drift")
    previous = load_json(PREVIOUS / "protocol.json")
    previous_manifest = load_json(PREVIOUS / "manifest.json")
    archive = load_json(ARCHIVE)["scientific"]
    history = load_json(HISTORICAL)["records"]
    cases = list(previous["cases"])
    for name, dod, seed in config["validation_cases"]:
        old = next(r for r in archive["cases"] if r["case"] == [name, dod, seed])
        cases.append(dict(case=old["case"], instance_sha256=old["instance_sha256"],
                          scenario_id=old["scenario_id"], reference_id=old["reference_id"],
                          k_ref=old["k_ref"],
                          scenario=archived_input(archive["inputs"], name, "scenarios", old["scenario_id"]),
                          reference=archived_input(archive["inputs"], name, "reference_schedules", old["reference_id"]),
                          base_options=baseline_options(load_config(BASE_CONFIG), name, dod, seed, "MPC_COMPLETION")))
    blocks = [dict(id=f"micro_{i}", stage="hardware", jobs=[
        job("micro", i, "MPC_COMPLETION", "compiled_cpu_v1", 30)]) for i in range(3)]
    historical_costs = []
    for i, case in enumerate(cases):
        for j, method in enumerate(config["methods"]):
            if i < 3:
                elapsed = next(r["execution"]["elapsed_seconds"] for r in previous_manifest["records"]
                               if r["kind"] == "pilot" and r["case_index"] == i and
                               r["method"] == method and r["variant"] == "original")
            else:
                name, dod, seed = case["case"]
                row = next(r for r in history if r["instance"] == name and
                           r["dynamicity"] == dod and r["seed"] == seed and r["method"] == method)
                raw = ROOT / row["raw"]
                if sha256(raw.read_bytes()).hexdigest() != row["raw_sha256"]:
                    raise ValueError("Historical admission evidence changed")
                elapsed = load_json(raw)["metrics"]["worker_wall_seconds"]
            upper = max(45, 2 * elapsed + 20)
            historical_costs.append(dict(index=i, method=method, historical_seconds=elapsed,
                                         upper_seconds=upper))
            stage = "compiled_pilot" if i < 3 else "quality_validation"
            variants = (config["stage_b_variants"] if i < 3 else config["stage_c_variants"])
            order = variants if (i + j) % 2 == 0 else list(reversed(variants))
            blocks.append(dict(id=f"{stage}_{i}_{method}", stage=stage,
                               jobs=[job("scenario", i, method, variant, upper) for variant in order]))
    estimate = (config["prestudy_charge_seconds"] + config["report_reserve_seconds"] +
                sum(j["upper_seconds"] for block in blocks for j in block["jobs"]))
    if estimate > config["maximum_total_seconds"]:
        save_json(OUTPUT / "admission_refused.json", dict(upper_seconds=estimate,
                  allowance_seconds=config["maximum_total_seconds"]))
        raise ValueError("Planned upper bounds exceed two-hour allowance")
    protocol = dict(config=config, cases=cases, common=previous["config"]["common"],
                    blocks=blocks, historical_costs=historical_costs,
                    source_sha256=source_hash(), benchmark_sha256=sha256(benchmark_path.read_bytes()).hexdigest(),
                    source_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                 capture_output=True, text=True, check=True).stdout.strip(),
                    estimated_upper_seconds_including_setup_and_report=estimate,
                    notes="Previously seen engineering parents for backend pilot; preselected R2/RC1 "
                          "development parents for quality/recovery. All methods paired with their own "
                          "original control; fresh sequential workers, one native thread, PYTHONHASHSEED=0; "
                          "no new final holdout. The 300-second setup charge conservatively covers "
                          "hardware installation/benchmark/preflight compute.")
    for i in range(len(cases)):
        for method in config["methods"]:
            baseline = asdict(simulation_config(options(protocol, i, method, "original")))
            variants = config["stage_b_variants"] if i < 3 else config["stage_c_variants"]
            for variant in variants:
                other = asdict(simulation_config(options(protocol, i, method, variant)))
                allowed = ({"proposal_cache_policy"} if i < 3 else
                           {"quality_policy", "service_recovery_policy"})
                if {key for key in baseline if baseline[key] != other[key]} - allowed:
                    raise ValueError("Variant changed optimizer, physics, fleet, visibility, or budget")
                if other["total_planning_time_limit"] != 5:
                    raise ValueError("Five-second decision cap changed")
    save_json(path, protocol)
    return protocol


def verify(raw, protocol, spec):
    if (raw["job_id"] != spec["id"] or raw["protocol_identifier"] != identifier(protocol) or
            raw["case_index"] != spec["case_index"] or raw["variant"] != spec["variant"]):
        raise ValueError("Worker identity mismatch")
    if spec["kind"] == "micro":
        values = raw["micro"]["variants"]
        if (not raw["micro"]["numba_available"] or
                values["original"]["checksum"] != values["compiled_cpu_v1"]["checksum"] or
                not all(row["exact_physical_replay"] for row in values.values())):
            raise ValueError("Compiled microcheck failed")
    else:
        from dataclasses import asdict
        result = raw["result"]
        expected = asdict(simulation_config(options(protocol, spec["case_index"], spec["method"], spec["variant"])))
        case = protocol["cases"][spec["case_index"]]
        if (identifier(result["effective_config"]) != identifier(expected) or
                result["metadata"]["scenario_identifier"] != case["scenario_id"] or
                result["metadata"]["K_ref"] != case["k_ref"] or
                result["metrics"]["max_optimization_latency"] > 5 + 1e-6 or
                not all(result["metadata"]["independent_audit"].values())):
            raise ValueError("Physical, information, parameter, or decision-budget violation")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    protocol = freeze()
    if args.freeze:
        return print(f"Frozen {sum(len(b['jobs']) for b in protocol['blocks'])} jobs; "
                     f"upper {protocol['estimated_upper_seconds_including_setup_and_report']:.1f}/7200 s")
    budget = HardBudget(OUTPUT, 7200)
    if not budget.path.exists():
        budget.data["charged_seconds"] = protocol["config"]["prestudy_charge_seconds"]
        budget.data["conservative_prestudy_charge_seconds"] = protocol["config"]["prestudy_charge_seconds"]
        budget.flush()
    manifest_path = OUTPUT / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else dict(
        protocol_identifier=identifier(protocol), records=[], status="partial")
    if manifest["protocol_identifier"] != identifier(protocol):
        raise ValueError("Manifest/protocol drift")
    records = {r["id"]: r for r in manifest["records"]}
    if len(records) != len(manifest["records"]):
        raise ValueError("Duplicate manifest entry")
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env.update({k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    status = "complete"
    for block in protocol["blocks"]:
        if block["stage"] == "compiled_pilot" and not all(
                f"micro_{i}_MPC_COMPLETION_compiled_cpu_v1" in records for i in range(3)):
            raise ValueError("Compiled pilot requires all fixed-work audits")
        pending = [j for j in block["jobs"] if j["id"] not in records]
        if pending and not admit(budget.remaining(), sum(j["upper_seconds"] for j in pending),
                                 protocol["config"]["report_reserve_seconds"]):
            status = "budget_admission_pause"
            print(f"Refused incomplete paired block {block['id']}", flush=True)
            break
        for spec in block["jobs"]:
            path = OUTPUT / "raw" / f"{spec['id']}.json.gz"
            if spec["id"] in records:
                if sha256(path.read_bytes()).hexdigest() != records[spec["id"]]["sha256"]:
                    raise ValueError("Saved raw hash changed")
                verify(load_json(path), protocol, spec)
                continue
            if path.exists():
                raise ValueError("Unmanifested evidence preserved; no silent retry")
            command = [sys.executable, "-u", "-m", "scripts.hybrid_acceleration_worker",
                       spec["kind"], str(spec["case_index"]), spec["method"], spec["variant"]]
            execution = budget.execute(spec["id"], command, spec["upper_seconds"],
                                       env=env, reserve=protocol["config"]["report_reserve_seconds"])
            if execution is None or execution["status"] != "complete":
                status = "worker_incomplete_preserved"
                break
            verify(load_json(path), protocol, spec)
            records[spec["id"]] = dict(id=spec["id"], kind=spec["kind"],
                                       raw=path.relative_to(ROOT).as_posix(),
                                       sha256=sha256(path.read_bytes()).hexdigest(), execution=execution)
            manifest.update(status="partial", records=list(records.values()))
            save_json(manifest_path, manifest)
            print(f"{len(records)}/{sum(len(b['jobs']) for b in protocol['blocks'])} "
                  f"{spec['id']} {execution['elapsed_seconds']:.2f}s", flush=True)
        if status == "worker_incomplete_preserved":
            break
    manifest.update(status=status, records=list(records.values()))
    save_json(manifest_path, manifest)
    budget.flush()
    execution = budget.execute("final_report", [sys.executable, "-u", "-m", "scripts.report_hybrid_acceleration"],
                               protocol["config"]["report_reserve_seconds"], env=env, reserve=0)
    if execution is None or execution["status"] != "complete":
        print("Report worker incomplete; raw evidence remains intact", flush=True)
    print(f"Hybrid study {status}; charged {budget.data['charged_seconds']:.2f}/7200 s", flush=True)


if __name__ == "__main__":
    lock = writable_path(OUTPUT / "execution.lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    try:
        main()
    finally:
        lock.unlink()
