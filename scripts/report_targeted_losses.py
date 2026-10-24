"""Read-only retrospective loss ledger; associations are not causal certificates."""

from hashlib import sha256

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.instance import load_instance,travel_time
from evrp.model import Action,EPS,Observation,transition
from evrp.storage import BENCHMARK, ROOT, load_json, save_json, writable_path
from scripts.analyze_planning_losses import covered,vehicle

OUTPUT=ROOT/"results/desaulniers/targeted_service_v1/diagnosis"
ARCHIVE=ROOT/"results/desaulniers/publication_development/frozen_inputs_v1"


def arrival_bound(origins,customer,parameters):
    values={k:max(s.time+travel_time(s.location,customer,parameters),customer.ready)
            for k,s in origins.items() if not s.finished and customer.id not in s.served_customers}
    return dict(earliest_service_start_lower_bound=min(values.values()) if values else None,
                time_eligible_vehicles=sum(t<=customer.due+EPS for t in values.values()),
                by_vehicle=values)


def report():
    manifest=load_json(OUTPUT/"manifest.json")
    inputs={r["identifier"]:r for r in load_json(ARCHIVE/"manifest.json")["inputs"] if r["kind"]=="scenarios"}
    previous_name=None
    rows=[]
    missed=[]
    for saved in manifest["records"]:
        path=ROOT/saved["root"]
        if sha256(path.read_bytes()).hexdigest()!=saved["sha256"]:
            raise ValueError("Saved root hash mismatch")
        root=load_json(path)
        if root["source_raw"]!=previous_name:
            raw_path=ROOT/root["source_raw"]
            if sha256(raw_path.read_bytes()).hexdigest()!=root["source_raw_sha256"]:
                raise ValueError("Instrumented raw bytes changed")
            raw=load_json(raw_path)
            decisions=[d for d in raw["decisions"] if d.get("planning_trace")]
            instance=load_instance(BENCHMARK/f"{root['instance']}.txt")
            customers={c.id:c for c in instance.customers}
            entry=inputs[raw["metadata"]["scenario_identifier"]]
            artifact=ARCHIVE/entry["artifact"]
            if sha256(artifact.read_bytes()).hexdigest()!=entry["sha256"]:
                raise ValueError("Historical exact scenario bytes changed")
            scenario=load_json(artifact)
            releases=dict(scenario["customer_release_times"])
            missed.extend(dict(instance=instance.name,customer=c,release=releases[c],ready=customers[c].ready,
                               due=customers[c].due) for c in raw["unserved_customers"])
            previous_name=root["source_raw"]
        decision=decisions[root["source_decision_index"]]
        trace=decision["planning_trace"]
        selected=covered(trace["stages"]["validation"])
        constructor=covered(trace["stages"]["optimizer"])
        origins={int(k):vehicle(s) for k,s in root["origins"].items()}
        after=dict(origins)
        observation=Observation(root["time"],instance.infrastructure,
            tuple(customers[c["id"]] for c in root["observation"]["customers"]),
            tuple(tuple(pair) for pair in root["observation"]["committed_customers"]))
        for k in root["ready_vehicles"]:
            actions=root["initial_routes"].get(str(k),[])
            if actions:
                after[k]=transition(origins[k],Action(**actions[0]),observation).after
        for target in root["selected_targets"]:
            customer=target["customer"]
            if releases[customer]>root["time"]+EPS:
                raise ValueError("A diagnostic target must already be released")
            before_bound=arrival_bound(origins,customers[customer],instance.infrastructure.parameters)
            after_bound=arrival_bound(after,customers[customer],instance.infrastructure.parameters)
            if customer in selected and not after_bound["time_eligible_vehicles"]:
                raise ValueError("Arrival bound contradicts a validated planned continuation")
            screens=[e for e in trace["events"] if e["kind"]=="insertion_screen" and e.get("customer")==customer]
            decodes=[e for e in trace["events"] if e["kind"]=="route_decode" and customer in e.get("sequence",[])]
            options=root["counterfactual"].get("selected_commitment_state",{}).get("screened_options",{}).get(customer)
            rows.append(dict(instance=instance.name,customer=customer,time=root["time"],selection=target["selection"],
                             release=releases[customer],ready=customers[customer].ready,due=customers[customer].due,
                             ready_evs=len(root["ready_vehicles"]),busy_evs=len(root["busy_actions"]),
                             constructor_planned=customer in constructor,selected_planned=customer in selected,
                             optimizer_replaced=customer in constructor and customer not in selected,
                             invalid_suffix=customer in covered(trace["invalid_suffixes"]),
                             optimizer_deadline=bool((decision.get("optimizer") or {}).get("deadline_reached")),
                             time_window_screen_rejections=sum(e["reason"]=="time_window" for e in screens),
                             capacity_screen_rejections=sum(e["reason"]=="capacity" for e in screens),
                             screen_passes=sum(bool(e["passed"]) for e in screens),
                             decodes_with_target=sum(e["outcome"]=="feasible" for e in decodes),
                             bounded_decode_failures=sum(e["outcome"]=="bounded_decoder_failure" for e in decodes),
                             necessary_screen_options_after_commitment=options,
                             time_bound_before_commitment=before_bound,time_bound_after_commitment=after_bound,
                             root_charging_failures=sum(e["kind"]=="charging_connection_failure" for e in trace["events"])))
    save_json(OUTPUT/"loss_ledger.json",dict(rows=rows,unserved=missed,
              interpretation="observed associations only; no mathematical or causal infeasibility certificates"))
    lines=["# Observable-state service-loss evidence","",
           "Each row is a retrospectively selected root/customer, not an independent experiment.",
           "Release/deadline values come from archived scenarios for postmortem reporting only.",
           "The online candidates never access unreleased customer attributes.",
           "Screen passes are necessary conditions; decode success need not be a feasible insertion",
           "preserving every other planned customer. Root charging failures are not target-specific",
           "or proof of battery infeasibility. Busy counts indicate fixed irreversible commitments,",
           "not proof they caused a miss. No bounded probe in this diagnosis found a better canonical plan.","",
           "| Instance | Customer | Root time | Selection | Release / ready / due | Ready / busy EVs | Constructor / selected planned | Optimizer replacement | Suffix invalid | Optimizer deadline | TW rejects / screen passes | Decodes feasible / failed | Post-commit screen options | Root charge failures |",
           "| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |"]
    for r in rows:
        lines.append(f"| {r['instance']} | {r['customer']} | {r['time']:.3f} | {r['selection']} | "
                     f"{r['release']:.3f} / {r['ready']:.3f} / {r['due']:.3f} | {r['ready_evs']} / {r['busy_evs']} | "
                     f"{r['constructor_planned']} / {r['selected_planned']} | {r['optimizer_replaced']} | "
                     f"{r['invalid_suffix']} | {r['optimizer_deadline']} | "
                     f"{r['time_window_screen_rejections']} / {r['screen_passes']} | {r['decodes_with_target']} / "
                     f"{r['bounded_decode_failures']} | {r['necessary_screen_options_after_commitment']} | {r['root_charging_failures']} |")
    writable_path(OUTPUT/"paper/loss_ledger.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    bounds=["# Optimistic arrival bounds around actual first commitments", "",
            "Counts ignore energy, remaining payload, other customer obligations and terminal return.",
            "A positive count is not a feasible insertion witness. A zero count means no measured",
            "origin meets even this optimistic time test under the stated immutable commitments;",
            "it is not an infeasibility claim about the original offline instance or all prior controls.",
            "Busy origins already represent immutable-action after-states. Ready origins are then",
            "advanced through the selected first action only, without revealing future requests.",
            "No eventually missed target is itself served by these first commitments.","",
            "| Instance | Target | Root time | Optimistic EV count before / after | Earliest service bound before / after | Due |",
            "| --- | --- | ---: | --- | --- | ---: |"]
    for row in rows:
        before,after=row["time_bound_before_commitment"],row["time_bound_after_commitment"]
        def number(value):
            return "NA" if value is None else f"{value:.3f}"
        bounds.append(f"| {row['instance']} | {row['customer']} | {row['time']:.3f} | "
                      f"{before['time_eligible_vehicles']} / {after['time_eligible_vehicles']} | "
                      f"{number(before['earliest_service_start_lower_bound'])} / "
                      f"{number(after['earliest_service_start_lower_bound'])} | {row['due']:.3f} |")
    writable_path(OUTPUT/"paper/arrival_bounds.md").write_text("\n".join(bounds)+"\n",encoding="utf-8")
    fig,ax=plt.subplots(figsize=(10,max(4,len(missed)*.24)))
    for i,r in enumerate(missed):
        ax.hlines(i,r["ready"],r["due"],color="#4d7d99",linewidth=3)
        ax.plot(r["release"],i,"o",color="#b44345",markersize=4)
    ax.set(yticks=range(len(missed)),yticklabels=[f"{r['instance']} / {r['customer']}" for r in missed],
           xlabel="Scenario time: red release, blue service-start window",
           title="Eventually unserved customers in the three diagnostic development runs")
    ax.tick_params(axis="y",labelsize=8)
    fig.tight_layout()
    fig.savefig(writable_path(OUTPUT/"paper/unserved_windows.png"),dpi=300)
    plt.close(fig)
    print(f"Retrospective ledger: {len(rows)} root/customer rows, {len(missed)} distinct run/customer losses",flush=True)


if __name__=="__main__":
    report()
