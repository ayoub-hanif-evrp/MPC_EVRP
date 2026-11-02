"""Bounded follow-up on two frozen service-loss transitions.

Busy origins are recorded post-action states. Their executing actions are fixed;
only the routes beginning at those origins may change.
"""

from dataclasses import asdict, replace
from time import perf_counter

from evrp.fleet_mcts import _SearchBudgetReached
from evrp.model import Action, escape, transition
from evrp.planning_budget import PlanningDeadlineExceeded, reset_deadline, set_deadline
from evrp.repair import route_proposal
from evrp.resource_decoder import decode_resource_labels
from evrp.storage import identifier, load_json, save_json, writable_path
from scripts.analyze_planning_losses import covered, routes
from scripts.experiments.paths import artifact_path
from scripts.experiments import probe_service_loss as v1


STUDY = "slad_feasibility_v2"
PAIRS = (
    ("C1 / C18", "ff126a096d7cf28a", "5231d02399560db9"),
    ("R1 / C65", "8165e1ffd495a276", "f324a97f201fb12f"),
)
NEGATIVE = "219bffea81a97e08"
PER_LATER_ROOT_SECONDS = 5.0
TOTAL_SECONDS = 60.0
MAX_CANDIDATES = 12
MAX_RESOURCE_FALLBACKS = 4


def load_contexts():
    protocol = load_json(v1.SOURCE / "protocol.json")
    manifest = load_json(v1.SOURCE / "manifest.json")
    source_manifest = load_json(v1.INSTRUMENTED / "manifest.json")
    source_protocol = load_json(v1.INSTRUMENTED / "protocol.json")
    if (manifest["status"] != "complete" or len(manifest["records"]) != 20 or
            manifest["protocol_identifier"] != identifier(protocol) or
            protocol["scientific"]["source_manifest_identifier"] != identifier(source_manifest) or
            source_manifest["protocol_identifier"] != identifier(source_protocol)):
        raise ValueError("Frozen diagnostic or instrumented protocol identity changed")
    records = {row["root"].rsplit("/", 1)[-1][:-5]: row for row in manifest["records"]}
    names = [name for _, earlier, later in PAIRS for name in (earlier, later)] + [NEGATIVE]
    if len(names) != len(set(names)) or not set(names) <= set(records):
        raise ValueError("Missing or duplicated selected roots")
    source_records = {row["raw"]: row for row in source_manifest["records"]}
    raw_cache = {}
    contexts = {name: v1.load_root(name, records, source_records, identifier(protocol), raw_cache)
                for name in names}
    return contexts, dict(root_manifest_sha256=v1._hash(v1.SOURCE / "manifest.json"),
                          source_manifest_sha256=v1._hash(v1.INSTRUMENTED / "manifest.json"))


def owners(plan, problem):
    return {customer: k for i, k in enumerate(problem.ids) for customer in plan.sequences[i]}


def recorded_firsts(decision, ready):
    return {k: Action(**decision["plans"][str(k)]["first_action"])
            for k in sorted(ready) if str(k) in decision["plans"] and
            decision["plans"][str(k)]["first_action"] is not None}


def check_busy_origins(root, problem):
    """Check that each suffix starts after, never in place of, its recorded action."""
    busy = {int(k): Action(**value) for k, value in root["busy_actions"].items()}
    ready = set(root["ready_vehicles"])
    if set(busy) & ready or set(busy) | ready != set(problem.ids):
        raise ValueError("Ready/busy partition changed")
    for k, action in busy.items():
        origin = problem.origins[k]
        if (origin.id != k or origin.time + 1e-8 < problem.observation.time or
                origin.location.id != action.destination or origin.current_committed_action is not None or
                (action.kind == "serve" and action.destination not in origin.served_customers)):
            raise ValueError("Busy origin does not represent the recorded post-action state")
    return busy


def check_transition(earlier, later):
    early_root, early_problem, early_decision, _, early_unserved = earlier
    late_root, late_problem, _, _, late_unserved = later
    target = early_root["selected_targets"][0]["customer"]
    if (target != late_root["selected_targets"][0]["customer"] or
            target not in early_unserved & late_unserved or
            early_root["source_raw"] != late_root["source_raw"] or
            early_root["instance"] != late_root["instance"] or
            late_root["source_decision_index"] != early_root["source_decision_index"] + 1 or
            late_root["time"] <= early_root["time"]):
        raise ValueError("Selected roots are not an adjacent loss transition")
    early_busy = check_busy_origins(early_root, early_problem)
    late_busy = check_busy_origins(late_root, late_problem)
    firsts = recorded_firsts(early_decision, set(early_root["ready_vehicles"]))
    for k in sorted(set(early_busy) & set(late_busy)):
        if early_busy[k] != late_busy[k] or early_problem.origins[k] != late_problem.origins[k]:
            raise ValueError("An in-flight action or its recorded after-state changed")
    newly_busy = {}
    for k in sorted(set(late_busy) - set(early_busy)):
        if k not in firsts or firsts[k] != late_busy[k]:
            raise ValueError("New busy action differs from prior recorded dispatch")
        replayed = transition(early_problem.origins[k], firsts[k], early_problem.observation).after
        if replayed != late_problem.origins[k]:
            raise ValueError("New busy post-action state does not replay exactly")
        newly_busy[str(k)] = dict(action=asdict(firsts[k]), after=asdict(replayed))
    return target, newly_busy


def replay_plan(problem, plan, root):
    """Independent physical replay from every recorded post-action origin."""
    check_busy_origins(root, problem)
    if len({c for seq in plan.sequences for c in seq}) != sum(map(len, plan.sequences)):
        raise ValueError("Duplicate planned customer")
    if any(c not in problem.pending for seq in plan.sequences for c in seq):
        raise ValueError("Plan uses hidden, served, or committed customer")
    evidence = {}
    for i, k in enumerate(problem.ids):
        origin = problem.origins[k]
        actions = plan.actions[i]
        if tuple(a.destination for a in actions if a.kind == "serve") != plan.sequences[i]:
            raise ValueError("Action route does not match service sequence")
        state = origin
        for action in actions:
            state = transition(state, action, problem.observation).after
        proposal = route_proposal(origin, actions, problem.observation, problem.config) if actions else None
        if actions and proposal is None:
            raise ValueError("Candidate route failed independent physical replay")
        safe = escape(state, problem.observation.infrastructure)
        if safe is None or safe.completion > problem.observation.infrastructure.depot.due + 1e-8:
            raise ValueError("Candidate has no feasible safe return")
        evidence[str(k)] = dict(recorded_busy_action=root["busy_actions"].get(str(k)),
                                origin=asdict(origin), actions=[asdict(a) for a in actions],
                                service_sequence=list(plan.sequences[i]),
                                final_state=asdict(state), safe_return_completion=safe.completion,
                                predicted_cost=proposal.cost if proposal else None)
    return evidence


def coverage_accounting(before, after, target):
    before, after = set(before), set(after)
    added, dropped = sorted(after - before), sorted(before - after)
    return dict(added=added, dropped=dropped, baseline_preserved=not dropped,
                service_delta=len(after) - len(before),
                target_served=target in after,
                additional_coverage=(target in added and not dropped),
                equal_service_swap=(target in added and bool(dropped) and len(added) == len(dropped)))


def first_action_changes(problem, candidate, decision, ready):
    original = recorded_firsts(decision, ready)
    changed = []
    for k in sorted(ready):
        actions = candidate.actions[problem.ids.index(k)]
        proposed = actions[0] if actions else None
        old = original.get(k)
        if old is not None and old.kind == "wait" and proposed is None:
            continue  # Empty route uses the simulator's interruptible idle fallback.
        if old != proposed:
            changed.append(k)
    return changed


def candidate_changes(problem, baseline, earlier_problem, earlier_plan, target, ready):
    """Targeted, deterministic reuse of insertion, retained suffix, and V1 exchanges."""
    seen = set()

    def unique(kind, changes):
        key = tuple(sorted(changes.items()))
        if key in seen:
            return None
        seen.add(key)
        return kind, changes

    for _, _, k, pos, _ in problem.screened_options(baseline.sequences, target)[:6]:
        seq = baseline.sequences[problem.ids.index(k)]
        item = unique("direct_insertion", {k: seq[:pos] + (target,) + seq[pos:]})
        if item:
            yield item

    prior_owner = owners(earlier_plan, earlier_problem)[target]
    prior = earlier_plan.sequences[earlier_problem.ids.index(prior_owner)]
    if prior_owner in problem.ids and all(c in problem.pending for c in prior):
        current = baseline.sequences[problem.ids.index(prior_owner)]
        if prior != current:
            item = unique("retained_prior_suffix", {prior_owner: prior})
            if item:
                yield item

    for _, changes, _ in v1.candidate_moves(problem, baseline, ready, target):
        item = unique("v1_ready_exchange", changes)
        if item:
            yield item

    if prior_owner in problem.ids and all(c in problem.pending for c in prior):
        current = baseline.sequences[problem.ids.index(prior_owner)]
        displaced = sorted(set(current) - set(prior))
        proposed = list(baseline.sequences)
        proposed[problem.ids.index(prior_owner)] = prior
        for customer in displaced[:2]:
            for _, _, k, pos, _ in problem.screened_options(tuple(proposed), customer)[:4]:
                if k == prior_owner:
                    continue
                sequence = baseline.sequences[problem.ids.index(k)]
                item = unique("retained_suffix_with_reassignment", {
                    prior_owner: prior, k: sequence[:pos] + (customer,) + sequence[pos:]})
                if item:
                    yield item


def decode_candidate(problem, baseline, changes, fallback_budget):
    candidate = problem.change(baseline, changes, "SLAD_V2_DIAGNOSTIC")
    fallback_used = 0
    if candidate is None and fallback_budget:
        for k, sequence in sorted(changes.items()):
            if fallback_used >= fallback_budget:
                break
            if problem.decoded.get((k, sequence), True) is not None or not sequence:
                continue
            fallback_used += 1
            actions = decode_resource_labels(
                problem.origins[k], sequence, problem.observation,
                replace(problem.config, route_decoder_version="resource_labels_v2"))
            proposal = (route_proposal(problem.origins[k], actions, problem.observation, problem.config)
                        if actions else None)
            if proposal is not None:
                problem.decoded[k, sequence] = (actions, proposal)
        if fallback_used:
            candidate = problem.change(baseline, changes, "SLAD_V2_DIAGNOSTIC")
    return candidate, fallback_used


def pair_observation(earlier, later, target, newly_busy):
    early_root, early_problem, _, early_entry, _ = earlier
    late_root, late_problem, _, late_entry, _ = later
    early_plan = early_problem.initial(routes(early_root["initial_routes"]))
    late_plan = late_problem.initial(routes(late_root["initial_routes"]))
    early_proof = replay_plan(early_problem, early_plan, early_root)
    late_proof = replay_plan(late_problem, late_plan, late_root)
    prior_owners = owners(early_plan, early_problem)
    current_owners = owners(late_plan, late_problem)
    committed_or_served = set(late_problem.observation.committed_ids)
    committed_or_served.update(c for state in late_problem.origins.values()
                               for c in state.served_customers)
    still_pending_prior = set(prior_owners) - committed_or_served
    old_visible = set(early_problem.observation.customer_by_id)
    new_visible = set(late_problem.observation.customer_by_id)
    assignments = {c: dict(before=prior_owners[c], after=current_owners.get(c),
                           status=("committed_or_served" if c in committed_or_served else
                                   "lost_from_plan" if c not in current_owners else
                                   "retained" if current_owners[c] == prior_owners[c] else "reassigned"))
                   for c in sorted(prior_owners)}
    suffix_changes = {str(k): dict(before=list(early_plan.sequences[early_problem.ids.index(k)]),
                                   after=list(late_plan.sequences[late_problem.ids.index(k)]))
                      for k in early_problem.ids if k in late_problem.ids and
                      early_plan.sequences[early_problem.ids.index(k)] !=
                      late_plan.sequences[late_problem.ids.index(k)]}
    return early_plan, late_plan, dict(
        target=target, earlier=dict(root=early_entry["root"], sha256=early_entry["sha256"],
                                    source_raw=early_root["source_raw"],
                                    source_raw_sha256=early_root["source_raw_sha256"],
                                    time=early_root["time"], ready=early_root["ready_vehicles"],
                                    busy_actions=early_root["busy_actions"],
                                    target_owner=prior_owners.get(target),
                                    planned_coverage=sorted(prior_owners),
                                    replay=early_proof),
        later=dict(root=late_entry["root"], sha256=late_entry["sha256"],
                   source_raw=late_root["source_raw"],
                   source_raw_sha256=late_root["source_raw_sha256"],
                   time=late_root["time"], ready=late_root["ready_vehicles"],
                   busy_actions=late_root["busy_actions"],
                   target_owner=current_owners.get(target),
                   planned_coverage=sorted(current_owners),
                   constructor_coverage=sorted(covered(late_root["constructor_routes"])),
                   replay=late_proof),
        newly_busy_replayed=newly_busy,
        visible_added=sorted(new_visible - old_visible),
        visible_removed=sorted(old_visible - new_visible),
        prior_assignments=assignments,
        previously_planned_still_pending=sorted(still_pending_prior),
        lost_from_plan=sorted(still_pending_prior - set(current_owners)),
        newly_planned=sorted(set(current_owners) - set(prior_owners)),
        changed_suffixes=suffix_changes)


def probe_later(earlier, later, target, earlier_plan, baseline, deadline):
    root, problem, decision, _, _ = later
    earlier_problem = earlier[1]
    before_coverage = set(owners(baseline, problem))
    ready = set(root["ready_vehicles"])
    bound = v1.timing_bound(problem.origins, problem.observation, target)
    result = dict(status="NO_WITNESS_FOUND", before_bound=bound, candidates=[],
                  candidate_count=0, timed_out=False, witnesses=0,
                  resource_fallbacks=0)
    if bound["certified"]:
        result["status"] = "ALREADY_UNREACHABLE"
        return result
    token = set_deadline(deadline)
    started = perf_counter()
    try:
        for kind, changes in candidate_changes(problem, baseline, earlier_problem,
                                               earlier_plan, target, ready):
            if result["candidate_count"] >= MAX_CANDIDATES:
                break
            row = dict(kind=kind, sequences={str(k): list(v) for k, v in changes.items()})
            result["candidate_count"] += 1
            try:
                candidate, used = decode_candidate(problem, baseline, changes,
                                                   MAX_RESOURCE_FALLBACKS - result["resource_fallbacks"])
                result["resource_fallbacks"] += used
                if candidate is None:
                    row["status"] = "BOUNDED_SEARCH_FAILURE"
                else:
                    proof = replay_plan(problem, candidate, root)
                    coverage = coverage_accounting(before_coverage, owners(candidate, problem), target)
                    row.update(status="PHYSICALLY_VALID", coverage=coverage,
                               busy_suffix_changed=[k for k in sorted(int(k) for k in root["busy_actions"])
                                                    if candidate.actions[problem.ids.index(k)] !=
                                                    baseline.actions[problem.ids.index(k)]],
                               ready_first_action_changed=first_action_changes(
                                   problem, candidate, decision, ready),
                               owner_after=owners(candidate, problem).get(target),
                               canonical_score=list(candidate.score), replay=proof)
                    result["witnesses"] += 1
            except (PlanningDeadlineExceeded, _SearchBudgetReached):
                row["status"] = "TIMEOUT"
                result["timed_out"] = True
                result["candidates"].append(row)
                break
            result["candidates"].append(row)
        if result["witnesses"]:
            result["status"] = "WITNESS_FOUND"
    except (PlanningDeadlineExceeded, _SearchBudgetReached):
        result["timed_out"] = True
    finally:
        reset_deadline(token)
    result["search_seconds"] = perf_counter() - started
    return result


def run():
    report_path = artifact_path(STUDY, "validation", "report.json")
    summary_path = artifact_path(STUDY, "validation", "RESULTS.md")
    started = perf_counter()
    contexts, hashes = load_contexts()
    cases = []
    for label, prior_name, late_name in PAIRS:
        earlier, later = contexts[prior_name], contexts[late_name]
        target, newly_busy = check_transition(earlier, later)
        early_plan, late_plan, observation = pair_observation(earlier, later, target, newly_busy)
        remaining = TOTAL_SECONDS - (perf_counter() - started)
        if remaining <= 0:
            probe = dict(status="NO_WITNESS_FOUND", timed_out=True, candidate_count=0,
                         candidates=[], witnesses=0, reason="total computation cap")
        else:
            probe = probe_later(earlier, later, target, early_plan, late_plan,
                                perf_counter() + min(PER_LATER_ROOT_SECONDS, remaining))
        cases.append(dict(case=label, observation=observation, probe=probe))
    negative = contexts[NEGATIVE]
    negative_root, negative_problem, _, negative_entry, _ = negative
    negative_target = negative_root["selected_targets"][0]["customer"]
    negative_bound = v1.timing_bound(negative_problem.origins, negative_problem.observation,
                                     negative_target)
    if not negative_bound["certified"]:
        raise ValueError("Negative-control direct-arrival certificate disappeared")
    gate = "INCONCLUSIVE"
    if any(row["probe"]["witnesses"] and any(
            c["status"] == "PHYSICALLY_VALID" and
            c["coverage"]["additional_coverage"] and c["busy_suffix_changed"]
            for c in row["probe"]["candidates"]) for row in cases):
        gate = "GO - prototype justified"
    report = dict(role="retrospective development diagnosis, not an online policy",
                  decision=gate, pairs=[list(p) for p in PAIRS],
                  negative_control=dict(root=negative_entry["root"], sha256=negative_entry["sha256"],
                                        target=negative_target, time=negative_root["time"],
                                        direct_arrival_bound=negative_bound,
                                        candidate_count=0, status="ALREADY_UNREACHABLE"),
                  per_later_root_seconds=PER_LATER_ROOT_SECONDS, total_seconds_limit=TOTAL_SECONDS,
                  max_candidates=MAX_CANDIDATES, max_resource_fallbacks=MAX_RESOURCE_FALLBACKS,
                  elapsed_seconds=perf_counter() - started, **hashes, cases=cases)
    save_json(report_path, report)
    lines = ["# SLAD service-loss transition diagnosis V2", "",
             "Retrospective, loss-selected development transitions. V1 outputs are unchanged.",
             "Only recorded observations enter candidate construction. Busy actions are",
             "immutable; their recorded after-states are the origins for adjustable suffixes.",
             "Earlier plans are observations, not recovery witnesses.", "",
             f"Decision: **{gate}**. Full hashes, actions, per-vehicle physical replay,",
             "candidate failures, and safe-return evidence are in `report.json`.", "",
             "| Case | Prior -> loss time | Prior owner | Candidates | Valid | Added-coverage witnesses | Equal swaps |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in cases:
        obs, probe = row["observation"], row["probe"]
        valid = [c for c in probe["candidates"] if c["status"] == "PHYSICALLY_VALID"]
        lines.append(f"| {row['case']} | {obs['earlier']['time']:.3f} -> {obs['later']['time']:.3f} | "
                     f"{obs['earlier']['target_owner']} | {probe['candidate_count']} | {len(valid)} | "
                     f"{sum(c['coverage']['additional_coverage'] for c in valid)} | "
                     f"{sum(c['coverage']['equal_service_swap'] for c in valid)} |")
        lines.extend(["", f"## {row['case']}", "",
                      f"Prior target owner: EV {obs['earlier']['target_owner']}; later validated "
                      f"target owner: {obs['later']['target_owner']}. "
                      f"Lost from plan: {', '.join(obs['lost_from_plan']) or 'none'}. "
                      f"Newly planned: {', '.join(obs['newly_planned']) or 'none'}.",
                      f"The later constructor still planned {obs['target']}: "
                      f"{obs['target'] in obs['later']['constructor_coverage']}. "
                      "The loss is a constructor-to-validated-plan selection change.",
                      f"New busy actions replayed: {', '.join(obs['newly_busy_replayed']) or 'none'}. "
                      f"Later search status: {probe['status']}; timed out: {probe['timed_out']}."])
        for candidate in probe["candidates"]:
            if candidate["status"] == "PHYSICALLY_VALID":
                cov = candidate["coverage"]
                lines.append(f"- {candidate['kind']}: physical; added {cov['added']}, "
                             f"dropped {cov['dropped']}, service delta {cov['service_delta']}; "
                             f"busy suffixes changed {candidate['busy_suffix_changed']}; "
                             f"ready firsts changed {candidate['ready_first_action_changed']}.")
            else:
                lines.append(f"- {candidate['kind']}: {candidate['status']} "
                             "(not a physical infeasibility proof).")
    lines += ["", "## Negative control", "",
              f"Root {NEGATIVE}: {negative_target} is already unreachable under the",
              "optimistic direct-travel necessary condition. No rescue candidate was",
              "generated. Passing an optimistic bound would not itself validate an EV route.",
              "", "## Interpretation", "",
              "A valid future-suffix change is not automatically a better dispatch policy.",
              "Equal-service swaps are not additional coverage. No candidate proves that",
              "the preceding decision caused a later service loss. This bounded result",
              "does not establish a closed-loop service-rate improvement.", ""]
    writable_path(summary_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"SLAD V2: {gate}; {[(r['case'], r['probe']['candidate_count'], r['probe']['witnesses']) for r in cases]}")
    return report


if __name__ == "__main__":
    run()
