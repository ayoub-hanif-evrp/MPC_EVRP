"""Audit instrumented development roots and test service-preserving recovery."""

import csv
from collections import Counter
from hashlib import sha256
from time import perf_counter

from evrp.audit import decode_result
from evrp.experiments import audit_result, load_config, prepare
from evrp.fleet_mcts import _FleetProblem, _SearchBudgetReached
from evrp.instance import Location
from evrp.model import Action, Observation, VehicleState
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, reset_deadline, set_deadline
from evrp.storage import ROOT, identifier, load_json, writable_path
from scripts.run_publication_campaign import configuration, options


def vehicle(data):
    values = dict(data)
    values["location"] = Location(**values["location"])
    values["route_history"] = tuple(values["route_history"])
    values["served_customers"] = tuple(values["served_customers"])
    if values["current_committed_action"] is not None:
        values["current_committed_action"] = Action(**values["current_committed_action"])
    return VehicleState(**values)


def routes(data):
    return {int(k): tuple(Action(**a) for a in actions) for k, actions in data.items()}


def covered(data):
    return {a["destination"] for actions in data.values() for a in actions if a["kind"] == "serve"}


def root_problem(trace, instance, mpc):
    origins = {int(k): vehicle(v) for k, v in trace["origins"].items()}
    visible = {customer["id"] for customer in trace["observation"]["customers"]}
    observation = Observation(trace["observation"]["time"], instance.infrastructure,
                              tuple(c for c in instance.customers if c.id in visible),
                              tuple(tuple(pair) for pair in trace["observation"]["committed_customers"]))
    return _FleetProblem(origins, observation, mpc, 3, 2)


def recovery_probe(trace, instance, mpc, target):
    problem = root_problem(trace, instance, mpc)
    token = set_deadline(perf_counter() + 2.0)
    try:
        plan = problem.initial(routes(trace["stages"]["validation"]))
        screened = problem.screened_options(plan.sequences, target)
        for rank, (_, _, k, position, _) in enumerate(screened, 1):
            sequence = plan.sequences[problem.ids.index(k)]
            candidate = problem.change(plan, {k: sequence[:position] + (target,) + sequence[position:]})
            if candidate is not None and candidate.score[0] < plan.score[0]:
                return "direct_insertion_witness", rank, candidate.score[0], problem.exact_decoded_options
        chains = problem._ejection_chain_candidates(plan, target, 2)
        if chains:
            return "ejection_chain_witness", "", min(p.score[0] for p in chains), problem.exact_decoded_options
        return "no_bounded_recovery_witness", "", "", problem.exact_decoded_options
    except (PlanningDeadlineExceeded, _SearchBudgetReached):
        return "recovery_probe_timeout", "", "", problem.exact_decoded_options
    finally:
        reset_deadline(token)


def analyze(config_path="configs/publication_diagnosis_v1.yaml"):
    _, config, output = configuration(config_path)
    protocol = load_json(output / "protocol.json")
    manifest = load_json(output / "manifest.json")
    if (manifest["status"] != "complete" or
            manifest["completed_runs"] != manifest["planned_runs"] or
            manifest["protocol_identifier"] != identifier(protocol)):
        raise ValueError("Instrumented campaign must be complete")
    rows, summaries = [], []
    events, rejection_reasons, decode_outcomes = Counter(), Counter(), Counter()
    dropped_events = dominated_decisions = 0
    for record in manifest["records"]:
        path = ROOT / record["raw"]
        if sha256(path.read_bytes()).hexdigest() != record["raw_sha256"]:
            raise ValueError("Instrumented raw hash mismatch")
        raw = load_json(path)
        result = decode_result(raw)
        case = config["cases"][record["case_index"]]
        instance, _, scenario, _ = prepare(case[0], options(config, case, record["method"], record["variant"]))
        if not all(audit_result(result, instance, scenario).values()):
            raise ValueError("Instrumented independent replay failed")
        values = raw["effective_config"]["mpc"]
        mpc = MPCConfig(**(values | {"charge_fractions": tuple(values["charge_fractions"])}))
        case_events = case_drops = 0
        for decision in result.decisions:
            trace = decision.get("planning_trace")
            if trace is None:
                continue
            dropped_events += trace["dropped_events"]
            case_events += len(trace["events"])
            final = covered(trace["stages"]["validation"])
            original = covered(trace["retained_suffixes"]) | covered(trace["invalid_suffixes"])
            for event in trace["events"]:
                events[event["kind"]] += 1
                if event["kind"] == "insertion_screen" and not event["passed"]:
                    rejection_reasons[event["reason"]] += 1
                if event["kind"] == "route_decode":
                    decode_outcomes[event["outcome"]] += 1
            if decision.get("optimizer"):
                objective = tuple(decision["optimizer"]["objective"])
                better = [e for e in trace["events"] if e["phase"] == "optimizer"
                          and e["kind"] in {"fleet_candidate", "incumbent"}
                          and tuple(e["score"]) < objective]
                dominated_decisions += bool(better)
            for target in sorted((original - final) & set(result.unserved_customers)):
                if target in covered(trace["invalid_suffixes"]):
                    stage = "suffix_replay"
                elif target not in covered(trace["stages"]["constructor"]):
                    stage = "coordination"
                elif target not in covered(trace["stages"]["optimizer"]):
                    stage = "constructor"
                else:
                    stage = "optimizer"
                outcome, rank, remaining, decodes = recovery_probe(trace, instance, mpc, target)
                rows.append(dict(instance=instance.name, dod=case[1], seed=case[2],
                                 customer=target, time=decision["time"], drop_stage=stage,
                                 trigger=decision["optimization_trigger_reason"],
                                 constructor_service=len(covered(trace["stages"]["optimizer"])),
                                 selected_service=len(final), recovery=outcome,
                                 insertion_rank=rank, remaining_uncovered=remaining,
                                 diagnostic_decodes=decodes))
                case_drops += 1
        summaries.append((instance.name, case[1], result.metrics["customers_served"], case_events, case_drops))
    fields = ("instance", "dod", "seed", "customer", "time", "drop_stage", "trigger",
              "constructor_service", "selected_service", "recovery", "insertion_rank",
              "remaining_uncovered", "diagnostic_decodes")
    with writable_path(output / "loss_transition_probes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = ["# Instrumented development diagnosis", "",
             "These are development diagnostic runs. Each raw record has a source-frozen",
             "protocol, matched scenario identity, SHA-256 manifest, and independent plant",
             "replay. Instrumentation consumes decision time, so these timings do not",
             "estimate uninstrumented algorithm performance.", "",
             "| Instance | DoD | Served | Trace events | Missed-customer plan drops |",
             "| --- | ---: | ---: | ---: | ---: |"]
    lines.extend(f"| {name} | {dod} | {served} | {count} | {drops} |"
                 for name, dod, served, count, drops in summaries)
    lines += ["", f"Dropped trace events: {dropped_events}. Decisions with a recorded, fully",
              f"scored optimizer candidate better than the selected objective: {dominated_decisions}.",
              "", "## Measured rejection events", "", "| Screening reason | Events |", "| --- | ---: |"]
    lines.extend(f"| {reason} | {count} |" for reason, count in rejection_reasons.most_common())
    lines += ["", "| Decoder outcome | Events (including cache hits) |", "| --- | ---: |"]
    lines.extend(f"| {reason} | {count} |" for reason, count in decode_outcomes.most_common())
    lines += ["", "## Missed-customer plan transitions", "",
              "| Stage | Recovery probe result | Transitions |", "| --- | --- | ---: |"]
    counts = Counter((row["drop_stage"], row["recovery"]) for row in rows)
    lines.extend(f"| {stage} | {outcome} | {count} |" for (stage, outcome), count in sorted(counts.items()))
    lines += ["", "Recovery probes use the exact recorded root, including after-states of",
              "immutable busy actions, all currently observable requests, and the selected",
              "fleet suffixes. A witness preserves every customer in the selected suffixes",
              "and inserts an additional missed customer. Bounded failure or timeout does",
              "not prove infeasibility. Counts are diagnostic transitions, not independent",
              "benchmark samples; they do not establish the closed-loop benefit of a fix.", ""]
    equal = sum(row["constructor_service"] == row["selected_service"] for row in rows)
    lines += [f"Of these {len(rows)} transitions, {equal} preserve the same immediate service",
              "count while replacing a previously planned customer. The canonical",
              "objective allows such a swap when its lower-priority terms improve.",
              "This motivates a separate search variant retaining incumbent coverage",
              "during equal-service improvements; its benefit requires new paired runs.", ""]
    writable_path(output / "DIAGNOSIS.md").write_text("\n".join(lines), encoding="utf-8")
    return rows


if __name__ == "__main__":
    analyze()
