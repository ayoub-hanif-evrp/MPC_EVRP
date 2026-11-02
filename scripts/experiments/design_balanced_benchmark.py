"""Read-only exposure audit and preflight; deliberately contains no study runner."""

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import gzip
from hashlib import sha256
import json
from math import ceil, isfinite
import os
from pathlib import Path
import re
import subprocess
from time import perf_counter

from evrp.experiments import load_config, simulation_config
from evrp.instance import load_instance
from evrp.reference import ReferenceConfig, ReferenceSchedule, published_full_reference
from evrp.scenario import generate
from evrp.storage import ROOT, identifier, verify_text_digest
from scripts.experiments.paths import artifact_path
from scripts.performance_budget import admit


STUDY = "balanced_evaluation_v1"
FAMILIES = ("C1", "C2", "R1", "R2", "RC1", "RC2")
SIZES = (25, 50, 100)
METHODS = ("MPC_ALNS", "MPC_HGS")
DOD, SCENARIO_SEED = .75, 7301
NAME = re.compile(r"((?:rc|c|r)([12])[0-9]+)_21_(25|50|100)\Z")
MENTION = re.compile(r"(?<![a-z0-9])((?:rc|c|r)[12][0-9]+)_21(?:_(25|50|100))?(?![0-9])")
POLICIES = ("dispatch_policy", "optimizer_initialization_policy", "coordination_policy",
            "constructor_policy", "first_action_policy", "proposal_cache_policy",
            "computation_policy", "mcts_rollout_policy", "quality_policy", "service_recovery_policy")
REFERENCE_MARKERS = ("/reference_validation/", "/reference_schedules/", "/references/",
                     "/reference_extension_v1/", "/partial_reference_witnesses/",
                     "/offline_resources/", "/scenarios/", "/inputs/", "/frozen_inputs_v1/")
OUTCOME_ROLES = {"outcome", "reviewed_outcome", "historical_outcome", "legacy_related", "diagnostic"}
TIMING_STUDIES = ("robustness_v3", "final_cpu_paper_v1")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read_json(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path):
    data = path.read_bytes()
    return data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")


def identity(name):
    match = NAME.fullmatch(name)
    if not match:
        raise ValueError(f"Unrecognized benchmark variant: {name}")
    parent, _, size = match.groups()
    return parent, family(parent), int(size)


def family(parent):
    match = re.fullmatch(r"(rc|c|r)([12])[0-9]+", parent)
    if not match:
        raise ValueError(f"Unrecognized parent: {parent}")
    return match[1].upper() + match[2]


def groups(variants):
    grouped = {}
    for row in variants:
        parent, _, size = identity(row["name"])
        entry = grouped.setdefault(parent, dict(parent=parent, family=family(parent), variants={}))
        if str(size) in entry["variants"]:
            raise ValueError(f"Duplicate parent-size variant: {parent}/{size}")
        entry["variants"][str(size)] = row
    return grouped


def benchmark_inventory(root):
    directory = root / "data/opre.2016.1535-sm-data/instances/instances_format_1"
    variants, auxiliary = [], []
    for path in sorted(directory.glob("*.txt")):
        if path.name == "Readme.txt":
            auxiliary.append(path.relative_to(root).as_posix())
            continue
        _, _, size = identity(path.stem)
        instance = load_instance(path)
        if instance.name != path.stem or len(instance.customers) != size:
            raise ValueError(f"Parsed benchmark size/name mismatch: {path}")
        arc = directory.parent / "instances_format_2" / (path.stem.removesuffix("_100") + ".inst")
        variants.append(dict(name=path.stem, size=size, path=path.relative_to(root).as_posix(),
                             sha256=instance.sha256, arcs_path=arc.relative_to(root).as_posix(),
                             arcs_sha256=digest(arc)))
    if not variants:
        raise ValueError("No benchmark instances found")
    return groups(variants), auxiliary


def mentions(value, parents):
    return sorted({m[1] for m in MENTION.finditer(value) if m[1] in parents})


def category(path):
    if "/robustness_v3/" in path:
        return "primary"
    if "/final_cpu_paper_v1/" in path:
        return "independent_replication"
    if "/targeted_service_v1/" in path:
        return "targeted_alns"
    if "/reliability_v2/" in path:
        return "reliability"
    if "/slad_feasibility_" in path:
        return "slad_diagnostic"
    if any(x in path for x in ("/development", "/publication_development/", "/enhancement_development/")):
        return "development_selection"
    return "other_historical"


def historical_paths(root):
    output = subprocess.check_output(
        ["git", "log", "--all", "--pretty=format:", "--name-only", "--", "results"],
        cwd=root, text=True)
    return sorted({p for p in output.splitlines() if "/raw/" in p})


def evidence_paths(root):
    """Inspect tracked and local evidence, excluding identified test/vendor scratch."""
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0"))
    found, skipped = set(), set()
    for prefix in ("results", "docs", "configs", "archive"):
        for base, dirs, files in os.walk(root / prefix):
            for name in list(dirs):
                if (name in {".git", "__pycache__", "external", "upstream"} or
                        name.startswith((".pytest", "pytest-", "test_", ".p"))):
                    skipped.add((Path(base) / name).relative_to(root).as_posix())
                    dirs.remove(name)
            for name in files:
                path = Path(base) / name
                rel = path.relative_to(root).as_posix()
                if (rel.startswith(f"results/research_v2/{STUDY}/") or
                        rel == "docs/BALANCED_BENCHMARK_PROTOCOL.md"):
                    continue
                if path.suffix in {".json", ".csv", ".md", ".yaml", ".yml", ".log"} or name.endswith(".json.gz"):
                    if path.is_symlink():
                        raise ValueError(f"Linked evidence is not permitted: {rel}")
                    found.add(rel)
    return sorted(found), tracked, sorted(skipped)


def scan_exposure(root, parents):
    paths, tracked, skipped = evidence_paths(root)
    evidence = defaultdict(lambda: defaultdict(list))
    sources, timings, errors = [], [], []
    expected = {}
    for study in TIMING_STUDIES:
        path = root / "results/desaulniers" / study / "manifest.json"
        if path.is_file():
            for row in read_json(path)["records"]:
                expected[row["raw"]] = row.get("raw_sha256", row.get("sha256"))

    def add(names, role, rel):
        for parent in names:
            evidence[parent][role + ":" + category(rel)].append(rel)

    for rel in paths:
        path = root / rel
        try:
            raw = path.name.endswith(".json.gz") or "/raw/" in rel
            if path.name.endswith((".json", ".json.gz")):
                data = read_json(path)
                payload = data.get("result", data) if isinstance(data, dict) else data
                text = json.dumps(payload.get("metadata", {}) if raw and
                                  isinstance(payload, dict) and "metrics" in payload else data)
            else:
                data = None
                text = read_text(path)
            names = mentions(text, parents)
            reference_only = any(x in rel for x in REFERENCE_MARKERS) or any(
                x in path.name.lower() for x in ("reference_inventory", "reference_coverage", "preflight_candidates"))
            if reference_only:
                role = "reference_only"
            elif raw and isinstance(data, dict) and "metrics" in data.get("result", data):
                result = data.get("result", data)
                meta = result.get("metadata", {})
                names = mentions(json.dumps(meta), parents)
                role = "reference_only" if meta.get("algorithm") == "STATIC_REFERENCE" else "outcome"
                if names and not any(NAME.fullmatch(n) for n in (meta.get("base_instance", ""), meta.get("instance", ""))):
                    role = "legacy_related" if role == "outcome" else role
                if (rel in expected and meta.get("isolated_worker") is True and
                        meta.get("algorithm") in METHODS):
                    actual_hash = digest(path)
                    if actual_hash != expected[rel]:
                        raise ValueError("Historical timing raw hash does not match manifest")
                    metrics = result["metrics"]
                    name = meta.get("base_instance", meta.get("instance", ""))
                    _, _, size = identity(name)
                    wall = data.get("worker_wall_seconds", metrics.get("worker_wall_seconds"))
                    cpu = data.get("worker_cpu_seconds", metrics.get("worker_cpu_seconds"))
                    timings.append(dict(path=rel, sha256=actual_hash, size=size,
                                        method=meta["algorithm"], wall_seconds=wall,
                                        cpu_seconds=cpu, bytes=path.stat().st_size))
            elif isinstance(data, dict) and path.name == "manifest.json":
                role = "outcome"
                # Planned protocol cases never become outcome exposure merely by being listed.
                names = mentions(json.dumps(data.get("records", [])), parents)
            elif isinstance(data, dict) and "/diagnosis/roots/" in rel:
                role = "diagnostic"
            elif "/slad_feasibility_" in rel:
                role = "diagnostic"
            elif (path.name in {"protocol.json", "manifest_pre_alias_fix.json", "PREREGISTRATION.md"} or
                  "/preflight/" in rel or path.suffix in {".yaml", ".yml"}):
                role = "planned_only"
            elif "inventory" in path.name or "archive_manifests" in rel:
                role = "inventory_mention"
            else:
                role = "uncertain_mention"
            if isinstance(data, dict) and data.get("historical_exposed_parents"):
                declared = {p.removesuffix("_21") for p in data["historical_exposed_parents"]}
                add(sorted(declared & set(parents)), "historical_outcome", rel)
            if names:
                if role == "reviewed_outcome":
                    direct = {m[1] for m in MENTION.finditer(text) if m[2] is not None}
                    add([p for p in names if p in direct], role, rel)
                    add([p for p in names if p not in direct], "legacy_related", rel)
                else:
                    add(names, role, rel)
            # Reference-only inventories are retained as provenance, without becoming outcome exposure.
            if names or rel in expected:
                sources.append(dict(path=rel, sha256=digest(path), tracked=rel in tracked, role=role))
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append(dict(path=rel, error=str(error)))
    history = historical_paths(root)
    for rel in history:
        role = "historical_outcome" if any(m[2] for m in MENTION.finditer(rel)) else "legacy_related"
        add(mentions(rel, parents), role, "git-history/" + rel)
    rows = {}
    for parent in sorted(parents):
        buckets = evidence[parent]
        roles = {key.split(":", 1)[0] for key in buckets}
        status = ("exposed" if roles & (OUTCOME_ROLES - {"legacy_related"}) else
                  "related_legacy_exposure" if "legacy_related" in roles else
                  "uncertain" if "uncertain_mention" in roles else "no_outcome_evidence_found")
        rows[parent] = dict(status=status, evidence=[dict(role=key.split(":", 1)[0],
            category=key.split(":", 1)[1], count=len(set(values)), examples=sorted(set(values))[:4])
            for key, values in sorted(buckets.items())])
    return dict(parents=rows, sources=sources, errors=errors,
                searched_files=len(paths), excluded_scratch_or_vendor_directories=skipped,
                historical_raw_paths_sha256=identifier(history)), timings


def validate_inputs(root, grouped, seconds=120):
    """No solve_reference/prepare calls: replay existing witnesses or published routes."""
    inventory_path = root / "results/desaulniers/targeted_service_v1/reference_inventory.json"
    inventory = read_json(inventory_path)
    rows = {row["instance"]: row for row in inventory["rows"]}
    valid, started = {}, perf_counter()
    for parent in grouped.values():
        for row in parent["variants"].values():
            if perf_counter() - started > seconds:
                raise ValueError("Reference preflight time cap exceeded; no new reference search allowed")
            try:
                instance = load_instance(root / row["path"])
                info = rows.get(instance.name)
                if not info or not info["physical_witness"] or info["instance_sha256"] != instance.sha256:
                    raise ValueError("Missing valid reference inventory entry")
                if info.get("artifact"):
                    path = (root / info["artifact"]).resolve()
                    if not path.is_relative_to((root / "results").resolve()):
                        raise ValueError("Reference artifact leaves results workspace")
                    verify_text_digest(path, info["artifact_sha256"])
                    ref = ReferenceSchedule.load(path, instance)
                    source = dict(path=path.relative_to(root).as_posix(), sha256=digest(path),
                                  registered_sha256=info["artifact_sha256"])
                else:
                    ref = published_full_reference(instance, ReferenceConfig())
                    if ref is None:
                        raise ValueError("No saved/published full-service reference; construction forbidden")
                    variant = ref.provenance.split("_")[1]
                    path = root / "data/opre.2016.1535-sm-data/solutions" / variant / ("solution" + instance.name)
                    source = dict(path=path.relative_to(root).as_posix(), sha256=digest(path))
                if ref.identifier != info["reference_id"]:
                    raise ValueError("Reference canonical identifier mismatch")
                bounds = [min(c.ready, ref.predecessor_departures[c.id]) for c in instance.customers]
                eligible = int(DOD * len(bounds) + .5) <= sum(t > 0 for t in bounds)
                row.update(reference=dict(**source, identifier=ref.identifier, k_ref=ref.fleet_size),
                           reference_valid=True, dod_eligible=eligible,
                           reference_inventory_sha256=digest(inventory_path))
                if not eligible:
                    row["exclusion"] = "DoD 0.75 exact-count release eligibility fails"
                valid[instance.name] = instance, ref
            except (OSError, ValueError, RuntimeError) as error:
                row.update(reference_valid=False, dod_eligible=False, exclusion=str(error))
    return valid


def select(grouped, exposure, per_family=3):
    candidates = {fam: [] for fam in FAMILIES}
    for parent, row in sorted(grouped.items()):
        complete = set(row["variants"]) == {str(size) for size in SIZES}
        usable = complete and all(v.get("reference_valid") and v.get("dod_eligible")
                                  for v in row["variants"].values())
        row["complete_size_panel"] = complete
        row["all_references_and_dynamicity_valid"] = usable
        row["outcome_exposure"] = exposure["parents"][parent]["status"]
        if usable and row["outcome_exposure"] == "no_outcome_evidence_found":
            candidates[row["family"]].append(parent)
    # Never produce a partial confirmatory selection.
    selected = ([p for fam in FAMILIES for p in candidates[fam][:per_family]]
                if not exposure["errors"] and all(len(v) >= per_family for v in candidates.values()) else [])
    return selected, candidates


def paired_configs(controller):
    configs = {}
    for method in METHODS:
        values = dict(controller, algorithm=method, dynamicity=DOD, scenario_seed=SCENARIO_SEED,
                      diagnostics=False, trace_level="summary", total_planning_time_limit=5.0,
                      engineering_watchdog_seconds=900.0, **dict.fromkeys(POLICIES, "original"))
        configs[method] = asdict(simulation_config(values))
    first, second = (configs[name] for name in METHODS)
    if {k for k in first if first[k] != second[k]} != {"algorithm"}:
        raise ValueError("Paired configurations differ beyond optimizer identity")
    for config in configs.values():
        if (config["total_planning_time_limit"] != 5 or config["mpc"]["charging_mode"] != "partial" or
                config["mpc"]["control_horizon"] != 1 or config["parallel_agents"] or
                any(config[k] != "original" for k in POLICIES)):
            raise ValueError("Original event-triggered paper settings changed")
    return configs


def planned_jobs(selected, grouped, validated, configs):
    cases, jobs = [], []
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate independent parent")
    for parent in selected:
        for size in SIZES:
            info = grouped[parent]["variants"][str(size)]
            instance, reference = validated[info["name"]]
            scenario = generate(instance, reference, SCENARIO_SEED, DOD, "exact_count")
            if (scenario.fleet_size != reference.fleet_size or
                    any(dict(scenario.customer_release_times)[c] > t + 1e-8
                        for c, t in reference.predecessor_departures.items())):
                raise ValueError("Scenario changes fleet or violates clairvoyant release legality")
            case_id = len(cases)
            case = dict(parent=parent, family=family(parent), size=size, instance=info,
                        scenario=asdict(scenario), scenario_identifier=scenario.identifier,
                        scenario_sha256=identifier(asdict(scenario)), k_ref=reference.fleet_size)
            cases.append(case)
            order = METHODS if case_id % 2 == 0 else tuple(reversed(METHODS))
            for method in order:
                jobs.append(dict(id=f"{case_id:03d}_{method}", paired_block=case_id,
                                 parent=parent, size=size, method=method,
                                 scenario_identifier=scenario.identifier,
                                 k_ref=reference.fleet_size, config_sha256=identifier(configs[method])))
    return cases, jobs


def cost_estimate(samples, wall_hours=12, cpu_hours=12, storage_gib=1, parents=18):
    if not all(isfinite(v) and v > 0 for v in (wall_hours, cpu_hours, storage_gib)):
        raise ValueError("Budgets must be finite and positive")
    strata, missing = [], []
    wall_by_method, cpu_by_method = Counter(), Counter()
    storage = 0
    for size in SIZES:
        for method in METHODS:
            rows = [r for r in samples if r["size"] == size and r["method"] == method]
            walls = [r["wall_seconds"] for r in rows if r.get("wall_seconds") is not None]
            cpus = [r["cpu_seconds"] for r in rows if r.get("cpu_seconds") is not None]
            if not walls or not cpus or any(not isfinite(v) or v <= 0 for v in walls + cpus):
                missing.append([size, method])
                continue
            wall_cap = ceil(max(60, 2 * max(walls) + 60, 2 * max(cpus) + 60))
            cpu_cap = wall_cap  # Future supervisor charges max(elapsed, child CPU).
            storage_cap = max(65536, 2 * max(r["bytes"] for r in rows)) + 65536
            strata.append(dict(size=size, method=method, wall_observations=len(walls),
                               cpu_observations=len(cpus), historical_max_wall=max(walls),
                               historical_max_cpu=max(cpus), worker_cap_seconds=wall_cap,
                               worker_cpu_cap_seconds=cpu_cap, bytes_per_job=storage_cap))
            wall_by_method[method] += parents * wall_cap
            cpu_by_method[method] += parents * cpu_cap
            storage += parents * storage_cap
    setup, validation, per_job_overhead = 600, 900, 2
    wall = sum(wall_by_method.values()) + setup + validation + parents * 6 * per_job_overhead
    cpu = sum(cpu_by_method.values()) + setup + validation + parents * 6 * per_job_overhead
    storage += 16 * 1024**2
    accepted = not missing and admit(wall_hours * 3600, wall - validation, validation) and cpu <= cpu_hours * 3600 and storage <= storage_gib * 1024**3
    return dict(admitted=accepted, strata=strata, missing_timing_strata=missing,
                wall_hours_limit=wall_hours, worker_cpu_hours_limit=cpu_hours,
                storage_gib_limit=storage_gib, predicted_worker_wall_seconds=dict(wall_by_method),
                predicted_worker_cpu_seconds=dict(cpu_by_method),
                sequential_wall_cap_seconds=wall, worker_cpu_budget_seconds=cpu,
                setup_reserve_seconds=setup, validation_reserve_seconds=validation,
                per_job_supervisor_reserve_seconds=per_job_overhead, storage_estimate_bytes=storage,
                rule="2 x maximum observed isolated size/method wall or measured child CPU + 60 s; floor 60; no clipping",
                completion_caveat="Empirical cost prediction; hard caps bound spending, not successful completion. No automatic retries.")


def source_files(root):
    paths = list((root / "evrp").rglob("*.py")) + [
        root / "configs/paper_controller.yaml", Path(__file__),
        root / "scripts/experiments/paths.py", root / "scripts/performance_budget.py"]
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(paths)}


def preview(root=ROOT, wall_hours=12, cpu_hours=12, storage_gib=1):
    root = Path(root).resolve()
    grouped, auxiliary = benchmark_inventory(root)
    exposure, timings = scan_exposure(root, grouped)
    validated = validate_inputs(root, grouped)
    selected, candidates = select(grouped, exposure)
    configs = paired_configs(load_config(root / "configs/paper_controller.yaml"))
    cases, jobs = planned_jobs(selected, grouped, validated, configs)
    budget = cost_estimate(timings, wall_hours, cpu_hours, storage_gib)
    status = "BLOCKED" if not selected else "READY" if budget["admitted"] else "OVER BUDGET"
    return dict(schema=1, study=STUDY, status=status, scenario_seed=SCENARIO_SEED,
                target_dod=DOD, methods=list(METHODS), intended_parents=18,
                intended_benchmark_files=54, intended_optimizer_jobs=108,
                selected_parents=selected, independent_parents=len(selected),
                benchmark_files=len(cases), optimizer_jobs=len(jobs),
                candidates_by_family=candidates, dataset_parents=grouped,
                auxiliary_files=auxiliary, exposure=exposure,
                budget=budget, timing_samples=timings, configs=configs, cases=cases, jobs=jobs,
                source_files=source_files(root), source_commit=subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                statistics=dict(primary="Mean across parents of the equal-weight mean of their three size-specific (ALNS served/n - HGS served/n) differences",
                    bootstrap="20000 percentile bootstrap draws; resample three parent groups with replacement within each of six fixed families; carry all three sizes together",
                    bootstrap_seed=7302, confidence=.95,
                    complete_service="Same parent/size aggregation using the indicator served == n",
                    superiority="Primary mean > 0 and 95% lower bound > 0; complete-service 95% lower bound >= 0; every paired run passes physics/information/five-second audits; no missing pair",
                    secondary=["Customer-weighted service", "Fully served scenarios", "Complete-service paired difference and CI", "Family and size descriptions", "100-customer subset", "Service wins/ties/losses", "p50/p95/p99/max decision latency", "Physical and hidden-information audit results", "Distance/operations only on identical served customer sets"],
                    limits="Subgroups exploratory; small within-family samples limit interval precision; no epoch-level pseudo-replication; non-significance is not equivalence"),
                selection_rule="Three lexicographically first no-outcome-evidence parents per family, all sizes and DoD eligible; abort whole selection if any family lacks three.",
                limitations=["No-outcome-evidence is conditional on the local tree, available archive inventories, and local Git refs; it is not proof against unavailable external experiments.",
                             "Prior plan-only/reference-only exposure is disclosed but is not an optimizer outcome.",
                             "One DoD and seed; family subgroup estimates are exploratory; three parents per family limit bootstrap precision.",
                             "Blocked designs have no selected cohort/jobs; budget is the hypothetical 18-parent design, not execution authorization."])


def write_artifact(report, filename, root=ROOT):
    path = artifact_path(STUDY, "validation", filename, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return path


def freeze(report, root=ROOT):
    if report["status"] != "READY" or not report["budget"]["admitted"]:
        raise ValueError(f"Cannot freeze {report['status']} design")
    if (report["independent_parents"], report["benchmark_files"], report["optimizer_jobs"]) != (18, 54, 108):
        raise ValueError("Incomplete confirmatory cohort")
    selected = report["selected_parents"]
    if (len(selected) != len(set(selected)) or len(selected) != 18 or
            Counter(family(p) for p in selected) != Counter(dict.fromkeys(FAMILIES, 3)) or
            tuple(report["methods"]) != METHODS or len(report["cases"]) != 54 or
            len(report["jobs"]) != 108 or len({job["id"] for job in report["jobs"]}) != 108):
        raise ValueError("Frozen parent groups or paired-job counts are invalid")
    return write_artifact(dict(protocol=report, protocol_identifier=identifier(report)), "protocol.json", root)


def verify(path, root=ROOT):
    saved = read_json(Path(path))
    report = saved["protocol"]
    if saved["protocol_identifier"] != identifier(report) or report["status"] != "READY":
        raise ValueError("Invalid frozen protocol content/decision")
    current = preview(root, report["budget"]["wall_hours_limit"],
                      report["budget"]["worker_cpu_hours_limit"], report["budget"]["storage_gib_limit"])
    # A later commit alone is harmless; actual source and evidence bytes must still match.
    current["source_commit"] = report["source_commit"]
    if "exposure" in report:
        for key in ("searched_files", "excluded_scratch_or_vendor_directories"):
            current["exposure"][key] = report["exposure"][key]
        tracked = {row["path"]: row["tracked"] for row in report["exposure"]["sources"]}
        for row in current["exposure"]["sources"]:
            # Tracking an identical local artifact does not change prior exposure.
            if row["path"] in tracked:
                row["tracked"] = tracked[row["path"]]
    if identifier(current) != identifier(report):
        raise ValueError("Frozen source, exposure, benchmark, reference, scenario, settings, or budget drift")
    return saved["protocol_identifier"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wall-hours", type=float, default=12)
    parser.add_argument("--cpu-hours", type=float, default=12)
    parser.add_argument("--storage-gib", type=float, default=1)
    parser.add_argument("--summary", action="store_true", help="Print concise read-only preview")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--verify", type=Path)
    action.add_argument("--write-inventory", nargs="?", const="exposure_inventory.json",
                        metavar="NAME", help="Explicitly save a new audit snapshot, never overwrite")
    args = parser.parse_args(argv)
    if args.write_inventory and not re.fullmatch(r"exposure_inventory(?:_[a-z0-9]+)*\.json", args.write_inventory):
        raise ValueError("Inventory name must be exposure_inventory[_version].json; protocols require --freeze")
    if args.verify:
        print(verify(args.verify))
        return 0
    report = preview(wall_hours=args.wall_hours, cpu_hours=args.cpu_hours, storage_gib=args.storage_gib)
    if args.freeze:
        print(freeze(report))
    elif args.write_inventory:
        print(write_artifact(report, args.write_inventory))
    else:
        display = ({key: report[key] for key in ("status", "selected_parents", "independent_parents",
                    "benchmark_files", "optimizer_jobs", "candidates_by_family", "budget")}
                   if args.summary else report)
        print(json.dumps(display, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
