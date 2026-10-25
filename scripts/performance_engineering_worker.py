"""Fixed-work diagnostics and fresh-process, full-parameter scenario workers."""

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from time import perf_counter, process_time
import cProfile
import pstats
import tracemalloc

from evrp import proposal_memo
from evrp.experiments import audit_result, simulation_config
from evrp.fleet_mcts import _FleetProblem
from evrp.instance import load_instance
from evrp.model import Action, Observation, transition
from evrp.performance import Measurements
from evrp.repair import _build_route_original, _decode_one_station, build_route, route_proposal
from evrp.scenario import DynamicScenario
from evrp.simulator import EventDrivenSimulator
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json
from scripts.diagnose_reliability_events import measured_origins

OUTPUT = ROOT/"results/desaulniers/performance_engineering_v1"


def options(protocol, index, method, variant):
    result = dict(protocol["cases"][index]["base_options"])
    result.update(protocol["config"]["common"])
    result.update(algorithm=method, proposal_cache_policy=variant)
    return result


def load_case(protocol, index):
    info = protocol["cases"][index]
    instance = load_instance(BENCHMARK/f"{info['case'][0]}.txt")
    if instance.sha256 != info["instance_sha256"]:
        raise ValueError("Instance identity changed")
    for field in ("scenario", "reference"):
        row = info[field]
        if sha256((ROOT/row["path"]).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Archived input bytes changed")
    scenario = DynamicScenario.load(ROOT/info["scenario"]["path"], instance)
    if scenario.identifier != info["scenario_id"] or scenario.fleet_size != info["k_ref"]:
        raise ValueError("Scenario or reference fleet changed")
    return instance, scenario


def corpus(protocol, index, instance):
    info = protocol["cases"][index]
    path = ROOT/info["micro_raw"]["path"]
    if sha256(path.read_bytes()).hexdigest() != info["micro_raw"]["sha256"]:
        raise ValueError("Previously seen corpus raw changed")
    raw = load_json(path)
    decisions = [d for d in raw["decisions"] if d.get("optimization_latency_seconds") is not None]
    decision = decisions[protocol["config"]["micro_root_index"]]
    visible = set(decision["available"])
    observation = Observation(decision["time"], instance.infrastructure,
        tuple(c for c in instance.customers if c.id in visible),
        tuple((k, v) for k, v in sorted(decision["committed_before"].items())))
    origins, busy = measured_origins(raw["steps"], decision["time"])
    routes = {}
    for k, plan in decision["plans"].items():
        actions = tuple(Action(**a) for a in plan["actions"])
        last = max((i+1 for i, a in enumerate(actions) if a.kind == "serve"), default=0)
        routes[int(k)] = actions[:last]
    sequences, seen = [], set()
    cap = protocol["config"]["micro_max_service_prefix"]
    for k, actions in sorted(routes.items()):
        sequence = tuple(a.destination for a in actions if a.kind == "serve")[:cap]
        if not sequence:
            continue
        candidates = [sequence[:length] for length in range(1, len(sequence)+1)]
        candidates += [sequence[:i]+(sequence[i+1], sequence[i])+sequence[i+2:]
                       for i in range(min(3, len(sequence)-1))]
        for other in sorted(visible-set(sequence))[:2]:
            candidates.append(sequence+(other,))
        for sequence in candidates:
            key = k, sequence
            if key not in seen:
                seen.add(key)
                sequences.append(key)
    return origins, observation, routes, sequences[:protocol["config"]["micro_max_sequences"]]


def scope(variant):
    return proposal_memo.begin(incremental=variant == "incremental_v1") if variant != "original" else (None, None)


def fixed_work(protocol, index, variant, *, allocation=False):
    started = perf_counter()
    instance, _ = load_case(protocol, index)
    origins, observation, routes, sequences = corpus(protocol, index, instance)
    config = simulation_config(options(protocol, index, "MPC_COMPLETION", "original")).mpc
    preparation = perf_counter()-started
    phases, physical = [], []
    for name, decoder, selected in (("route_construction", build_route, sequences),
                                     ("forced_charging_fallback", _decode_one_station, sequences[:4])):
        _build_route_original.cache_clear()
        memo, token = scope(variant)
        before_wall, before_cpu = perf_counter(), process_time()
        outputs = []
        try:
            for k, sequence in selected:
                actions = decoder(origins[k], sequence, observation, config)
                proposal = route_proposal(origins[k], actions, observation, config) if actions else None
                outputs.append(dict(vehicle=k, sequence=sequence,
                                    actions=[asdict(a) for a in actions] if actions is not None else None,
                                    proposal=asdict(proposal) if proposal is not None else None))
                if actions:
                    physical.append((k, actions))
        finally:
            elapsed, cpu = perf_counter()-before_wall, process_time()-before_cpu
            if token is not None:
                proposal_memo.end(token)
        phases.append(dict(phase=name, unique_sequences=len(selected), wall_seconds=elapsed, cpu_seconds=cpu,
                           checksum=identifier(outputs), outputs=outputs,
                           memo_counts=dict(memo.counts) if memo else {},
                           replay_hits=memo.hits if memo else 0, replay_misses=memo.misses if memo else 0))
    memo, token = scope(variant)
    before_wall, before_cpu = perf_counter(), process_time()
    try:
        problem = _FleetProblem(origins, observation, config, 3, 2)
        plan = problem.initial(routes)
        objectives = [problem._score(plan.sequences, plan.actions, plan.costs) for _ in range(80)]
    finally:
        elapsed, cpu = perf_counter()-before_wall, process_time()-before_cpu
        if token is not None:
            proposal_memo.end(token)
    phases.append(dict(phase="repeated_exact_objective", calls=80, wall_seconds=elapsed, cpu_seconds=cpu,
                       checksum=identifier(objectives), memo_counts=dict(memo.counts) if memo else {}))
    # Audit with the unchanged physical function after every planning cache has closed.
    for k, actions in physical:
        state = origins[k]
        for action in actions:
            state = transition(state, action, observation).after
    return dict(preparation_seconds=preparation, phases=phases,
                distinct_routes=len(set(sequences)), independent_original_physical_replay=True,
                scope="One fixed first-observation root, up to twelve unique candidates and eight-service prefixes. "
                      "Forced fallback and repeated-objective timings are microbenchmarks, not whole-scenario gains.")


def simulation(protocol, index, method, variant):
    started, cpu_started = perf_counter(), process_time()
    instance, scenario = load_case(protocol, index)
    preparation = perf_counter()-started
    with Measurements() as measurements:
        result = EventDrivenSimulator(instance, scenario, simulation_config(options(protocol, index, method, variant))).run()
    simulation_wall, simulation_cpu = perf_counter()-started-preparation, process_time()-cpu_started
    audit_started = perf_counter()
    try:
        audit = audit_result(result, instance, scenario)
        if not all(audit.values()) or result.metrics["max_optimization_latency"] > 5+1e-6:
            raise ValueError("Independent physical/information replay or five-second limit failed")
    except Exception:
        save_json(OUTPUT/"failures"/f"{index}_{method}_{variant}_audit_trace.json.gz",asdict(result))
        raise
    info = protocol["cases"][index]
    if result.metadata["K_ref"] != info["k_ref"] or result.metadata["scenario_identifier"] != info["scenario_id"]:
        raise ValueError("Matched inputs or fleet mismatch")
    result.metadata.update(performance_protocol=identifier(protocol), performance_variant=variant,
                           independent_audit=audit, source_sha256=protocol["source_sha256"])
    timing = dict(preparation_seconds=preparation, simulation_seconds=simulation_wall,
                  cpu_seconds_before_audit=simulation_cpu, audit_seconds=perf_counter()-audit_started,
                  constructor_seconds=sum(d.get("constructor_seconds", 0) for d in result.decisions),
                  optimizer_seconds=sum((d.get("optimizer") or {}).get("runtime", 0) for d in result.decisions),
                  final_validation_seconds=sum(d.get("final_validation_seconds", 0) for d in result.decisions),
                  nonplanning_simulation_seconds=max(0, simulation_wall-result.metrics["total_planning_time"]))
    return result, timing, measurements.report()


def worker(kind, index, method, variant):
    from scripts.run_performance_engineering import source_hash
    protocol = load_json(OUTPUT/"protocol.json")
    if protocol["source_sha256"] != source_hash():
        raise ValueError("Frozen performance worker source drift")
    job_id = f"{kind}_{index}_{method}_{variant}"
    path = OUTPUT/"raw"/f"{job_id}.json.gz"
    if path.exists():
        raise ValueError("Never overwrite a finished, failed or unfavorable worker")
    if not any(j["id"] == job_id for b in protocol["blocks"] for j in b["jobs"]):
        raise ValueError("Job outside the frozen engineering design")
    cpu_started, started = process_time(), perf_counter()
    record = dict(job_id=job_id, protocol_identifier=identifier(protocol), kind=kind,
                  case_index=index, method=method, variant=variant)
    if kind in {"micro", "allocation"}:
        if kind == "allocation":
            tracemalloc.start()
        record["fixed_work"] = fixed_work(protocol, index, variant)
        if kind == "allocation":
            current, peak = tracemalloc.get_traced_memory()
            record["allocation"] = dict(current_bytes=current, peak_bytes=peak,
                note="Python allocations during fixed-work preparation/evaluation, not total process RSS")
            tracemalloc.stop()
    elif kind == "optimizer_profile":
        from evrp.optimizers import OptimizationContext, create_optimizer
        instance, _ = load_case(protocol,index)
        origins, observation, routes, _ = corpus(protocol,index,instance)
        config=simulation_config(options(protocol,index,method,variant))
        profiler=cProfile.Profile()
        memo,token=scope(variant)
        try:
            with Measurements() as measurements:
                profiler.enable()
                context=OptimizationContext(observation,origins,{}, {},frozenset(observation.customer_by_id),
                    observation.committed_ids,frozenset(),routes,protocol["cases"][index]["k_ref"],
                    perf_counter()+4.75,0,config.mpc)
                result=create_optimizer(method,config).optimize(context)
        finally:
            profiler.disable()
            if token is not None:
                proposal_memo.end(token)
        for k,actions in result.routes.items():
            if actions and route_proposal(origins[k],actions,observation,config.mpc) is None:
                raise ValueError("Profiled optimizer route failed uncached physical replay")
        stats=pstats.Stats(profiler)
        record.update(profile=[dict(file=k[0],line=k[1],function=k[2],calls=v[1],own_seconds=v[2],
                                    cumulative_seconds=v[3]) for k,v in stats.stats.items()],
                      measurements=measurements.report(),independent_profile_route_replay=True,
                      scope="One saved observable root, full iteration parameters and 4.75-second inner search cap; "
                            "cProfile perturbs search and is not unprofiled decision timing evidence.")
    elif kind in {"profile", "pilot"}:
        profiler = cProfile.Profile() if kind == "profile" else None
        if profiler:
            profiler.enable()
        try:
            result, timings, measurements = simulation(protocol, index, method, variant)
        finally:
            if profiler:
                profiler.disable()
        record.update(result=asdict(result), timing=timings, measurements=measurements)
        if profiler:
            stats = pstats.Stats(profiler)
            record["profile"] = [dict(file=k[0], line=k[1], function=k[2], calls=v[1],
                                     own_seconds=v[2], cumulative_seconds=v[3]) for k, v in stats.stats.items()]
    else:
        raise ValueError("Unknown job kind")
    if protocol["source_sha256"] != source_hash():
        raise ValueError("Source changed during performance worker")
    record.update(worker_wall_seconds=perf_counter()-started, worker_cpu_seconds=process_time()-cpu_started,
                  global_route_cache=_build_route_original.cache_info()._asdict())
    serialization_started = perf_counter()
    save_json(path, record)
    save_json(OUTPUT/"serialization"/f"{job_id}.json", dict(seconds=perf_counter()-serialization_started,
              raw_bytes=path.stat().st_size, raw_sha256=sha256(path.read_bytes()).hexdigest()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("micro", "profile", "allocation", "optimizer_profile", "pilot"))
    parser.add_argument("index", type=int)
    parser.add_argument("method")
    parser.add_argument("variant")
    args = parser.parse_args()
    worker(args.kind, args.index, args.method, args.variant)
