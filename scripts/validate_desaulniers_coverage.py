"""Inspect every active Desaulniers instance without changing benchmark inputs.

Fallback construction runs in isolated, time-limited processes. A timeout is
evidence of an unresolved search, never a claim of physical infeasibility.
"""

import argparse
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
          "published_variants", "published_mp_feasible",
          "fallback_status", "reference_vehicles", "reference_distance",
          "reference_seconds", "reference_valid", "information_model_valid", "reason")


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
    print(json.dumps({"vehicles": schedule.fleet_size, "distance": schedule.total_distance,
                      "identifier": schedule.identifier}), flush=True)


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


def render(rows):
    fingerprint = dataset_hash()
    final = load_json(ROOT / "results/desaulniers/final_holdout_audit_erratum/protocol.json")
    if fingerprint != final["dataset_sha256"]:
        raise ValueError("Benchmark bundle differs from the corrected final protocol")
    for row in rows:
        row["coordinates_valid"] = row["parsed"] is True
        for field in ("travel_time_consistent", "rounded_cost_consistent", "energy_consistent"):
            row[field] = row["arcs_consistent"] is True
        row["available_solutions"] = ",".join(
            variant for variant in ("SF", "MF", "SP", "MP") if
            (PUBLISHED_SOLUTIONS / variant / f"solution{row['instance']}").is_file())
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
             f"Dataset fingerprint: `{fingerprint}` (matches corrected final protocol).", "",
             f"Inspected: {counts['inspected']}/168; parsed/arcs consistent: {counts['parsed']}; "
             f"published MP references: {counts['published']}; constructed/cached: {counts['fallback']}; "
             f"unresolved: {counts['unresolved']}.", "",
             "A search failure or timeout is not proof of infeasibility. Full per-instance "
             "evidence and reasons are in `coverage.csv`.", "",
             "`available_solutions` lists SF/MF/SP/MP files; only physically replayed "
             "SF/MF routes are used to define offline reference fleets. "
             "`arcs_consistent` validates every cost, travel-time, and energy arc "
             "against the coordinate source. The information-model check records "
             "complete reference predecessor-departure bounds; online no-future-leakage "
             "is separately tested and audited in experiment traces.", "",
             "| Size | Instances | Published MP-feasible | Fallback validated | Unresolved |",
             "| ---: | ---: | ---: | ---: | ---: |"]
    for size in (25, 50, 100):
        group = [r for r in rows if r["customers"] == size]
        lines.append(f"| {size} | {len(group)} | "
                     f"{sum(r['published_mp_feasible'] is True for r in group)} | "
                     f"{sum(r['fallback_status'] in {'validated_cache', 'constructed'} for r in group)} | "
                     f"{sum(r['reference_valid'] is not True for r in group)} |")
    lines.append("")
    for r in rows:
        if r["reference_valid"] is not True:
            lines.append(f"- {r['instance']}: {r['fallback_status'] or 'parse/replay failure'}; {r['reason']}")
    writable_path(OUTPUT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main(timeout):
    checkpoint = OUTPUT / "checkpoint.json"
    existing = load_json(checkpoint) if checkpoint.exists() else {}
    rows = {}
    for path in discover_instances():
        fingerprint = sha256(path.read_bytes()).hexdigest()
        saved = existing.get(path.stem)
        if saved and saved["format1_sha256"] == fingerprint:
            rows[path.stem] = saved
            continue
        row = inspect(path, timeout)
        rows[path.stem] = dict(row, format1_sha256=fingerprint)
        save_json(checkpoint, rows)
        print(f"coverage {len(rows)}/168 {path.stem}: {row['reference_valid']}", flush=True)
    counts = render([rows[p.stem] for p in discover_instances()])
    print(counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker")
    parser.add_argument("--fallback-timeout", type=int, default=120)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    else:
        main(args.fallback_timeout)
