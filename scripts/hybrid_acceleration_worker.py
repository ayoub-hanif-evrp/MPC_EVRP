"""Fresh-process physical-audit workers for the bounded hybrid study."""

import argparse
from dataclasses import asdict
from hashlib import sha256
from time import perf_counter, process_time

from evrp import proposal_memo
from evrp.experiments import audit_result, simulation_config
from evrp.fleet_mcts import _FleetProblem
from evrp.model import transition
from evrp.performance import Measurements
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, identifier, load_json, save_json
from scripts.performance_engineering_worker import corpus, load_case

OUTPUT = ROOT / "results/desaulniers/hybrid_acceleration_v1"


def options(protocol, index, method, variant):
    result = dict(protocol["cases"][index]["base_options"])
    result.update(protocol["common"])
    result.update(algorithm=method, proposal_cache_policy="original",
                  computation_policy="original", first_action_policy="original",
                  quality_policy="original", service_recovery_policy="original",
                  mcts_rollout_policy="original")
    if variant == "compiled_cpu_v1":
        result["proposal_cache_policy"] = "compiled_cpu_v1"
    elif variant == "quality_recovery_v1":
        result.update(quality_policy="epsilon_route_v1",
                      service_recovery_policy="critical_insert_v1")
    elif variant != "original":
        raise ValueError("Unknown hybrid variant")
    return result


def micro(protocol, index):
    from evrp.compiled_screen import available, prepare

    if not prepare():
        raise ValueError("Compiled pilot requires Numba in its isolated environment")
    instance, _ = load_case(protocol, index)
    origins, observation, routes, sequences = corpus(protocol, index, instance)
    config = simulation_config(options(protocol, index, "MPC_COMPLETION", "original")).mpc
    variants = {}
    for variant in ("original", "compiled_cpu_v1"):
        memo, token = proposal_memo.begin(incremental=variant != "original",
                                          fast_screen=variant != "original",
                                          compiled_screen=variant != "original")
        started = perf_counter()
        try:
            with Measurements() as measurements:
                problem = _FleetProblem(origins, observation, config, 3, 2)
                signatures = []
                for k, sequence in sequences:
                    targets = sorted(set(observation.customer_by_id) - set(sequence))[:4]
                    for customer in targets:
                        # Full fleet sequence shape is required by the option cache.
                        full = tuple(sequence if vehicle == k else () for vehicle in problem.ids)
                        signatures.append((k, sequence, customer, problem.screened_options(full, customer)))
                initial = problem.initial(routes)
                signatures.append(("objective", initial.score, initial.components))
            for k, actions in routes.items():
                state = origins[k]
                for action in actions:
                    state = transition(state, action, observation).after
            variants[variant] = dict(checksum=identifier(signatures), seconds=perf_counter() - started,
                                     screened_insertions=problem.screened_insertions,
                                     compiled_batches=measurements.report()["counts"].get("compiled_screen_batches", 0),
                                     proven_late=measurements.report()["counts"].get("compiled_screen_proven_late", 0),
                                     exact_physical_replay=True)
        finally:
            proposal_memo.end(token)
    if variants["original"]["checksum"] != variants["compiled_cpu_v1"]["checksum"]:
        raise ValueError("Compiled fixed-work candidate/objective mismatch")
    return dict(numba_available=available(), variants=variants)


def worker(kind, index, method, variant):
    from scripts.run_hybrid_acceleration import source_hash

    protocol = load_json(OUTPUT / "protocol.json")
    if source_hash() != protocol["source_sha256"]:
        raise ValueError("Frozen scientific source drift")
    job_id = f"r1_{kind}_{index}_{method}_{variant}"
    if not any(job_id == j["id"] for block in protocol["blocks"] for j in block["jobs"]):
        raise ValueError("Job outside protocol")
    path = OUTPUT / "raw" / f"{job_id}.json.gz"
    if path.exists():
        raise ValueError("Never overwrite raw evidence")
    started, cpu = perf_counter(), process_time()
    record = dict(job_id=job_id, protocol_identifier=identifier(protocol),
                  kind=kind, case_index=index, method=method, variant=variant)
    if kind == "micro":
        record["micro"] = micro(protocol, index)
    elif kind == "scenario":
        from evrp.compiled_screen import available

        if variant == "compiled_cpu_v1" and not available():
            raise ValueError("Compiled worker unexpectedly lacks Numba")
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
            raise ValueError("Scenario or fixed fleet mismatch")
        result.metadata.update(hybrid_protocol=identifier(protocol),
                               independent_audit=audit, source_sha256=protocol["source_sha256"])
        record.update(result=asdict(result), measurements=measurements.report())
    else:
        raise ValueError("Unknown worker kind")
    if source_hash() != protocol["source_sha256"]:
        raise ValueError("Source changed during worker")
    record.update(worker_wall_seconds=perf_counter()-started,
                  worker_cpu_seconds=process_time()-cpu)
    save_json(path, record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("micro", "scenario"))
    parser.add_argument("index", type=int)
    parser.add_argument("method")
    parser.add_argument("variant")
    args = parser.parse_args()
    worker(args.kind, args.index, args.method, args.variant)
