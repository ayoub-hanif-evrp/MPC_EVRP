"""Parse the complete dataset and replay all separately preserved witnesses."""

import csv
from hashlib import sha256

from evrp.instance import discover_instances, load_instance
from evrp.reference import ReferenceConfig, ReferenceSchedule, published_full_reference, validate_reference
from evrp.scenario import generate
from evrp.storage import (ROOT, benchmark_hashes, identifier, load_json, save_json,
                          verify_text_digest, writable_path)


BASE = ROOT / "results/desaulniers"
OUTPUT = BASE / "publication_development/audits"


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return {row["instance"]: row for row in csv.DictReader(stream)}


def audit():
    coverage = read_csv(BASE / "reference_validation/coverage.csv")
    partial = read_csv(BASE / "enhancement_development/partial_reference_witnesses/manifest.csv")
    extension = load_json(BASE / "publication_development/reference_extension_v1/manifest.json")
    extra = {row["instance"]: row for row in extension["records"]}
    rows = []
    for path in discover_instances():
        instance = load_instance(path)
        if instance.infrastructure.parameters.allow_station_to_station:
            raise ValueError("MP station topology restriction unexpectedly absent")
        row = dict(instance=instance.name, instance_sha256=instance.sha256,
                   parsed_and_all_arcs_validated=True, historical_reference_policy=False,
                   physical_witness=False)
        artifact = None
        if coverage[instance.name]["reference_valid"] == "True":
            row.update(source="historical_reference", historical_reference_policy=True)
            if coverage[instance.name]["published_full_route_mp_feasible"] == "True":
                reference = published_full_reference(instance, ReferenceConfig())
            else:
                artifact = ROOT / coverage[instance.name]["reference_artifact"]
                reference = ReferenceSchedule.load(artifact, instance)
        elif instance.name in partial:
            row["source"] = "separate_published_partial_route_witness"
            artifact = ROOT / partial[instance.name]["reference"]
            row["line_ending_transport"] = verify_text_digest(
                artifact, partial[instance.name]["reference_sha256"])
            reference = ReferenceSchedule.load(artifact, instance)
            if reference.identifier != partial[instance.name]["reference_identifier"]:
                raise ValueError("Published partial-route witness canonical identifier mismatch")
        elif instance.name in extra and extra[instance.name]["status"] == "feasible_reference_found":
            row["source"] = "separate_mp_first_feasible_witness"
            artifact = ROOT / extra[instance.name]["reference"]
            if sha256(artifact.read_bytes()).hexdigest() != extra[instance.name]["reference_sha256"]:
                raise ValueError("MP extension reference SHA-256 mismatch")
            reference = ReferenceSchedule.load(artifact, instance)
        else:
            reference = None
            row.update(source="unresolved_search", reason=extra.get(instance.name, {}).get("reason", "No witness"))
        if reference is not None:
            validate_reference(instance, reference)
            row.update(physical_witness=True, fleet_size=reference.fleet_size,
                       distance=reference.total_distance, reference_id=reference.identifier,
                       provenance=reference.provenance)
            eligibility = {}
            for dod in (0, .25, .5, .75):
                try:
                    scenario = generate(instance, reference, seed=1, dynamicity=dod)
                except ValueError as error:
                    if not str(error).startswith("Target DoD is ineligible"):
                        raise
                    eligibility[str(dod)] = dict(eligible=False, reason=str(error))
                    continue
                releases = dict(scenario.customer_release_times)
                if any(releases[c] > departure + 1e-8
                       for c, departure in reference.predecessor_departures.items()):
                    raise ValueError("Clairvoyant reference would dispatch before release")
                eligibility[str(dod)] = dict(eligible=True, scenario_id=scenario.identifier)
            row.update(dynamicity_preflight=eligibility, clairvoyant_release_legality_checked=True)
            if artifact is not None:
                row.update(artifact=artifact.relative_to(ROOT).as_posix(),
                           artifact_sha256=sha256(artifact.read_bytes()).hexdigest())
        rows.append(row)
    if len(rows) != 168 or set(coverage) != {row["instance"] for row in rows}:
        raise ValueError("Reference inventory does not cover the full 168-instance benchmark")
    found = sum(row["physical_witness"] for row in rows)
    save_json(OUTPUT / "reference_inventory.json", dict(instances=168, physically_witnessed=found,
              dataset_sha256=identifier(benchmark_hashes()),
              historical_reference_policy=sum(row["historical_reference_policy"] for row in rows),
              unresolved=168-found, rows=rows))
    lines = ["# Complete MP benchmark and physical reference inventory", "",
             f"Parsed and all arcs validated: 168/168. Independently replayed full-service",
             f"reference witnesses: {found}/168; unresolved searches: {168-found}.", "",
             "The historical reference policy still contains exactly 144 instances.",
             "New witnesses are separate heuristic fleet upper bounds and do not change",
             "historical K_ref, request releases, scenario IDs, protocols or results.", "",
             "DoD eligibility was preflighted without online optimization. Every eligible",
             "generated release schedule preserves legal dispatch in its clairvoyant",
             "offline reference. This reference is not an online MPC competitor.", "",
             "| Instance | Source | Physical witness | Fleet size | Distance | DoD .25 / .50 / .75 |",
             "| --- | --- | --- | ---: | ---: | --- |"]
    lines.extend(f"| {row['instance']} | {row['source']} | {row['physical_witness']} | "
                 f"{row.get('fleet_size', '')} | {row.get('distance', '')} | "
                 f"{' / '.join(str(row.get('dynamicity_preflight', {}).get(str(dod), {}).get('eligible', False)) for dod in (.25, .5, .75))} |"
                 for row in rows)
    writable_path(OUTPUT / "REFERENCE_INVENTORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Reference inventory: {found}/168 independently replayed; historical policy remains 144")
    return rows


if __name__ == "__main__":
    audit()
