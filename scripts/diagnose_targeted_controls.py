"""Development-only counterfactual commitments at saved service-loss roots."""

from collections import Counter
from hashlib import sha256
from pathlib import Path
import subprocess

from evrp.instance import load_instance
from evrp.mpc import MPCConfig
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json, writable_path
from evrp.targeted_recovery import counterfactual_actions
from scripts.analyze_planning_losses import covered, root_problem, routes


OUTPUT = ROOT / "results/desaulniers/targeted_service_v1/diagnosis"
SOURCE = ROOT / "results/desaulniers/publication_development/instrumented_v1/manifest.json"
LIMIT = 24


def run():
    manifest = load_json(SOURCE)
    files = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__)]
    frozen = dict(source_sha256=identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                                           for p in files}),
                  source_manifest_identifier=identifier(manifest), maximum_roots=LIMIT,
                  seconds_per_root=1.0, selection="first visibility, last planned, first subsequent plan loss",
                  role="loss-selected development diagnosis; no causal or infeasibility claim")
    protocol = OUTPUT / "protocol.json"
    if protocol.exists() and load_json(protocol)["scientific"] != frozen:
        raise ValueError("Counterfactual diagnostic source or selection drift")
    if not protocol.exists():
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.strip()
        save_json(protocol, dict(scientific=frozen, source_commit=commit))
    records = []
    for row in manifest["records"]:
        source = ROOT / row["raw"]
        if sha256(source.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Instrumented source raw changed")
        raw = load_json(source)
        decisions = [d for d in raw["decisions"] if d.get("planning_trace")]
        selected = {}
        for customer in sorted(raw["unserved_customers"]):
            visible = [i for i, d in enumerate(decisions)
                       if customer in {c["id"] for c in d["planning_trace"]["observation"]["customers"]}]
            planned = [i for i in visible if customer in covered(
                decisions[i]["planning_trace"]["stages"]["validation"])]
            indices = [(visible[0], "first_visible")] if visible else []
            if planned:
                indices.append((planned[-1], "last_planned"))
                if planned[-1] + 1 < len(decisions):
                    indices.append((planned[-1]+1, "subsequent_plan_loss"))
            for index, reason in indices:
                selected.setdefault(index, []).append(dict(customer=customer, selection=reason))
        instance = load_instance(BENCHMARK / f"{row['instance']}.txt")
        values = raw["effective_config"]["mpc"]
        mpc = MPCConfig(**(values | {"charge_fractions": tuple(values["charge_fractions"])}))
        for index in sorted(selected):
            if len(records) >= LIMIT:
                break
            decision = decisions[index]
            trace = decision["planning_trace"]
            name = identifier([row["raw_sha256"], index])[:16]
            target = OUTPUT / "roots" / f"{name}.json"
            if target.exists():
                record = load_json(target)
            else:
                problem = root_problem(trace, instance, mpc)
                ready = sorted(set(problem.ids) - {int(k) for k in trace["busy_actions"]})
                initial = routes(trace["stages"]["validation"])
                changed, _, result = counterfactual_actions(
                    problem.origins, initial, problem.observation, mpc, ready, seconds=1.0,
                    reference_routes=routes(trace["stages"]["optimizer"]), diagnostic=True)
                failures = Counter((event["kind"], event.get("reason", event.get("outcome", "")))
                                   for event in trace["events"] if event["kind"] in {
                                       "insertion_screen", "route_decode", "charging_connection_failure"})
                record = dict(instance=instance.name, time=decision["time"], selected_targets=selected[index],
                              source_raw=row["raw"], source_raw_sha256=row["raw_sha256"],
                              source_decision_index=index, protocol_identifier=identifier(load_json(protocol)),
                              ready_vehicles=ready, busy_actions=trace["busy_actions"],
                              observation=trace["observation"], origins=trace["origins"],
                              initial_routes=trace["stages"]["validation"],
                              constructor_routes=trace["stages"]["optimizer"],
                              selected_routes={k: [vars(a) for a in actions] for k, actions in changed.items()},
                              counterfactual=result,
                              observed_failures=[dict(kind=kind, reason=reason, events=count)
                                                 for (kind, reason), count in failures.items()])
                save_json(target, record)
            if record["protocol_identifier"] != identifier(load_json(protocol)):
                raise ValueError("Diagnostic root protocol mismatch")
            records.append(dict(root=target.relative_to(ROOT).as_posix(),
                                sha256=sha256(target.read_bytes()).hexdigest(),
                                instance=record["instance"], time=record["time"],
                                improved=record["counterfactual"]["accepted_improvements"] > 0,
                                candidates=record["counterfactual"]["first_action_candidates"],
                                timeout=record["counterfactual"]["deadline_reached"]))
            save_json(OUTPUT / "manifest.json", dict(protocol_identifier=identifier(load_json(protocol)),
                      status="complete" if len(records) == LIMIT else "partial", records=records))
            print(f"Counterfactual root {len(records)}/{LIMIT}: {instance.name} t={decision['time']:.3f} "
                  f"improvements={record['counterfactual']['accepted_improvements']}", flush=True)
    save_json(OUTPUT / "manifest.json", dict(protocol_identifier=identifier(load_json(protocol)),
              status="complete", roots=len(records), maximum_roots=LIMIT, records=records))
    lines = ["# Counterfactual next-action development diagnosis", "",
             f"Evaluated {len(records)} recorded observable roots. Each probe is bounded at one second.",
             "Candidates preserve busy physical commitments and are decoded, fully scored",
             "with the canonical objective, and independently replayed. Post-commitment",
             "screens are necessary-condition counts, not infeasibility certificates.",
             "Loss selection uses outcomes only for retrospective diagnosis. It is not",
             "evidence that a different action would improve closed-loop service.", "",
             "| Instance | Time | First-control candidates | Canonical improvement | Deadline reached |",
             "| --- | ---: | ---: | --- | --- |"]
    lines.extend(f"| {r['instance']} | {r['time']:.3f} | {r['candidates']} | {r['improved']} | {r['timeout']} |"
                 for r in records)
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


if __name__ == "__main__":
    run()
