"""Archive and restore exact audited inputs without running reference optimization."""

import argparse
from hashlib import sha256
from pathlib import Path
import shutil

from evrp.instance import load_instance
from evrp.reference import ReferenceSchedule
from evrp.scenario import DynamicScenario
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json, writable_path


OUTPUT = ROOT / "results/desaulniers/publication_development/frozen_inputs_v1"
HISTORICAL = ("development_campaign", "final_holdout_audit_erratum", "robustness_v3")


def evidence_manifests():
    paths = [ROOT / "results/desaulniers" / name / "manifest.json" for name in HISTORICAL]
    for base in ("enhancement_development", "publication_development"):
        for path in sorted((ROOT / "results/desaulniers" / base).glob("*/manifest.json")):
            manifest = load_json(path)
            if manifest.get("records") and all("raw" in row for row in manifest["records"]):
                paths.append(path)
    return paths


def cache_target(record, cache_root):
    relative = Path(record["cache_path"])
    expected = Path("results") / record["kind"]
    if relative.is_absolute() or relative.parent != expected or relative.suffix != ".json":
        raise ValueError("Frozen cache target escapes its designated input directory")
    target = (Path(cache_root) / record["kind"] / relative.name).resolve()
    if not target.is_relative_to((ROOT / "results").resolve()):
        raise ValueError("Restored input cache must stay inside repository results")
    return target


def validate(manifest):
    for relative, expected in manifest["evidence_manifests"].items():
        if identifier(load_json(ROOT / relative)) != expected:
            raise ValueError("Input archive no longer matches the recorded experiment manifests")
    instances, references, scenarios = {}, {}, {}
    for record in manifest["inputs"]:
        name = record["instance"]
        if name not in instances:
            instances[name] = load_instance(BENCHMARK / f"{name}.txt")
        instance = instances[name]
        artifact = (OUTPUT / record["artifact"]).resolve()
        if (not artifact.is_relative_to(OUTPUT.resolve()) or
                sha256(artifact.read_bytes()).hexdigest() != record["sha256"] or
                instance.sha256 != record["instance_sha256"]):
            raise ValueError("Archived input path, bytes or dataset identity mismatch")
        cache_target(record, ROOT / "results")
        for alias in record.get("cache_aliases", []):
            cache_target(record | {"cache_path": alias}, ROOT / "results")
        if record["kind"] == "reference_schedules":
            obj = ReferenceSchedule.load(artifact, instance)
            references[obj.identifier] = obj
        elif record["kind"] == "scenarios":
            obj = DynamicScenario.load(artifact, instance)
            scenarios[obj.identifier] = obj
        else:
            raise ValueError("Unknown frozen input kind")
        if obj.identifier != record["identifier"]:
            raise ValueError("Archived input canonical content differs from its manifest")
    if len(references) + len(scenarios) != len(manifest["inputs"]):
        raise ValueError("Duplicated frozen reference or scenario input")
    for scenario in scenarios.values():
        reference = references[scenario.reference_schedule_identifier]
        instance = instances[scenario.base_instance]
        if (scenario.fleet_size != reference.fleet_size or
                dict(scenario.release_upper_bounds) != {
                    c.id: min(c.ready, reference.predecessor_departures[c.id]) for c in instance.customers}):
            raise ValueError("Archived scenario changes the fixed fleet or reference-preserving releases")
    if set(scenarios) != set(manifest["scenario_ids"]):
        raise ValueError("Archived scenario coverage differs from the complete audited design")
    return len(references), len(scenarios)


def cache_aliases(record):
    aliases = []
    for path in sorted((ROOT / "results" / record["kind"]).glob(f"{record['instance']}_*.json")):
        data = load_json(path)
        content_id = data.get("identifier") if record["kind"] == "reference_schedules" else identifier(data)
        relative = path.relative_to(ROOT).as_posix()
        if content_id == record["identifier"] and relative != record["cache_path"]:
            aliases.append(relative)
    return aliases


def add_cache_aliases():
    path = OUTPUT / "manifest.json"
    manifest = load_json(path)
    validate(manifest)
    previous = OUTPUT / "manifest_pre_alias_fix.json"
    if not previous.exists():
        shutil.copyfile(path, writable_path(previous))
    for record in manifest["inputs"]:
        record["cache_aliases"] = sorted(set(record.get("cache_aliases", [])) | set(cache_aliases(record)))
    validate(manifest)
    save_json(path, manifest)
    print(f"Recorded {sum(len(row['cache_aliases']) for row in manifest['inputs'])} additional cache aliases; "
          "all scientific content and original archive bytes unchanged")


def create():
    target = OUTPUT / "manifest.json"
    if target.exists():
        counts = validate(load_json(target))
        print(f"Existing exact input archive verified: {counts[0]} references, {counts[1]} scenarios")
        return
    evidence, wanted = {}, {}
    for path in evidence_manifests():
        manifest = load_json(path)
        if (manifest.get("status") not in {"complete", "development_complete", "final_complete"} or
                manifest["completed_runs"] != manifest["planned_runs"] or
                len(manifest["records"]) != manifest["planned_runs"]):
            raise ValueError("Only completed experiment evidence may supply frozen inputs")
        evidence[path.relative_to(ROOT).as_posix()] = identifier(manifest)
        for row in manifest["records"]:
            entry = dict(instance=row["instance"], k_ref=row["k_ref"])
            previous = wanted.setdefault(row["scenario_id"], entry)
            if previous != entry:
                raise ValueError("One scenario ID has inconsistent instance/fleet metadata")
    scenarios, reference_ids = {}, set()
    for name in sorted({row["instance"] for row in wanted.values()}):
        instance = load_instance(BENCHMARK / f"{name}.txt")
        for path in sorted((ROOT / "results/scenarios").glob(f"{name}_*.json")):
            if identifier(load_json(path)) not in wanted:
                continue
            scenario = DynamicScenario.load(path, instance)
            if scenario.fleet_size != wanted[scenario.identifier]["k_ref"]:
                raise ValueError("Cached scenario fleet differs from audited records")
            scenarios[scenario.identifier] = path
            reference_ids.add(scenario.reference_schedule_identifier)
    if set(scenarios) != set(wanted):
        raise ValueError("Required scenario cache is missing; never silently regenerate scientific inputs")
    references = {}
    for name in sorted({row["instance"] for row in wanted.values()}):
        for path in sorted((ROOT / "results/reference_schedules").glob(f"{name}_*.json")):
            reference_id = load_json(path).get("identifier")
            if reference_id in reference_ids:
                references[reference_id] = path
    if set(references) != reference_ids:
        raise ValueError("Required exact reference cache is missing; no optimization is launched")
    records = []
    for kind, indexed in (("reference_schedules", references), ("scenarios", scenarios)):
        for content_id, path in sorted(indexed.items()):
            data = load_json(path)
            artifact = OUTPUT / kind / f"{content_id}.json"
            digest = sha256(path.read_bytes()).hexdigest()
            if artifact.exists() and sha256(artifact.read_bytes()).hexdigest() != digest:
                raise ValueError("Unmanifested input archive differs; preserve it for investigation")
            if not artifact.exists():
                shutil.copyfile(path, writable_path(artifact))
            records.append(dict(kind=kind, artifact=artifact.relative_to(OUTPUT).as_posix(),
                                identifier=content_id, sha256=digest,
                                cache_path=path.relative_to(ROOT).as_posix(),
                                instance=data["base_instance"], instance_sha256=data["instance_sha256"]))
            records[-1]["cache_aliases"] = cache_aliases(records[-1])
    manifest = dict(inputs=records, scenario_ids=sorted(wanted), evidence_manifests=evidence,
                    operation="byte-for-byte archive; no reference search or online optimization")
    references_count, scenario_count = validate(manifest)
    save_json(target, manifest)
    writable_path(OUTPUT / "RESULTS.md").write_text(
        "# Exact frozen reference and scenario inputs\n\n"
        f"Archived {references_count} reference schedules and {scenario_count} dynamic scenarios\n"
        "used by the completed original and enhancement studies. Files were copied\n"
        "byte-for-byte from the executed caches and independently loaded and replayed.\n"
        "The manifest binds dataset hashes, canonical IDs, byte hashes, original\n"
        "cache paths and experiment-manifest content IDs. No optimization was run.\n\n"
        "On a fresh checkout run `python -m scripts.archive_frozen_inputs --restore`\n"
        "before auditing historical experiments. Restoration never overwrites a\n"
        "conflicting cache or silently regenerates references. An alternate empty\n"
        "cache can be tested using `--cache-root results/.input_restore_smoke`.\n",
        encoding="utf-8")
    print(f"Archived exact scientific inputs: {references_count} references, {scenario_count} scenarios")


def restore(cache_root):
    manifest = load_json(OUTPUT / "manifest.json")
    references, scenarios = validate(manifest)
    pending, reused = [], 0
    for record in manifest["inputs"]:
        for relative in [record["cache_path"], *record.get("cache_aliases", [])]:
            target = cache_target(record | {"cache_path": relative}, cache_root)
            if target.exists():
                instance = load_instance(BENCHMARK / f"{record['instance']}.txt")
                loader = ReferenceSchedule if record["kind"] == "reference_schedules" else DynamicScenario
                if loader.load(target, instance).identifier != record["identifier"]:
                    raise ValueError("Conflicting existing cache preserved; restoration stopped")
                reused += 1
            else:
                pending.append((OUTPUT / record["artifact"], target))
    for artifact, target in pending:
        shutil.copyfile(artifact, writable_path(target))
    print(f"Verified {references} references and {scenarios} scenarios; "
          f"restored {len(pending)}, reused {reused}; no optimization executed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--add-cache-aliases", action="store_true")
    parser.add_argument("--cache-root", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    if args.restore:
        restore(args.cache_root)
    elif args.add_cache_aliases:
        add_cache_aliases()
    else:
        create()
