"""Instrument all simulator phases on one already-seen development input only."""

import cProfile
from hashlib import sha256
import pstats

from evrp.experiments import audit_result, simulation_config
from evrp.instance import load_instance
from evrp.scenario import DynamicScenario
from evrp.simulator import EventDrivenSimulator
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json, writable_path
from scripts.run_reliability_study import OUTPUT, options


def main():
    prior = ROOT/"results/desaulniers/targeted_service_v1/development/protocol.json"
    old = load_json(prior)["scientific"]
    info = next(r for r in old["cases"] if r["case"] == ["c101_21_25", .25, 0])
    artifact = next(r for r in old["inputs"] if r["kind"] == "scenarios" and r["identifier"] == info["scenario_id"])
    path = ROOT/artifact["artifact"]
    if sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
        raise ValueError("Historical scenario bytes changed")
    instance = load_instance(BENCHMARK/f"{info['case'][0]}.txt")
    scenario = DynamicScenario.load(path, instance)
    config = load_json(OUTPUT/"preflight/initial_structural_protocol.json")["config"]
    profiles = []
    for method in config["methods"]:
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            result = EventDrivenSimulator(instance, scenario, simulation_config(options(config, info["case"], method, "original"))).run()
        finally:
            profiler.disable()
        audit = audit_result(result, instance, scenario)
        if not all(audit.values()):
            raise ValueError("Profiled simulation physical audit failed")
        stats = pstats.Stats(profiler)
        rows = [dict(file=k[0], function=k[2], calls=v[1], own_seconds=v[2], cumulative_seconds=v[3])
                for k, v in stats.stats.items() if "evrp" in k[0]]
        profiles.append(dict(method=method, audit=audit, simulation_seconds=result.metrics["complete_instance_wall_clock_seconds"],
                             planning_seconds=result.metrics["total_planning_time"],
                             functions=sorted(rows, key=lambda r: -r["cumulative_seconds"])[:60]))
        print("Whole-pipeline diagnostic profile:", method, flush=True)
    source = identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                         for p in sorted((ROOT/"evrp").rglob("*.py"))})
    save_json(OUTPUT/"diagnosis/whole_pipeline.json", dict(profiles=profiles, source_sha256=source,
        case=info["case"], scenario_sha256=artifact["sha256"],
        caveat="One previously seen 25-customer input. cProfile perturbs timings. Includes coordination, constructor, "
               "optimizer, final replay, dispatch and event overhead; excludes input loading and post-run audit. "
               "Diagnostic replay only, not a scientific campaign rerun, new-parent result, or timing certification."))
    lines = ["# Whole-simulation diagnostic profiling", "", "One already-seen c101_21_25 scenario; no reserved or new development parent.",
             "cProfile perturbs timing. This is not latency certification or a representative speedup claim.",
             "All profiled trajectories pass independent physical and information replay.", "",
             "| Engine | Function | Calls | Own seconds | Cumulative seconds |", "| --- | --- | ---: | ---: | ---: |"]
    for p in profiles:
        lines += [f"| {p['method']} | {r['function']} | {r['calls']} | {r['own_seconds']:.6f} | {r['cumulative_seconds']:.6f} |"
                  for r in p["functions"][:12]]
    writable_path(OUTPUT/"diagnosis/PROFILE.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
