"""Bounded new-neighborhood witnesses and matched, instrumented cache ablation."""

from dataclasses import asdict
from hashlib import sha256
from time import perf_counter
import cProfile
import pstats

from evrp import proposal_memo
from evrp.flex_exchange import improve_first_controls
from evrp.instance import load_instance
from evrp.mpc import MPCConfig
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json, writable_path
from scripts.analyze_planning_losses import root_problem, routes
from scripts.diagnose_reliability_events import OUTPUT, SOURCE


def run():
    records, profiles = [], []
    source = identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                         for p in sorted((ROOT/"evrp").rglob("*.py"))})
    for index, row in enumerate(load_json(SOURCE/"diagnosis/manifest.json")["records"]):
        if sha256((ROOT/row["root"]).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Diagnostic root changed")
        root = load_json(ROOT/row["root"])
        raw = load_json(ROOT/root["source_raw"])
        if sha256((ROOT/root["source_raw"]).read_bytes()).hexdigest() != root["source_raw_sha256"]:
            raise ValueError("Historical raw changed")
        trace = [d for d in raw["decisions"] if d.get("planning_trace")][root["source_decision_index"]]["planning_trace"]
        instance = load_instance(BENCHMARK/f"{root['instance']}.txt")
        values = raw["effective_config"]["mpc"]
        config = MPCConfig(**(values | {"charge_fractions": tuple(values["charge_fractions"])}))
        problem = root_problem(trace, instance, config)
        initial = routes(trace["stages"]["validation"])
        selected, proof, record = improve_first_controls(problem.origins, initial, problem.observation,
            config, root["ready_vehicles"], seconds=1, reference_routes=routes(trace["stages"]["optimizer"]))
        path = OUTPUT/"diagnosis/exchange_roots"/f"{index:03}.json"
        save_json(path, dict(source_sha256=source, source_root=row, result=record,
                            selected_routes={k: [asdict(a) for a in v] for k, v in selected.items()},
                            independently_replayed=proof is not None,
                            role="Retrospective bounded observable-state probe, not online performance"))
        records.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha256(path.read_bytes()).hexdigest(),
                            improved=proof is not None, deadline=record["deadline_reached"],
                            candidates=record["candidates"]))
        if index < 6:
            # Identical route replay workload; no time-truncated optimizer or input changes.
            from evrp.repair import route_proposal
            for cached in (False, True):
                profiler = cProfile.Profile()
                memo, token = proposal_memo.begin() if cached else (None, None)
                started = perf_counter()
                profiler.enable()
                values = []
                try:
                    for _ in range(5):
                        for k, actions in initial.items():
                            values.append(route_proposal(problem.origins[k], actions, problem.observation, config))
                finally:
                    profiler.disable()
                    if token is not None:
                        proposal_memo.end(token)
                if not cached:
                    original = values
                elif values != original:
                    raise ValueError("Pure replay cache changed a proposal")
                stats = pstats.Stats(profiler)
                profiles.append(dict(root=index, cached=cached, seconds=perf_counter()-started,
                    hits=memo.hits if memo else 0, misses=memo.misses if memo else len(values),
                    functions=[dict(function=k[2], calls=v[1], own_seconds=v[2], cumulative_seconds=v[3])
                               for k, v in stats.stats.items() if k[2] in {"_evaluate", "route_proposal", "transition"}]))
    save_json(OUTPUT/"diagnosis/exchange_manifest.json", dict(records=records, source_sha256=source))
    save_json(OUTPUT/"diagnosis/cache_ablation.json", dict(profiles=profiles, source_sha256=source,
              caveat="Repeated fixed-work replay microbenchmark; not end-to-end speedup or closed-loop gain"))
    lines = ["# Bounded exchange probes and exact replay-cache ablation", "",
        f"Saved roots: {len(records)}. Strict canonical improvements: {sum(r['improved'] for r in records)}.",
        f"One-second diagnostic deadlines: {sum(r['deadline'] for r in records)}.",
        "No heuristic failure is called infeasible. Accepted witnesses retain measured busy commitments",
        "and are independently replayed through the original physical transitions.", "",
        "The cache ablation repeats identical routes five times, checks exact proposal equality, and",
        "reports fixed-work timing only. It is not a claim about online service or whole-pipeline speedup.", "",
        "| Root | Cached | Seconds | Hits | Misses |", "| --- | --- | ---: | ---: | ---: |"]
    lines += [f"| {r['root']} | {r['cached']} | {r['seconds']:.6f} | {r['hits']} | {r['misses']} |" for r in profiles]
    writable_path(OUTPUT/"diagnosis/PROBES.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(f"Exchange diagnostic roots {len(records)}, validated improvements {sum(r['improved'] for r in records)}", flush=True)


if __name__ == "__main__":
    run()
