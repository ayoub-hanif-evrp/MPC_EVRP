"""Read-only service-loss observations from audited corrected-final traces."""

import csv
from collections import Counter, defaultdict
from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.audit import decode_result
from evrp.experiments import load_config, prepare
from evrp.model import Action, Observation, try_transition
from evrp.reference import initial_vehicle
from evrp.storage import ROOT, load_json, writable_path
from scripts.run_desaulniers_final import CONFIG, OUTPUT, options
from scripts.verify_desaulniers_final import verify


DEST = ROOT / "results/desaulniers/service_diagnosis_v2"
FIELDS = ("instance", "family", "size", "dod", "seed", "method", "customer",
          "release", "deadline", "release_to_deadline", "first_visible_decision",
          "visible_decisions_before_due", "ever_in_selected_plan", "direct_idle_actions_at_first_decision",
          "busy_vehicles_at_release", "finished_vehicles_at_release", "observation")


def moving_at(events, time):
    moving, finished = set(), set()
    for event in sorted(events, key=lambda e: (e.time, {"release": 0, "complete": 1,
                                                      "dispatch": 2}.get(e.kind, 3))):
        if event.time >= time:
            break
        if event.kind == "dispatch" and event.action and event.action.kind != "wait":
            moving.add(event.vehicle_id)
        elif event.kind == "complete" and event.action:
            moving.discard(event.vehicle_id)
            if event.action.kind == "return":
                finished.add(event.vehicle_id)
    return moving, finished


def selected_in_plan(decision, customer):
    return any(action["kind"] == "serve" and action["destination"] == customer
               for plan in decision["plans"].values() for action in plan["actions"])


def direct_actions(instance, result, decision, customer):
    time = decision["time"]
    busy, finished = moving_at(result.events, time)
    visible = tuple(c for c in instance.customers if c.id in decision["available"])
    observation = Observation(time, instance.infrastructure, visible)
    count = 0
    for vehicle_id in range(result.metadata["K_ref"]):
        if vehicle_id in busy or vehicle_id in finished:
            continue
        steps = [step for step in result.steps if step.before.id == vehicle_id and
                 step.after.time <= time + 1e-8]
        state = max(steps, key=lambda step: step.after.time).after if steps else initial_vehicle(instance, vehicle_id)
        if state.time > time + 1e-8 or state.finished:
            continue
        candidate = try_transition(replace(state, time=time), Action("serve", customer), observation)
        count += candidate.feasible
    return count


def render():
    verify()
    manifest = load_json(OUTPUT / "manifest.json")
    config = load_config(CONFIG)
    scenarios = {}
    records = []
    outcomes = defaultdict(dict)
    for row in manifest["records"]:
        key = row["instance"], row["dynamicity"], row["seed"]
        outcomes[key][row["method"]] = row["customers_served"]
        if key not in scenarios:
            instance, reference, scenario, _ = prepare(
                row["instance"], options(config, *key, "MPC_COMPLETION"))
            scenarios[key] = instance, scenario
        instance, scenario = scenarios[key]
        raw = load_json(ROOT / row["raw"])
        result = decode_result(raw)
        release = dict(scenario.customer_release_times)
        customers = {c.id: c for c in instance.customers}
        for customer in raw["unserved_customers"]:
            c = customers[customer]
            visible = [d for d in result.decisions if customer in d["available"] and
                       d["time"] <= c.due + 1e-8]
            first = visible[0] if visible else None
            busy, finished = moving_at(result.events, release[customer])
            if not visible:
                observation = "no_visible_decision_before_due"
            elif any(selected_in_plan(d, customer) for d in visible):
                observation = "selected_in_plan_but_unserved"
            else:
                observation = "never_in_selected_plan"
            records.append(dict(instance=row["instance"], family=row["family"],
                                size=row["size"], dod=row["dynamicity"], seed=row["seed"],
                                method=row["method"], customer=customer,
                                release=round(release[customer], 6), deadline=c.due,
                                release_to_deadline=round(c.due - release[customer], 6),
                                first_visible_decision=round(first["time"], 6) if first else "",
                                visible_decisions_before_due=len(visible),
                                ever_in_selected_plan=observation == "selected_in_plan_but_unserved",
                                direct_idle_actions_at_first_decision=(direct_actions(instance, result, first, customer)
                                                                       if first else ""),
                                busy_vehicles_at_release=len(busy),
                                finished_vehicles_at_release=len(finished),
                                observation=observation))
    records.sort(key=lambda r: (r["method"], r["instance"], r["dod"], r["customer"]))
    path = writable_path(DEST / "unserved_observations.csv")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    categories = Counter(r["observation"] for r in records)
    by_method = Counter(r["method"] for r in records)
    alns_cases = Counter((r["instance"], r["dod"], r["seed"]) for r in records
                         if r["method"] == "MPC_ALNS")
    lines = ["# Corrected-final service-loss observations", "",
             "All 270 corrected-final traces were independently replayed before this report. "
             "Rows describe unserved customers; they are not causal labels or proofs of "
             "infeasibility. `direct_idle_actions_at_first_decision` counts feasible "
             "immediate service actions with a safe return, not feasible route insertions "
             "or guaranteed complete routes. The decision trace does not preserve every "
             "rejected insertion or search candidate, so optimizer failure cannot be "
             "inferred solely from a missing selected plan.", "",
             f"Unserved customer observations: {len(records)}.", "",
             "| Method | Unserved customer observations |", "| --- | ---: |"]
    lines.extend(f"| {method} | {by_method[method]} |" for method in
                 ("MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"))
    lines.extend(["", "| Observable trace category | Count |", "| --- | ---: |"])
    lines.extend(f"| {kind} | {count} |" for kind, count in sorted(categories.items()))
    lines.extend(["", "## Highest-loss ALNS scenarios", "",
                  "These cases are retrospective descriptions of the fixed final holdout, "
                  "not targets for algorithm tuning.", "",
                  "| Instance | DoD | Seed | ALNS served | Other methods served (Completion/MCTS/HGS/ACS) |",
                  "| --- | ---: | ---: | ---: | --- |"])
    for (name, dod, seed), count in alns_cases.most_common(8):
        scores = outcomes[name, dod, seed]
        other = "/".join(str(scores[m]) for m in
                         ("MPC_COMPLETION", "MPC_MCTS", "MPC_HGS", "MPC_ACS"))
        lines.append(f"| {name} | {dod} | {seed} | {scores['MPC_ALNS']}/{int(name.rsplit('_', 1)[1])} | {other} |")
    if alns_cases:
        case = alns_cases.most_common(1)[0][0]
        lines.extend(["", "## Example trace facts", "",
                      f"For `{case[0]}`, DoD {case[1]}, seed {case[2]}, ALNS left "
                      f"{alns_cases[case]} customers unserved. A selected plan can later change "
                      "before its action executes; the trace does not prove why.", "",
                      "| Customer | Release | Deadline | Busy EVs at release | First visible decision | "
                      "Direct feasible idle actions | Selected in a plan |",
                      "| --- | ---: | ---: | ---: | ---: | ---: | --- |"])
        for r in records:
            if (r["method"] == "MPC_ALNS" and
                    (r["instance"], r["dod"], r["seed"]) == case):
                lines.append(f"| {r['customer']} | {r['release']} | {r['deadline']} | "
                             f"{r['busy_vehicles_at_release']} | {r['first_visible_decision']} | "
                             f"{r['direct_idle_actions_at_first_decision']} | "
                             f"{r['ever_in_selected_plan']} |")
        lines.extend(["", "The full customer-level table also records finished EVs, number of "
                      "visible decisions before due, and trace category. These facts constrain, "
                      "but do not establish, the causal mechanism.", ""])
    writable_path(DEST / "REPORT.md").write_text("\n".join(lines).rstrip() + "\n",
                                                   encoding="utf-8")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = list(sorted(categories))
    display = {"never_in_selected_plan": "Never selected in a plan",
               "selected_in_plan_but_unserved": "Selected in a plan, unserved",
               "no_visible_decision_before_due": "No visible decision before due"}
    bars = ax.barh([display.get(k, k) for k in labels],
                   [categories[k] for k in labels], color="#2377a5")
    ax.bar_label(bars, padding=4)
    ax.set_xlim(0, max(categories.values()) * 1.12)
    ax.set(xlabel="Unserved customer observations (not causal diagnoses)")
    fig.tight_layout()
    fig.savefig(writable_path(DEST / "trace_categories.png"), dpi=300)
    plt.close(fig)
    print(f"Documented {len(records)} unserved-customer observations", flush=True)


if __name__ == "__main__":
    render()
