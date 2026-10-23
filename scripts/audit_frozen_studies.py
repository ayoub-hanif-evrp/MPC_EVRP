"""Audit immutable original studies using their actual historical Git source."""

import argparse
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
from itertools import product
import subprocess

from evrp.audit import decode_result
from evrp.experiments import audit_result, load_config, prepare
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts import run_desaulniers_campaign as development
from scripts import run_desaulniers_final as final
from scripts import run_desaulniers_robustness_v3 as robustness
from scripts.run_desaulniers_pilot import dataset_hash


OUTPUT = ROOT / "results/desaulniers/publication_development/audits"
STUDIES = {
    "development": (development, ("5942452", "c17761e"),
                    ("scripts/run_desaulniers_campaign.py", "scripts/run_desaulniers_pilot.py")),
    "corrected_final": (final, ("380099c", "24bfed9"),
                        ("scripts/run_desaulniers_pilot.py", "scripts/run_desaulniers_campaign.py",
                         "scripts/run_desaulniers_final.py")),
    "robustness_v3": (robustness, ("73e28a8", "73d34b7"),
                      ("scripts/run_desaulniers_pilot.py", "scripts/run_desaulniers_robustness.py",
                       "scripts/run_desaulniers_robustness_v3.py")),
}
PHYSICS = ("evrp/instance.py", "evrp/model.py", "evrp/reference.py",
           "evrp/scenario.py", "evrp/observation.py")


def cluster_sign_flip(values):
    """Exact two-sided sign-flip sensitivity for at most 20 parent clusters."""
    values = tuple(values)
    if not values or len(values) > 20:
        raise ValueError("Exact parent sign-flip test requires 1-20 clusters")
    observed = abs(sum(values))
    extreme = sum(abs(sum(sign * value for sign, value in zip(signs, values))) >= observed - 1e-12
                  for signs in product((-1, 1), repeat=len(values)))
    return extreme / (2 ** len(values))


def holm_adjust(values):
    """Familywise adjustment retaining the input contrast names."""
    result, previous = {}, 0.0
    ordered = sorted(values, key=values.get)
    for index, name in enumerate(ordered):
        previous = max(previous, min(1.0, (len(ordered) - index) * values[name]))
        result[name] = previous
    return result


def git(*arguments, data=None):
    return subprocess.run(["git", *arguments], cwd=ROOT, input=data,
                          capture_output=True, check=True).stdout


def historical_hashes(revision, runners):
    names = [name for name in git("ls-tree", "-r", "--name-only", revision, "--", "evrp").decode().splitlines()
             if name.endswith(".py")]
    names.extend(runners)
    requests = "".join(f"{revision}:{name}\n" for name in names).encode()
    stream = BytesIO(git("cat-file", "--batch", data=requests))
    hashes = {}
    for name in names:
        header = stream.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError(f"Missing historical source file: {revision}:{name}")
        content = stream.read(int(header[2]))
        if stream.read(1) != b"\n":
            raise ValueError("Invalid Git object stream")
        hashes[name] = sha256(content).hexdigest()
    return hashes


def source_evidence(label):
    campaign, revisions, runners = STUDIES[label]
    frozen = load_json(campaign.OUTPUT / "protocol.json")
    for revision in revisions:
        hashes = historical_hashes(revision, runners)
        if identifier(hashes) != frozen["source_sha256"]:
            continue
        if any(sha256((ROOT / path).read_bytes()).hexdigest() != hashes[path] for path in PHYSICS):
            raise ValueError("Current physical/scenario engine differs from frozen evidence")
        return dict(source_commit=git("rev-parse", revision).decode().strip(),
                    source_sha256=frozen["source_sha256"], matching_source_files=len(hashes),
                    current_physics_matches_historical=True)
    raise ValueError(f"No matching historical source fingerprint for {label}")


def audit(label, dataset):
    campaign = STUDIES[label][0]
    evidence = source_evidence(label)
    frozen = load_json(campaign.OUTPUT / "protocol.json")
    manifest = load_json(campaign.OUTPUT / "manifest.json")
    config = load_config(campaign.CONFIG)
    if (frozen["dataset_sha256"] != dataset or
            frozen["config_sha256"] != sha256(campaign.CONFIG.read_bytes()).hexdigest() or
            manifest["protocol_identifier"] != identifier(frozen) or manifest.get("ineligible") or
            manifest["completed_runs"] != manifest["planned_runs"] or
            len(manifest["records"]) != manifest["planned_runs"]):
        raise ValueError(f"Frozen {label} configuration, completeness or dataset mismatch")
    expected = {(case["instance"], dod, seed, method) for case in frozen["selected"]
                for dod in frozen["dynamicities"] for seed in frozen["scenario_seeds"]
                for method in frozen["methods"]}
    keys = [(r["instance"], r["dynamicity"], r["seed"], r["method"]) for r in manifest["records"]]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError(f"Frozen {label} contains missing or duplicate scenario/method keys")
    cache, grouped = {}, defaultdict(dict)
    for index, row in enumerate(manifest["records"], 1):
        key = row["instance"], row["dynamicity"], row["seed"]
        if key not in cache:
            settings = (campaign.options(config, row["dynamicity"], row["seed"], row["method"])
                        if label == "robustness_v3" else campaign.options(config, *key, row["method"]))
            cache[key] = prepare(row["instance"], settings)[:3]
        instance, reference, scenario = cache[key]
        path = (ROOT / row["raw"]).resolve()
        if (not path.is_relative_to((campaign.OUTPUT / "raw").resolve()) or
                sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
            raise ValueError(f"Frozen {label} raw path or SHA-256 mismatch")
        raw = load_json(path)
        meta, metrics = raw["metadata"], raw["metrics"]
        if (meta["algorithm"] != row["method"] or meta["instance"] != row["instance"] or
                not (meta["scenario_identifier"] == row["scenario_id"] == scenario.identifier) or
                not (meta["K_ref"] == row["k_ref"] == reference.fleet_size) or
                meta["source_sha256"] != frozen["source_sha256"] or meta["dataset_sha256"] != dataset or
                meta["instance_sha256"] != instance.sha256 or
                meta["reference_schedule_identifier"] != reference.identifier or
                meta["scenario_seed"] != row["seed"] or not meta["isolated_worker"] or
                metrics["customers_served"] != row["customers_served"] or
                metrics["complete_service"] != row["complete_service"] or
                metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                raw["effective_config"]["total_planning_time_limit"] != 5.0 or
                raw["effective_config"]["mpc"]["charging_mode"] != "partial" or
                any(metrics[v] for v in ("battery_violations", "capacity_violations", "time_window_violations",
                                          "duplicate_service_violations", "hidden_information_violations"))):
            raise ValueError(f"Frozen {label} raw identity, physical or deadline mismatch")
        checks = audit_result(decode_result(raw), instance, scenario)
        if not all(checks.values()) or checks != meta["independent_audit"]:
            raise ValueError(f"Frozen {label} independent replay failed")
        grouped[key][row["method"]] = metrics
        if index % 50 == 0:
            print(f"{label}: independently replayed {index}/{len(keys)}", flush=True)
    if any(set(methods) != set(frozen["methods"]) for methods in grouped.values()):
        raise ValueError("Frozen study has unpaired method sets")
    methods = {}
    common_complete = [group for group in grouped.values()
                       if all(row["complete_service"] for row in group.values())]
    for method in frozen["methods"]:
        subset = [group[method] for group in grouped.values()]
        opportunities = sum(len(cache[key][0].customers) for key in grouped)
        methods[method] = dict(customers_served=sum(row["customers_served"] for row in subset),
                               customer_opportunities=opportunities,
                               service=sum(row["customers_served"] for row in subset) / opportunities,
                               complete_scenarios=sum(row["complete_service"] for row in subset),
                               scenarios=len(subset), max_decision_seconds=max(
                                   row["max_optimization_latency"] for row in subset),
                               conditional_efficiency=dict(
                                   common_complete_scenarios=len(common_complete),
                                   **{field: sum(group[method][field] for group in common_complete) /
                                      len(common_complete) if common_complete else None
                                      for field in ("vehicles_activated", "total_distance",
                                                    "total_energy_charged", "total_charging_visits",
                                                    "total_charging_time")}))
    from scripts.analyze_alns_recovery_screen import _interval
    contrasts = [(method, "MPC_COMPLETION") for method in frozen["methods"] if method != "MPC_COMPLETION"]
    contrasts.append(("MPC_ALNS", "MPC_HGS"))
    sensitivity = {}
    for method, baseline in contrasts:
        parents = defaultdict(lambda: [0.0, 0])
        for key, group in grouped.items():
            size = len(cache[key][0].customers)
            parent = parents[key[0].rsplit("_", 1)[0]]
            parent[0] += (group[method]["customers_served"] - group[baseline]["customers_served"]) / size
            parent[1] += 1
        values = list(parents.values())
        interval = _interval(values, [v[0] for v in values], [v[1] for v in values])
        sensitivity[f"{method}_vs_{baseline}"] = dict(
            mean_scenario_service_effect=sum(v[0] for v in values) / sum(v[1] for v in values),
            parent_clustered_ci=interval, parent_cases=len(values),
            parent_sign_flip_p=cluster_sign_flip(v[0] for v in values))
    adjusted = holm_adjust({name: value["parent_sign_flip_p"] for name, value in sensitivity.items()})
    for name, value in adjusted.items():
        sensitivity[name]["holm_adjusted_p"] = value
    return dict(**evidence, protocol_identifier=identifier(frozen), audited_runs=len(keys),
                paired_scenarios=len(grouped), base_instances=len({key[0] for key in grouped}),
                parent_instances=len({key[0].rsplit("_", 1)[0] for key in grouped}),
                methods=methods, parent_clustered_sensitivity=sensitivity,
                all_independent_audits_passed=True)


def run(source_only=False):
    if source_only:
        result = {label: source_evidence(label) for label in STUDIES}
        print(result)
        return result
    dataset = dataset_hash()
    result = {label: audit(label, dataset) for label in STUDIES}
    save_json(OUTPUT / "historical_integrity.json", dict(dataset_sha256=dataset, studies=result))
    lines = ["# Immutable original-study audit", "",
             "Frozen source fingerprints are reconstructed from historical Git blobs.",
             "Current physical and scenario engines exactly match those historical files.",
             "Every raw file was SHA-256 checked, independently replayed and matched",
             "against its fixed scenario, fleet and five-second decision budget.", "",
             "| Study | Runs | Paired scenarios | Benchmark files | Parent cases | Source commit |",
             "| --- | ---: | ---: | ---: | ---: | --- |"]
    lines.extend(f"| {label} | {row['audited_runs']} | {row['paired_scenarios']} | "
                 f"{row['base_instances']} | {row['parent_instances']} | {row['source_commit']} |"
                 for label, row in result.items())
    lines += ["", "Size variants can share customer records from an underlying parent",
              "instance. The separate sensitivity below clusters those files together.",
              "It retains the original equally weighted scenario-service contrast.",
              "Exact parent sign-flip p-values assume clusterwise sign exchangeability;",
              "Holm adjusts the five contrasts within each study. This is an exploratory",
              "sensitivity analysis, not a retroactive change to the original protocol.", "",
              "| Study | Contrast | Mean effect pp | Parent-clustered 95% CI pp | Holm p |",
              "| --- | --- | ---: | --- | ---: |"]
    for label, row in result.items():
        for contrast, values in row["parent_clustered_sensitivity"].items():
            lo, hi = values["parent_clustered_ci"]
            lines.append(f"| {label} | {contrast} | {100*values['mean_scenario_service_effect']:+.2f} | "
                         f"[{100*lo:+.2f}, {100*hi:+.2f}] | {values['holm_adjusted_p']:.4f} |")
    writable_path(OUTPUT / "HISTORICAL_INTEGRITY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    run(parser.parse_args().source_only)
