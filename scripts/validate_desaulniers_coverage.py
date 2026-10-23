"""Inspect every active Desaulniers instance without changing benchmark inputs.

Fallback construction runs in isolated, time-limited processes. A timeout is
evidence of an unresolved search, never a claim of physical infeasibility.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

from evrp.instance import discover_instances, load_instance
from evrp.reference import (ReferenceConfig, ReferenceSchedule, published_full_reference,
                            solve_reference, validate_reference)
from evrp.scenario import generate
from evrp.storage import PUBLISHED_SOLUTIONS, ROOT, load_json, save_json, writable_path
from scripts.run_desaulniers_pilot import dataset_hash, family_of


OUTPUT = ROOT / "results/desaulniers/reference_validation"
FIELDS = ("instance", "family", "customers", "stations", "parsed", "arcs_consistent",
          "coordinates_valid", "travel_time_consistent", "rounded_cost_consistent",
          "energy_consistent", "charging_policy", "available_solutions",
          "published_variants", "published_full_route_mp_feasible",
          "partial_route_order_mp_feasible",
          "fallback_status", "reference_vehicles", "reference_distance",
          "reference_seconds", "reference_valid", "information_model_valid",
          "reference_artifact", "reason")


def cached_reference(instance, config):
    for path in sorted((ROOT / "results/reference_schedules").glob(f"{instance.name}_*.json")):
        try:
            schedule = ReferenceSchedule.load(path, instance)
        except (ValueError, KeyError, TypeError, OSError) as error:
            continue
        if schedule.config == config and schedule.provenance == "constructed":
            return schedule
    return None


def worker(name):
    instance = load_instance(next(p for p in discover_instances() if p.stem == name))
    schedule = solve_reference(instance, ReferenceConfig())
    validate_reference(instance, schedule)
    generate(instance, schedule, seed=1, dynamicity=0.0).validate(instance)
    artifact = OUTPUT / "references" / f"{name}_{schedule.identifier[:16]}.json"
    if artifact.exists():
        if ReferenceSchedule.load(artifact, instance).identifier != schedule.identifier:
            raise ValueError("Existing constructed-reference artifact differs")
    else:
        schedule.save(artifact)
    print(json.dumps({"vehicles": schedule.fleet_size, "distance": schedule.total_distance,
                      "identifier": schedule.identifier,
                      "artifact": artifact.relative_to(ROOT).as_posix()}), flush=True)


def inspect(path, timeout):
    row = dict.fromkeys(FIELDS, "")
    row.update(instance=path.stem, family=family_of(path.stem),
               customers=int(path.stem.rsplit("_", 1)[1]), charging_policy="MP")
    started = perf_counter()
    try:
        instance = load_instance(path)  # Validates every format-2 arc against format-1.
        row.update(parsed=True, arcs_consistent=True,
                   stations=len(instance.infrastructure.stations))
        if instance.infrastructure.parameters.allow_station_to_station:
            raise ValueError("Station-to-station travel unexpectedly enabled")
        variants = [v for v in ("MF", "SF") if
                    (PUBLISHED_SOLUTIONS / v / f"solution{instance.name}").is_file()]
        row["published_variants"] = ",".join(variants)
        schedule = published_full_reference(instance, ReferenceConfig()) if variants else None
        row["published_mp_feasible"] = schedule is not None
        if schedule is None:
            schedule = cached_reference(instance, ReferenceConfig())
            if schedule is not None:
                row["fallback_status"] = "validated_cache"
            else:
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "scripts.validate_desaulniers_coverage",
                         "--worker", instance.name], cwd=ROOT, capture_output=True,
                        text=True, timeout=timeout, check=True)
                    payload = json.loads(result.stdout.strip())
                    row.update(fallback_status="constructed", reference_vehicles=payload["vehicles"],
                               reference_distance=payload["distance"], reference_valid=True,
                               information_model_valid=True)
                except subprocess.TimeoutExpired:
                    row.update(fallback_status="timeout", reason=f"Reference search exceeded {timeout}s")
                except (subprocess.CalledProcessError, ValueError) as error:
                    row.update(fallback_status="search_failed", reason=str(error)[-600:])
        if schedule is not None:
            validate_reference(instance, schedule)
            departures = schedule.predecessor_departures
            row.update(reference_vehicles=schedule.fleet_size,
                       reference_distance=schedule.total_distance, reference_valid=True,
                       information_model_valid=(len(departures) == len(instance.customers)
                           and set(departures) == {c.id for c in instance.customers}
                           and all(instance.infrastructure.depot.ready <= t <=
                                   instance.infrastructure.depot.due for t in departures.values())))
    except Exception as error:
        row["reason"] = f"{type(error).__name__}: {error}"
    row["reference_seconds"] = round(perf_counter() - started, 3)
    return row


def render(rows, timeout=120):
    fingerprint = dataset_hash()
    final = load_json(ROOT / "results/desaulniers/final_holdout_audit_erratum/protocol.json")
    if fingerprint != final["dataset_sha256"]:
        raise ValueError("Benchmark bundle differs from the corrected final protocol")
    partial_path = OUTPUT / "partial_published_audit.csv"
    partial = {}
    if partial_path.exists():
        with partial_path.open(newline="", encoding="utf-8") as stream:
            for evidence in csv.DictReader(stream):
                name = evidence["instance"]
                partial[name] = partial.get(name, False) or (
                    evidence["route_order_replay_feasible"] == "True" and
                    evidence["complete"] == "True")
    for row in rows:
        row["coordinates_valid"] = row["parsed"] is True
        row["published_full_route_mp_feasible"] = row["published_mp_feasible"] is True
        row["partial_route_order_mp_feasible"] = partial.get(row["instance"], False)
        for field in ("travel_time_consistent", "rounded_cost_consistent", "energy_consistent"):
            row[field] = row["arcs_consistent"] is True
        row["available_solutions"] = ",".join(
            variant for variant in ("SF", "MF", "SP", "MP") if
            (PUBLISHED_SOLUTIONS / variant / f"solution{row['instance']}").is_file())
        artifacts = sorted((OUTPUT / "references").glob(f"{row['instance']}_*.json"))
        row["reference_artifact"] = (artifacts[0].relative_to(ROOT).as_posix()
                                     if len(artifacts) == 1 else "")
    csv_path = writable_path(OUTPUT / "coverage.csv")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    counts = {"inspected": len(rows), "parsed": sum(r["parsed"] is True for r in rows),
              "published": sum(r["published_mp_feasible"] is True for r in rows),
              "fallback": sum(r["fallback_status"] in {"validated_cache", "constructed"} for r in rows),
              "unresolved": sum(r["reference_valid"] is not True for r in rows)}
    lines = ["# Desaulniers MP reference coverage", "",
             "Every format-1 file is paired with and checked against all format-2 arcs."
             " Published full-charge routes are replayed under MP. Constructed references"
             " are offline preprocessing, not online MPC runs.", "",
             "Fallback uses the unchanged offline `ReferenceConfig` defaults "
             "(3 multistarts, 1 improvement pass, seed 0, 24 labels) in an "
             f"isolated process with a {timeout}-second per-instance limit. "
             "Validation time includes parsing and replay overhead.", "",
             f"Dataset fingerprint: `{fingerprint}` (matches corrected final protocol).", "",
             f"Inspected: {counts['inspected']}/168; parsed/arcs consistent: {counts['parsed']}; "
             f"published MP references: {counts['published']}; constructed/cached: {counts['fallback']}; "
             f"unresolved: {counts['unresolved']}.", "",
             "A search failure or timeout is not proof of infeasibility. Full per-instance "
             "evidence and reasons are in `coverage.csv`.", "",
             "`available_solutions` lists SF/MF/SP/MP files; only physically replayed "
             "SF/MF routes are used to define offline reference fleets. "
             "SP/MP route-order witnesses are reported separately and never substituted "
             "into the frozen final or robustness reference policy. "
             "`arcs_consistent` validates every cost, travel-time, and energy arc "
             "against the coordinate source. The information-model check records "
             "complete reference predecessor-departure bounds; online no-future-leakage "
             "is separately tested and audited in experiment traces.", "",
             "| Size | Instances | SF/MF MP references | Fallback validated | Unresolved |",
             "| ---: | ---: | ---: | ---: | ---: |"]
    for size in (25, 50, 100):
        group = [r for r in rows if r["customers"] == size]
        lines.append(f"| {size} | {len(group)} | "
                     f"{sum(r['published_mp_feasible'] is True for r in group)} | "
                     f"{sum(r['fallback_status'] in {'validated_cache', 'constructed'} for r in group)} | "
                     f"{sum(r['reference_valid'] is not True for r in group)} |")
    lines.append("")
    lines.append(f"Published SP/MP route-order witnesses on instances lacking SF/MF: "
                 f"{sum(r['partial_route_order_mp_feasible'] for r in rows)} distinct instances. "
                 "See `PARTIAL_SOLUTIONS.md` for the LP-witness limitation.")
    lines.append(f"Of the unresolved reference cases, "
                 f"{sum(r['reference_valid'] is not True and r['partial_route_order_mp_feasible'] for r in rows)} "
                 "already have a physically witnessable published partial route order; "
                 "their unresolved status is a limitation of the frozen reference path, "
                 "not evidence of MP infeasibility.")
    lines.append("")
    for r in rows:
        if r["reference_valid"] is not True:
            lines.append(f"- {r['instance']}: {r['fallback_status'] or 'parse/replay failure'}; {r['reason']}")
    writable_path(OUTPUT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main(timeout, workers=1):
    checkpoint = OUTPUT / "checkpoint.json"
    existing = load_json(checkpoint) if checkpoint.exists() else {}
    rows = {}
    pending = []
    for path in discover_instances():
        fingerprint = sha256(path.read_bytes()).hexdigest()
        saved = existing.get(path.stem)
        if saved and saved["format1_sha256"] == fingerprint:
            rows[path.stem] = saved
            continue
        pending.append((path, fingerprint))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(inspect, path, timeout): (path, fingerprint)
                   for path, fingerprint in pending}
        for future in as_completed(futures):
            path, fingerprint = futures[future]
            row = future.result()
            rows[path.stem] = dict(row, format1_sha256=fingerprint)
            save_json(checkpoint, rows)
            print(f"coverage {len(rows)}/168 {path.stem}: {row['reference_valid']}", flush=True)
    counts = render([rows[p.stem] for p in discover_instances()], timeout)
    print(counts)


def materialize_reference(name, timeout):
    instance = load_instance(next(p for p in discover_instances() if p.stem == name))
    artifacts = list((OUTPUT / "references").glob(f"{name}_*.json"))
    if artifacts:
        if len(artifacts) != 1:
            raise ValueError(f"Multiple constructed-reference artifacts for {name}")
        ReferenceSchedule.load(artifacts[0], instance)
        return
    schedule = cached_reference(instance, ReferenceConfig())
    if schedule is not None:
        artifact = OUTPUT / "references" / f"{name}_{schedule.identifier[:16]}.json"
        schedule.save(artifact)
    else:
        subprocess.run([sys.executable, "-m", "scripts.validate_desaulniers_coverage",
                        "--worker", name], cwd=ROOT, capture_output=True, text=True,
                       timeout=timeout, check=True)


def materialize_references(timeout, workers=1):
    rows = load_json(OUTPUT / "checkpoint.json")
    if set(rows) != {path.stem for path in discover_instances()}:
        raise ValueError("Complete 168-instance scan is required before materialization")
    selected = [name for name, row in sorted(rows.items())
                if row["published_mp_feasible"] is not True and row["reference_valid"] is True]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(materialize_reference, name, timeout): name
                   for name in selected}
        for future in as_completed(futures):
            name = futures[future]
            future.result()
            print(f"materialized {name}", flush=True)
    render([rows[p.stem] for p in discover_instances()], timeout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker")
    parser.add_argument("--fallback-timeout", type=int, default=120)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--materialize-references", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 8:
        parser.error("--workers must be between 1 and 8")
    if args.worker:
        worker(args.worker)
    elif args.materialize_references:
        materialize_references(args.fallback_timeout, args.workers)
    else:
        main(args.fallback_timeout, args.workers)
