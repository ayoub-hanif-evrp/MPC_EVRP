"""Audit saved MP traces and report observable service loss without retuning them."""

import csv
from collections import Counter, defaultdict
from dataclasses import replace
from hashlib import sha256
from statistics import mean

from evrp.audit import decode_result
from evrp.experiments import audit_result, load_config, prepare
from evrp.model import Action, EPS, Observation, try_transition
from evrp.mpc import MPCConfig
from evrp.reference import initial_vehicle
from evrp.repair import build_route
from evrp.storage import ROOT, load_json, writable_path
from scripts import run_desaulniers_campaign as development
from scripts import run_desaulniers_robustness_v3 as robustness


DEST = ROOT / "results/desaulniers/enhancement_development/diagnostics"
COHORTS = (("development", development), ("historical_robustness", robustness))
LOSS_FIELDS = ("cohort", "instance", "family", "size", "dod", "seed", "method",
               "customer", "release", "deadline", "first_visible_decision",
               "visible_decisions", "ever_selected_in_plan", "direct_ready_actions",
               "ready_vehicles", "committed_vehicles", "observation")
TIME_FIELDS = ("cohort", "method", "runs", "optimization_decisions", "mean_latency_s",
               "p95_latency_s", "max_latency_s", "constructor_s", "optimizer_s",
               "unattributed_s", "screened_insertions", "exact_decodes",
               "zero_option_customers", "deadline_reached")
PROBE_FIELDS = ("instance", "dod", "seed", "customer", "first_visible_decision",
                "ready_vehicles", "single_customer_route_vehicles", "ever_selected_in_plan")


def _percentile(values, percentile):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    low = int(index)
    return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (index - low)


def _selected(decision, customer):
    return any(action["kind"] == "serve" and action["destination"] == customer
               for plan in decision["plans"].values() for action in plan["actions"])


def ready_states(instance, result, decision):
    """Reconstruct only EVs with selected ready-vehicle plans at this epoch."""
    time = decision["time"]
    states = {}
    for key in decision["plans"]:
        vehicle_id = int(key)
        completed = (step.after for step in result.steps
                     if step.before.id == vehicle_id and step.after.time <= time + EPS)
        state = max(completed, key=lambda item: item.time,
                    default=initial_vehicle(instance, vehicle_id))
        if not state.finished and state.time <= time + EPS:
            states[vehicle_id] = replace(state, time=time)
    return states


def direct_ready_actions(instance, result, decision, customer):
    """Count immediate legal service actions, not feasible route insertions."""
    visible = tuple(c for c in instance.customers if c.id in decision["available"])
    observation = Observation(decision["time"], instance.infrastructure, visible,
                              tuple((c, int(k)) for c, k in decision["committed_before"].items()))
    states = ready_states(instance, result, decision)
    return sum(try_transition(state, Action("serve", customer), observation).feasible
               for state in states.values()), len(states)


def local_route_probe(instance, result, decision, customer, config):
    """Feasible one-customer suffixes; does not preserve other soft routes."""
    visible = tuple(c for c in instance.customers if c.id in decision["available"])
    observation = Observation(decision["time"], instance.infrastructure, visible,
                              tuple((c, int(k)) for c, k in decision["committed_before"].items()))
    return sum(build_route(state, (customer,), observation, config) is not None
               for state in ready_states(instance, result, decision).values())


def _write_csv(path, fields, rows):
    with writable_path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def diagnose():
    losses = []
    probes = []
    timing = defaultdict(lambda: defaultdict(list))
    cohort_counts = Counter()
    scenario_cache = {}
    for cohort, campaign in COHORTS:
        manifest = load_json(campaign.OUTPUT / "manifest.json")
        expected_status = "development_complete" if cohort == "development" else "complete"
        if (manifest["status"] != expected_status or
                manifest["completed_runs"] != manifest["planned_runs"]):
            raise ValueError(f"Incomplete frozen manifest: {cohort}")
        config = load_config(campaign.CONFIG)
        for row in manifest["records"]:
            key = (cohort, row["instance"], row["dynamicity"], row["seed"])
            if key not in scenario_cache:
                opts = (campaign.options(config, row["instance"], row["dynamicity"],
                                         row["seed"], row["method"])
                        if cohort == "development" else
                        campaign.options(config, row["dynamicity"], row["seed"], row["method"]))
                instance, reference, scenario, _ = prepare(row["instance"], opts)
                departures = reference.predecessor_departures
                releases = dict(scenario.customer_release_times)
                if (set(departures) != {c.id for c in instance.customers} or
                        any(releases[c] > departures[c] + EPS for c in departures)):
                    raise ValueError(f"Offline full-service reference is not release-feasible: {key}")
                scenario_cache[key] = instance, reference, scenario
            instance, reference, scenario = scenario_cache[key]
            path = ROOT / row["raw"]
            if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
                raise ValueError(f"Raw trace differs from frozen manifest: {path}")
            raw = load_json(path)
            result = decode_result(raw)
            mpc_config = (MPCConfig(**(raw["effective_config"]["mpc"] |
                                       {"charge_fractions": tuple(
                                           raw["effective_config"]["mpc"]["charge_fractions"])}))
                          if cohort == "development" and row["method"] == "MPC_ALNS" else None)
            if (result.metadata["scenario_identifier"] != scenario.identifier or
                    result.metadata["reference_schedule_identifier"] != reference.identifier or
                    result.metadata["algorithm"] != row["method"] or
                    result.metadata["K_ref"] != reference.fleet_size or
                    not all(audit_result(result, instance, scenario).values())):
                raise ValueError(f"Independent replay or metadata mismatch: {path}")
            cohort_counts[cohort] += 1
            aggregate = timing[cohort, row["method"]]
            aggregate["runs"].append(1)
            for decision in result.decisions:
                latency = decision.get("optimization_latency_seconds")
                if latency is None:
                    continue
                constructor = decision.get("constructor_seconds") or 0.0
                optimizer = decision.get("optimizer")
                search = (optimizer.get("runtime") or 0.0) if optimizer else 0.0
                aggregate["latencies"].append(latency)
                aggregate["constructor"].append(constructor)
                aggregate["optimizer"].append(search)
                aggregate["unattributed"].append(max(0.0, latency - constructor - search))
                aggregate["screened"].append(decision.get("constructor_screened_insertions") or 0)
                aggregate["decoded"].append(decision.get("constructor_exact_decoder_calls") or 0)
                aggregate["zero"].append(decision.get("constructor_zero_option_customers") or 0)
                aggregate["deadline"].append(bool(optimizer and optimizer.get("deadline_reached")))
            releases = dict(scenario.customer_release_times)
            customers = {c.id: c for c in instance.customers}
            for customer_id in result.unserved_customers:
                customer = customers[customer_id]
                visible = [decision for decision in result.decisions
                           if customer_id in decision["available"] and
                           decision["time"] <= customer.due + EPS]
                selected = any(_selected(decision, customer_id) for decision in visible)
                first = visible[0] if visible else None
                direct, ready = (direct_ready_actions(instance, result, first, customer_id)
                                 if first else (0, 0))
                observation = ("no_visible_decision_before_due" if not first else
                               "selected_but_unserved" if selected else
                               "direct_ready_action_unselected" if direct else
                               "no_direct_ready_action")
                losses.append(dict(cohort=cohort, instance=row["instance"], family=row["family"],
                                   size=row["size"], dod=row["dynamicity"], seed=row["seed"],
                                   method=row["method"], customer=customer_id,
                                   release=round(releases[customer_id], 6), deadline=customer.due,
                                   first_visible_decision=round(first["time"], 6) if first else "",
                                   visible_decisions=len(visible), ever_selected_in_plan=selected,
                                   direct_ready_actions=direct, ready_vehicles=ready,
                                   committed_vehicles=len(first["committed_before"]) if first else 0,
                                   observation=observation))
                if mpc_config is not None:
                    probes.append(dict(instance=row["instance"], dod=row["dynamicity"],
                                       seed=row["seed"], customer=customer_id,
                                       first_visible_decision=round(first["time"], 6) if first else "",
                                       ready_vehicles=ready,
                                       single_customer_route_vehicles=(local_route_probe(
                                           instance, result, first, customer_id, mpc_config) if first else 0),
                                       ever_selected_in_plan=selected))
        print(f"Audited {cohort_counts[cohort]} {cohort} traces", flush=True)
    losses.sort(key=lambda row: (row["cohort"], row["method"], row["instance"],
                                 row["dod"], row["seed"], row["customer"]))
    _write_csv(DEST / "unserved_observations.csv", LOSS_FIELDS, losses)
    _write_csv(DEST / "development_alns_local_route_probe.csv", PROBE_FIELDS, probes)
    times = []
    for (cohort, method), data in sorted(timing.items()):
        latencies = data["latencies"]
        times.append(dict(cohort=cohort, method=method, runs=len(data["runs"]),
                          optimization_decisions=len(latencies),
                          mean_latency_s=round(mean(latencies), 6),
                          p95_latency_s=round(_percentile(latencies, 0.95), 6),
                          max_latency_s=round(max(latencies), 6),
                          constructor_s=round(sum(data["constructor"]), 3),
                          optimizer_s=round(sum(data["optimizer"]), 3),
                          unattributed_s=round(sum(data["unattributed"]), 3),
                          screened_insertions=sum(data["screened"]),
                          exact_decodes=sum(data["decoded"]),
                          zero_option_customers=sum(data["zero"]),
                          deadline_reached=sum(data["deadline"])))
    _write_csv(DEST / "timing.csv", TIME_FIELDS, times)
    lines = ["# MPC enhancement diagnosis", "",
             "This is a read-only analysis of frozen traces. Development cases may guide new work; "
             "historical robustness cases are descriptive only and must not be tuning targets.", "",
             "Every source raw SHA-256 was checked against its manifest; each result was independently "
             "replayed. Every scenario has an audited full-service reference whose customer dispatches "
             "occur after release. This is a **clairvoyant offline feasibility reference, not a valid "
             "online MPC competitor**.", "",
             "## Audit and observations", "",
             "| Cohort | Audited runs | Unserved customer observations |", "| --- | ---: | ---: |"]
    for cohort, _ in COHORTS:
        lines.append(f"| {cohort} | {cohort_counts[cohort]} | "
                     f"{sum(row['cohort'] == cohort for row in losses)} |")
    lines += ["", "| Cohort | Trace observation | Count |", "| --- | --- | ---: |"]
    counts = Counter((row["cohort"], row["observation"]) for row in losses)
    lines.extend(f"| {cohort} | {category} | {count} |"
                 for (cohort, category), count in sorted(counts.items()))
    lines += ["", "`direct_ready_action_unselected` means one immediate service action "
             "passed the plant's safe-return check at the first visible decision. It does not "
             "prove a feasible insertion preserving other work, or establish a causal error. "
             "`no_direct_ready_action` does not prove route infeasibility because a charging "
             "stop or later dispatch may work. A soft plan may be replanned before execution.", "",
             "## Five-second budget", "",
             "| Cohort | Method | Decisions | Mean / p95 / max latency (s) | "
             "Constructor / optimizer / other measured time (s) | Screened / decoded |",
             "| --- | --- | ---: | --- | --- | --- |"]
    for row in times:
        lines.append(f"| {row['cohort']} | {row['method']} | {row['optimization_decisions']} | "
                     f"{row['mean_latency_s']:.3f} / {row['p95_latency_s']:.3f} / "
                     f"{row['max_latency_s']:.3f} | {row['constructor_s']:.1f} / "
                     f"{row['optimizer_s']:.1f} / {row['unattributed_s']:.1f} | "
                     f"{row['screened_insertions']} / {row['exact_decodes']} |")
    lines += ["", "Other measured time is the residual, including final validation, "
             "coordination, and fallback; these components cannot be separated for every "
             "method from existing traces. The per-decision five-second budget remains "
             "unchanged. CSVs retain customer-level and timing evidence.", "",
             "## Development failure cases", "",
             "| Instance | DoD | Seed | ALNS losses | Direct-ready unselected | Selected then unserved |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    cases = defaultdict(list)
    for row in losses:
        if row["cohort"] == "development" and row["method"] == "MPC_ALNS":
            cases[row["instance"], row["dod"], row["seed"]].append(row)
    for (name, dod, seed), rows in sorted(cases.items(), key=lambda item: -len(item[1]))[:12]:
        lines.append(f"| {name} | {dod} | {seed} | {len(rows)} | "
                     f"{sum(r['observation'] == 'direct_ready_action_unselected' for r in rows)} | "
                     f"{sum(r['ever_selected_in_plan'] for r in rows)} |")
    lines += ["", f"For ALNS development losses, {sum(p['single_customer_route_vehicles'] > 0 for p in probes)} "
             f"of {len(probes)} had at least one plant-validated, charging-aware one-customer "
             "route at their first visible decision. This does not establish a "
             "service-preserving insertion into the other selected routes.", "",
             "These are measured opportunities and trace outcomes, not proofs of "
             "why a route failed. Existing traces do not retain rejected insertions, so "
             "constructor/decoder failure and online-commitment loss require separate "
             "instrumented development experiments.", ""]
    writable_path(DEST / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    diagnose()
