"""Separate first-feasible MP witnesses for unresolved offline reference cases."""

import argparse
import csv
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from time import perf_counter

from evrp.instance import distance, load_instance, travel_time
from evrp.model import EPS, Observation, escape_action, transition
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, check_deadline, reset_deadline, set_deadline
from evrp.reference import (ReferenceConfig, ReferenceSchedule, RouteTrace,
                            initial_vehicle, validate_reference)
from evrp.repair import build_route, route_proposal
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json, writable_path


OUTPUT = ROOT / "results/desaulniers/publication_development/reference_extension_v1"
COVERAGE = ROOT / "results/desaulniers/reference_validation/coverage.csv"
PARTIAL = ROOT / "results/desaulniers/enhancement_development/partial_reference_witnesses/manifest.csv"
LIMIT = 120.0
MPC = MPCConfig()


def unresolved_names():
    with PARTIAL.open(newline="", encoding="utf-8") as stream:
        witnessed = {row["instance"] for row in csv.DictReader(stream)}
    with COVERAGE.open(newline="", encoding="utf-8") as stream:
        return sorted(row["instance"] for row in csv.DictReader(stream)
                      if row["reference_valid"] != "True" and row["instance"] not in witnessed)


def protocol():
    files = sorted((ROOT / "evrp").rglob("*.py")) + [Path(__file__), COVERAGE, PARTIAL]
    science = dict(instances=unresolved_names(), seconds_per_instance=LIMIT,
                   mpc=asdict(MPC) | {"charge_fractions": list(MPC.charge_fractions)},
                   strategy="deadline-ordered bounded MP insertion; first full-service witness",
                   source_sha256=identifier({p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                                              for p in files}),
                   separate_from_historical_fleet_policy=True)
    path = OUTPUT / "protocol.json"
    if path.exists():
        saved = load_json(path)
        if saved["scientific"] != science:
            raise ValueError("Offline extension source or protocol drift")
        return saved
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
    frozen = dict(scientific=science, source_commit=commit)
    save_json(path, frozen)
    return frozen


def construct(instance):
    observation = Observation(instance.infrastructure.depot.ready,
                              instance.infrastructure, instance.customers)
    origin = initial_vehicle(instance)
    nodes, p = observation.customer_by_id, observation.infrastructure.parameters
    sequences, actions, costs = [], [], []
    failed = []

    def optimistic(sequence):
        if sum(nodes[c].demand for c in sequence) > p.capacity + EPS:
            return False
        location, time = origin.location, origin.time
        for c in sequence:
            customer = nodes[c]
            start = max(time + travel_time(location, customer, p), customer.ready)
            if start > customer.due + EPS:
                return False
            location, time = customer, start + customer.service
        return time + travel_time(location, observation.infrastructure.depot, p) <= observation.infrastructure.depot.due + EPS

    def insert(customer, exhaustive=False):
        candidates = []
        for index, sequence in enumerate(sequences):
            for position in range(len(sequence) + 1):
                proposed = sequence[:position] + (customer,) + sequence[position:]
                if not optimistic(proposed):
                    continue
                before = origin.location if position == 0 else nodes[sequence[position - 1]]
                after = observation.infrastructure.depot if position == len(sequence) else nodes[sequence[position]]
                delta = distance(before, nodes[customer]) + distance(nodes[customer], after) - distance(before, after)
                candidates.append((delta, index, position, proposed))
        for _, index, _, proposed in sorted(candidates)[:None if exhaustive else 12]:
            check_deadline()
            decoded = build_route(origin, proposed, observation, MPC)
            if decoded is None:
                continue
            proposal = route_proposal(origin, decoded, observation, MPC)
            if proposal is not None:
                sequences[index], actions[index], costs[index] = proposed, decoded, proposal.cost
                return True
        return False

    for customer in sorted(instance.customers, key=lambda c: (c.due, c.ready, c.id)):
        check_deadline()
        if insert(customer.id):
            continue
        decoded = build_route(origin, (customer.id,), observation, MPC)
        proposal = route_proposal(origin, decoded, observation, MPC) if decoded else None
        if proposal is None:
            failed.append(customer.id)
        else:
            sequences.append((customer.id,))
            actions.append(decoded)
            costs.append(proposal.cost)
    for customer in failed:
        if not insert(customer, exhaustive=True):
            raise ValueError(f"No bounded construction witness for {customer}; not an infeasibility proof")
    traces = []
    for k, (sequence, route) in enumerate(zip(sequences, actions)):
        state, steps = initial_vehicle(instance, k), []
        for action in route:
            check_deadline()
            step = transition(state, action, observation)
            steps.append(step)
            state = step.after
        for _ in range(len(instance.infrastructure.stations) + 3):
            if state.finished:
                break
            check_deadline()
            step = transition(state, escape_action(state, instance.infrastructure), observation)
            steps.append(step)
            state = step.after
        if not state.finished:
            raise ValueError("Offline safe-return action guard exceeded")
        traces.append(RouteTrace(sequence, tuple(steps)))
    reference = ReferenceSchedule(instance.name, instance.sha256,
                                  ReferenceConfig(multistarts=1, improvement_passes=0), tuple(traces),
                                  provenance="separate_mp_first_feasible_insertion_v1")
    validate_reference(instance, reference)
    return reference


def worker(name):
    frozen = protocol()
    if name not in frozen["scientific"]["instances"]:
        raise ValueError("Unknown offline extension instance")
    target = OUTPUT / "workers" / f"{name}.json"
    if target.exists():
        raise ValueError("Existing offline worker evidence must be reused")
    started = perf_counter()
    instance = load_instance(BENCHMARK / f"{name}.txt")
    token = set_deadline(perf_counter() + LIMIT)
    record = dict(instance=name, instance_sha256=instance.sha256, protocol_identifier=identifier(frozen))
    try:
        reference = construct(instance)
        path = OUTPUT / "references" / f"{name}.json"
        if path.exists():
            raise ValueError("Unmanifested reference already exists")
        reference.save(path)
        loaded = ReferenceSchedule.load(path, instance)
        record.update(status="feasible_reference_found", fleet_size=loaded.fleet_size,
                      distance=loaded.total_distance, reference=path.relative_to(ROOT).as_posix(),
                      reference_sha256=sha256(path.read_bytes()).hexdigest(), reference_id=loaded.identifier)
    except PlanningDeadlineExceeded:
        record.update(status="search_timeout", reason=f"MP witness search reached {LIMIT}s")
    except ValueError as error:
        record.update(status="construction_unresolved", reason=str(error))
    finally:
        reset_deadline(token)
    record["seconds"] = perf_counter() - started
    save_json(target, record)


def run():
    frozen = protocol()
    records = []
    for name in frozen["scientific"]["instances"]:
        path = OUTPUT / "workers" / f"{name}.json"
        if not path.exists():
            subprocess.run([sys.executable, "-u", "-m", "scripts.extend_mp_reference_coverage",
                            "--worker", name], cwd=ROOT, check=True, timeout=LIMIT + 30)
        record = load_json(path)
        if record["protocol_identifier"] != identifier(frozen):
            raise ValueError("Offline reference worker protocol mismatch")
        if record["status"] == "feasible_reference_found":
            target = ROOT / record["reference"]
            if sha256(target.read_bytes()).hexdigest() != record["reference_sha256"]:
                raise ValueError("Offline reference artifact corrupted")
            instance = load_instance(BENCHMARK / f"{name}.txt")
            loaded = ReferenceSchedule.load(target, instance)
            if loaded.identifier != record["reference_id"]:
                raise ValueError("Offline reference physical replay or identity mismatch")
        records.append(record | {"worker_sha256": sha256(path.read_bytes()).hexdigest()})
        save_json(OUTPUT / "manifest.json", dict(protocol_identifier=identifier(frozen), records=records,
                  completed_instances=len(records), planned_instances=len(frozen["scientific"]["instances"])))
        print(f"MP reference {len(records)}/{len(frozen['scientific']['instances'])}: {name} "
              f"{record['status']} K={record.get('fleet_size', '-')}", flush=True)
    valid = sum(r["status"] == "feasible_reference_found" for r in records)
    lines = ["# Separate MP reference coverage extension", "",
             "This offline study uses the original partial-charge route decoder to",
             "construct and immediately save a first full-service feasible reference.",
             "Every successful schedule was independently reloaded and replayed.",
             "Fleet sizes are heuristic upper bounds, not optimal fleet counts. They",
             "are not substituted into any historical online comparison or scenario.", "",
             f"Additional references found: {valid}/{len(records)}. Combined physical",
             f"witness coverage: {150 + valid}/168 (144 historical references plus six",
             "separate published-route partial-charge witnesses and this extension).", "",
             "| Instance | Status | Fleet size | Distance | Seconds |",
             "| --- | --- | ---: | ---: | ---: |"]
    lines.extend(f"| {r['instance']} | {r['status']} | {r.get('fleet_size', '')} | "
                 f"{r.get('distance', '')} | {r['seconds']:.1f} |" for r in records)
    lines += ["", "Unresolved construction and timeout records are not proofs of physical infeasibility.", ""]
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker")
    args = parser.parse_args()
    worker(args.worker) if args.worker else run()
