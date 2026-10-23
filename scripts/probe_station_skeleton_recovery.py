"""Search offline witnesses by preserving an existing route's charging stations."""

import csv
from dataclasses import asdict
from time import perf_counter

from evrp.enhanced_decoder import _charge_witness
from evrp.instance import energy, load_instance
from evrp.model import Action, InfeasibleAction, escape, transition
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, check_deadline, reset_deadline, set_deadline
from evrp.repair import route_proposal
from evrp.storage import BENCHMARK, ROOT, load_json, save_json, writable_path
from scripts.analyze_planning_losses import root_problem, routes


OUTPUT = ROOT / "results/desaulniers/publication_development/instrumented_v1"


def probe(trace, instance, config, target, seconds=5):
    problem = root_problem(trace, instance, config)
    selected = routes(trace["stages"]["validation"])
    token = set_deadline(perf_counter() + seconds)
    tested = 0
    try:
        for k in problem.ids:
            original = selected.get(k, ())
            sequence = tuple(a.destination for a in original if a.kind == "serve")
            if target in sequence:
                continue
            state = problem.origins[k]
            original_proposal = route_proposal(state, original, problem.observation, config) if original else None
            if original and original_proposal is None:
                raise ValueError("Selected recorded route is not replayable")
            end = original_proposal.predicted_end_state if original_proposal else state
            tail = escape(end, problem.observation.infrastructure)
            if tail is None:
                continue
            stops = tuple(problem.observation.infrastructure.node_by_id[a.destination]
                          if a.kind == "charge" else problem.observation.customer_by_id[a.destination]
                          for a in original if a.kind in {"serve", "charge"})
            customer = problem.observation.customer_by_id[target]
            for gap in range(len(stops) + 1):
                check_deadline()
                position = sum(node.kind == "c" for node in stops[:gap])
                if not problem._screen_gap(k, sequence, target, position)[0]:
                    continue
                order = stops[:gap] + (customer,) + stops[gap:] + tail.path
                witness = _charge_witness(state, order, problem.observation)
                tested += 1
                if witness is None:
                    continue
                measured, actions = state, []
                try:
                    for i, node in enumerate(order):
                        if node.kind == "d":
                            break
                        if node.kind == "f":
                            arrival = measured.battery - energy(measured.location, node,
                                                               problem.observation.infrastructure.parameters)
                            action = Action("charge", node.id, arrival + witness[i])
                        else:
                            action = Action("serve", node.id)
                        measured = transition(measured, action, problem.observation).after
                        actions.append(action)
                    last = max((i for i, action in enumerate(actions) if action.kind == "serve"), default=-1)
                    actions = tuple(actions[:last + 1])
                    proposal = route_proposal(state, actions, problem.observation, config)
                    if proposal is None or set(proposal.unique_predicted_customer_set) != set(sequence) | {target}:
                        continue
                    return dict(status="station_skeleton_witness", vehicle=k,
                                actions=[asdict(action) for action in actions], tested=tested)
                except InfeasibleAction:
                    continue
    except PlanningDeadlineExceeded:
        return dict(status="probe_timeout", tested=tested)
    finally:
        reset_deadline(token)
    return dict(status="no_bounded_skeleton_witness", tested=tested)


def run():
    manifest = load_json(OUTPUT / "manifest.json")
    with (OUTPUT / "loss_transition_probes.csv").open(newline="", encoding="utf-8") as stream:
        losses = list(csv.DictReader(stream))
    witnesses = []
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
            result = probe(decision["planning_trace"], instance, config, row["customer"])
            result.update(instance=instance.name, dod=record["dynamicity"], seed=record["seed"],
                          time=decision["time"], customer=row["customer"])
            witnesses.append(result)
            print(f"{instance.name} {row['customer']}: {result['status']} ({result['tested']} LPs)", flush=True)
    save_json(OUTPUT / "station_skeleton_probes.json", witnesses)
    lines = ["# Selective charging-station skeleton recovery probe", "",
             "Each diagnostic probe preserves the selected fleet's customer orders and",
             "each changed route's existing station order, inserts one missed customer,",
             "and solves continuous linear charge quantities. It uses only the recorded",
             "observable root, including after-states of busy actions. Successful routes",
             "are replayed through the original plant and safe-return validator.", "",
             "Each root has at most five seconds of offline diagnostic work. A failure",
             "under this bounded search is not proof of infeasibility.", "",
             "| Instance | Customer | Time | Outcome | LPs tried |", "| --- | --- | ---: | --- | ---: |"]
    lines.extend(f"| {r['instance']} | {r['customer']} | {r['time']:.3f} | {r['status']} | {r['tested']} |"
                 for r in witnesses)
    writable_path(OUTPUT / "STATION_SKELETON.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
