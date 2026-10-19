"""Read-only analysis of frozen final traces; writes only a separate supplement."""

from collections import Counter, defaultdict
from dataclasses import fields
from hashlib import sha256
from itertools import product
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evrp.instance import Location, load_instance
from evrp.model import Action, InfeasibleAction, Observation, VehicleState, transition
from evrp.reference import ReferenceSchedule, initial_vehicle
from evrp.scenario import DynamicScenario
from evrp.storage import BENCHMARK, ROOT, load_json
from scripts.run_portfolio_campaign import source_hash


FINAL = ROOT / "results" / "final_study"
OUTPUT = FINAL / "postmortem"
EPS = 1e-7


def markdown_table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |",
                      *("| " + " | ".join(map(str, row)) + " |" for row in rows)])


def vehicle_from_raw(raw):
    values = dict(raw)
    values["location"] = Location(**values["location"])
    values["route_history"] = tuple(values["route_history"])
    values["served_customers"] = tuple(values["served_customers"])
    if values["current_committed_action"]:
        values["current_committed_action"] = Action(**values["current_committed_action"])
    assert set(values) == {field.name for field in fields(VehicleState)}
    return VehicleState(**values)


def clustered_interval(records, first, second):
    """Exact six-instance percentile bootstrap of paired service differences."""
    paired = defaultdict(dict)
    for row in records:
        paired[(row["instance"], row["scenario_id"])][row["method"]] = row["customers_served"]
    groups = defaultdict(list)
    for (instance, _), methods in paired.items():
        if not {first, second}.issubset(methods):
            raise ValueError("Incomplete method pairing")
        groups[instance].append(methods[first] - methods[second])
    if len(groups) != 6 or any(len(values) != 9 for values in groups.values()):
        raise ValueError("Expected six instances with nine paired scenarios each")
    means = np.array([np.mean(groups[name]) for name in sorted(groups)])
    samples = np.array(list(product(range(6), repeat=6)), dtype=np.int8)
    values = means[samples].mean(axis=1)
    return float(means.mean()), tuple(float(v) for v in np.percentile(values, [2.5, 97.5]))


def validate_inputs():
    manifest = load_json(FINAL / "manifest.json")
    protocol_path = FINAL / "PRE_REGISTERED_PROTOCOL.json"
    protocol = load_json(protocol_path)
    if (manifest["status"] != "final_complete" or manifest["expected_records"] != 324
            or len(manifest["records"]) != 324 or manifest["expected_scenarios"] != 54
            or sha256(protocol_path.read_bytes()).hexdigest() != manifest["protocol_sha256"]
            or source_hash() != manifest["source_sha256"]
            or protocol["source_sha256"] != manifest["source_sha256"]):
        raise ValueError("Frozen final study provenance or completeness mismatch")
    records = manifest["records"]
    keys = [(r["scenario_id"], r["method"]) for r in records]
    if len(set(keys)) != 324:
        raise ValueError("Duplicate final record")
    scenarios = defaultdict(list)
    for row in records:
        if (not row["isolated_worker"] or not row["independent_audit"]
                or row["max_optimization_latency"] > 5 + 1e-6
                or row["protocol_sha256"] != manifest["protocol_sha256"]
                or row["source_sha256"] != manifest["source_sha256"]):
            raise ValueError("Unaudited or mismatched final record")
        scenarios[row["scenario_id"]].append(row)
    if len(scenarios) != 54 or any({r["method"] for r in group} != set(protocol["methods"])
                                    or len(group) != 6 for group in scenarios.values()):
        raise ValueError("Incomplete six-method pairing")

    instances = {name: load_instance(BENCHMARK / f"{name}.txt")
                 for name in {r["instance"] for r in records}}
    references = {}
    for name, instance in instances.items():
        options = list((ROOT / "data" / "reference_schedules").glob(f"{name}_*.json"))
        options += list((ROOT / "results" / "reference_schedules").glob(f"{name}_*.json"))
        references[name] = {ref.identifier: ref for ref in
                            (ReferenceSchedule.load(path, instance) for path in options)}
    scenario_cache = {}
    for path in (ROOT / "results" / "scenarios").glob("*.json"):
        data = load_json(path)
        if data.get("base_instance") in instances:
            scenario = DynamicScenario.load(path, instances[data["base_instance"]])
            scenario_cache[scenario.identifier] = scenario

    for sid, group in scenarios.items():
        row = group[0]
        instance = instances[row["instance"]]
        scenario = scenario_cache.get(sid)
        if scenario is None or scenario.fleet_size != row["k_ref"]:
            raise ValueError(f"Missing or fleet-mismatched scenario {sid}")
        ref = references[row["instance"]].get(scenario.reference_schedule_identifier)
        if ref is None or ref.fleet_size != scenario.fleet_size:
            raise ValueError(f"Missing matching validated reference {sid}")
        releases = dict(scenario.customer_release_times)
        if any(releases[cid] > departure + EPS for cid, departure in
               ref.predecessor_departures.items()):
            raise ValueError(f"Reference is unavailable at a predecessor departure: {sid}")
        if any((r["instance"], r["instance_sha256"], r["scenario_seed"])
               != (instance.name, instance.sha256, scenario.scenario_seed) for r in group):
            raise ValueError(f"Scenario identity mismatch: {sid}")
    return manifest, instances, scenario_cache


def missed_customer_rows(raw, record, instance, scenario):
    """Sample actual decision states; do not infer unobserved insertion feasibility."""
    missed = set(raw["unserved_customers"])
    if len(missed) != len(instance.customers) - record["customers_served"]:
        raise ValueError("Raw service count and missed IDs disagree")
    customer_by_id = {c.id: c for c in instance.customers}
    releases = dict(scenario.customer_release_times)
    events = {e["customer_id"]: e["time"] for e in raw["events"] if e["kind"] == "release"}
    if any(abs(events[cid] - releases[cid]) > EPS for cid in missed):
        raise ValueError("Release event differs from frozen scenario")
    steps = sorted(enumerate(raw["steps"]), key=lambda item: (item[1]["after"]["time"], item[0]))
    states = {k: initial_vehicle(instance, k) for k in range(scenario.fleet_size)}
    cursor = 0
    observations = {cid: dict(visible=0, planned=0, directly_feasible=0,
                              last_visible=None, last_planned=None, last_direct=None,
                              ready_at_last_visible=0, busy_at_last_visible=0,
                              finished_at_last_visible=0, ready_at_last_direct=None,
                              busy_at_last_direct=None, finished_at_last_direct=None)
                    for cid in missed}
    for decision in raw["decisions"]:
        t = decision["time"]
        while cursor < len(steps) and steps[cursor][1]["after"]["time"] <= t + EPS:
            step = steps[cursor][1]
            states[step["after"]["id"]] = vehicle_from_raw(step["after"])
            cursor += 1
        visible = set(decision["available"])
        planned = {action["destination"] for plan in decision["plans"].values()
                   for action in plan["actions"] if action["kind"] == "serve"}
        committed = set(decision["committed_before"])
        ready = [state for state in states.values() if not state.finished and
                 abs(state.time - t) <= EPS]
        finished = sum(state.finished for state in states.values())
        busy = scenario.fleet_size - len(ready) - finished
        obs = Observation(t, instance.infrastructure,
                          tuple(customer_by_id[cid] for cid in visible),
                          tuple(decision["committed_before"].items()))
        for cid in missed & visible:
            info = observations[cid]
            info["visible"] += 1
            info["last_visible"] = t
            info["ready_at_last_visible"] = len(ready)
            info["busy_at_last_visible"] = busy
            info["finished_at_last_visible"] = finished
            if cid in planned:
                info["planned"] += 1
                info["last_planned"] = t
            if cid not in committed:
                for state in ready:
                    try:
                        transition(state, Action("serve", cid), obs)
                        info["directly_feasible"] += 1
                        info["last_direct"] = t
                        info["ready_at_last_direct"] = len(ready)
                        info["busy_at_last_direct"] = busy
                        info["finished_at_last_direct"] = finished
                        break
                    except InfeasibleAction:
                        pass
    rows = []
    for cid in sorted(missed):
        c = customer_by_id[cid]
        info = observations[cid]
        rows.append(dict(instance=record["instance"], family=record["family"],
                         dod=record["dynamicity"], seed=record["scenario_seed"],
                         method=record["method"], scenario_id=record["scenario_id"],
                         customer=cid, release=releases[cid], ready=c.ready, due=c.due,
                         **info))
    return rows


def render(manifest, rows):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    figures = OUTPUT / "figures"
    figures.mkdir(exist_ok=True)
    tables = OUTPUT / "tables"
    tables.mkdir(exist_ok=True)
    records = manifest["records"]
    methods = sorted({r["method"] for r in records})
    deficits = Counter(r["method"] for r in rows)
    summary = [(method, 5400 - deficits[method], f"{(5400-deficits[method])/54:.2f}",
                sum(r["complete_service"] for r in records if r["method"] == method),
                deficits[method]) for method in methods]
    alns = [r for r in rows if r["method"] == "MPC_ALNS"]
    cases = sorted((r for r in records if r["method"] == "MPC_ALNS" and not r["complete_service"]),
                   key=lambda r: (r["customers_served"], r["instance"], r["dynamicity"], r["scenario_seed"]))
    case_rows = [(r["instance"], r["dynamicity"], r["scenario_seed"],
                  r["customers_served"], 100-r["customers_served"]) for r in cases]
    diagnostic = Counter("planned in selected route" if r["planned"] else
                         "direct service feasible at sampled decision" if r["directly_feasible"] else
                         "no sampled direct opportunity" for r in alns)
    cluster_rows = []
    for first, second in [("MPC_MCTS", "MPC_COMPLETION"), ("MPC_ALNS", "MPC_COMPLETION"),
                          ("MPC_ALNS", "MPC_PORTFOLIO")]:
        estimate, ci = clustered_interval(records, first, second)
        cluster_rows.append((first, second, f"{estimate:.2f}", f"[{ci[0]:.2f}, {ci[1]:.2f}]"))
    family_rows = []
    for family in sorted({r["family"] for r in records}):
        for method in methods:
            group = [r for r in records if r["family"] == family and r["method"] == method]
            family_rows.append((family, method, sum(100-r["customers_served"] for r in group),
                                sum(r["complete_service"] for r in group)))
    dod_rows = []
    for dod in sorted({r["dynamicity"] for r in records}):
        for method in methods:
            group = [r for r in records if r["dynamicity"] == dod and r["method"] == method]
            dod_rows.append((dod, method, sum(100-r["customers_served"] for r in group),
                             sum(r["complete_service"] for r in group)))
    all_missed_rows = [(r["method"], r["instance"], r["dod"], r["seed"], r["customer"],
                        f"{r['release']:.2f}", f"{r['due']:.2f}", r["visible"], r["planned"],
                        r["directly_feasible"],
                        "-" if r["last_direct"] is None else f"{r['last_direct']:.2f}",
                        f"{r['ready_at_last_visible']}/{r['busy_at_last_visible']}/{r['finished_at_last_visible']}",
                        "-" if r["last_direct"] is None else
                        f"{r['ready_at_last_direct']}/{r['busy_at_last_direct']}/{r['finished_at_last_direct']}")
                       for r in sorted(rows, key=lambda x: (x["method"], x["instance"], x["dod"],
                                                           x["seed"], x["customer"]))]
    (tables / "all_missed_customers.md").write_text(
        "# All Missed Customers\n\n" +
        "A direct opportunity is a sampled direct-next-service action from a ready vehicle "
        "with safe depot escape, not a causal proof of a better end-to-end plan. "
        "Ready/Busy/Finished counts are at the last visible recorded decision.\n\n" +
        markdown_table(["Method", "Instance", "DoD", "Seed", "Customer", "Release", "Due",
                        "Visible", "Planned", "Direct-feasible", "Last direct",
                        "Ready/Busy/Finished at last visible", "Ready/Busy/Finished at last direct"],
                       all_missed_rows) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([m.removeprefix("MPC_") for m in methods], [deficits[m] for m in methods], color="#326c81")
    ax.set_ylabel("Customers unserved across 54 scenarios")
    ax.set_title("Online service gap to feasible clairvoyant reference")
    fig.tight_layout()
    fig.savefig(figures / "service_gap.png", dpi=300)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for group, marker, color in [(True, "o", "#b64833"), (False, "x", "#326c81")]:
        selected = [r for r in alns if bool(r["planned"]) == group]
        ax.scatter([r["release"] for r in selected], [r["due"] for r in selected],
                   marker=marker, color=color, label="Appeared in selected route" if group else "Never selected")
    ax.set_xlabel("Release time")
    ax.set_ylabel("Due time")
    ax.set_title("Unserved ALNS customers: release and deadline")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "alns_release_due.png", dpi=300)
    plt.close(fig)

    lines = ["# Online Service Gap: Read-Only Final-Trace Postmortem", "",
             "This supplement does not alter the frozen primary results in "
             "[RESULTS.md](../paper/RESULTS.md). The offline reference is a **feasible "
             "clairvoyant schedule**, not an online method or an optimality bound on distance.", "",
             "## Reference verification", "",
             "All 54 cached final scenarios and all six associated benchmark references were "
             "validated using the exact stored transition trace. Each reference serves all 100 "
             "customers with the same K_ref; every release is no later than its reference "
             "predecessor departure. This proves feasibility with advance knowledge, not "
             "attainability under online information.", "",
             "## Service gap", "",
             markdown_table(["MPC method", "Served / 5400", "Mean / 100", "Complete / 54", "Unserved"], summary), "",
             "[PNG: service gap](figures/service_gap.png)", "",
             "### Gap by family and dynamicity", "",
             "Each family has nine scenarios per method; each DoD has 18. A gap of zero "
             "means every customer was served in that stratum.", "",
             markdown_table(["Family", "Method", "Unserved / 900", "Complete / 9"], family_rows), "",
             markdown_table(["DoD", "Method", "Unserved / 1800", "Complete / 18"], dod_rows), "",
             "[All missed customers and sampled decision evidence](tables/all_missed_customers.md)", "",
             "## ALNS failure cases", "",
             markdown_table(["Instance", "DoD", "Seed", "Served", "Unserved"], case_rows), "",
             f"ALNS missed {len(alns)} customer opportunities. Of these, "
             f"{sum(r['planned'] > 0 for r in alns)} appeared in a selected route at least once; "
             f"{sum(r['directly_feasible'] > 0 for r in alns)} had a sampled direct-next-service "
             "opportunity from a ready vehicle at a recorded decision epoch.", "",
             markdown_table(["Descriptive evidence (exclusive)", "Missed customers"], sorted(diagnostic.items())), "",
             "[PNG: release versus due](figures/alns_release_due.png)", "",
             "### Largest paired failure case", "",
             "At r207_21, DoD 0.25, seeds 1 and 2, ALNS served 93/100 in each "
             "run with K_ref=3. The two runs account for 14/36 (39%) of ALNS's "
             "missed customers. Nine of those 14 appeared in at least one selected "
             "route; all 14 had a sampled direct-next-service opportunity. This "
             "shows that the missed customers were not uniformly invisible or "
             "individually unreachable at every recorded decision. It does not "
             "establish that serving them would have preserved the other 93 "
             "services. The case motivates development-only tests of plan "
             "retention and targeted service recovery.", "",
             "### Per-customer evidence for MPC + ALNS", "",
             markdown_table(["Instance", "DoD", "Seed", "Customer", "Release", "Due", "Visible epochs",
                             "Planned epochs", "Direct-feasible epochs", "Last direct time", "Ready/Busy/Finished at last visible"],
                            [(r["instance"], r["dod"], r["seed"], r["customer"],
                              f"{r['release']:.1f}", f"{r['due']:.1f}", r["visible"], r["planned"],
                              r["directly_feasible"],
                              "-" if r["last_direct"] is None else f"{r['last_direct']:.1f}",
                              f"{r['ready_at_last_visible']}/{r['busy_at_last_visible']}/{r['finished_at_last_visible']}")
                             for r in sorted(alns, key=lambda x: (x["instance"], x["dod"], x["seed"], x["customer"]))]), "",
             "## Instance-clustered sensitivity", "",
             markdown_table(["First", "Second", "Paired mean gain", "95% cluster-bootstrap CI"], cluster_rows), "",
             "The percentile intervals enumerate all 6^6 resamples of the six benchmark "
             "instances, retaining each instance's nine DoD/seed scenarios together. They are "
             "descriptive robustness intervals with only six independent clusters; they do "
             "not replace the preregistered scenario-paired analysis or adjust for method selection.", "",
             "## Interpretation and limits", "",
             "A selected plan is a forecast, not an executed route. A direct-feasible observation "
             "means an immediate service action plus safe depot escape passed the common physics "
             "at one recorded decision state. It does not show a feasible multi-customer insertion "
             "or prove that taking the action would improve final service. A missing sampled "
             "direct opportunity does not prove infeasibility: charging-mediated routes, busy "
             "vehicle continuations, and states between recorded epochs are not exhaustively "
             "tested. Fleet availability counts are at the last visible decision, not necessarily "
             "at the customer's final feasible time. These are observational classifications, "
             "not causal failure labels.", "",
             "The R2 r207_21 DoD 0.25 seed 1 and 2 cases are the largest ALNS losses. "
             "They can motivate hypotheses about fleet flexibility or recovery, but are seen "
             "holdout instances and must not be used to select a new policy. Any new controller "
             "must be developed on development data and evaluated in a separately preregistered "
             "unused-instance study with the fixed baselines rerun.", "",
             "## Reproduction", "",
             "Run `python -m scripts.diagnose_final_service_loss`. The script checks the frozen "
             "manifest, protocol/source hashes, all 324 raw checksums and audits, 54 scenario "
             "identities, and six full-service references. It reads final evidence and writes "
             "only this postmortem directory. Figures are PNG at 300 dpi; tables are Markdown.", ""]
    (OUTPUT / "ONLINE_SERVICE_GAP.md").write_text("\n".join(lines), encoding="utf-8")
    return summary, len(alns)


def main():
    manifest, instances, scenarios = validate_inputs()
    rows = []
    for index, record in enumerate(manifest["records"], 1):
        path = ROOT / record["raw"]
        if sha256(path.read_bytes()).hexdigest() != record["raw_sha256"]:
            raise ValueError(f"Raw checksum mismatch: {path}")
        raw = load_json(path)
        meta = raw["metadata"]
        if (meta["scenario_identifier"] != record["scenario_id"] or
                meta["algorithm"] != record["method"] or
                not meta["isolated_worker"] or
                not all(meta["independent_audit"].values()) or
                any(raw["metrics"][key] != 0 for key in
                    ("hidden_information_violations", "time_window_violations",
                     "battery_violations", "capacity_violations")) or
                raw["metrics"]["customers_served"] != record["customers_served"]):
            raise ValueError(f"Raw audit mismatch: {path}")
        rows.extend(missed_customer_rows(raw, record, instances[record["instance"]],
                                         scenarios[record["scenario_id"]]))
        if index % 54 == 0:
            print(f"Audited {index}/324 raw traces", flush=True)
    summary, n_alns = render(manifest, rows)
    print(f"Verified 54 feasible references, 324 audited runs; ALNS missed {n_alns} customers")
    for row in summary:
        print(row)
    print(OUTPUT / "ONLINE_SERVICE_GAP.md")


if __name__ == "__main__":
    main()
