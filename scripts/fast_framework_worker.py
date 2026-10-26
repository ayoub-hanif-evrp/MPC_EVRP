"""Fresh-process, independently audited workers for the bounded development study."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from time import perf_counter, process_time

from evrp import proposal_memo
from evrp.experiments import audit_result, simulation_config
from evrp.fleet_mcts import _FleetProblem
from evrp.model import transition
from evrp.performance import Measurements
from evrp.repair import build_route, route_proposal
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json
from scripts.performance_engineering_worker import corpus, load_case

OUTPUT = ROOT / "results/desaulniers/fast_framework_v1/revision_1"


def options(protocol, index, method, variant):
    result = dict(protocol["cases"][index]["base_options"])
    result.update(protocol["common"])
    result["algorithm"] = method
    if variant == "enhanced":
        result.update(protocol["config"]["enhanced"])
        if method != "MPC_MCTS":
            result["mcts_rollout_policy"] = "original"
    return result


def micro(protocol, index):
    instance, _ = load_case(protocol, index)
    origins, observation, routes, sequences = corpus(protocol, index, instance)
    config = simulation_config(options(protocol, index, "MPC_COMPLETION", "original")).mpc
    outputs = {}
    for variant in ("original", "enhanced"):
        memo, token = proposal_memo.begin(incremental=variant == "enhanced",
                                          fast_screen=variant == "enhanced")
        started, cpu = perf_counter(), process_time()
        try:
            problem = _FleetProblem(origins, observation, config, 3, 2)
            rows = []
            for k, sequence in sequences:
                profile = problem._screen_profile(k, sequence)
                actions = build_route(origins[k], sequence, observation, config)
                proposal = route_proposal(origins[k], actions, observation, config) if actions else None
                if actions:
                    state = origins[k]
                    for action in actions:
                        state = transition(state, action, observation).after
                rows.append(dict(vehicle=k, sequence=sequence, profile=tuple(profile),
                                 actions=[asdict(a) for a in actions] if actions is not None else None,
                                 proposal=asdict(proposal) if proposal else None))
            plan = problem.initial(routes)
            scores = [problem._score(plan.sequences, plan.actions, plan.costs) for _ in range(80)]
            checksum = identifier(dict(rows=rows, scores=scores))
            outputs[variant] = dict(checksum=checksum, wall_seconds=perf_counter()-started,
                                    cpu_seconds=process_time()-cpu, counts=dict(memo.counts),
                                    screened_insertions=problem.screened_insertions,
                                    exact_decoded_options=problem.exact_decoded_options,
                                    route_count=len(rows), independent_replay=True)
        finally:
            proposal_memo.end(token)
    if outputs["original"]["checksum"] != outputs["enhanced"]["checksum"]:
        raise ValueError("Fast fixed-work mathematical or physical mismatch")
    return outputs


def worker(kind, index, method, variant):
    from scripts.run_fast_framework import source_hash

    protocol = load_json(OUTPUT / "protocol.json")
    if protocol["source_sha256"] != source_hash():
        raise ValueError("Frozen worker source drift")
    job_id = f"{kind}_{index}_{method}_{variant}"
    if not any(j["id"] == job_id for block in protocol["blocks"] for j in block["jobs"]):
        raise ValueError("Job outside preregistered development protocol")
    path = OUTPUT / "raw" / f"{job_id}.json.gz"
    if path.exists():
        raise ValueError("Existing evidence cannot be overwritten")
    started, cpu = perf_counter(), process_time()
    record = dict(job_id=job_id, protocol_identifier=identifier(protocol), kind=kind,
                  case_index=index, method=method, variant=variant)
    if kind == "micro":
        record["fixed_work"] = micro(protocol, index)
    elif kind == "pilot":
        instance, scenario = load_case(protocol, index)
        config = simulation_config(options(protocol, index, method, variant))
        with Measurements() as measurements:
            result = EventDrivenSimulator(instance, scenario, config).run()
        audit = audit_result(result, instance, scenario)
        if not all(audit.values()) or result.metrics["max_optimization_latency"] > 5 + 1e-6:
            save_json(OUTPUT / "failures" / f"{job_id}.json.gz", asdict(result))
            raise ValueError("Independent physical/information/deadline audit failed")
        info = protocol["cases"][index]
        if result.metadata["K_ref"] != info["k_ref"] or result.metadata["scenario_identifier"] != info["scenario_id"]:
            raise ValueError("Scenario or fleet drift")
        result.metadata.update(fast_framework_protocol=identifier(protocol), source_sha256=protocol["source_sha256"],
                               independent_audit=audit)
        record.update(result=asdict(result), measurements=measurements.report())
    else:
        raise ValueError("Unknown job")
    if protocol["source_sha256"] != source_hash():
        raise ValueError("Source changed during worker")
    record.update(worker_wall_seconds=perf_counter()-started,
                  worker_cpu_seconds=process_time()-cpu)
    save_json(path, record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("micro", "pilot"))
    parser.add_argument("index", type=int)
    parser.add_argument("method")
    parser.add_argument("variant")
    args = parser.parse_args()
    worker(args.kind, args.index, args.method, args.variant)
