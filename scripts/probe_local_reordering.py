"""Bounded exhaustive customer-order witnesses on recorded development roots."""

import csv
from time import perf_counter

from evrp.instance import load_instance, travel_time
from evrp.model import EPS
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, check_deadline, reset_deadline, set_deadline
from evrp.repair import build_route, route_proposal
from evrp.storage import BENCHMARK, ROOT, load_json, save_json, writable_path
from scripts.analyze_planning_losses import root_problem, routes


OUTPUT = ROOT / "results/desaulniers/publication_development/instrumented_v1"


def reorder_probe(trace, instance, config, target, seconds=5):
    problem = root_problem(trace, instance, config)
    selected = routes(trace["stages"]["validation"])
    token = set_deadline(perf_counter() + seconds)
    expanded = decoded = eligible = 0
    try:
        customer_map = problem.observation.customer_by_id
        p = problem.observation.infrastructure.parameters
        for k in sorted(problem.ids, key=lambda k: (
                travel_time(problem.origins[k].location, customer_map[target], p), k)):
            sequence = tuple(a.destination for a in selected.get(k, ()) if a.kind == "serve")
            pool = frozenset(sequence) | {target}
            state = problem.origins[k]
            if (target in sequence or len(pool) > 8 or
                    sum(customer_map[c].demand for c in pool) > state.load + EPS):
                continue
            eligible += 1

            def orders(prefix, remaining, location, time):
                nonlocal expanded
                check_deadline()
                expanded += 1
                if not remaining:
                    yield prefix
                    return
                for c in sorted(remaining, key=lambda c: (customer_map[c].due,
                                travel_time(location, customer_map[c], p), c)):
                    node = customer_map[c]
                    start = max(time + travel_time(location, node, p), node.ready)
                    if start > node.due + EPS:
                        continue
                    yield from orders(prefix + (c,), remaining - {c}, node, start + node.service)

            for order in orders((), pool, state.location, state.time):
                decoded += 1
                actions = build_route(state, order, problem.observation, config)
                if actions is None:
                    continue
                proposal = route_proposal(state, actions, problem.observation, config)
                if proposal is not None:
                    return dict(status="local_reordering_witness", vehicle=k, sequence=order,
                                eligible_routes=eligible, expanded=expanded, decoded=decoded)
    except PlanningDeadlineExceeded:
        return dict(status="reordering_probe_timeout", eligible_routes=eligible,
                    expanded=expanded, decoded=decoded)
    finally:
        reset_deadline(token)
    return dict(status="no_bounded_reordering_witness", eligible_routes=eligible,
                expanded=expanded, decoded=decoded)


def run():
    manifest = load_json(OUTPUT / "manifest.json")
    with (OUTPUT / "loss_transition_probes.csv").open(newline="", encoding="utf-8") as stream:
        losses = list(csv.DictReader(stream))
    results = []
    for record in manifest["records"]:
        raw = load_json(ROOT / record["raw"])
        instance = load_instance(BENCHMARK / f"{record['instance']}.txt")
        values = raw["effective_config"]["mpc"]
        config = MPCConfig(**(values | {"charge_fractions": tuple(values["charge_fractions"])}))
        for row in losses:
            if (row["instance"], float(row["dod"]), int(row["seed"])) != (
                    record["instance"], record["dynamicity"], record["seed"]):
                continue
            decision = next(d for d in raw["decisions"] if d["time"] == float(row["time"]))
            result = reorder_probe(decision["planning_trace"], instance, config, row["customer"])
            result.update(instance=instance.name, dod=record["dynamicity"], seed=record["seed"],
                          time=decision["time"], customer=row["customer"])
            results.append(result)
            print(f"{instance.name} {row['customer']}: {result}", flush=True)
    save_json(OUTPUT / "local_reordering_probes.json", results)
    lines = ["# Small-route customer reordering probe", "",
             "At each missed-customer plan drop, enumerate time-screened permutations",
             "of one selected route's customers plus the target (at most eight total).",
             "Every witness uses the original decoder and plant, preserving all other",
             "fleet routes and hard commitments. Each root has five seconds of offline",
             "diagnostic computation. No witness or timeout does not prove infeasibility.", "",
             "| Instance | Customer | Outcome | Eligible routes | DFS nodes | Exact decodes |",
             "| --- | --- | --- | ---: | ---: | ---: |"]
    lines.extend(f"| {r['instance']} | {r['customer']} | {r['status']} | {r['eligible_routes']} | "
                 f"{r['expanded']} | {r['decoded']} |" for r in results)
    writable_path(OUTPUT / "LOCAL_REORDERING.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
