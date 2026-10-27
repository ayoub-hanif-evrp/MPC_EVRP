"""Small audited two-worker throughput probe, separate from paper timing."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter, process_time, sleep

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.audit import decode_result
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.run_desaulniers_campaign import CONFIG, options
from scripts.run_desaulniers_pilot import VIOLATIONS


OUTPUT = ROOT / "results/desaulniers/two_worker_probe_v1"
CASES = (("c101_21_25", "MPC_MCTS"), ("r201_21_25", "MPC_HGS"))
WATCHDOG = 600.0
CAMPAIGN_LIMIT = 1800.0


def source_hash():
    files = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__), CONFIG,
             ROOT / "scripts/run_desaulniers_campaign.py", ROOT / "scripts/run_desaulniers_pilot.py"]
    return identifier({path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                       for path in files})


def freeze():
    path = OUTPUT / "protocol.json"
    config = load_config(CONFIG)
    scenarios = []
    for name, method in CASES:
        instance, reference, scenario, _ = prepare(name, options(config, name, .5, 3, method))
        scenarios.append(dict(instance=name, method=method, instance_sha256=instance.sha256,
                              scenario_id=scenario.identifier, reference_id=reference.identifier,
                              k_ref=reference.fleet_size))
    frozen = dict(purpose="technical_two_worker_probe_not_paper_timing",
                  cases=scenarios, modes=["sequential", "two_workers"],
                  source_sha256=source_hash(), watchdog_seconds=WATCHDOG,
                  campaign_limit_seconds=CAMPAIGN_LIMIT, five_second_decision_limit=5.0,
                  machine_load="shared workstation; background processes not suspended")
    if path.exists():
        if load_json(path) != frozen:
            raise ValueError("Two-worker probe protocol drift")
    else:
        save_json(path, frozen)
    return frozen


def worker(mode, index):
    frozen = freeze()
    if mode not in frozen["modes"] or index not in range(len(CASES)):
        raise ValueError("Unknown probe worker")
    path = OUTPUT / "raw" / f"{mode}_{index}.json.gz"
    if path.exists():
        raise ValueError("Never overwrite probe raw")
    info = frozen["cases"][index]
    config = load_config(CONFIG)
    opts = options(config, info["instance"], .5, 3, info["method"])
    opts.update(study="two_worker_throughput_probe", proposal_cache_policy="original")
    instance, reference, scenario, _ = prepare(info["instance"], opts)
    if (instance.sha256 != info["instance_sha256"] or reference.identifier != info["reference_id"]
            or scenario.identifier != info["scenario_id"] or reference.fleet_size != info["k_ref"]):
        raise ValueError("Probe input drift")
    started, cpu = perf_counter(), process_time()
    result = EventDrivenSimulator(instance, scenario, simulation_config(opts)).run()
    audit = audit_result(result, instance, scenario)
    if (not all(audit.values()) or any(result.metrics[key] for key in VIOLATIONS) or
            result.metrics["max_optimization_latency"] > 5.0 + 1e-6):
        raise ValueError("Probe worker failed physical/information/deadline audit")
    save_json(path, dict(result=asdict(result), audit=audit, source_sha256=frozen["source_sha256"],
                         worker_wall_seconds=perf_counter()-started,
                         worker_cpu_seconds=process_time()-cpu))


def _working_set(process):
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD),
                    ("peak_working_set", ctypes.c_size_t), ("working_set", ctypes.c_size_t),
                    ("peak_paged_pool", ctypes.c_size_t), ("paged_pool", ctypes.c_size_t),
                    ("peak_nonpaged_pool", ctypes.c_size_t), ("nonpaged_pool", ctypes.c_size_t),
                    ("pagefile", ctypes.c_size_t), ("peak_pagefile", ctypes.c_size_t)]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        wintypes.HANDLE(int(process._handle)), ctypes.byref(counters), counters.cb)
    return int(counters.working_set) if ok else None


def run():
    frozen = freeze()
    manifest_path = OUTPUT / "manifest.json"
    if manifest_path.exists():
        raise ValueError("Probe already started; preserve existing evidence")
    env = dict(os.environ, PYTHONHASHSEED="0", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    started = perf_counter()
    modes = {}
    for mode in frozen["modes"]:
        mode_started = perf_counter()
        pending = {}
        results = []
        indices = range(len(CASES))
        for index in indices:
            log = writable_path(OUTPUT / "logs" / f"{mode}_{index}.log")
            with log.open("xb") as stream:
                process = subprocess.Popen([sys.executable, "-u", "-m",
                    "scripts.benchmark_two_worker_throughput", "--worker", mode, str(index)],
                    cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
                pending[index] = dict(process=process, started=perf_counter(), log=log, peak=0)
                if mode == "sequential":
                    _supervise(pending, started)
                    results.append(_collect(mode, index, pending.pop(index)))
        if pending:
            _supervise(pending, started)
            results.extend(_collect(mode, index, item) for index, item in sorted(pending.items()))
        modes[mode] = dict(elapsed_seconds=perf_counter()-mode_started, results=results)
        save_json(manifest_path, dict(status="partial", protocol_identifier=identifier(frozen),
                                      modes=modes))
    sequential, concurrent = modes["sequential"], modes["two_workers"]
    same_service = all(a["served"] == b["served"] for a, b in
                       zip(sequential["results"], concurrent["results"]))
    throughput = sequential["elapsed_seconds"] / concurrent["elapsed_seconds"]
    report = ["# Two-worker CPU throughput probe", "",
              "Technical shared-machine observation only. Both modes used the original "
              "methods and the same fixed released-request scenarios, fleet, physics, "
              "objective and five-second MPC decision limit. Background host load was "
              "not controlled; these timings are not paper comparisons.", "",
              f"Sequential elapsed: {sequential['elapsed_seconds']:.2f} s; two-worker elapsed: "
              f"{concurrent['elapsed_seconds']:.2f} s; throughput ratio: {throughput:.2f}x. "
              f"Identical served counts: {same_service}.",
              "",
              "| Mode | Instance | Method | Served | Worker CPU s | Peak observed working set MiB |",
              "| --- | --- | --- | ---: | ---: | ---: |"]
    for mode, bundle in modes.items():
        for info, result in zip(frozen["cases"], bundle["results"]):
            report.append(f"| {mode} | {info['instance']} | {info['method']} | "
                          f"{result['served']} | {result['cpu_seconds']:.2f} | "
                          f"{result['peak_working_set_bytes']/1048576:.1f} |")
    report += ["", "Two workers are a supported technical option, but concurrent "
               "deadline-sensitive optimization must be evaluated as a separate "
               "execution methodology. The sequential original-method paper timings "
               "are not replaced by this probe."]
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    save_json(manifest_path, dict(status="complete", protocol_identifier=identifier(frozen),
                                  modes=modes, total_elapsed_seconds=perf_counter()-started,
                                  same_service=same_service, throughput_ratio=throughput))


def _supervise(pending, campaign_started):
    while any(item["process"].poll() is None for item in pending.values()):
        for item in pending.values():
            process = item["process"]
            if process.poll() is None:
                item["peak"] = max(item["peak"], _working_set(process) or 0)
                if (perf_counter()-item["started"] > WATCHDOG or
                        perf_counter()-campaign_started > CAMPAIGN_LIMIT):
                    process.kill()
                    process.wait()
                    raise TimeoutError("Probe worker/campaign watchdog; logs and partial raw preserved")
        sleep(.05)
    for item in pending.values():
        if item["process"].returncode:
            raise RuntimeError(f"Probe worker failed: {item['log']}")


def _collect(mode, index, item):
    path = OUTPUT / "raw" / f"{mode}_{index}.json.gz"
    raw = load_json(path)
    info = load_json(OUTPUT / "protocol.json")["cases"][index]
    if (raw["source_sha256"] != source_hash() or
            raw["result"]["metadata"]["scenario_identifier"] != info["scenario_id"] or
            raw["result"]["metadata"]["K_ref"] != info["k_ref"] or
            not all(raw["audit"].values())):
        raise ValueError("Probe raw identity/audit mismatch")
    config = load_config(CONFIG)
    instance, _, scenario, _ = prepare(info["instance"],
                                       options(config, info["instance"], .5, 3, info["method"]))
    if (not all(audit_result(decode_result(raw["result"]), instance, scenario).values()) or
            raw["result"]["metrics"]["max_optimization_latency"] > 5.0 + 1e-6):
        raise ValueError("Independent probe replay/deadline failure")
    return dict(index=index, raw=path.relative_to(ROOT).as_posix(),
                sha256=sha256(path.read_bytes()).hexdigest(),
                served=raw["result"]["metrics"]["customers_served"],
                max_latency=raw["result"]["metrics"]["max_optimization_latency"],
                cpu_seconds=raw["worker_cpu_seconds"], wall_seconds=raw["worker_wall_seconds"],
                peak_working_set_bytes=item["peak"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=2)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker[0], int(args.worker[1]))
    else:
        run()
