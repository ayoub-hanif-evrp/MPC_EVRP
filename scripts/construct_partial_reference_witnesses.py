"""Materialize separate offline MP witnesses for timed-out reference cases."""

import csv
from hashlib import sha256

from evrp.external.replay import _charge_witness, replay_routes
from evrp.instance import energy, load_instance
from evrp.model import Action, Observation, transition
from evrp.reference import (ReferenceConfig, ReferenceSchedule, RouteTrace,
                            initial_vehicle, validate_reference)
from evrp.storage import BENCHMARK, PUBLISHED_SOLUTIONS, ROOT, writable_path
from scripts.audit_desaulniers_partial_solutions import parse


OUTPUT = ROOT / "results/desaulniers/enhancement_development/partial_reference_witnesses"
COVERAGE = ROOT / "results/desaulniers/reference_validation/coverage.csv"


def make_schedule(instance, routes, fleet, variant):
    replay = replay_routes(instance, routes, fleet)
    if not (replay.feasible and replay.complete):
        raise ValueError(f"Published order has no complete MP replay: {replay.reason}")
    nodes = instance.geometry.by_id
    observation = Observation(instance.infrastructure.depot.ready,
                              instance.infrastructure, instance.customers)
    traces = []
    for route in routes:
        if len(route) <= 2:
            continue
        sequence = tuple(route)
        charges = _charge_witness(instance, sequence)
        state = initial_vehicle(instance, len(traces))
        steps = []
        for position, key in enumerate(sequence[1:], 1):
            node = nodes[key]
            if node.kind == "f":
                arrival = state.battery - energy(state.location, node,
                                                  instance.infrastructure.parameters)
                action = Action("charge", key, arrival + charges[position])
            else:
                action = Action("serve" if node.kind == "c" else "return", key)
            step = transition(state, action, observation)
            steps.append(step)
            state = step.after
        traces.append(RouteTrace(tuple(step.served for step in steps if step.served),
                                 tuple(steps)))
    if len(traces) != fleet:
        raise ValueError("Published vehicle count differs from nonempty routes")
    schedule = ReferenceSchedule(instance.name, instance.sha256, ReferenceConfig(),
                                 tuple(traces), provenance=f"separate_{variant}_partial_LP_MP_witness")
    validate_reference(instance, schedule)
    return schedule


def construct():
    with COVERAGE.open(newline="", encoding="utf-8") as stream:
        unresolved = [row["instance"] for row in csv.DictReader(stream)
                      if row["reference_valid"] != "True"]
    rows = []
    for name in unresolved:
        instance = load_instance(BENCHMARK / f"{name}.txt")
        for variant in ("SP", "MP"):
            source = PUBLISHED_SOLUTIONS / variant / f"solution{name}"
            if not source.is_file():
                continue
            fleet, _, routes = parse(source)
            try:
                schedule = make_schedule(instance, routes, fleet, variant)
            except ValueError:
                continue
            target = OUTPUT / "references" / f"{name}.json"
            if target.exists():
                loaded = ReferenceSchedule.load(target, instance)
                if loaded.identifier != schedule.identifier:
                    raise ValueError(f"Existing witness differs: {name}")
            else:
                schedule.save(target)
            loaded = ReferenceSchedule.load(target, instance)
            rows.append((name, variant, fleet, loaded.total_distance,
                         source.relative_to(ROOT).as_posix(),
                         sha256(source.read_bytes()).hexdigest(),
                         target.relative_to(ROOT).as_posix(),
                         sha256(target.read_bytes()).hexdigest(), loaded.identifier))
            print(f"{name}: {variant} LP witness, K={fleet}", flush=True)
            break
    path = writable_path(OUTPUT / "manifest.csv")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("instance", "variant", "vehicles", "distance", "source",
                         "source_sha256", "reference", "reference_sha256", "reference_identifier"))
        writer.writerows(rows)
    report = ["# Separate offline partial-charge reference witnesses", "",
              "These are clairvoyant offline feasibility references, **not online MPC competitors**.",
              "Each published route order was given continuous LP charge quantities and replayed",
              "through the MP transition engine. Saved traces were independently replayed on load.",
              "They do not alter historical K_ref, dynamic scenarios, protocols, or results.", "",
              f"Timed-out cases examined: {len(unresolved)}; full-service witnesses: {len(rows)}.",
              "The other timed-out cases remain unresolved, not proven infeasible.", "",
              "| Instance | Source | Vehicles | Distance |", "| --- | --- | ---: | ---: |"]
    report.extend(f"| {name} | {variant} | {fleet} | {distance:.2f} |"
                  for name, variant, fleet, distance, *_ in rows)
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return rows


if __name__ == "__main__":
    construct()
