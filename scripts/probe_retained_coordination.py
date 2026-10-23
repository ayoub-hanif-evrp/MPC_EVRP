"""Check an exact forced-choice shortcut against three-stage MILP coordination."""

from statistics import median
from time import perf_counter

from evrp.continuity import reserved_customers, route_observation, with_soft_incumbent
from evrp.coordinator import coordinate, forced_retained_choice
from evrp.instance import load_instance
from evrp.mpc import MPCConfig, PlanningResult
from evrp.simulator import idle_proposal
from evrp.storage import BENCHMARK, ROOT, load_json, save_json, writable_path
from scripts.analyze_planning_losses import root_problem, routes


OUTPUT = ROOT / "results/desaulniers/publication_development/coordination_probe_v1"
CAPTURE = ROOT / "results/desaulniers/publication_development/instrumented_v1"


def run():
    manifest = load_json(CAPTURE / "manifest.json")
    records = []
    for record in manifest["records"]:
        raw = load_json(ROOT / record["raw"])
        instance = load_instance(BENCHMARK / f"{record['instance']}.txt")
        values = raw["effective_config"]["mpc"]
        config = MPCConfig(**(values | {"charge_fractions": tuple(values["charge_fractions"])}))
        traces = [decision for decision in raw["decisions"]
                  if decision.get("planning_trace") and decision["planning_trace"]["retained_suffixes"]][:3]
        for decision in traces:
            trace = decision["planning_trace"]
            problem = root_problem(trace, instance, config)
            busy = {int(k) for k in trace["busy_actions"]}
            ready = [k for k in problem.ids if k not in busy]
            retained = routes(trace["retained_suffixes"])
            frozen = {k: actions for k, actions in retained.items() if k not in ready}
            candidates = {}
            for k in ready:
                observation = route_observation(problem.observation, frozen, k)
                incumbent = with_soft_incumbent(
                    PlanningResult((), idle_proposal(problem.origins[k], observation, config)),
                    problem.origins[k], observation, config, retained.get(k, ()))
                candidates[k] = incumbent.candidates
            kwargs = dict(available=frozenset(problem.observation.customer_by_id),
                          background_intents=reserved_customers(frozen))
            committed = problem.observation.committed_ids
            fast_times, milp_times = [], []
            for _ in range(20):
                start = perf_counter()
                actual = coordinate(candidates, committed, **kwargs)
                milp_times.append(perf_counter() - start)
                start = perf_counter()
                fast = forced_retained_choice(candidates, committed, **kwargs)
                fast_times.append(perf_counter() - start)
                if fast is None or {k: p.actions for k, p in actual.items()} != {k: p.actions for k, p in fast.items()}:
                    raise ValueError("Forced-choice shortcut differs from MILP output")
            records.append(dict(instance=instance.name, time=decision["time"], ready_vehicles=len(ready),
                                repeats=20, all_routes_equal=True,
                                median_milp_seconds=median(milp_times),
                                median_forced_choice_seconds=median(fast_times),
                                source_raw=record["raw"], source_raw_sha256=record["raw_sha256"]))
    save_json(OUTPUT / "measurements.json", records)
    lines = ["# Forced retained-route coordination probe", "",
             "A retained route is forced by maximum coverage when each ready EV has at",
             "most one positive-coverage proposal and those proposals are mutually",
             "disjoint and disjoint from immutable background routes. EVs without",
             "coverage have exactly one fallback. There is then no remaining activation",
             "or distance choice. Unsupported inputs return to general coordination.", "",
             "The shortcut was compared with the unchanged three-stage MILP on recorded",
             "observable development roots. Every selected action sequence must match.", "",
             "| Instance | Time | Ready EVs | MILP median ms | Shortcut median ms | Equal routes |",
             "| --- | ---: | ---: | ---: | ---: | --- |"]
    lines.extend(f"| {r['instance']} | {r['time']:.3f} | {r['ready_vehicles']} | "
                 f"{1000*r['median_milp_seconds']:.4f} | {1000*r['median_forced_choice_seconds']:.4f} | "
                 f"{r['all_routes_equal']} |" for r in records)
    lines += ["", "Each root was repeated 20 times on one machine. This microbenchmark",
              "establishes exact route agreement on these inputs; it does not establish",
              "closed-loop service gains or general hardware speedups.", ""]
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
