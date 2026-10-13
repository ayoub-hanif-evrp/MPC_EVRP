"""Resumable, protocol-bound paper runs; no controller code or tuning changes."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
from time import perf_counter

from evrp.experiments import load_config, run_single, source_fingerprint
from evrp.external.audit import reference_for
from evrp.external.replay import replay_routes
from evrp.external.routingblocks_adapter import run_routingblocks
from evrp.instance import load_instance
from evrp.storage import BENCHMARK, ROOT, load_json, save_json


FROZEN_SOURCE = "4cdead8ab9956362ba9921c0818b7bcc9690487ab11ba001d087abebe43176b6"
CONTROLLER = ROOT / "configs/paper_controller.yaml"
CAMPAIGN = ROOT / "configs/paper_campaign.yaml"
PROTOCOL = ROOT / "results/paper/PAPER_PROTOCOL.md"
FREEZE = ROOT / "results/paper/protocol_freeze.json"


def _git(*args):
    return subprocess.check_output(("git", *args), cwd=ROOT, text=True).strip()


def require_freeze() -> dict:
    """Hard gate before any holdout instance is prepared or inspected."""
    if source_fingerprint() != FROZEN_SOURCE:
        raise RuntimeError("Frozen MPC-MCTS source hash changed")
    if not PROTOCOL.is_file() or not _git("ls-files", "--error-unmatch", str(PROTOCOL.relative_to(ROOT))):
        raise RuntimeError("Paper protocol has not been committed")
    if _git("status", "--porcelain"):
        raise RuntimeError("Working tree must be clean before holdout")
    record = {"git_sha": _git("rev-parse", "HEAD"),
              "source_sha256": source_fingerprint(),
              "protocol_sha256": sha256(PROTOCOL.read_bytes()).hexdigest(),
              "controller_sha256": sha256(CONTROLLER.read_bytes()).hexdigest(),
              "campaign_sha256": sha256(CAMPAIGN.read_bytes()).hexdigest()}
    if FREEZE.exists() and load_json(FREEZE) != record:
        raise RuntimeError("Existing holdout freeze differs; no redefinition allowed")
    save_json(FREEZE, record)
    return record


def _record(path: Path, manifest: dict, output: Path) -> dict:
    result = load_json(path)
    item = {"path": str(path.relative_to(ROOT)), "sha256": sha256(path.read_bytes()).hexdigest(),
            "status": result["status"], "scenario_hash": result.get("scenario", {}).get("scenario_hash")}
    manifest["records"].append(item)
    save_json(output, manifest)
    if result["status"] != "completed":
        raise RuntimeError(f"Run failed: {path}: {result.get('error')}")
    return result


def run_dynamic(phase: str):
    if phase not in {"development_rh", "holdout"}:
        raise ValueError(phase)
    protocol = require_freeze() if phase == "holdout" else None
    grid = load_config(CAMPAIGN)
    base = load_config(CONTROLLER)
    names = grid["holdout_instances" if phase == "holdout" else "development_instances"]
    dods = grid["holdout_dynamicity" if phase == "holdout" else "development_dynamicity"]
    seeds = grid["holdout_seeds" if phase == "holdout" else "development_seeds"]
    methods = grid["dynamic_methods"] if phase == "holdout" else ["RH_REGRET"]
    output = ROOT / "results/paper/raw" / phase
    manifest_path = ROOT / "results/paper" / f"{phase}_manifest.json"
    manifest = {"phase": phase, "protocol": protocol, "records": []}
    for name, dod, seed in product(names, dods, seeds):
        paired = set()
        for method in methods:
            config = {**base, "algorithm": method, "dynamicity": dod,
                      "scenario_seed": seed, "experiment_seed": seed}
            path = run_single(name, config, output, resume=True)
            record = _record(path, manifest, manifest_path)
            paired.add(record["scenario"]["scenario_hash"])
            print(f"{phase} {name} DoD={dod} seed={seed} {method}: "
                  f"{record['metrics']['customers_served']}/{record['metadata']['number_of_customers']}",
                  flush=True)
        if len(paired) != 1:
            raise RuntimeError(f"Paired scenario mismatch: {name} {dod} {seed}")
    return manifest_path


def run_static_controller():
    grid = load_config(CAMPAIGN)
    base = load_config(CONTROLLER)
    output = ROOT / "results/paper/raw/static_controller"
    manifest_path = ROOT / "results/paper/static_controller_manifest.json"
    manifest = {"phase": "static_controller", "records": []}
    for name, seed in product(grid["static_instances"], grid["static_seeds"]):
        config = {**base, "algorithm": "FLEET_MPC_MCTS", "dynamicity": 0.0,
                  "scenario_seed": 0, "experiment_seed": seed}
        path = run_single(name, config, output, resume=True)
        record = _record(path, manifest, manifest_path)
        print(f"static_controller {name} seed={seed}: "
              f"{record['metrics']['customers_served']}/{record['metadata']['number_of_customers']}",
              flush=True)
    return manifest_path


def run_static_routingblocks(examples: Path, external_python: Path | None = None):
    grid = load_config(CAMPAIGN)
    output = ROOT / "results/paper/raw/routingblocks"
    manifest_path = ROOT / "results/paper/routingblocks_manifest.json"
    manifest = {"phase": "routingblocks", "records": []}
    for name, seed, budget in product(grid["static_instances"], grid["static_seeds"],
                                      grid["external_runtime_seconds"]):
        path = BENCHMARK / f"{name}.txt"
        instance = load_instance(path)
        k_ref = reference_for(instance).fleet_size
        destination = output / f"{name}_seed{seed}_budget{budget}.json"
        if destination.exists():
            raw = load_json(destination)
            if (raw.get("instance") != name or raw.get("seed") != seed
                    or raw.get("runtime_budget") != budget):
                raise RuntimeError(f"Incompatible existing raw result: {destination}")
        else:
            if external_python is None:
                raw = run_routingblocks(instance, path, examples, k_ref, seed, budget)
            else:
                command = [str(external_python), "-m", "evrp.external.routingblocks_worker",
                           "--instance", str(path), "--examples", str(examples),
                           "--fleet-size", str(k_ref), "--seed", str(seed),
                           "--budget", str(budget), "--output", str(destination)]
                started = perf_counter()
                subprocess.run(command, cwd=ROOT, check=True, timeout=budget + 120)
                raw = load_json(destination)
                raw["external_wall_seconds"] = perf_counter() - started
            if raw.get("status", "completed") == "completed":
                routes = [route["nodes"] for route in raw["external"]["routes"]]
                audit = replay_routes(instance, routes, k_ref)
                raw["our_replay"] = vars(audit)
                raw["budget_respected"] = raw["runtime"] <= budget
            save_json(destination, raw)
        manifest["records"].append({"path": str(destination.relative_to(ROOT)),
                                    "sha256": sha256(destination.read_bytes()).hexdigest()})
        save_json(manifest_path, manifest)
        if raw.get("status") == "failed":
            print(f"RoutingBlocks {name} seed={seed} budget={budget}: {raw['error']}", flush=True)
        else:
            print(f"RoutingBlocks {name} seed={seed} budget={budget}: "
                  f"{raw['our_replay']['served']}/{len(instance.customers)} "
                  f"replay={raw['our_replay']['feasible']} "
                  f"budget_respected={raw['budget_respected']}", flush=True)
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("development_rh", "holdout", "static_controller", "routingblocks"))
    parser.add_argument("--routingblocks-examples", type=Path)
    parser.add_argument("--external-python", type=Path)
    args = parser.parse_args()
    if args.phase == "routingblocks":
        if args.routingblocks_examples is None:
            parser.error("--routingblocks-examples is required")
        result = run_static_routingblocks(args.routingblocks_examples, args.external_python)
    elif args.phase == "static_controller":
        result = run_static_controller()
    else:
        result = run_dynamic(args.phase)
    print(json.dumps({"manifest": str(result)}, indent=2))


if __name__ == "__main__":
    main()
