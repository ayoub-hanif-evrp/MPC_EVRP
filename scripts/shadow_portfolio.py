"""Freeze observable MPC snapshots, then compare optimizers on identical states."""

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import ceil
from pathlib import Path
from statistics import median
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


def snapshot_protocol_hash():
    return sha256(Path(__file__).read_bytes()).hexdigest()


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
    min_tw_slack = min((context.observation.customer_by_id[c].due -
                        context.observation.time for c in problem.pending), default=0)
    return dict(time_fraction=min(1.0, context.observation.time / max(1.0, depot_due)),
                uncovered=int(root.score[0]),
                zero_option=sum(row[1] == 0 for row in ranked),
                one_option=sum(row[1] == 1 for row in ranked),
                min_tw_slack=min_tw_slack,
                tw_pressure=1.0 - min(1.0, max(0.0, min_tw_slack) /
                                      max(1.0, depot_due - context.observation.time)),
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
        for item in unique:
            item["features"] = _features(item["payload"])
        return unique
    indexes = sorted({round((len(unique) - 1) * step / 11) for step in range(12)})
    candidates = [unique[index] for index in indexes]
    for item in candidates:
        item["features"] = _features(item["payload"])
    dimensions = ("uncovered", "zero_option", "one_option", "control_risk",
                  "flexibility_risk", "min_battery_fraction", "tw_pressure")
    thresholds = {key: median(row["features"][key] for row in candidates)
                  for key in dimensions}
    variable = {key for key in dimensions if len({row["features"][key] for row in candidates}) > 1}
    def strata(row):
        return {(key, "high" if row["features"][key] > thresholds[key] else "low")
                for key in variable}
    result = list({row["state_hash"]: row for row in
                   (candidates[0], candidates[len(candidates) // 2], candidates[-1])}.values())
    covered = set().union(*(strata(row) for row in result))
    while len(result) < min(6, len(candidates)):
        remaining = [row for row in candidates if row["state_hash"] not in
                     {chosen["state_hash"] for chosen in result}]
        best = max(remaining, key=lambda row: (len(strata(row) - covered),
                                               row["features"]["zero_option"] +
                                               row["features"]["one_option"],
                                               row["state_hash"]))
        result.append(best)
        covered.update(strata(best))
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
                           source_sha256=source_hash(),
                           snapshot_protocol_sha256=snapshot_protocol_hash(),
                           captured=len(observed),
                           selected=selected))


def capture(case_limit=None):
    study = load_config(CONFIG_PATH)
    scenarios = list(cases(study))
    if len(scenarios) != 66:
        raise ValueError("Expected 66 development scenarios")
    if case_limit is not None:
        scenarios = scenarios[:case_limit]
    code = source_hash()
    protocol = snapshot_protocol_hash()
    if case_limit is None:
        development = load_json(ROOT / "results" / "portfolio" / "development" / "manifest.json")
        if (development["status"] != "development_complete" or
                len(development["records"]) != 330 or
                any(row["source_sha256"] != code for row in development["records"])):
            raise ValueError("Full final-source development study must complete before shadow capture")
    records = []
    for index, (name, dod, seed) in enumerate(scenarios, 1):
        path = OUTPUT / "captures" / f"{name}_{dod:.2f}_{seed}_{code[:12]}_{protocol[:12]}.json.gz"
        if not path.exists():
            subprocess.run([sys.executable, "-m", "scripts.shadow_portfolio", "--capture-worker",
                            name, str(dod), str(seed), str(path)], cwd=ROOT, check=True)
        record = load_json(path)
        if (record["source_sha256"] != code or
                record["snapshot_protocol_sha256"] != protocol):
            raise ValueError("Stale snapshot capture")
        if case_limit is None and not 4 <= len(record["selected"]) <= 6:
            raise ValueError(f"Expected 4-6 observable states for {name}")
        records.extend(record["selected"])
        print(f"capture {index}/{len(scenarios)} {name} selected={len(record['selected'])}", flush=True)
    hashes = [row["state_hash"] for row in records]
    if len(set(hashes)) != len(hashes):
        raise ValueError("Duplicate shadow state hash")
    save_json(OUTPUT / "selection.json", dict(
        status="frozen_selection" if len(scenarios) == 66 else "incomplete_selection",
        source_sha256=code, snapshot_protocol_sha256=protocol,
        scenario_count=len(scenarios), snapshot_count=len(records),
        snapshots=records))


def shadow_worker(snapshot_path, method, selection_digest, output):
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
                           source_sha256=source_hash(),
                           snapshot_protocol_sha256=snapshot_protocol_hash(),
                           selection_sha256=selection_digest,
                           objective=result.objective, components=dict(result.components),
                           runtime=result.runtime, wall_seconds=perf_counter() - started,
                           status=result.status, audit_pass=True,
                           diagnostics=dict(result.diagnostics.values)))


def run_shadow():
    selection_path = OUTPUT / "selection.json"
    selection = load_json(selection_path)
    if (selection["status"] != "frozen_selection" or
            selection["scenario_count"] != 66 or
            not 66 * 4 <= selection["snapshot_count"] <= 66 * 6 or
            len(selection["snapshots"]) != selection["snapshot_count"] or
            len({row["state_hash"] for row in selection["snapshots"]}) !=
            selection["snapshot_count"] or
            selection["source_sha256"] != source_hash() or
            selection["snapshot_protocol_sha256"] != snapshot_protocol_hash()):
        raise ValueError("Shadow selection must be complete and source-frozen first")
    relative = selection_path.relative_to(ROOT).as_posix()
    try:
        committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"],
                                            cwd=ROOT, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as error:
        raise ValueError("Commit the complete snapshot selection before shadow outcomes") from error
    if committed != selection_path.read_bytes():
        raise ValueError("Shadow selection differs from committed preregistration")
    selection_digest = sha256(committed).hexdigest()
    rows = []
    for index, snapshot in enumerate(selection["snapshots"], 1):
        snapshot_path = OUTPUT / "selected" / f"{snapshot['state_hash']}.json.gz"
        if not snapshot_path.exists():
            save_json(snapshot_path, snapshot)
        for method in SEARCH_METHODS:
            path = OUTPUT / "raw" / (f"{snapshot['state_hash']}_{method}_"
                                      f"{source_hash()[:12]}_{selection_digest[:12]}.json.gz")
            if not path.exists():
                subprocess.run([sys.executable, "-m", "scripts.shadow_portfolio",
                                "--shadow-worker", str(snapshot_path), method,
                                selection_digest, str(path)],
                               cwd=ROOT, check=True)
            result = load_json(path)
            if (result["snapshot_hash"] != snapshot["state_hash"] or
                    result["method"] != method or not result["audit_pass"] or
                    result["source_sha256"] != source_hash() or
                    result["snapshot_protocol_sha256"] != snapshot_protocol_hash() or
                    result["selection_sha256"] != selection_digest):
                raise ValueError("Stale or unaudited shadow result")
            rows.append(dict(snapshot_hash=snapshot["state_hash"], method=method,
                             raw=str(path.relative_to(ROOT)).replace("\\", "/"),
                             raw_sha256=sha256(path.read_bytes()).hexdigest(),
                             objective=result["objective"], runtime=result["runtime"]))
        save_json(OUTPUT / "manifest.json", dict(selection_sha256=selection_digest,
                  source_sha256=source_hash(), status="shadow_complete" if
                  len(rows) == selection["snapshot_count"] * len(SEARCH_METHODS)
                  else "shadow_incomplete", rows=rows))
        print(f"shadow {index}/{selection['snapshot_count']}", flush=True)


def analyze_shadow():
    selection = load_json(OUTPUT / "selection.json")
    manifest = load_json(OUTPUT / "manifest.json")
    if manifest["status"] != "shadow_complete":
        raise ValueError("Shadow experiment incomplete")
    if manifest.get("selection_sha256") != sha256((OUTPUT / "selection.json").read_bytes()).hexdigest():
        raise ValueError("Shadow selection changed after optimizer outcomes")
    grouped = {}
    snapshots = {row["state_hash"]: row for row in selection["snapshots"]}
    for row in manifest["rows"]:
        raw_path = ROOT / row["raw"]
        if sha256(raw_path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Shadow raw hash mismatch")
        raw = load_json(raw_path)
        if (raw["snapshot_hash"] != row["snapshot_hash"] or
                raw["method"] != row["method"] or not raw["audit_pass"] or
                raw["objective"] != row["objective"] or
                raw["source_sha256"] != selection["source_sha256"] or
                raw["snapshot_protocol_sha256"] != selection["snapshot_protocol_sha256"] or
                raw["selection_sha256"] != manifest["selection_sha256"]):
            raise ValueError("Shadow raw and manifest disagree")
        runs = grouped.setdefault(row["snapshot_hash"], {})
        if row["method"] in runs:
            raise ValueError("Duplicate shadow method for state")
        runs[row["method"]] = raw
    if (set(grouped) != set(snapshots) or len(grouped) != selection["snapshot_count"] or
            any(set(runs) != set(SEARCH_METHODS) for runs in grouped.values())):
        raise ValueError("Unpaired shadow results")
    result = summarize_shadow(grouped, snapshots)
    save_json(OUTPUT / "sbs_vbs_gate.json", result)
    plot_shadow_win_map(grouped, snapshots)
    return result


def plot_shadow_win_map(grouped, snapshots):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = dict(MPC_MCTS="#2474a6", MPC_ALNS="#12806a",
                  MPC_HGS="#bd7b13", MPC_ACS="#a14851", TIE="#59636e")
    points = {method: ([], []) for method in colors}
    for state_hash, runs in grouped.items():
        best = min(tuple(row["objective"]) for row in runs.values())
        winners = [method for method, row in runs.items()
                   if tuple(row["objective"]) == best]
        winner = winners[0] if len(winners) == 1 else "TIE"
        features = snapshots[state_hash]["features"]
        points[winner][0].append(features["time_fraction"])
        points[winner][1].append(features["uncovered"] / max(1, features["pending"]))
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for method, (times, uncovered) in points.items():
        if times:
            ax.scatter(times, uncovered, s=22, alpha=0.65, color=colors[method],
                       label=method.replace("MPC_", "MPC + "))
    ax.set(xlabel="Current horizon fraction", ylabel="Constructor uncovered / pending",
           xlim=(0, 1), ylim=(-0.03, 1.03))
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUTPUT / "common_state_win_map.png", dpi=220)
    plt.close(fig)


def summarize_shadow(grouped, snapshots):
    if not grouped:
        raise ValueError("No shadow states")
    def objective(row):
        return tuple(row["objective"])
    def rank(method, runs):
        return sum(objective(row) < objective(runs[method]) for row in runs.values())
    sbs = min(SEARCH_METHODS, key=lambda method: (
        sum(objective(runs[method])[0] for runs in grouped.values()),
        -sum(objective(runs[method])[0] == 0 for runs in grouped.values()),
        sum(rank(method, runs) for runs in grouped.values()), method))
    unique_wins = {method: 0 for method in SEARCH_METHODS}
    unique_service_wins = {method: 0 for method in SEARCH_METHODS}
    strongest_states = {method: [] for method in SEARCH_METHODS}
    pairwise = {left: {} for left in SEARCH_METHODS}
    for left in SEARCH_METHODS:
        for right in SEARCH_METHODS:
            if left == right:
                continue
            pairwise[left][right] = dict(service_wins=0, service_ties=0,
                                         service_losses=0, canonical_wins=0,
                                         canonical_ties=0, canonical_losses=0,
                                         equal_service_states=0,
                                         fewer_evs_at_equal_service=0,
                                         equal_evs_at_equal_service=0,
                                         lower_distance_at_equal_service_and_evs=0)
    vbs_service_gain = 0
    for state_hash, runs in grouped.items():
        best = min(objective(row) for row in runs.values())
        winners = [method for method, row in runs.items() if objective(row) == best]
        if len(winners) == 1:
            unique_wins[winners[0]] += 1
            strongest_states[winners[0]].append(dict(state_hash=state_hash,
                                                      features=snapshots[state_hash]["features"]))
        best_service = min(objective(row)[0] for row in runs.values())
        service_winners = [method for method, row in runs.items()
                           if objective(row)[0] == best_service]
        if len(service_winners) == 1:
            unique_service_wins[service_winners[0]] += 1
        vbs_service_gain += -best[0] + objective(runs[sbs])[0]
        for left, opponents in pairwise.items():
            for right, counts in opponents.items():
                lhs, rhs = runs[left], runs[right]
                service_diff = objective(lhs)[0] - objective(rhs)[0]
                canonical_diff = (objective(lhs) > objective(rhs)) - (objective(lhs) < objective(rhs))
                counts[("service_wins" if service_diff < 0 else
                        "service_losses" if service_diff > 0 else "service_ties")] += 1
                counts[("canonical_wins" if canonical_diff < 0 else
                        "canonical_losses" if canonical_diff > 0 else "canonical_ties")] += 1
                if service_diff == 0:
                    counts["equal_service_states"] += 1
                    lhs_evs = lhs["components"]["activated_vehicles"]
                    rhs_evs = rhs["components"]["activated_vehicles"]
                    if lhs_evs < rhs_evs:
                        counts["fewer_evs_at_equal_service"] += 1
                    if lhs_evs == rhs_evs:
                        counts["equal_evs_at_equal_service"] += 1
                        if lhs["components"]["distance"] < rhs["components"]["distance"]:
                            counts["lower_distance_at_equal_service_and_evs"] += 1
    rate = sum(min(objective(row)[0] for row in runs.values()) <
               objective(runs[sbs])[0] for runs in grouped.values()) / len(grouped)
    gate = (sum(count >= max(2, round(0.02 * len(grouped)))
                for count in unique_service_wins.values()) >= 2 and rate >= 0.05)
    runtimes = {}
    for method in SEARCH_METHODS:
        values = sorted(runs[method]["wall_seconds"] for runs in grouped.values())
        runtimes[method] = dict(mean_seconds=sum(values) / len(values),
                                p95_seconds=values[ceil(0.95 * len(values)) - 1],
                                max_seconds=values[-1])
    result = dict(sbs=sbs, snapshots=len(grouped), unique_wins=unique_wins,
                  unique_service_wins=unique_service_wins,
                  vbs_minus_sbs_served=vbs_service_gain,
                  vbs_service_win_fraction=rate, pairwise=pairwise,
                  strongest_states=strongest_states, runtimes=runtimes,
                  portfolio_gate_passed=gate,
                  vbs_is_analysis_only=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "run", "analyze"), nargs="?")
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--capture-worker", nargs=4, help=argparse.SUPPRESS)
    parser.add_argument("--shadow-worker", nargs=4, help=argparse.SUPPRESS)
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
