"""Bounded, retrospective service-opportunity probes at frozen development roots."""

from dataclasses import asdict
from collections import Counter
from hashlib import sha256
from math import hypot
from time import perf_counter

from evrp.fleet_mcts import _SearchBudgetReached
from evrp.flex_exchange import exchange_changes
from evrp.instance import load_instance
from evrp.model import Action, transition
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, reset_deadline, set_deadline
from evrp.repair import route_proposal
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json, writable_path
from scripts.analyze_planning_losses import root_problem, routes
from scripts.experiments.paths import artifact_path


STUDY = "slad_feasibility_v1"
SOURCE = ROOT / "results/desaulniers/targeted_service_v1/diagnosis"
INSTRUMENTED = ROOT / "results/desaulniers/publication_development/instrumented_v1"
ROOT_NAMES = (
    "5231d02399560db9",  # C1, first plan loss at t=388.353
    "af0a79ea93904f45",  # C1, late visible miss at t=421.240
    "219bffea81a97e08",  # R1, early visible miss at t=18.258
    "ffb3472dce60a7f9",  # R1, visible miss at t=36.408
    "f324a97f201fb12f",  # R1, subsequent plan loss at t=38.736
)
PER_ROOT_SECONDS = 3.0
TOTAL_SECONDS = 60.0
MAX_CANDIDATES = 8


def _hash(path):
    return sha256(path.read_bytes()).hexdigest()


def _owned(plan):
    return {c for sequence in plan.sequences for c in sequence}


def candidate_options(problem, plan, ready, target):
    """Deterministic bounded insertion order; a rejected screen proves nothing."""
    return [(k, pos) for _, _, k, pos, _ in problem.screened_options(plan.sequences, target)
            if k in ready][:MAX_CANDIDATES]


def candidate_moves(problem, plan, ready, target):
    """Reuse prior insertion/exchange generators without touching busy suffixes."""
    seen = set()
    for k, pos in candidate_options(problem, plan, ready, target):
        seq = plan.sequences[problem.ids.index(k)]
        changes = {k: seq[:pos] + (target,) + seq[pos:]}
        signature = tuple(sorted(changes.items()))
        seen.add(signature)
        yield "insertion", changes, signature
    for changes in exchange_changes(problem, plan, ready):
        if not set(changes) <= ready or target not in {c for seq in changes.values() for c in seq}:
            continue
        signature = tuple(sorted(changes.items()))
        if signature in seen:
            continue
        proposed = list(plan.sequences)
        for k, seq in changes.items():
            proposed[problem.ids.index(k)] = seq
        if not _owned(plan) | {target} <= {c for seq in proposed for c in seq}:
            continue
        seen.add(signature)
        yield "exchange", changes, signature


def timing_bound(origins, observation, target, first_actions=None):
    """Euclidean direct travel is a necessary-condition lower bound on arrival."""
    customer = observation.customer_by_id[target]
    speed = observation.infrastructure.parameters.speed
    if speed <= 0:
        raise ValueError("Positive constant speed is required for the timing certificate")
    first_actions = first_actions or {}
    starts, ignored_waits = {}, []
    for k, origin in sorted(origins.items()):
        if target in origin.served_customers:
            return dict(certified=False, reason="already_served", earliest_starts={})
        state = origin
        action = first_actions.get(k)
        if action is not None and action.kind == "wait":
            ignored_waits.append(k)  # An idle wait is interruptible, not a commitment.
        elif action is not None:
            state = transition(origin, action, observation).after
        if state.finished:
            continue
        direct = hypot(state.location.x - customer.x, state.location.y - customer.y) / speed
        starts[str(k)] = max(state.time, observation.time) + direct
        starts[str(k)] = max(starts[str(k)], customer.ready)
    certified = all(start > customer.due + 1e-8 for start in starts.values())
    return dict(certified=certified, reason="all_direct_arrivals_after_due" if certified else
                "at_least_one_optimistic_arrival", earliest_starts=starts,
                due=customer.due, ignored_interruptible_waits=ignored_waits)


def validate_witness(problem, baseline, candidate, ready, target):
    """Replay every route under the original plant and require safe return."""
    if not _owned(baseline) | {target} <= _owned(candidate):
        raise ValueError("Witness drops a planned customer or the target")
    evidence = {}
    for index, k in enumerate(problem.ids):
        actions = candidate.actions[index]
        if k not in ready and actions != baseline.actions[index]:
            raise ValueError("Witness modifies a busy vehicle suffix")
        state = problem.origins[k]
        for action in actions:
            state = transition(state, action, problem.observation).after
        proposal = route_proposal(problem.origins[k], actions, problem.observation,
                                  problem.config) if actions else None
        if actions and proposal is None:
            raise ValueError("Witness lacks a physically feasible safe return")
        evidence[str(k)] = dict(actions=[asdict(a) for a in actions],
                                final_time=state.time, final_battery=state.battery,
                                final_load=state.load,
                                served=list(state.served_customers),
                                safe_return_cost=proposal.cost if proposal else None)
    if target not in {c for row in evidence.values() for c in row["served"]}:
        raise ValueError("Target was not physically served")
    return evidence


def load_root(name, records, source_records, protocol_id, raw_cache=None):
    entry = records[name]
    path = ROOT / entry["root"]
    if path != SOURCE / "roots" / f"{name}.json" or _hash(path) != entry["sha256"]:
        raise ValueError("Recorded root path or SHA-256 changed")
    root = load_json(path)
    if root["protocol_identifier"] != protocol_id or root["instance"] != entry["instance"]:
        raise ValueError("Recorded root protocol or instance changed")
    source = source_records.get(root["source_raw"])
    if source is None or source["raw_sha256"] != root["source_raw_sha256"]:
        raise ValueError("Instrumented source manifest does not match root")
    raw_path = ROOT / root["source_raw"]
    if not raw_path.is_relative_to(INSTRUMENTED / "raw") or _hash(raw_path) != root["source_raw_sha256"]:
        raise ValueError("Instrumented raw bytes changed")
    raw_cache = {} if raw_cache is None else raw_cache
    if root["source_raw"] not in raw_cache:
        raw_cache[root["source_raw"]] = load_json(raw_path)
    raw = raw_cache[root["source_raw"]]
    decisions = [d for d in raw["decisions"] if d.get("planning_trace")]
    decision = decisions[root["source_decision_index"]]
    trace = decision["planning_trace"]
    for key, actual in (("observation", trace["observation"]), ("origins", trace["origins"]),
                        ("busy_actions", trace["busy_actions"]),
                        ("initial_routes", trace["stages"]["validation"]),
                        ("constructor_routes", trace["stages"]["optimizer"])):
        if root[key] != actual:
            raise ValueError(f"Recorded root differs from source trace: {key}")
    instance = load_instance(BENCHMARK / f"{root['instance']}.txt")
    if (decision["time"] != root["time"] or len(instance.customers) != 100 or
            raw["metadata"]["instance_sha256"] != instance.sha256 or
            raw["metadata"]["scenario_identifier"] != source["scenario_id"]):
        raise ValueError("Recorded decision, benchmark, or scenario identity changed")
    config_data = raw["effective_config"]["mpc"]
    config = MPCConfig(**(config_data | {"charge_fractions": tuple(config_data["charge_fractions"])}))
    problem = root_problem(root, instance, config)
    visible = {c["id"] for c in root["observation"]["customers"]}
    if (visible != set(problem.observation.customer_by_id) or
            identifier(root["observation"]["infrastructure"]) != identifier(asdict(instance.infrastructure)) or
            any(identifier(c) != identifier(asdict(problem.observation.customer_by_id[c["id"]]))
                for c in root["observation"]["customers"])):
        raise ValueError("Observable customer or infrastructure data changed")
    ready = set(root["ready_vehicles"])
    busy = {int(k) for k in root["busy_actions"]}
    if ready & busy or ready | busy != set(problem.ids):
        raise ValueError("Ready/busy partition changed")
    for k in ready:
        planned = decision["plans"].get(str(k))
        saved = root["initial_routes"][str(k)]
        interruptible_idle = (not saved and planned is not None and
                              len(planned["actions"]) == 1 and
                              planned["actions"][0]["kind"] == "wait")
        if planned is not None and planned["actions"] != saved and not interruptible_idle:
            raise ValueError("Original committed route differs from saved root")
    return root, problem, decision, entry, frozenset(raw["unserved_customers"])


def probe_root(root, problem, decision, entry, unserved, deadline):
    started = perf_counter()
    target = root["selected_targets"][0]["customer"]
    if (len(root["selected_targets"]) != 1 or
            target not in problem.observation.customer_by_id or target not in unserved):
        raise ValueError("Selected missed customer is not visible and unserved")
    ready = set(root["ready_vehicles"])
    first = {k: Action(**decision["plans"][str(k)]["first_action"])
             for k in ready if str(k) in decision["plans"] and
             decision["plans"][str(k)]["first_action"] is not None}
    before = timing_bound(problem.origins, problem.observation, target)
    after = timing_bound(problem.origins, problem.observation, target, first)
    record = dict(root=entry["root"], root_sha256=entry["sha256"],
                  source_raw=root["source_raw"], source_raw_sha256=root["source_raw_sha256"],
                  instance=root["instance"], observation_time=root["time"], target=target,
                  selection=root["selected_targets"][0]["selection"],
                  original_committed_actions=dict(busy=root["busy_actions"],
                                                  ready_firsts={str(k): asdict(v) for k, v in first.items()}),
                  before_bound=before, after_bound=after,
                  post_commitment_impossibility_certified=not before["certified"] and after["certified"],
                  candidates=[], candidate_count=0, timed_out=False, witness=None,
                  screened_positions={}, screened_ready_options=0,
                  screened_busy_options=0)
    if before["certified"]:
        record["status"] = "ALREADY_UNREACHABLE"
    else:
        token = set_deadline(deadline)
        try:
            plan = problem.initial(routes(root["initial_routes"]))
            if target in _owned(plan):
                raise ValueError("Selected target is already in the validated plan")
            reasons = Counter()
            for k in sorted(ready):
                sequence = plan.sequences[problem.ids.index(k)]
                for position in range(len(sequence) + 1):
                    _, _, reason = problem._screen_gap_detail(k, sequence, target, position)
                    reasons[reason] += 1
            record["screened_positions"] = dict(sorted(reasons.items()))
            options = problem.screened_options(plan.sequences, target)
            record["screened_ready_options"] = sum(k in ready for _, _, k, _, _ in options)
            record["screened_busy_options"] = len(options) - record["screened_ready_options"]
            for kind, changes, signature in candidate_moves(problem, plan, ready, target):
                if record["candidate_count"] >= MAX_CANDIDATES:
                    break
                row = dict(kind=kind, vehicles=sorted(changes),
                           sequences={str(k): list(seq) for k, seq in changes.items()})
                record["candidate_count"] += 1
                candidate = problem.change(plan, changes, "DIAGNOSTIC_" + kind.upper())
                if candidate is None:
                    row["status"] = "BOUNDED_DECODER_FAILURE"
                else:
                    proof = validate_witness(problem, plan, candidate, ready, target)
                    row["status"] = "PHYSICALLY_VALID"
                    row["first_action_changed"] = any(
                        candidate.actions[problem.ids.index(k)][:1] !=
                        plan.actions[problem.ids.index(k)][:1] for k in changes)
                    row["canonical_score"] = list(candidate.score)
                    if record["witness"] is None or row["first_action_changed"]:
                        record["witness"] = dict(kind=kind, vehicles=sorted(changes),
                                                  first_action_changed=row["first_action_changed"],
                                                  canonical_score=list(candidate.score), routes=proof)
                record["candidates"].append(row)
                if row["status"] == "PHYSICALLY_VALID" and row["first_action_changed"]:
                    break
            record["status"] = "WITNESS_FOUND" if record["witness"] else "NO_WITNESS_FOUND"
        except (PlanningDeadlineExceeded, _SearchBudgetReached):
            record["timed_out"] = True
            record["status"] = "WITNESS_FOUND" if record["witness"] else "NO_WITNESS_FOUND"
        finally:
            reset_deadline(token)
    record["diagnostic_seconds"] = perf_counter() - started
    return record


def run():
    report_path = artifact_path(STUDY, "validation", "report.json")
    summary_path = artifact_path(STUDY, "validation", "RESULTS.md")
    protocol = load_json(SOURCE / "protocol.json")
    manifest = load_json(SOURCE / "manifest.json")
    source_manifest = load_json(INSTRUMENTED / "manifest.json")
    source_protocol = load_json(INSTRUMENTED / "protocol.json")
    if (manifest["status"] != "complete" or len(manifest["records"]) != 20 or
            manifest["protocol_identifier"] != identifier(protocol) or
            protocol["scientific"]["source_manifest_identifier"] != identifier(source_manifest) or
            source_manifest["protocol_identifier"] != identifier(source_protocol)):
        raise ValueError("Frozen diagnostic or instrumented protocol identity changed")
    records = {entry["root"].rsplit("/", 1)[-1][:-5]: entry for entry in manifest["records"]}
    if len(ROOT_NAMES) > 6 or not set(ROOT_NAMES) <= set(records):
        raise ValueError("Diagnostic root selection is invalid")
    source_records = {row["raw"]: row for row in source_manifest["records"]}
    started = perf_counter()
    cache = {}
    contexts = [load_root(name, records, source_records, identifier(protocol), cache)
                for name in ROOT_NAMES]
    results = []
    for root, problem, decision, entry, unserved in contexts:
        remaining = TOTAL_SECONDS - (perf_counter() - started)
        if remaining <= 0:
            break
        results.append(probe_root(root, problem, decision, entry, unserved,
                                  perf_counter() + min(PER_ROOT_SECONDS, remaining)))
    gate = any(row["witness"] and row["witness"]["first_action_changed"] and
               row["post_commitment_impossibility_certified"] for row in results)
    report = dict(role="retrospective development feasibility only; no online policy",
                  root_manifest_sha256=_hash(SOURCE / "manifest.json"),
                  source_manifest_sha256=_hash(INSTRUMENTED / "manifest.json"),
                  selected_roots=list(ROOT_NAMES), per_root_seconds=PER_ROOT_SECONDS,
                  total_seconds_limit=TOTAL_SECONDS, max_candidates=MAX_CANDIDATES,
                  processed_roots=len(results), diagnostic_seconds=perf_counter() - started,
                  feasibility_gate="GO" if gate else "INCONCLUSIVE", results=results)
    save_json(report_path, report)
    lines = ["# SLAD service-loss feasibility probe", "",
             "Retrospective, loss-selected development roots only. No algorithm or objective changed.",
             "A feasible suffix is not evidence of a closed-loop service gain. A failed bounded",
             "decoder is not infeasibility. Direct-time certificates are conditional on",
             "the measured state and recorded physical first actions, not offline proofs.", "",
             f"Gate: **{report['feasibility_gate']}**. Processed {len(results)}/{len(ROOT_NAMES)} roots; "
             f"{report['diagnostic_seconds']:.3f} seconds. Details and replayable routes: `report.json`.", "",
             "| Instance | Time | Target | Candidates | Pre witness | Post bound | Status |",
             "| --- | ---: | --- | ---: | --- | --- | --- |"]
    lines.extend(f"| {r['instance']} | {r['observation_time']:.3f} | {r['target']} | "
                 f"{r['candidate_count']} | {bool(r['witness'])} | "
                 f"{r['post_commitment_impossibility_certified']} | {r['status']} |" for r in results)
    lines += ["", "Prior service_guard_v1, counterfactual_actions, and flex_exchange already",
              "search urgent insertions and changed first actions. This probe adds only",
              "a replayable preservation witness and a conservative post-action timing test;",
              "it does not establish a distinct online method or justify promotion.", ""]
    writable_path(summary_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"SLAD feasibility: {report['feasibility_gate']} on {len(results)} roots; "
          f"{sum(bool(r['witness']) for r in results)} physical witnesses")
    return report


if __name__ == "__main__":
    run()
