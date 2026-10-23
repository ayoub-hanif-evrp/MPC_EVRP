"""Read-only first-visible insertion audit for missed development ALNS customers."""

import csv
from collections import Counter
from hashlib import sha256
from time import perf_counter

from evrp.audit import decode_result
from evrp.experiments import load_config, prepare
from evrp.fleet_mcts import _FleetProblem
from evrp.model import Observation
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, reset_deadline, set_deadline
from evrp.repair import build_route, route_proposal
from evrp.storage import ROOT, load_json, writable_path
from scripts.diagnose_mpc_enhancement import ready_states
from scripts import run_desaulniers_campaign as development


OUTPUT = ROOT / "results/desaulniers/publication_development/diagnostics"
FIELDS = ("instance", "dod", "seed", "customer", "decision_time", "ready_vehicles",
          "screened_options", "first_feasible_rank", "screened_rejections",
          "exact_failures_before_witness", "screened_out_witness", "chain_witness",
          "in_flight_first_dispatches", "status")
TIMELINE_FIELDS = ("instance", "dod", "seed", "customer", "release", "due", "time",
                   "visible", "soft_owner", "committed_owner", "former_owner_action",
                   "trigger", "soft_plan_lost")


def audit_customer(instance, result, decision, customer_id, mpc):
    ready = ready_states(instance, result, decision)
    base = dict(instance=instance.name, customer=customer_id,
                decision_time=decision["time"], ready_vehicles=len(ready),
                screened_options=0, first_feasible_rank="", screened_rejections="",
                exact_failures_before_witness=0, screened_out_witness="", chain_witness="",
                in_flight_first_dispatches=sum(
                    step.before.location.kind == "d" and not step.before.departed
                    and step.action.kind != "wait"
                    and step.before.time <= decision["time"] + 1e-8
                    and step.after.time > decision["time"] + 1e-8
                    for step in result.steps))
    if not ready:
        return base | {"status": "no_ready_vehicle"}
    visible = tuple(c for c in instance.customers if c.id in decision["available"])
    observation = Observation(decision["time"], instance.infrastructure, visible,
                              tuple((c, int(k)) for c, k in decision["committed_before"].items()))
    routes = {int(k): tuple(action for action in plan["actions"])
              for k, plan in decision["plans"].items() if int(k) in ready}
    from evrp.model import Action
    routes = {k: tuple(Action(**action) for action in actions) for k, actions in routes.items()}
    if any(route and route_proposal(ready[k], route, observation, mpc) is None
           for k, route in routes.items()):
        return base | {"status": "reconstructed_plan_mismatch"}
    sequences = {k: tuple(action.destination for action in routes.get(k, ())
                          if action.kind == "serve") for k in ready}
    if any(customer_id in sequence for sequence in sequences.values()):
        return base | {"status": "selected_soft_plan"}
    problem = _FleetProblem(ready, observation, mpc, 3, 2)
    problems = []
    rejections = Counter()
    for k, sequence in sequences.items():
        for pos in range(len(sequence) + 1):
            passed, _, reason = problem._screen_gap_detail(k, sequence, customer_id, pos)
            if not passed:
                rejections[reason] += 1
            else:
                problems.append((k, pos))
    base["screened_rejections"] = ";".join(f"{key}:{value}" for key, value in sorted(rejections.items()))
    options = problem.screened_options(tuple(sequences[k] for k in problem.ids), customer_id)
    base["screened_options"] = len(options)
    if {(k, pos) for _, _, k, pos, _ in options} != set(problems):
        raise ValueError("Screening enumeration mismatch")
    token = set_deadline(perf_counter() + 2.0)
    try:
        for rank, (_, _, k, pos, _) in enumerate(options, 1):
            sequence = sequences[k]
            proposed = sequence[:pos] + (customer_id,) + sequence[pos:]
            if problem._decode(k, proposed) is not None:
                return base | {"first_feasible_rank": rank,
                               "status": "feasible_in_top3" if rank <= 3 else "feasible_beyond_top3"}
            base["exact_failures_before_witness"] += 1
        for k, sequence in sequences.items():
            for pos in range(len(sequence) + 1):
                if (k, pos) in problems:
                    continue
                proposed = sequence[:pos] + (customer_id,) + sequence[pos:]
                if build_route(ready[k], proposed, observation, mpc) is not None:
                    return base | {"screened_out_witness": f"{k}:{pos}",
                                   "status": "screen_false_negative"}
    except PlanningDeadlineExceeded:
        return base | {"status": "probe_timeout"}
    finally:
        reset_deadline(token)
    token = set_deadline(perf_counter() + 2.0)
    try:
        initial = problem.initial(routes)
        chains = problem._ejection_chain_candidates(initial, customer_id, 2)
        if chains:
            return base | {"chain_witness": len(chains), "status": "ejection_chain_witness"}
    except PlanningDeadlineExceeded:
        return base | {"status": "chain_probe_timeout"}
    finally:
        reset_deadline(token)
    return base | {"status": "no_bounded_insertion_witness"}


def run():
    manifest = load_json(development.OUTPUT / "manifest.json")
    config = load_config(development.CONFIG)
    rows = []
    timeline = []
    for record in manifest["records"]:
        if record["method"] != "MPC_ALNS":
            continue
        path = ROOT / record["raw"]
        if sha256(path.read_bytes()).hexdigest() != record["raw_sha256"]:
            raise ValueError(f"Frozen trace hash mismatch: {path}")
        raw = load_json(path)
        result = decode_result(raw)
        if not result.unserved_customers:
            continue
        instance, _, scenario, _ = prepare(record["instance"],
                                           development.options(config, record["instance"],
                                                               record["dynamicity"], record["seed"],
                                                               record["method"]))
        if scenario.identifier != result.metadata["scenario_identifier"]:
            raise ValueError("Scenario mismatch")
        mpc_data = raw["effective_config"]["mpc"]
        mpc = MPCConfig(**(mpc_data | {"charge_fractions": tuple(mpc_data["charge_fractions"])}))
        due = {c.id: c.due for c in instance.customers}
        releases = dict(scenario.customer_release_times)
        for customer_id in result.unserved_customers:
            first = next((decision for decision in result.decisions
                          if customer_id in decision["available"]
                          and decision["time"] <= due[customer_id]), None)
            row = (audit_customer(instance, result, first, customer_id, mpc) if first else
                   dict.fromkeys(FIELDS, "") | {"instance": instance.name,
                                                  "customer": customer_id,
                                                  "status": "no_visible_decision_before_due"})
            row.update(dod=record["dynamicity"], seed=record["seed"])
            rows.append(row)
            former_owner = ""
            for decision in result.decisions:
                if decision["time"] < releases[customer_id] - 1e-8:
                    continue
                if decision["time"] > due[customer_id] + 1e-8:
                    break
                owner = str(decision.get("route_owners_after_repair", {}).get(customer_id, ""))
                committed = decision["committed_before"].get(customer_id, "")
                former_actions = (decision["plans"].get(former_owner, {}).get("actions", ())
                                  if former_owner else ())
                former_action = former_actions[0] if former_actions else {}
                timeline.append(dict(instance=instance.name, dod=record["dynamicity"],
                                     seed=record["seed"], customer=customer_id,
                                     release=releases[customer_id], due=due[customer_id],
                                     time=decision["time"],
                                     visible=customer_id in decision["available"],
                                     soft_owner=owner,
                                     committed_owner=committed,
                                     former_owner_action=(former_action.get("kind", "") + ":" +
                                                          former_action.get("destination", "")
                                                          if former_action else ""),
                                     trigger=decision["optimization_trigger_reason"],
                                     soft_plan_lost=bool(former_owner and not owner and not committed)))
                former_owner = owner
        print(f"{record['instance']} DoD={record['dynamicity']} probed", flush=True)
    rows.sort(key=lambda row: (row["instance"], row["dod"], row["customer"]))
    with writable_path(OUTPUT / "first_visible_alns_insertions.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with writable_path(OUTPUT / "alns_loss_timelines.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=TIMELINE_FIELDS)
        writer.writeheader()
        writer.writerows(timeline)
    counts = Counter(row["status"] for row in rows)
    no_ready = [row for row in rows if row["status"] == "no_ready_vehicle"]
    lost = {(row["instance"], row["dod"], row["seed"], row["customer"])
            for row in timeline if row["soft_plan_lost"]}
    lines = ["# First-visible ALNS insertion audit", "",
             "Development losses only, read from hash-checked frozen traces. The probe",
             "reconstructs ready-vehicle states and selected soft routes at the first",
             "decision where each missed customer is visible. Each customer has a",
             "two-second direct-insertion and two-second ejection-chain diagnostic",
             "deadlines. Feasible means the original route decoder",
             "and plant replay accept a one-customer insertion preserving the other",
             "customers in that ready vehicle's selected suffix. It does not prove that",
             "the original constructor examined that exact route or that the customer",
             "would ultimately be served in closed loop.", "",
             "| Outcome | Missed customers |", "| --- | ---: |"]
    lines.extend(f"| {status} | {count} |" for status, count in sorted(counts.items()))
    lines += ["", f"Among {len(no_ready)} first-visible no-ready losses, "
              f"{sum(int(row['in_flight_first_dispatches']) > 0 for row in no_ready)} had "
              "at least one EV in its initial depot-dispatch action at that decision. "
              "This is a temporal correlation, not evidence that waiting would have "
              "served the customer."]
    lines += ["", "A screening rejection without an independently decoded witness is",
              "not proof of infeasibility. Busy vehicles and alternative route orders",
              "are not exhaustively searched. See the CSV for measured details.", "",
              f"Soft-plan disappearance is recorded for {len(lost)} distinct losses",
              "across the decision timelines. This is a trace observation, not proof",
              "that the preceding physical action caused the disappearance. Full",
              "per-decision rows are in `alns_loss_timelines.csv`.", ""]
    writable_path(OUTPUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return rows


if __name__ == "__main__":
    run()
