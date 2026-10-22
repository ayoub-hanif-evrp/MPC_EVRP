"""Eligible three-DoD robustness version, preserving the rejected v2 preflight."""

import argparse
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

from evrp.experiments import load_config, prepare
from evrp.instance import load_instance
from evrp.reference import ReferenceConfig, published_full_reference
from evrp.scenario import generate
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json
from scripts.run_desaulniers_pilot import dataset_hash, settings
import scripts.run_desaulniers_robustness as v2


CONFIG = ROOT / "configs/desaulniers_mp_robustness_v3.yaml"
OUTPUT = ROOT / "results/desaulniers/robustness_v3"
V2_PROTOCOL = ROOT / "results/desaulniers/robustness_v2/protocol.json"
METHODS = v2.METHODS


def source_hash():
    paths = sorted((ROOT / "evrp").rglob("*.py")) + [
        ROOT / "scripts/run_desaulniers_pilot.py",
        ROOT / "scripts/run_desaulniers_robustness.py", Path(__file__)]
    return identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                       for p in paths})


def options(config, dod, seed, method):
    return dict(settings(dict(config, dynamicity=dod, scenario_seed=seed), "", method),
                study="desaulniers_mp_robustness_v3")


def protocol(config):
    if (config["charging_policy"] != "MP" or
            config["total_planning_time_limit"] != 5.0 or
            tuple(config["methods"]) != METHODS or
            config["dynamicities"] != [0.25, 0.5, 0.75] or
            config["scenario_seeds"] != [1, 2, 3, 4, 5]):
        raise ValueError("V3 differs from the unchanged five-method MP design")
    cases = v2.selected(config)
    eligibility = []
    for case in cases:
        instance = load_instance(BENCHMARK / f"{case['instance']}.txt")
        reference = published_full_reference(instance, ReferenceConfig())
        for dod in config["dynamicities"]:
            generate(instance, reference, config["scenario_seeds"][0], dod)
            eligibility.append(dict(instance=instance.name, dynamicity=dod, eligible=True))
    frozen = dict(purpose="multi_seed_robustness_v3", dataset="Desaulniers et al. 2016",
                  charging_policy="MP", selected=cases, eligibility=eligibility,
                  methods=list(METHODS), dynamicities=config["dynamicities"],
                  scenario_seeds=config["scenario_seeds"], total_planning_time_limit=5.0,
                  execution="sequential isolated worker processes",
                  selection_rule="lexicographically first unused SF/MF-replayed instance "
                                 "eligible for DoD 0.75 in each predefined family-size slot",
                  preflight_v2_identifier=identifier(load_json(V2_PROTOCOL)),
                  dataset_sha256=dataset_hash(), source_sha256=source_hash(),
                  config_sha256=sha256(CONFIG.read_bytes()).hexdigest(),
                  controller_sha256=sha256((ROOT / config["base_controller"]).read_bytes()).hexdigest())
    path = OUTPUT / "protocol.json"
    if path.exists():
        if load_json(path) != frozen:
            raise ValueError("Existing v3 protocol differs from source, data, or config")
    else:
        save_json(path, frozen)
    return frozen


def worker(name, dod, seed, method, path):
    # Reuse the audited v2 worker implementation with v3-bound protocol and paths.
    # Each worker is its own process, so these module bindings cannot leak to v2.
    v2.CONFIG = CONFIG
    v2.OUTPUT = OUTPUT
    v2.protocol = lambda config, pilot=False: protocol(config)
    v2.options = options
    v2.worker(name, dod, seed, method, path, pilot=False)


def run(freeze=False, limit=None):
    config = load_config(CONFIG)
    frozen = protocol(config)
    if freeze:
        print(f"Frozen {identifier(frozen)}", flush=True)
        return
    scenarios = [(case, dod, seed) for case in frozen["selected"]
                 for dod in frozen["dynamicities"] for seed in frozen["scenario_seeds"]]
    manifest_path = OUTPUT / "manifest.json"
    old = load_json(manifest_path) if manifest_path.exists() else None
    fingerprint = identifier(frozen)
    if old and old["protocol_identifier"] != fingerprint:
        raise ValueError("Existing v3 manifest belongs to another protocol")
    records = {(r["instance"], r["dynamicity"], r["seed"], r["method"]): r
               for r in old["records"]} if old else {}

    def checkpoint():
        total = len(scenarios) * len(METHODS)
        save_json(manifest_path, dict(status="complete" if len(records) == total else "partial",
                                      protocol_identifier=fingerprint, planned_runs=total,
                                      completed_runs=len(records), ineligible_scenarios=0,
                                      records=sorted(records.values(), key=lambda r: (
                                          r["instance"], r["dynamicity"], r["seed"], r["method"])),
                                      ineligible=[]))

    for case, dod, seed in scenarios[:limit]:
        name = case["instance"]
        instance, reference, scenario, _ = prepare(name, options(config, dod, seed, METHODS[0]))
        for method in METHODS:
            key = name, dod, seed, method
            identity = identifier(dict(protocol=fingerprint, scenario=scenario.identifier,
                                       method=method))
            path = OUTPUT / "raw" / f"{name}_{dod}_{seed}_{method}_{identity[:12]}.json.gz"
            if key in records:
                row = records[key]
                if ((ROOT / row["raw"]).resolve() != path.resolve() or not path.is_file() or
                        sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
                    raise ValueError(f"Saved v3 raw run is missing or corrupted: {key}")
                continue
            if path.exists():
                raise ValueError(f"Unmanifested v3 raw file exists: {path}")
            subprocess.run([sys.executable, "-m", "scripts.run_desaulniers_robustness_v3",
                            "--worker", name, str(dod), str(seed), method, str(path)],
                           cwd=ROOT, check=True,
                           timeout=config["whole_worker_timeout_seconds"])
            raw = load_json(path)
            if (raw["metadata"]["scenario_identifier"] != scenario.identifier or
                    raw["metadata"]["algorithm"] != method or
                    raw["metadata"]["source_sha256"] != frozen["source_sha256"] or
                    not all(raw["metadata"]["independent_audit"].values())):
                raise ValueError("V3 worker identity or audit mismatch")
            records[key] = dict(instance=name, size=case["size"], family=case["family"],
                                dynamicity=dod, seed=seed, scenario_id=scenario.identifier,
                                instance_sha256=instance.sha256,
                                reference_identifier=reference.identifier,
                                k_ref=reference.fleet_size, method=method,
                                customers_served=raw["metrics"]["customers_served"],
                                complete_service=raw["metrics"]["complete_service"],
                                vehicles_activated=raw["metrics"]["vehicles_activated"],
                                total_distance=raw["metrics"]["total_distance"],
                                max_optimization_latency=raw["metrics"]["max_optimization_latency"],
                                raw=path.relative_to(ROOT).as_posix(),
                                raw_sha256=sha256(path.read_bytes()).hexdigest())
            checkpoint()
            print(f"robustness-v3 {len(records)}/{len(scenarios)*len(METHODS)} "
                  f"{name} DoD={dod} seed={seed} {method} "
                  f"served={raw['metrics']['customers_served']}", flush=True)
    checkpoint()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--scenario-limit", type=int)
    parser.add_argument("--worker", nargs=5,
                        metavar=("INSTANCE", "DOD", "SEED", "METHOD", "OUTPUT"))
    args = parser.parse_args()
    if args.worker:
        name, dod, seed, method, path = args.worker
        worker(name, float(dod), int(seed), method, path)
    else:
        run(args.freeze, args.scenario_limit)
