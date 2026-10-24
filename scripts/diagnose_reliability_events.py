"""Read-only event-level loss bounds and diagnostic whole-pipeline profiling."""

from collections import Counter, defaultdict
from dataclasses import asdict, replace
from hashlib import sha256
from time import perf_counter
import cProfile
import pstats

from evrp.experiments import simulation_config
from evrp.fleet_mcts import construct_fleet_root
from evrp.instance import load_instance
from evrp.model import EPS
from evrp.optimizers import OptimizationContext, create_optimizer
from evrp.planning_budget import PlanningDeadlineExceeded, reset_deadline, set_deadline
from evrp.storage import BENCHMARK, ROOT, load_json, save_json, writable_path
from scripts.analyze_planning_losses import root_problem, routes, vehicle
from scripts.report_targeted_losses import arrival_bound

OUTPUT = ROOT / "results/desaulniers/reliability_v2"
SOURCE = ROOT / "results/desaulniers/targeted_service_v1"


def measured_origins(steps, time, after_dispatch=False):
    by_vehicle = defaultdict(list)
    for step in steps:
        by_vehicle[step["before"]["id"]].append(step)
    result, commitments = {}, {}
    for k, history in by_vehicle.items():
        history.sort(key=lambda s: (s["before"]["time"], s["after"]["time"]))
        state = vehicle(history[0]["before"])
        for step in history:
            start, end = step["before"]["time"], step["after"]["time"]
            if end <= time + EPS:
                state = vehicle(step["after"])
            elif start < time - EPS or (after_dispatch and start <= time + EPS):
                if step["action"]["kind"] == "wait":
                    # Simulator wait is idle_until, not an immutable busy action.
                    state = replace(vehicle(step["before"]), time=time)
                else:
                    state = vehicle(step["after"])
                    commitments[k] = step["action"]
                break
            else:
                break
        if not state.finished:
            result[k] = replace(state, time=max(time, state.time))
    return result, commitments


def diagnose():
    manifest = load_json(SOURCE / "development/manifest.json")
    protocol = load_json(SOURCE / "development/protocol.json")
    inputs = {r["identifier"]: r for r in protocol["scientific"]["inputs"] if r["kind"] == "scenarios"}
    losses, evidence = [], []
    for row in manifest["records"]:
        if row["variant"] != "original":
            continue
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Historical raw changed")
        raw = load_json(path)
        instance = load_instance(BENCHMARK / f"{row['instance']}.txt")
        artifact = inputs[raw["metadata"]["scenario_identifier"]]
        scenario_path = ROOT / artifact["artifact"]
        if sha256(scenario_path.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError("Archived scenario changed")
        releases = dict(load_json(scenario_path)["customer_release_times"])
        customers = {c.id: c for c in instance.customers}
        event_times = sorted({e["time"] for e in raw["events"]})
        for customer in raw["unserved_customers"]:
            samples = []
            for time in event_times:
                if time + EPS < releases[customer]:
                    continue
                for phase in (False, True):
                    origins, busy = measured_origins(raw["steps"], time, phase)
                    bound = arrival_bound(origins, customers[customer], instance.infrastructure.parameters)
                    samples.append(dict(time=time, phase="after_dispatch" if phase else "before_dispatch",
                                        **bound, busy_actions=busy))
            first = samples[0] if samples else None
            crossing = next((s for s in samples if s["time_eligible_vehicles"] == 0), None)
            category = ("unreachable_at_revelation" if first and first["time_eligible_vehicles"] == 0 else
                        "becomes_time_unreachable" if crossing else "feasibility_unknown")
            proof = crossing or first
            evidence_path = OUTPUT / "diagnosis/roots" / f"{row['case_index']:03}_{row['method']}_{customer}.json"
            if proof:
                origins, busy = measured_origins(raw["steps"], proof["time"], proof["phase"] == "after_dispatch")
                visible = [asdict(c) for c in instance.customers if releases[c.id] <= proof["time"] + EPS]
                save_json(evidence_path, dict(origins={k: asdict(v) for k, v in origins.items()}, busy_actions=busy, visible_customers=visible,
                          target=customer, time=proof["time"], phase=proof["phase"], source_raw=row["raw"],
                          source_raw_sha256=row["raw_sha256"], arrival_bound=proof))
                evidence.append(dict(path=evidence_path.relative_to(ROOT).as_posix(),
                                     sha256=sha256(evidence_path.read_bytes()).hexdigest()))
            losses.append(dict(instance=row["instance"], method=row["method"], case=row["case"], customer=customer,
                               release=releases[customer], due=customers[customer].due, category=category,
                               first_visible=first, first_zero=crossing, events=samples))
    save_json(OUTPUT / "diagnosis/events.json", dict(losses=losses, evidence=evidence,
              scope="All original Completion/ALNS targeted development trajectories; no holdout outcomes used",
              caveat="Direct-time lower bounds only. Positive counts are not feasible-route witnesses. "
                     "Zero counts are conditional on measured immutable commitments, not global infeasibility. "
                     "Simultaneous dispatch crossings are associations, not causal closed-loop effects."))
    counts = Counter(r["category"] for r in losses)
    lines = ["# Event-level service-loss diagnosis", "", f"Misses examined: {len(losses)}.", "",
             "All original targeted development trajectories; no new optimization and no holdout tuning.",
             "Direct-time bounds ignore energy, load, other obligations and safe return. A zero is a",
             "conditional measured-state timing certificate, not offline infeasibility or a causal proof.",
             "Idle waits are interruptible; charge, serve and return commitments are not.", "",
             "| Category | Misses |", "| --- | ---: |"]
    lines += [f"| {key} | {value} |" for key, value in sorted(counts.items())]
    lines += ["", "Feasible-route misses require a separately replayed route witness. No such witness is",
              "claimed from an optimistic arrival count. Unknown cases remain unknown.", "",
              "| Instance | Method | Customer | Release | Due | Category | First zero time |",
              "| --- | --- | --- | ---: | ---: | --- | ---: |"]
    lines += [f"| {r['instance']} | {r['method']} | {r['customer']} | {r['release']:.3f} | "
              f"{r['due']:.3f} | {r['category']} | {r['first_zero']['time'] if r['first_zero'] else 'NA'} |" for r in losses]
    writable_path(OUTPUT / "diagnosis/RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Event-level diagnoses:", dict(counts), flush=True)


def profile():
    saved = load_json(SOURCE / "diagnosis/manifest.json")["records"]
    reports = []
    for row in saved[:3]:
        root = load_json(ROOT / row["root"])
        raw = load_json(ROOT / root["source_raw"])
        trace = [d for d in raw["decisions"] if d.get("planning_trace")][root["source_decision_index"]]["planning_trace"]
        instance = load_instance(BENCHMARK / f"{root['instance']}.txt")
        for method in ("MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"):
            config = simulation_config({"algorithm": method, "total_planning_time_limit": 5})
            problem = root_problem(trace, instance, config.mpc)
            started, profiler = perf_counter(), cProfile.Profile()
            token = set_deadline(started + 4.75)
            profiler.enable()
            timeout = False
            try:
                inner = set_deadline(started + 2)
                try:
                    constructor = construct_fleet_root(problem.origins, routes(trace["retained_suffixes"]),
                                                       problem.observation, config.mpc).routes
                finally:
                    reset_deadline(inner)
                context = OptimizationContext(problem.observation, problem.origins, {}, {},
                    frozenset(problem.observation.customer_by_id), problem.observation.committed_ids,
                    frozenset(), constructor, len(problem.ids), started + 4.75, 0, config.mpc)
                create_optimizer(method, config).optimize(context)
            except PlanningDeadlineExceeded:
                timeout = True
            finally:
                profiler.disable()
                reset_deadline(token)
            stats = pstats.Stats(profiler)
            calls = [dict(file=key[0], line=key[1], function=key[2], calls=value[1],
                          own_seconds=value[2], cumulative_seconds=value[3]) for key, value in stats.stats.items()]
            reports.append(dict(root=row["root"], method=method, elapsed=perf_counter()-started,
                                deadline=timeout, functions=sorted(calls, key=lambda v: -v["cumulative_seconds"])[:40]))
    save_json(OUTPUT / "diagnosis/profile.json", dict(roots=3, profiles=reports,
              caveat="Instrumented offline replay, not latency certification or closed-loop performance"))
    print("Profiled complete constructor/optimizer pipelines:", len(reports), flush=True)


if __name__ == "__main__":
    diagnose()
    profile()
