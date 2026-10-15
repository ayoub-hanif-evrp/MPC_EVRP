"""Freeze observable MPC snapshots, then compare optimizers on identical states."""

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import subprocess
import sys
from time import perf_counter

from evrp.experiments import audit_result, load_config, prepare, simulation_config
from evrp.fleet_mcts import _FleetProblem
from evrp.instance import Infrastructure, Location, Parameters
from evrp.model import Action, Observation, VehicleState
from evrp.mpc import MPCConfig
from evrp.optimizers import OptimizationContext, create_optimizer
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json
from scripts.run_portfolio_campaign import CONFIG_PATH, cases, source_hash


OUTPUT = ROOT / "results" / "portfolio" / "shadow"
SEARCH_METHODS = ("MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS")


@dataclass(frozen=True)
class OptimizationSnapshot:
    scenario_id: str
    instance_sha256: str
    epoch: int
    state_hash: str
    available_seconds: float
    features: dict
    payload: dict


def _payload(context):
    def keyed(mapping):
        return {str(key): [asdict(action) for action in value]
                for key, value in mapping.items()}
    return dict(observation=asdict(context.observation),
                origins={str(k): asdict(state) for k, state in context.origins.items()},
                busy_actions={str(k): asdict(action) for k, action in context.busy_actions.items()},
                soft_suffixes=keyed(context.soft_suffixes),
                released_customers=sorted(context.released_customers),
                committed_customers=sorted(context.committed_customers),
                served_customers=sorted(context.served_customers),
                constructor_routes=keyed(context.constructor_routes),
                k_ref=context.k_ref, seed=context.seed, mpc=asdict(context.mpc))


def _context(payload, available_seconds):
    def location(data):
        return Location(**data)
    obs = payload["observation"]
    infra = obs["infrastructure"]
    observation = Observation(obs["time"], Infrastructure(
        location(infra["depot"]), tuple(location(node) for node in infra["stations"]),
        Parameters(**infra["parameters"])),
        tuple(location(node) for node in obs["customers"]),
        tuple(tuple(item) for item in obs["committed_customers"]))
    origins = {}
    for key, data in payload["origins"].items():
        value = dict(data, location=location(data["location"]),
                     route_history=tuple(data["route_history"]),
                     served_customers=tuple(data["served_customers"]),
                     current_committed_action=(Action(**data["current_committed_action"])
                                               if data["current_committed_action"] else None))
        origins[int(key)] = VehicleState(**value)
    routes = lambda mapping: {int(k): tuple(Action(**action) for action in values)
                              for k, values in mapping.items()}
    mpc = dict(payload["mpc"], charge_fractions=tuple(payload["mpc"]["charge_fractions"]))
    return OptimizationContext(
        observation, origins,
        {int(k): Action(**value) for k, value in payload["busy_actions"].items()},
        routes(payload["soft_suffixes"]),
        frozenset(payload["released_customers"]),
        frozenset(payload["committed_customers"]),
        frozenset(payload["served_customers"]),
        routes(payload["constructor_routes"]), payload["k_ref"],
        perf_counter() + available_seconds, payload["seed"], MPCConfig(**mpc))


def _features(payload):
    context = _context(payload, 3600.0)
    problem = _FleetProblem(dict(context.origins), context.observation, context.mpc, 3, 2)
    root = problem.initial(dict(context.constructor_routes))
    ranked = problem._criticality(root.sequences)
    pending = max(1, len(problem.pending))
    depot_due = context.observation.infrastructure.depot.due
    battery = context.observation.infrastructure.parameters.battery
    return dict(time_fraction=min(1.0, context.observation.time / max(1.0, depot_due)),
                uncovered=int(root.score[0]),
                zero_option=sum(row[1] == 0 for row in ranked),
                one_option=sum(row[1] == 1 for row in ranked),
                min_tw_slack=min((context.observation.customer_by_id[c].due -
                                  context.observation.time for c in problem.pending), default=0),
                min_battery_fraction=min((state.battery / battery for state in context.origins.values()),
                                         default=1.0),
                control_risk=root.components["control_risk"],
                flexibility_risk=root.components["flexibility_risk"],
                pending=pending)


def _select(all_snapshots):
    if not all_snapshots:
        return []
    unique = list({item["state_hash"]: item for item in all_snapshots}.values())
    unique.sort(key=lambda item: (item["payload"]["observation"]["time"], item["state_hash"]))
    if len(unique) <= 6:
        return unique
    indexes = sorted({round((len(unique) - 1) * fraction) for fraction in
                      (0, 0.2, 0.4, 0.6, 0.8, 1.0)})
    candidates = [unique[index] for index in indexes]
    for item in candidates:
        item["features"] = _features(item["payload"])
    risk = lambda row: (row["features"]["zero_option"] * 2 +
                        row["features"]["one_option"] +
                        row["features"]["control_risk"] +
                        row["features"]["flexibility_risk"] +
                        (1 - row["features"]["min_battery_fraction"]))
    selected = [candidates[0], candidates[2], candidates[-1],
                max(candidates, key=lambda row: (risk(row), row["state_hash"])),
                min(candidates, key=lambda row: (risk(row), row["state_hash"])),
                candidates[3]]
    result = list({item["state_hash"]: item for item in selected}.values())
    for candidate in candidates:
        if len(result) >= 6:
            break
        if candidate["state_hash"] not in {item["state_hash"] for item in result}:
            result.append(candidate)
    return sorted(result, key=lambda row: (row["payload"]["observation"]["time"],
                                           row["state_hash"]))


def capture_worker(name, dod, seed, output):
    import evrp.optimizers as optimizers

    study = load_config(CONFIG_PATH)
    base = load_config(ROOT / study["base_controller"])
    options = dict(base, scenario_seed=seed, dynamicity=dod,
                   total_planning_time_limit=5.0, diagnostics=False,
                   trace_level="summary", algorithm="MPC_COMPLETION")
    instance, _, scenario, _ = prepare(name, options)
    observed = []
    original = optimizers.create_optimizer

    def recording_factory(method, config):
        optimizer = original(method, config)
        class RecordingOptimizer:
            def optimize(self, context):
                payload = _payload(context)
                observed.append(dict(scenario_id=scenario.identifier,
                                     instance_sha256=instance.sha256,
                                     epoch=len(observed), state_hash=identifier(payload),
                                     available_seconds=context.time_left(),
                                     features={}, payload=payload))
                return optimizer.optimize(context)
        return RecordingOptimizer()

    optimizers.create_optimizer = recording_factory
    try:
        result = EventDrivenSimulator(instance, scenario, simulation_config(options)).run()
    finally:
        optimizers.create_optimizer = original
    audit_result(result, instance, scenario)
    selected = [asdict(OptimizationSnapshot(**item)) for item in _select(observed)]
    save_json(output, dict(scenario_id=scenario.identifier, instance_sha256=instance.sha256,
                           source_sha256=source_hash(), captured=len(observed),
                           selected=selected))


def capture(case_limit=None):
    study = load_config(CONFIG_PATH)
    scenarios = list(cases(study))
    if len(scenarios) != 66:
        raise ValueError("Expected 66 development scenarios")
    if case_limit is not None:
        scenarios = scenarios[:case_limit]
    code = source_hash()
    records = []
    for index, (name, dod, seed) in enumerate(scenarios, 1):
        path = OUTPUT / "captures" / f"{name}_{dod:.2f}_{seed}_{code[:12]}.json.gz"
        if not path.exists():
            subprocess.run([sys.executable, "-m", "scripts.shadow_portfolio", "--capture-worker",
                            name, str(dod), str(seed), str(path)], cwd=ROOT, check=True)
        record = load_json(path)
        if record["source_sha256"] != code:
            raise ValueError("Stale snapshot capture")
        records.extend(record["selected"])
        print(f"capture {index}/{len(scenarios)} {name} selected={len(record['selected'])}", flush=True)
    hashes = [row["state_hash"] for row in records]
    if len(set(hashes)) != len(hashes):
        raise ValueError("Duplicate shadow state hash")
    save_json(OUTPUT / "selection.json", dict(
        status="frozen_selection" if len(scenarios) == 66 else "incomplete_selection",
        source_sha256=code, scenario_count=len(scenarios), snapshot_count=len(records),
        snapshots=records))


def shadow_worker(snapshot_path, method, output):
    if method not in SEARCH_METHODS:
        raise ValueError("Unknown shadow method")
    snapshot = load_json(snapshot_path)
    context = _context(snapshot["payload"], snapshot["available_seconds"])
    study = load_config(CONFIG_PATH)
    base = load_config(ROOT / study["base_controller"])
    config = simulation_config(dict(base, algorithm=method,
                                    total_planning_time_limit=study["total_planning_time_limit"]))
    started = perf_counter()
    result = create_optimizer(method, config).optimize(context)
    problem = _FleetProblem(dict(context.origins), context.observation, context.mpc, 3, 2)
    root = problem.initial(dict(context.constructor_routes))
    sequences = {k: tuple(action.destination for action in result.routes[k]
                          if action.kind == "serve") for k in problem.ids}
    replay = problem.change(root, sequences)
    if replay is None or replay.score != result.objective:
        raise AssertionError("Shadow optimizer failed independent exact objective replay")
    save_json(output, dict(snapshot_hash=snapshot["state_hash"], method=method,
                           objective=result.objective, components=dict(result.components),
                           runtime=result.runtime, wall_seconds=perf_counter() - started,
                           status=result.status, audit_pass=True,
                           diagnostics=dict(result.diagnostics.values)))


def run_shadow():
    selection = load_json(OUTPUT / "selection.json")
    if selection["status"] != "frozen_selection" or selection["source_sha256"] != source_hash():
        raise ValueError("Shadow selection must be complete and source-frozen first")
    rows = []
    for index, snapshot in enumerate(selection["snapshots"], 1):
        snapshot_path = OUTPUT / "selected" / f"{snapshot['state_hash']}.json.gz"
        if not snapshot_path.exists():
            save_json(snapshot_path, snapshot)
        for method in SEARCH_METHODS:
            path = OUTPUT / "raw" / f"{snapshot['state_hash']}_{method}.json.gz"
            if not path.exists():
                subprocess.run([sys.executable, "-m", "scripts.shadow_portfolio",
                                "--shadow-worker", str(snapshot_path), method, str(path)],
                               cwd=ROOT, check=True)
            result = load_json(path)
            if result["snapshot_hash"] != snapshot["state_hash"] or not result["audit_pass"]:
                raise ValueError("Stale or unaudited shadow result")
            rows.append(dict(snapshot_hash=snapshot["state_hash"], method=method,
                             raw=str(path.relative_to(ROOT)).replace("\\", "/"),
                             raw_sha256=sha256(path.read_bytes()).hexdigest(),
                             objective=result["objective"], runtime=result["runtime"]))
        save_json(OUTPUT / "manifest.json", dict(status="shadow_complete" if
                  len(rows) == selection["snapshot_count"] * len(SEARCH_METHODS)
                  else "shadow_incomplete", rows=rows))
        print(f"shadow {index}/{selection['snapshot_count']}", flush=True)


def analyze_shadow():
    selection = load_json(OUTPUT / "selection.json")
    manifest = load_json(OUTPUT / "manifest.json")
    if manifest["status"] != "shadow_complete":
        raise ValueError("Shadow experiment incomplete")
    grouped = {}
    for row in manifest["rows"]:
        if sha256((ROOT / row["raw"]).read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Shadow raw hash mismatch")
        grouped.setdefault(row["snapshot_hash"], {})[row["method"]] = row
    if len(grouped) != selection["snapshot_count"] or any(set(runs) != set(SEARCH_METHODS)
                                                           for runs in grouped.values()):
        raise ValueError("Unpaired shadow results")
    def objective(row):
        return tuple(row["objective"])
    sbs = min(SEARCH_METHODS, key=lambda method: (
        sum(objective(runs[method])[0] for runs in grouped.values()),
        -sum(objective(runs[method])[0] == 0 for runs in grouped.values()),
        sum(objective(runs[method])[1] for runs in grouped.values())))
    unique_wins = {method: 0 for method in SEARCH_METHODS}
    unique_service_wins = {method: 0 for method in SEARCH_METHODS}
    vbs_service_gain = 0
    for runs in grouped.values():
        best = min(objective(row) for row in runs.values())
        winners = [method for method, row in runs.items() if objective(row) == best]
        if len(winners) == 1:
            unique_wins[winners[0]] += 1
        best_service = min(objective(row)[0] for row in runs.values())
        service_winners = [method for method, row in runs.items()
                           if objective(row)[0] == best_service]
        if len(service_winners) == 1:
            unique_service_wins[service_winners[0]] += 1
        vbs_service_gain += -best[0] + objective(runs[sbs])[0]
    rate = sum(min(objective(row)[0] for row in runs.values()) <
               objective(runs[sbs])[0] for runs in grouped.values()) / len(grouped)
    gate = (sum(count >= max(2, round(0.02 * len(grouped)))
                for count in unique_service_wins.values()) >= 2 and rate >= 0.05)
    result = dict(sbs=sbs, snapshots=len(grouped), unique_wins=unique_wins,
                  unique_service_wins=unique_service_wins,
                  vbs_minus_sbs_served=vbs_service_gain,
                  vbs_service_win_fraction=rate, portfolio_gate_passed=gate,
                  vbs_is_analysis_only=True)
    save_json(OUTPUT / "sbs_vbs_gate.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "run", "analyze"), nargs="?")
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--capture-worker", nargs=4, help=argparse.SUPPRESS)
    parser.add_argument("--shadow-worker", nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.capture_worker:
        name, dod, seed, output = args.capture_worker
        capture_worker(name, float(dod), int(seed), output)
    elif args.shadow_worker:
        shadow_worker(*args.shadow_worker)
    elif args.command == "capture":
        capture(args.case_limit)
    elif args.command == "run":
        run_shadow()
    elif args.command == "analyze":
        print(analyze_shadow())
