"""Independently replay and render the original five-method CPU paper package."""

from collections import Counter, defaultdict
import csv
from hashlib import sha256
import json
from math import isfinite, sqrt
from pathlib import Path
import re
from shutil import copyfile
from statistics import mean
import subprocess
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from evrp.audit import decode_result
from evrp.experiments import audit_result, load_config, prepare
from evrp.instance import energy, travel_time
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.run_desaulniers_robustness_v3 import CONFIG as ROBUST_CONFIG, options as robust_options
from scripts.run_final_cpu_replication import OUTPUT, archived_case, verify_raw, METHODS

PRIMARY = ROOT / "results/desaulniers/robustness_v3"
ARCHIVE_TAG = "archive/hybrid-gpu-negative-v1"
LABELS = {method: method.removeprefix("MPC_") for method in METHODS}
COLORS = {"MPC_COMPLETION": "#666d76", "MPC_MCTS": "#216e83", "MPC_ALNS": "#218462",
          "MPC_HGS": "#c07932", "MPC_ACS": "#995c82"}
PLT = OUTPUT / "figures"
TABLES = OUTPUT / "tables"
OPERATIONAL_FIELDS = (
    "distance", "travel_time", "last_service_completion_time", "completion_time",
    "charging_time", "charged_energy", "travel_energy", "waiting_time", "vehicles",
    "workload_std", "tw_margin_min", "battery_min")
OPERATIONAL_HEADERS = (
    "Distance", "Travel time", "Last service completion time",
    "Fleet end time (horizon-censored)", "Charging time", "Energy charged",
    "Energy consumed", "Waiting time", "Active EVs", "Load SD", "Min TW slack",
    "Min battery")
REQUIRED_FIGURES = {
    "01_customer_service", "02_complete_service", "03_service_by_size",
    "04_service_by_family", "05_service_by_dod", "06_matched_service_distance",
    "07_worker_runtime", "08_decision_latency_ecdf", "09_service_runtime_tradeoff",
    "10_energy_charging_fleet", "11_development_paired_differences",
    "12_development_ablation", "13_balanced_development_service_changes",
    "14_balanced_development_cpu_ratio"}


def attempted_cpu_seconds(*ledgers):
    """Count all supervised attempts, including failed jobs and retries."""
    total = 0.0
    for ledger in ledgers:
        for job in ledger["jobs"]:
            value = job.get("cpu_seconds")
            if value is None or not isfinite(value) or value < 0:
                raise ValueError("Attempted worker CPU time is missing or invalid")
            total += value
    return total


def integrate_balanced_development():
    from scripts.analyze_final_cpu_development import analyze
    from scripts.run_final_cpu_development import OUTPUT as DEV

    analyze()
    manifest = load_json(DEV / "manifest.json")
    correction = load_json(DEV / "technical_extension" / "completion.json")
    attempted_cpu = attempted_cpu_seconds(
        load_json(DEV / "budget.json"),
        load_json(DEV / "technical_extension" / "budget.json"))
    if (manifest["status"] != "complete" or manifest["completed_runs"] != 120 or
            correction["status"] != "complete" or correction["completed_runs"] != 120 or
            correction["total_charged_wall_seconds"] > 21600 or
            attempted_cpu > 36000):
        raise ValueError("Balanced development study is incomplete or exceeded its hard allowance")
    for name in ("paired_cases", "variant_summary"):
        for suffix in (".md", ".csv", ".tex"):
            copyfile(DEV / "tables" / f"{name}{suffix}",
                     writable_path(TABLES / f"balanced_development_{name}{suffix}"))
    for old, new in (("development_service_changes", "13_balanced_development_service_changes"),
                     ("development_cpu_ratio", "14_balanced_development_cpu_ratio")):
        for suffix in (".png", ".svg"):
            copyfile(DEV / "figures" / f"{old}{suffix}", writable_path(PLT / f"{new}{suffix}"))
        copyfile(DEV / "audit/figure_data" / f"{old}.json",
                 writable_path(OUTPUT / "audit/figure_data" / f"{new}.json"))
    with (DEV / "tables" / "paired_cases.csv").open(newline="", encoding="utf-8") as stream:
        pairs = list(csv.DictReader(stream))
    combined = [row for row in pairs if row["variant"] == "combined"]
    if len(combined) != 30:
        raise ValueError("Balanced development combined comparison must have 30 pairs")
    probe_dir = ROOT / "results/desaulniers/two_worker_probe_v1"
    probe_protocol = load_json(probe_dir / "protocol.json")
    probe = load_json(probe_dir / "manifest.json")
    if probe["status"] != "complete" or probe["protocol_identifier"] != identifier(probe_protocol):
        raise ValueError("Two-worker technical probe is incomplete")
    from scripts.run_desaulniers_campaign import CONFIG as DEV_CONFIG, options as dev_options
    config = load_config(DEV_CONFIG)
    for mode in probe_protocol["modes"]:
        rows = probe["modes"][mode]["results"]
        if len(rows) != 2:
            raise ValueError("Two-worker technical probe is unpaired")
        for row in rows:
            info = probe_protocol["cases"][row["index"]]
            path = ROOT / row["raw"]
            if sha256(path.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError("Two-worker raw hash drift")
            raw = load_json(path)
            instance, reference, scenario, _ = prepare(
                info["instance"], dev_options(config, info["instance"], .5, 3, info["method"]))
            if (raw["source_sha256"] != probe_protocol["source_sha256"] or
                    scenario.identifier != info["scenario_id"] or
                    reference.fleet_size != info["k_ref"] or
                    not all(audit_result(decode_result(raw["result"]), instance, scenario).values()) or
                    raw["result"]["metrics"]["max_optimization_latency"] > 5.0 + 1e-6):
                raise ValueError("Two-worker technical probe replay failed")
    return dict(records=120, service_delta=sum(int(row["served_delta"]) for row in combined),
                gains=sum(int(row["served_delta"]) > 0 for row in combined),
                losses=sum(int(row["served_delta"]) < 0 for row in combined),
                harmed_parents=len({row["case"] for row in combined
                                    if int(row["served_delta"]) < 0}),
                charged_wall_seconds=correction["total_charged_wall_seconds"],
                worker_cpu_seconds=attempted_cpu,
                correction_protocol_sha256=sha256((DEV / "technical_extension" /
                                                    "protocol.json").read_bytes()).hexdigest(),
                protocol_sha256=sha256((DEV / "protocol.json").read_bytes()).hexdigest(),
                two_worker_probe=dict(records=4, same_service=probe["same_service"],
                                      throughput_ratio=probe["throughput_ratio"],
                                      protocol_sha256=sha256((probe_dir / "protocol.json").read_bytes()).hexdigest()))


def fmt(value, digits=2):
    return "NA" if value is None else f"{value:.{digits}f}"


def markdown(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(str(value) for value in row) + " |" for row in rows])


def write_table(name, headers, rows, note):
    writable_path(TABLES / f"{name}.md").write_text(
        f"# {name.replace('_', ' ').title().replace('Cpu', 'CPU').replace('Dod', 'DoD')}"
        f"\n\n{note}\n\n{markdown(headers, rows)}\n", encoding="utf-8")
    with writable_path(TABLES / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
    def tex(value):
        return (str(value).replace("\\", "\\textbackslash{}")
                .replace("_", "\\_").replace("%", "\\%")
                .replace("&", "\\&"))
    row_end = " " + chr(92) * 2
    lines = ["% " + note, "\\begin{tabular}{" + "l" * len(headers) + "}", "\\hline",
             " & ".join(map(tex, headers)) + row_end, "\\hline"]
    lines += [" & ".join(map(tex, row)) + row_end for row in rows]
    lines += ["\\hline", "\\end{tabular}"]
    writable_path(TABLES / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_figure(name, figure):
    figure.tight_layout()
    figure.savefig(writable_path(PLT / f"{name}.png"), dpi=300, facecolor="white")
    vector = writable_path(PLT / f"{name}.svg")
    figure.savefig(vector, facecolor="white", metadata={"Date": None})
    vector.write_text("\n".join(line.rstrip() for line in
                                vector.read_text(encoding="utf-8").splitlines()) + "\n",
                      encoding="utf-8")
    from scripts.paper_plot_audit import record_figure
    record_figure(figure, PLT / f"{name}.png", OUTPUT / "audit/figure_data" / f"{name}.json")
    plt.close(figure)


def configure_figures():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.axisbelow": True,
        "grid.color": "#d5d9dc", "grid.linewidth": .55,
        "svg.fonttype": "none", "svg.hashsalt": "mpc-evrp-final-cpu-paper-v1"})


def physical_features(raw, instance, worker_wall, worker_cpu):
    metrics = raw["metrics"]
    if any(metrics[key] != 0 for key in
            ("battery_violations", "capacity_violations", "time_window_violations",
             "hidden_information_violations", "duplicate_service_violations")):
        raise ValueError("Saved trajectory has a physical or information-boundary violation")
    customers = {customer.id: customer for customer in instance.customers}
    p = instance.infrastructure.parameters
    travel = consumption = 0.0
    service = Counter()
    final_time = {}
    last_service_completion = 0.0
    margins = []
    batteries = []
    for step in raw["steps"]:
        before, after = step["before"], step["after"]
        final_time[after["id"]] = max(final_time.get(after["id"], 0.0), after["time"])
        batteries.extend((before["battery"], after["battery"],
                          after["battery"] - step["energy_charged"]))
        if step["distance"]:
            a = instance.geometry.by_id[before["location"]["id"]]
            b = instance.geometry.by_id[after["location"]["id"]]
            travel += travel_time(a, b, p)
            consumption += energy(a, b, p)
        if step["served"] is not None:
            service[after["id"]] += 1
            margins.append(customers[step["served"]].due - step["service_start"])
            last_service_completion = max(last_service_completion, after["time"])
    loads = [service[k] for k in sorted(final_time)]
    balance = sqrt(mean((x-mean(loads))**2 for x in loads)) if loads else 0.0
    latencies = [d["optimization_latency_seconds"] for d in raw["decisions"]
                 if d.get("optimization_latency_seconds") is not None]
    cache_rates = [d["constructor_cache_hit_rate"] for d in raw["decisions"]
                   if d.get("constructor_cache_hit_rate") is not None]
    solver = [(d.get("optimizer") or {}).get("diagnostics") or {}
              for d in raw["decisions"]]
    if not latencies or max(latencies) > 5.0 + 1e-6:
        raise ValueError("Missing latency trace or five-second decision overrun")
    return dict(served=metrics["customers_served"], total=len(instance.customers),
                complete=int(bool(metrics["complete_service"])),
                served_ids=tuple(sorted(customers.keys() - set(raw["unserved_customers"]))),
                distance=metrics["total_distance"], travel_time=travel,
                completion_time=max(final_time.values(), default=0.0),
                last_service_completion_time=last_service_completion,
                charging_time=metrics["total_charging_time"], charged_energy=metrics["total_energy_charged"],
                travel_energy=consumption, waiting_time=metrics["total_waiting_time"],
                vehicles=metrics["vehicles_activated"], workload_std=balance,
                tw_margin_min=min(margins) if margins else None,
                tw_margin_mean=mean(margins) if margins else None,
                battery_min=min(batteries) if batteries else None,
                wall=worker_wall, cpu=worker_cpu,
                decisions=len(latencies), lat_mean=mean(latencies),
                lat_p95=float(np.percentile(latencies, 95)), lat_max=max(latencies),
                latencies=latencies,
                constructor_decodes=sum(d.get("constructor_exact_decoder_calls") or 0 for d in raw["decisions"]),
                constructor_screens=sum(d.get("constructor_screened_insertions") or 0 for d in raw["decisions"]),
                constructor_cache_hit_mean=mean(cache_rates) if cache_rates else None,
                optimizer_iterations=sum(d.get("iterations", 0) for d in solver),
                hgs_generations=sum(d.get("generations", 0) for d in solver),
                acs_ants=sum(d.get("ants_completed", 0) for d in solver),
                optimizer_decodes=sum(d.get("exact_decoder_calls", 0) for d in solver),
                feasibility=bool(metrics["feasible"]))


def load_primary():
    protocol = load_json(PRIMARY / "protocol.json")
    manifest = load_json(PRIMARY / "manifest.json")
    if (manifest["status"] != "complete" or len(manifest["records"]) != 450 or
            manifest["protocol_identifier"] != identifier(protocol)):
        raise ValueError("The 450-run independent primary cohort is incomplete")
    config = load_config(ROBUST_CONFIG)
    cached = {}
    rows = []
    seen = set()
    for item in manifest["records"]:
        key = (item["instance"], item["dynamicity"], item["seed"])
        method = item["method"]
        if (*key, method) in seen:
            raise ValueError("Duplicate primary method run")
        seen.add((*key, method))
        if key not in cached:
            instance, reference, scenario, _ = prepare(
                key[0], robust_options(config, key[1], key[2], METHODS[0]))
            if (scenario.identifier != item["scenario_id"] or reference.fleet_size != item["k_ref"]):
                raise ValueError("Historical scenario or fleet changed")
            cached[key] = instance, reference, scenario
        instance, reference, scenario = cached[key]
        path = ROOT / item["raw"]
        if (not path.resolve().is_relative_to((PRIMARY / "raw").resolve()) or
                sha256(path.read_bytes()).hexdigest() != item["raw_sha256"]):
            raise ValueError("Historical raw path/hash changed")
        raw = load_json(path)
        meta = raw["metadata"]
        if (meta["source_sha256"] != protocol["source_sha256"] or
                meta["algorithm"] != method or meta["scenario_identifier"] != scenario.identifier or
                meta["reference_schedule_identifier"] != reference.identifier or
                meta["K_ref"] != reference.fleet_size):
            raise ValueError("Historical source/method/input identity changed")
        audit = audit_result(decode_result(raw), instance, scenario)
        if not all(audit.values()) or audit != meta["independent_audit"]:
            raise ValueError("Independent historical disk replay failed")
        rows.append(dict(cohort="independent_primary_robustness_v3", case=key,
                         parent=key[0].split("_21_")[0], family=item["family"],
                         size=item["size"], dod=key[1], seed=key[2], method=method,
                         scenario_id=scenario.identifier, k_ref=reference.fleet_size,
                         source_sha256=protocol["source_sha256"], raw_sha256=item["raw_sha256"],
                         features=physical_features(raw, instance, raw["metrics"]["worker_wall_seconds"], None)))
    if len(cached) != 90 or len(seen) != 450:
        raise ValueError("Primary grid is not 90 scenarios by five methods")
    return rows, protocol


def load_replication():
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    if (manifest["status"] != "complete" or len(manifest["records"]) != 60 or
            manifest["protocol_identifier"] != identifier(protocol)):
        raise ValueError("New replication is incomplete; no final package may be rendered")
    specs = {spec["id"]: spec for block in protocol["blocks"] for spec in block["jobs"]}
    cached = {}
    rows = []
    seen = set()
    for item in manifest["records"]:
        if item["id"] in seen or item["id"] not in specs:
            raise ValueError("Duplicate or unplanned replication run")
        seen.add(item["id"])
        spec = specs[item["id"]]
        index = spec["index"]
        info = protocol["selected"][index]
        if index not in cached:
            cached[index] = archived_case(info)
        instance, reference, scenario = cached[index]
        path = ROOT / item["raw"]
        if (not path.resolve().is_relative_to((OUTPUT / "raw").resolve()) or
                sha256(path.read_bytes()).hexdigest() != item["sha256"]):
            raise ValueError("Replication raw path/hash changed")
        saved = load_json(path)
        verify_raw(protocol, spec, saved)
        raw = saved["result"]
        audit = audit_result(decode_result(raw), instance, scenario)
        if not all(audit.values()) or audit != raw["metadata"]["independent_audit"]:
            raise ValueError("Independent replication disk replay failed")
        rows.append(dict(cohort="independent_cpu_replication_v1",
                         case=(info["instance"], info["dynamicity"], info["seed"]),
                         parent=info["instance"].split("_21_")[0], family=info["family"],
                         size=info["size"], dod=info["dynamicity"], seed=info["seed"],
                         method=spec["method"], scenario_id=scenario.identifier,
                         k_ref=reference.fleet_size, source_sha256=protocol["source_sha256"],
                         raw_sha256=item["sha256"],
                         features=physical_features(raw, instance, item["execution"]["elapsed_seconds"],
                                                    item["execution"]["cpu_seconds"]
                                                    if item["execution"]["cpu_seconds"] is not None
                                                    else saved["worker_cpu_seconds"])))
    if len(cached) != 12 or len(seen) != 60:
        raise ValueError("Replication grid is not 12 scenarios by five methods")
    return rows, protocol


def paired(rows):
    groups = defaultdict(dict)
    for row in rows:
        if row["method"] in groups[row["case"]]:
            raise ValueError("Duplicate method in case")
        groups[row["case"]][row["method"]] = row
    if any(set(group) != set(METHODS) for group in groups.values()):
        raise ValueError("Missing method from a matched scenario")
    return groups


def cluster_ci(groups, left, right, seed=20261026, *, endpoint="parent_equal_service"):
    if endpoint not in ("parent_equal_service", "customer_weighted_service", "complete_service"):
        raise ValueError(f"Unknown paired endpoint: {endpoint}")
    if not groups:
        raise ValueError("Empty paired comparison")
    parent_groups = defaultdict(list)
    for group in groups.values():
        if (group[left]["parent"] != group[right]["parent"] or
                group[left]["features"]["total"] != group[right]["features"]["total"]):
            raise ValueError("Paired parent or customer denominator mismatch")
        parent_groups[group[left]["parent"]].append(group)
    parents = sorted(parent_groups)
    numerators, denominators = [], []
    for parent in parents:
        cases = parent_groups[parent]
        if endpoint == "parent_equal_service":
            numerators.append(mean(100 * (group[left]["features"]["served"] -
                                         group[right]["features"]["served"]) /
                                   group[left]["features"]["total"] for group in cases))
            denominators.append(1)
        else:
            field = "complete" if endpoint == "complete_service" else "served"
            numerators.append(100 * sum(group[left]["features"][field] -
                                        group[right]["features"][field] for group in cases))
            denominators.append(len(cases) if endpoint == "complete_service" else
                                sum(group[left]["features"]["total"] for group in cases))
    observed = sum(numerators) / sum(denominators)
    rng = np.random.default_rng(seed)
    draw = rng.integers(0, len(parents), size=(10000, len(parents)))
    sampled = (np.asarray(numerators)[draw].sum(axis=1) /
               np.asarray(denominators)[draw].sum(axis=1))
    low, high = np.percentile(sampled, [2.5, 97.5])
    field = "complete" if endpoint == "complete_service" else "served"
    changes = [group[left]["features"][field] - group[right]["features"][field]
               for group in groups.values()]
    return dict(effect=observed, low=float(low), high=float(high),
                wins=sum(change > 0 for change in changes),
                ties=sum(change == 0 for change in changes),
                losses=sum(change < 0 for change in changes), parents=len(parents),
                scenarios=len(changes), seed=seed, endpoint=endpoint)


def archived_development():
    output = subprocess.check_output(["git", "show", f"{ARCHIVE_TAG}:"
        "results/desaulniers/hybrid_acceleration_v1/analysis.json"], cwd=ROOT)
    data = json.loads(output)
    if data["status"] != "complete" or data["pairs"] is None or len(data["pairs"]) != 25:
        raise ValueError("Archived development evidence is incomplete")
    return data["pairs"]


def aggregate(rows):
    if not rows:
        raise ValueError("Empty comparison group")
    served = sum(row["features"]["served"] for row in rows)
    total = sum(row["features"]["total"] for row in rows)
    return dict(runs=len(rows), served=served, total=total, service=100*served/total,
                complete=sum(row["features"]["complete"] for row in rows),
                complete_rate=100*mean(row["features"]["complete"] for row in rows),
                wall=mean(row["features"]["wall"] for row in rows),
                cpu=(mean(row["features"]["cpu"] for row in rows)
                     if all(row["features"]["cpu"] is not None for row in rows) else None))


def parent_interval(groups, method, endpoint, seed=20261026):
    by_parent = defaultdict(list)
    for group in groups.values():
        row = group[method]
        by_parent[row["parent"]].append(row)
    parent_data = list(by_parent.values())
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(parent_data), size=(10000, len(parent_data)))
    values = []
    for draw in draws:
        selected = [row for index in draw for row in parent_data[index]]
        if endpoint == "service":
            values.append(100*sum(r["features"]["served"] for r in selected)/
                          sum(r["features"]["total"] for r in selected))
        else:
            values.append(100*mean(r["features"]["complete"] for r in selected))
    return tuple(float(x) for x in np.percentile(values, [2.5, 97.5]))


def group_table(rows, field, values, note, name):
    output = []
    for value in values:
        for method in METHODS:
            subset = [r for r in rows if r[field] == value and r["method"] == method]
            stats = aggregate(subset)
            output.append([value, LABELS[method], stats["runs"],
                           f"{stats['served']}/{stats['total']}", fmt(stats["service"]),
                           f"{stats['complete']}/{stats['runs']}", fmt(stats["complete_rate"])])
    write_table(name, [field.title(), "Method", "Runs", "Served/total",
                       "Service %", "Complete/runs", "Complete %"], output, note)
    return output


def unconditional_operations(cohorts):
    output = []
    for cohort, rows in cohorts:
        for method in METHODS:
            selected = [row for row in rows if row["method"] == method]
            stats = aggregate(selected)
            features = [row["features"] for row in selected]
            values, counts = [], []
            for field in OPERATIONAL_FIELDS:
                observed = [f[field] for f in features if f[field] is not None]
                values.append(fmt(mean(observed)) if observed else "NA")
                counts.append(len(observed))
            output.append([cohort, LABELS[method], stats["runs"],
                           f"{stats['served']}/{stats['total']}", stats["complete"],
                           *values, *counts])
    return output


def render_tables(primary, replication, dev):
    pg, rg = paired(primary), paired(replication)
    common = [key for key, group in pg.items() if all(group[m]["features"]["complete"] for m in METHODS)]
    rcommon = [key for key, group in rg.items() if all(group[m]["features"]["complete"] for m in METHODS)]
    if not common:
        raise ValueError("No common complete primary cases for operational comparison")
    main_rows = []
    stats = {}
    for method in METHODS:
        selected = [r for r in primary if r["method"] == method]
        item = aggregate(selected)
        dist = mean(pg[key][method]["features"]["distance"] for key in common)
        stats[method] = dict(item, common_distance=dist,
                             service_ci=parent_interval(pg, method, "service"),
                             complete_ci=parent_interval(pg, method, "complete"))
        main_rows.append([LABELS[method], item["runs"], f"{item['served']}/{item['total']}",
                          fmt(item["service"]), f"{item['complete']}/{item['runs']}",
                          fmt(item["complete_rate"]), item["total"]-item["served"],
                          fmt(dist), len(common), fmt(item["wall"])])
    write_table("main_five_methods",
        ["Method", "Runs", "Served/total", "Service %", "Complete/runs",
         "Complete %", "Offline service gap", "Distance on common complete",
         "Common complete n", "Mean worker wall s"], main_rows,
        "Independent robustness v3, 90 matched scenarios, 6 parent instances. "
        "Distance uses only scenarios completed by all five methods. "
        "The offline gap is to a physically feasible full-service reference, not an online oracle score.")
    size_rows = group_table(primary, "size", (25, 50, 100),
        "Independent robustness v3; customer-weighted service within each size. "
        "Two underlying parent instances per size, repeated DoD/seeds.", "by_size")
    family_rows = group_table(primary, "family", ("C1", "C2", "R1", "R2", "RC1", "RC2"),
        "Independent robustness v3; one underlying parent per family. "
        "Family comparisons are descriptive, not six independent parents within each family.", "by_family")
    strata = []
    for field, values in (("dod", (.25, .5, .75)), ("seed", (1, 2, 3, 4, 5))):
        for value in values:
            for method in METHODS:
                item = aggregate([r for r in primary if r[field] == value and r["method"] == method])
                strata.append([field, value, LABELS[method], item["runs"],
                               f"{item['served']}/{item['total']}", fmt(item["service"]),
                               f"{item['complete']}/{item['runs']}", fmt(item["complete_rate"])])
    write_table("dynamism_seed",
        ["Stratum", "Value", "Method", "Runs", "Served/total", "Service %",
         "Complete/runs", "Complete %"], strata,
        "Independent robustness v3 only. DoD is target degree of dynamism; "
        "seeds 1-5 repeat the same six benchmark parents.")
    operational = []
    for method in METHODS:
        f = [pg[key][method]["features"] for key in common]
        operational.append([LABELS[method], len(f),
            *[fmt(mean(r[field] for r in f)) for field in OPERATIONAL_FIELDS]])
    write_table("operational_matched_service",
        ["Method", "Common complete n", *OPERATIONAL_HEADERS], operational,
        "Independent robustness v3 only, restricted to the same fully served "
        f"{len(common)} scenarios for every method. Distance is benchmark units; "
        "times are benchmark time units; energy is benchmark battery units. "
        "The fleet end is censored by the scheduled depot-return horizon and "
        "should not be ranked as a routing-quality metric. "
        "Load SD is across vehicles represented in the trace.")
    unconditional = unconditional_operations((
        ("independent primary robustness v3", primary),
        ("independent CPU replication", replication)))
    write_table("operational_unconditional_by_cohort",
        ["Cohort", "Method", "Runs", "Served/total", "Complete runs",
         *OPERATIONAL_HEADERS, *[f"{header} n" for header in OPERATIONAL_HEADERS]],
        unconditional,
        "Unconditional descriptive means over all runs, separately by independent cohort. "
        "Different served-customer sets preclude efficiency rankings. Each metric has its "
        "own nonmissing run denominator; undefined margins are excluded, not set to zero. "
        "Distance is in benchmark distance units, times in benchmark time units, energy "
        "and battery in benchmark battery units, active EVs in vehicles, and load SD in "
        "customers across traced vehicles. TW slack and battery are means of run minima. "
        "Fleet end time is horizon-censored. Use matched-service tables for comparisons.")
    computation = []
    for cohort, rows in (("primary v3", primary), ("new replication", replication)):
        for method in METHODS:
            selected = [r for r in rows if r["method"] == method]
            features = [r["features"] for r in selected]
            latency = [value for f in features for value in f["latencies"]]
            item = aggregate(selected)
            computation.append([cohort, LABELS[method], len(selected),
                fmt(item["wall"]), fmt(item["cpu"]), fmt(mean(f["decisions"] for f in features)),
                fmt(mean(f["constructor_decodes"] for f in features)),
                fmt(mean(f["constructor_screens"] for f in features)),
                fmt(mean(f["constructor_cache_hit_mean"] for f in features
                         if f["constructor_cache_hit_mean"] is not None))
                if any(f["constructor_cache_hit_mean"] is not None for f in features) else "NA",
                fmt(mean(f["optimizer_iterations"] for f in features))
                if method in ("MPC_MCTS", "MPC_ALNS") else "NA",
                fmt(mean(f["hgs_generations"] for f in features))
                if method == "MPC_HGS" else "NA",
                fmt(mean(f["acs_ants"] for f in features))
                if method == "MPC_ACS" else "NA",
                fmt(mean(f["optimizer_decodes"] for f in features))
                if method in ("MPC_ALNS", "MPC_HGS", "MPC_ACS") else "NA",
                fmt(mean(latency), 3), fmt(np.percentile(latency, 95), 3),
                fmt(max(latency), 3)])
    write_table("computational_performance",
        ["Cohort", "Method", "Runs", "Mean worker wall s", "Mean worker CPU s",
         "Mean replans", "Mean constructor exact decodes", "Mean insertion screens",
         "Mean constructor cache-hit fraction", "Mean MCTS/ALNS iterations",
         "Mean HGS generations", "Mean ACS ants", "Mean optimizer exact decodes",
         "Decision mean s", "Decision p95 s", "Decision max s"], computation,
        "Workers ran sequentially in separate processes. The new replication "
        "shared a host with other pre-existing Python processes, so its timing "
        "is a shared-machine observation. Historical v3 did not record child CPU time, "
        "so its CPU entries are NA, not inferred from wall time. "
        "Constructor decode/screen/cache values do not include all optimizer work. "
        "Search-work counters are read from per-decision optimizer diagnostics; "
        "MCTS iterations, ALNS iterations, HGS generations and ACS ants are "
        "method-specific units and are not directly comparable. MCTS reports "
        "decoded options rather than the optimizer exact-decoder-call counter, "
        "so that cell is NA. NA also marks nonapplicable methods.")
    replica_rows = []
    for method in METHODS:
        selected = [r for r in replication if r["method"] == method]
        item = aggregate(selected)
        matched = [rg[key][method]["features"] for key in rcommon]
        replica_rows.append([LABELS[method], item["runs"], f"{item['served']}/{item['total']}",
                             fmt(item["service"]), f"{item['complete']}/{item['runs']}",
                             fmt(item["complete_rate"]), fmt(item["wall"]), fmt(item["cpu"]),
                             fmt(mean(f["distance"] for f in matched)) if matched else "NA", len(matched)])
    write_table("independent_cpu_replication",
        ["Method", "Runs", "Served/total", "Service %", "Complete/runs", "Complete %",
         "Mean wall s", "Mean CPU s", "Common-complete distance", "Common-complete n"],
        replica_rows,
        "New independently preregistered CPU-only replication on six previously unused "
        "underlying parents, DoD 0.50, seeds 6 and 7. Do not pool with robustness v3.")
    dev_rows = []
    ablation = []
    for stage, label in ((0, "B: compiled CPU screen/cache"), (1, "C: quality/recovery policy")):
        for method in METHODS:
            chosen = [r for r in dev if (r["index"] < 3) == (stage == 0) and r["method"] == method]
            old = [r["original"] for r in chosen]
            new = [r["enhanced"] for r in chosen]
            delta = [b["served"]-a["served"] for a, b in zip(old, new)]
            equal = [r for r in chosen if r["equal_service"]]
            shorter = sum(r["enhanced"]["distance"] < r["original"]["distance"]-.01 for r in equal)
            dev_rows.append([label, LABELS[method], len(chosen),
                f"{sum(a['served'] for a in old)}/{sum(a['total'] for a in old)}",
                f"{sum(b['served'] for b in new)}/{sum(b['total'] for b in new)}",
                sum(a["complete"] for a in old), sum(b["complete"] for b in new),
                sum(delta), fmt(sum(a["wall"] for a in old)), fmt(sum(b["wall"] for b in new)),
                fmt(sum(a["wall"] for a in old)/sum(b["wall"] for b in new)),
                f"{sum(x>0 for x in delta)}/{sum(x==0 for x in delta)}/{sum(x<0 for x in delta)}"])
            ablation.append([label, LABELS[method], len(chosen), sum(delta),
                             sum(x>0 for x in delta), sum(x==0 for x in delta),
                             sum(x<0 for x in delta), len(equal), shorter])
    write_table("development_original_vs_enhanced",
        ["Development stage", "Method", "Pairs", "Original served", "Enhanced served",
         "Original complete", "Enhanced complete", "Service delta",
         "Original wall s", "Enhanced wall s", "Original/enhanced wall speedup", "W/T/L"], dev_rows,
        f"Historical 25-pair development experiment recovered byte-for-byte from Git tag "
        f"{ARCHIVE_TAG}. Opt-in variants were not promoted. These are not independent final results.")
    write_table("development_ablation",
        ["Development stage", "Method", "Pairs", "Service delta", "Wins", "Ties",
         "Losses", "Equal-served-set pairs", "Shorter distance on equal service"],
        ablation, f"Historical negative development ablation from tag {ARCHIVE_TAG}. "
        "No new optimizer was selected for the independent CPU replication.")
    contrasts = [(method, METHODS[0]) for method in METHODS[1:]] + [
        ("MPC_ALNS", "MPC_HGS")]
    statistics = []
    endpoint_statistics = []
    ci = {}
    for cohort, groups in (("primary v3", pg), ("new replication", rg)):
        for left, right in contrasts:
            result = cluster_ci(groups, left, right)
            ci[(cohort, left, right)] = result
            statistics.append([cohort, LABELS[left] + " vs " + LABELS[right],
                result["parents"], result["scenarios"], fmt(result["effect"], 3),
                fmt(result["low"], 3), fmt(result["high"], 3),
                result["wins"], result["ties"], result["losses"]])
            for endpoint, label in (("customer_weighted_service", "Customer-weighted service"),
                                    ("complete_service", "Complete-service scenario rate")):
                estimate = cluster_ci(groups, left, right, endpoint=endpoint)
                endpoint_statistics.append([
                    cohort, label, LABELS[left] + " vs " + LABELS[right],
                    estimate["parents"], estimate["scenarios"], fmt(estimate["effect"], 3),
                    fmt(estimate["low"], 3), fmt(estimate["high"], 3),
                    estimate["wins"], estimate["ties"], estimate["losses"]])
    write_table("parent_clustered_paired_statistics",
        ["Cohort", "Contrast", "Parents", "Paired scenarios", "Parent-equal service difference pp",
         "95% lower pp", "95% upper pp", "Wins", "Ties", "Losses"], statistics,
        "Exploratory parent-cluster bootstrap, 10,000 resamples, fixed seed 20261026. "
        "Parent-level scenario differences are averaged equally. Intervals are not "
        "multiplicity-adjusted; six independent parent clusters per cohort.")
    write_table("primary_endpoint_paired_statistics",
        ["Cohort", "Endpoint", "Contrast", "Parents", "Paired scenarios", "Difference pp",
         "95% lower pp", "95% upper pp", "Wins", "Ties", "Losses"], endpoint_statistics,
        "Exploratory paired parent-cluster percentile bootstrap, 10,000 resamples, seed "
        "20261026. Each draw retains all matched scenarios for sampled parents, including "
        "multiplicity, and recomputes total service difference / total customers or total "
        "completion difference / total scenarios. Wins/ties/losses refer to the named "
        "endpoint. Six parent clusters per cohort; intervals are not multiplicity-adjusted. "
        "Cohorts are not pooled; these analyses do not establish benchmark-wide superiority.")
    details = []
    for row in primary + replication:
        f = row["features"]
        details.append([row["cohort"], row["case"][0], row["family"], row["size"],
                        row["dod"], row["seed"], LABELS[row["method"]],
                        f["served"], f["total"], f["complete"], fmt(f["distance"]),
                        fmt(f["wall"]), fmt(f["cpu"]), fmt(f["lat_max"], 3),
                        row["scenario_id"], row["raw_sha256"]])
    write_table("all_audited_runs",
        ["Cohort", "Instance", "Family", "Size", "DoD", "Seed", "Method",
         "Served", "Total", "Complete", "Distance", "Wall s", "CPU s",
         "Max decision s", "Scenario ID", "Raw SHA-256"], details,
        "All 510 independently replayed original-method results. Cohorts are separate; "
        "distance is unconditional in this trace inventory and must not be used "
        "for cross-method efficiency claims when service differs.")
    return dict(primary=stats, primary_groups=pg, replication_groups=rg,
                common_primary=common, common_replication=rcommon,
                main_rows=main_rows, size_rows=size_rows, family_rows=family_rows,
                strata_rows=strata, operational_rows=operational, computation_rows=computation,
                 unconditional_operational_rows=unconditional,
                replication_rows=replica_rows, development_rows=dev_rows,
                 ablation_rows=ablation, statistics_rows=statistics,
                 endpoint_statistics_rows=endpoint_statistics, ci=ci)


def grouped_bars(name, groups, values, ylabel, title, *, ylim=None):
    figure, ax = plt.subplots(figsize=(10.8, 4.6))
    x = np.arange(len(groups))
    width = .15
    for index, method in enumerate(METHODS):
        ax.bar(x + (index-2)*width, values[method], width,
               color=COLORS[method], label=LABELS[method])
    ax.set(xticks=x, xticklabels=[str(item) for item in groups], ylabel=ylabel, title=title)
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_title(title, pad=42)
    ax.legend(ncol=5, loc="lower center", bbox_to_anchor=(.5, 1.01),
              frameon=False, fontsize=8)
    save_figure(name, figure)


def render_figures(primary, dev, output):
    configure_figures()
    stats = output["primary"]
    pg = output["primary_groups"]
    common = output["common_primary"]
    x = np.arange(len(METHODS))
    labels = [LABELS[m] for m in METHODS]
    colors = [COLORS[m] for m in METHODS]
    for endpoint, title, ylabel, name in (
        ("service", "Customer-weighted service (independent primary cohort)",
         "Customers served (%)", "01_customer_service"),
        ("complete_rate", "Complete-service scenarios (independent primary cohort)",
         "Complete scenarios (%)", "02_complete_service")):
        figure, ax = plt.subplots(figsize=(8.2, 4.7))
        values = [stats[m][endpoint] for m in METHODS]
        interval = [stats[m]["service_ci" if endpoint == "service" else "complete_ci"] for m in METHODS]
        error = [[max(0, value-pair[0]) for value, pair in zip(values, interval)],
                 [max(0, pair[1]-value) for value, pair in zip(values, interval)]]
        ax.bar(x, values, color=colors, width=.65)
        ax.errorbar(x, values, yerr=error, fmt="none", capsize=3,
                    color="#292c30", linewidth=.8)
        ax.set(xticks=x, xticklabels=labels, ylabel=ylabel, title=title, ylim=(0, 105))
        save_figure(name, figure)
    for field, values, name, title in (
        ("size", (25, 50, 100), "03_service_by_size", "Service by customer count"),
        ("family", ("C1", "C2", "R1", "R2", "RC1", "RC2"), "04_service_by_family",
         "Service by benchmark family"),
        ("dod", (.25, .5, .75), "05_service_by_dod", "Service by target DoD")):
        matrix = {method: [
            aggregate([r for r in primary if r[field] == value and r["method"] == method])["service"]
            for value in values] for method in METHODS}
        grouped_bars(name, values, matrix, "Customers served (%)", title, ylim=(0, 103))
    figure, ax = plt.subplots(figsize=(8.2, 4.7))
    distance = [stats[m]["common_distance"] for m in METHODS]
    ax.bar(x, distance, color=colors, width=.65)
    ax.set(xticks=x, xticklabels=labels, ylabel="Mean route distance (benchmark units)",
           title=f"Matched complete-service distance (n={len(common)} scenarios)")
    ax.set_ylim(0, max(distance)*1.12)
    save_figure("06_matched_service_distance", figure)
    figure, ax = plt.subplots(figsize=(8.2, 4.7))
    runtime = [stats[m]["wall"] for m in METHODS]
    ax.bar(x, runtime, color=colors, width=.65)
    ax.set(xticks=x, xticklabels=labels, ylabel="Mean recorded worker wall time (s)",
           title="Full-scenario computation")
    save_figure("07_worker_runtime", figure)
    figure, ax = plt.subplots(figsize=(8.3, 4.8))
    for method in METHODS:
        values = np.sort([latency for row in primary if row["method"] == method
                          for latency in row["features"]["latencies"]])
        ax.step(values, np.arange(1, len(values)+1)/len(values), where="post",
                label=LABELS[method], color=COLORS[method], linewidth=1.5)
    ax.axvline(5.0, color="#bd3d3d", linestyle="--", linewidth=1.1,
               label="Five-second limit")
    ax.set(xlabel="One MPC decision latency (s)", ylabel="Empirical cumulative probability",
           title="Decision latency ECDF", xlim=(0, 5.1), ylim=(0, 1.01))
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    save_figure("08_decision_latency_ecdf", figure)
    figure, ax = plt.subplots(figsize=(8.2, 4.7))
    for method in METHODS:
        ax.scatter(stats[method]["wall"], stats[method]["service"], s=95,
                   color=COLORS[method], label=LABELS[method])
    ax.set(xlabel="Mean recorded worker wall time (s)", ylabel="Customers served (%)",
           title="Service and computation trade-off", ylim=(83, 102))
    ax.legend(frameon=False, fontsize=8)
    save_figure("09_service_runtime_tradeoff", figure)
    figure, axes = plt.subplots(1, 3, figsize=(13.3, 4.6))
    for ax, field, ylabel in zip(axes, ("travel_energy", "charged_energy", "vehicles"),
                                 ("Energy consumed (battery units)",
                                  "Energy charged (battery units)", "Active EVs (count)")):
        values = [mean(pg[key][method]["features"][field] for key in common) for method in METHODS]
        ax.bar(x, values, color=colors, width=.72)
        ax.set(xticks=x, xticklabels=labels, ylabel=ylabel)
        ax.tick_params(axis="x", labelrotation=45)
    figure.suptitle(f"Operational efficiency on common complete-service scenarios (n={len(common)})")
    save_figure("10_energy_charging_fleet", figure)
    figure, ax = plt.subplots(figsize=(9.5, 4.8))
    for stage, marker, offset, label in ((0, "o", -.1, "Compiled CPU"),
                                          (1, "s", .1, "Quality/recovery")):
        for index, method in enumerate(METHODS):
            chosen = [r for r in dev if r["method"] == method and
                      ((r["index"] < 3) == (stage == 0))]
            for run, item in enumerate(chosen):
                ax.scatter(index+offset+(run-(len(chosen)-1)/2)*.025,
                           item["enhanced"]["served"]-item["original"]["served"],
                           s=38, marker=marker, color=COLORS[method],
                           label=label if index == 0 and run == 0 else None)
    ax.axhline(0, color="#555", linewidth=.8)
    ax.set(xticks=x, xticklabels=labels, ylabel="Enhanced minus original customers served",
           title="Archived development paired service differences")
    ax.legend(frameon=False, fontsize=8)
    save_figure("11_development_paired_differences", figure)
    figure, axes = plt.subplots(1, 2, figsize=(11.4, 4.5), sharey=True)
    for ax, stage, title in zip(axes, (0, 1), ("Compiled CPU screen/cache",
                                               "Operational quality/recovery")):
        counts = []
        for method in METHODS:
            chosen = [r for r in dev if r["method"] == method and
                      ((r["index"] < 3) == (stage == 0))]
            delta = [r["enhanced"]["served"]-r["original"]["served"] for r in chosen]
            counts.append((sum(value > 0 for value in delta),
                           sum(value == 0 for value in delta),
                           sum(value < 0 for value in delta)))
        bottom = np.zeros(len(METHODS))
        for index, label, color in ((0, "Gain", "#218462"), (1, "Tie", "#9ca5a9"),
                                    (2, "Loss", "#ba5550")):
            values = np.asarray([row[index] for row in counts])
            ax.bar(x, values, bottom=bottom, color=color, label=label)
            bottom += values
        ax.set(xticks=x, xticklabels=labels, title=title, ylabel="Matched cases")
        ax.tick_params(axis="x", labelrotation=35)
    axes[1].legend(ncol=3, loc="upper right", frameon=False, fontsize=8)
    save_figure("12_development_ablation", figure)


def service_loss_diagnosis():
    path = ROOT / "results/desaulniers/reliability_v2/diagnosis/events.json"
    data = load_json(path)
    categories = Counter(row["category"] for row in data["losses"])
    transitions = ROOT / "results/desaulniers/publication_development/instrumented_v1/loss_transition_probes.csv"
    with transitions.open(newline="", encoding="utf-8") as stream:
        drops = list(csv.DictReader(stream))
    stages = Counter(row["drop_stage"] for row in drops)
    lines = ["# Service-loss mechanisms and proof status", "",
        "Retrospective development evidence only. These cases were selected by missed-service "
        "outcomes and must not tune the independent cohorts.", "",
        f"Source event diagnosis: {path.relative_to(ROOT).as_posix()} "
        f"(SHA-256 {sha256(path.read_bytes()).hexdigest()}). "
        f"Source plan-transition probes: {transitions.relative_to(ROOT).as_posix()} "
        f"(SHA-256 {sha256(transitions.read_bytes()).hexdigest()}).", "",
        "| Mechanism | Observed count | Evidence label |", "| --- | ---: | --- |",
        f"| Optimistic direct-time arrival impossible at first reveal | {categories['unreachable_at_revelation']} "
        "| Conditional timing certificate given observed commitments; not offline impossibility |",
        f"| Direct-time opportunity disappears later | {categories['becomes_time_unreachable']} "
        "| Conditional timing certificate at the later measured state; association, not causal proof |",
        f"| Customer still feasibly insertable when omitted | 0 proven among {len(drops)} probed plan drops "
        "| Bounded probes found no additional service witness; global feasibility remains unknown |",
        f"| Previously planned customer lost by reassignment | {stages['optimizer']} traced drops; "
        "4 of 5 preserved immediate service count | Recorded plan transition, not a closed-loop causal effect |",
        "| Charging/energy reconstruction affected omission | 104,486 bounded decoder failures in "
        "three instrumented runs | Decoder event counts, not missed-customer counts or proof of energy infeasibility |",
        "| Deadline or weak candidate caused omission | 0 recorded dominated selected decisions "
        "| No positive causal witness; wall-clock search may still affect later trajectories |", "",
        "The direct-time bound ignores battery, load, other obligations and safe return. "
        "A positive bound never proves a feasible EV route. No unreleased customer was supplied to the controller. "
        "The six mechanisms overlap in time and are not an exhaustive partition of the 128 missed customers."]
    writable_path(OUTPUT / "audit" / "SERVICE_LOSS_DIAGNOSIS.md").write_text(
        "\n".join(lines)+"\n", encoding="utf-8")
    return dict(missed_customers=len(data["losses"]), categories=dict(categories),
                traced_plan_drops=len(drops), drop_stages=dict(stages))


def render_documents(primary, replication, dev, output, diagnosis, primary_protocol,
                     replication_protocol, balanced):
    p = output["primary"]
    r = {method: aggregate([row for row in replication if row["method"] == method])
         for method in METHODS}
    paired_primary = output["ci"]
    alns_hgs = paired_primary["primary v3", "MPC_ALNS", "MPC_HGS"]
    mcts_completion = paired_primary["primary v3", "MPC_MCTS", "MPC_COMPLETION"]
    total_primary = sum(row["features"]["total"] for row in primary if row["method"] == METHODS[0])
    cohort_methods = markdown(
        ["Method", "Primary service", "Primary complete", "Replication service",
         "Replication complete"],
        [[LABELS[method], f"{fmt(p[method]['service'])}%",
          f"{p[method]['complete']}/90",
          f"{fmt(r[method]['service'])}%", f"{r[method]['complete']}/12"]
         for method in METHODS])
    ci_rows = [row for row in output["statistics_rows"] if row[0] == "primary v3"]
    ci_table = markdown(["Contrast", "Parent-equal service difference pp", "95% cluster interval pp",
                         "Win/tie/loss"],
        [[row[1], row[4], f"[{row[5]}, {row[6]}]",
          f"{row[7]}/{row[8]}/{row[9]}"] for row in ci_rows])
    dev_losses = sum(item["enhanced"]["served"] < item["original"]["served"] for item in dev)
    dev_gains = sum(item["enhanced"]["served"] > item["original"]["served"] for item in dev)
    def leaders(field, values):
        output_rows = []
        for value in values:
            scores = {method: aggregate([row for row in primary if row[field] == value
                                          and row["method"] == method])["service"]
                      for method in METHODS}
            best = max(scores.values())
            output_rows.append([value, "/".join(LABELS[method] for method in METHODS
                                                if abs(scores[method]-best) < 1e-10),
                                fmt(best)])
        return markdown([field.upper(), "Highest observed service", "Service %"], output_rows)
    size_leaders = leaders("size", (25, 50, 100))
    family_leaders = leaders("family", ("C1", "C2", "R1", "R2", "RC1", "RC2"))
    common = output["common_primary"]
    pg = output["primary_groups"]
    operating_winners = []
    for field, name, direction in (
        ("distance", "Route distance (benchmark units)", "min"),
        ("travel_time", "Travel time (benchmark time units)", "min"),
        ("last_service_completion_time",
         "Last service completion (benchmark time units)", "min"),
        ("charging_time", "Charging time (benchmark time units)", "min"),
        ("charged_energy", "Charged energy (battery units)", "min"),
        ("travel_energy", "Travel energy (battery units)", "min"),
        ("waiting_time", "Waiting time (benchmark time units)", "min"),
        ("vehicles", "Active EVs", "min"),
        ("workload_std", "Vehicle load SD (customers)", "min"),
        ("tw_margin_min", "Minimum TW margin (benchmark time units)", "max"),
        ("battery_min", "Minimum battery (battery units)", "max")):
        values = {method: mean(pg[key][method]["features"][field] for key in common)
                  for method in METHODS}
        best = min(values.values()) if direction == "min" else max(values.values())
        operating_winners.append([name,
            "/".join(LABELS[method] for method in METHODS
                     if abs(values[method]-best) < 1e-10), fmt(best)])
    operating_table = markdown(["Conditional metric", "Best observed mean", "Value"],
                               operating_winners)
    replication_budget = load_json(OUTPUT / "budget.json")
    replica_worker_wall = sum(job.get("elapsed_seconds", 0) for job in replication_budget["jobs"])
    replica_worker_cpu = attempted_cpu_seconds(replication_budget)
    primary_worker_wall = sum(row["features"]["wall"] for row in primary)
    max_latency = max(row["features"]["lat_max"] for row in primary+replication)
    audit_caption = ("Every saved record used here was SHA-256 checked against its frozen "
                     "manifest and independently replayed for physical feasibility, "
                     "information boundaries, duplicate service, and deadline compliance. "
                     "All recorded optimization decisions met the five-second limit.")
    files = {
        "PAPER_RESULTS.md": "\n".join([
            "# Event-triggered fleet MPC on Desaulniers MP instances", "",
            "## Design and scope", "",
            "The primary, independently frozen Desaulniers MP robustness study contains "
            "90 matched dynamic scenarios and 450 original-method simulations, spanning "
            "six underlying benchmark parents, three target degrees of dynamism, and five "
            "release seeds. The separate prospective CPU replication contains 12 scenarios "
            "and 60 original-method simulations on six previously unused parents at target "
            "DoD 0.50 and seeds 6 and 7. The cohorts are reported separately and never pooled.",
            "", "## Results", "", cohort_methods, "",
            f"The primary cohort has {total_primary} customer opportunities per method. "
            f"ALNS had the highest observed primary customer-weighted service "
            f"({fmt(p['MPC_ALNS']['service'])}%) and complete-service frequency "
            f"({p['MPC_ALNS']['complete']}/90). MCTS improved paired service over "
            f"Completion by {fmt(mcts_completion['effect'])} percentage points "
            f"(parent-clustered exploratory 95% interval "
            f"[{fmt(mcts_completion['low'])}, {fmt(mcts_completion['high'])}]). "
            f"The ALNS-HGS difference was {fmt(alns_hgs['effect'])} percentage points "
            f"([{fmt(alns_hgs['low'])}, {fmt(alns_hgs['high'])}]); its interval includes "
            "zero, so superiority across benchmark parents is not established.", "",
            "### Paired primary contrasts", "", ci_table, "",
            "The 100%-service offline reference is physically feasible with the same "
            "reference fleet on each generated scenario. The online methods do not know "
            "unreleased requests; the service gap is therefore an offline-reference gap, "
            "not a claim of an online oracle optimum. Distance and energy comparisons "
            f"use only the {len(output['common_primary'])} primary scenarios where all "
            "five methods served everyone. They are conditional comparisons, not "
            "unconditional efficiency rankings.", "",
            "The opt-in compiled CPU and quality/recovery pilots are development evidence "
            f"only: {dev_gains} service gains and {dev_losses} service losses in 25 "
            "matched cases. These regressions do not justify enhanced promotion. The replication "
            "therefore tests the original methods, not an improved controller.", "",
            f"A separate, later 120-run balanced development ablation tested recovery, "
            f"first-action protection, route quality, CPU caching, and their combination. "
            f"The combination changed served customers by {balanced['service_delta']:+d} "
            f"over 30 paired method-runs, with {balanced['gains']} gains and "
            f"{balanced['losses']} {'loss' if balanced['losses'] == 1 else 'losses'}. "
            "A stricter post hoc service-preservation gate "
            "was applied; this is not the frozen selection rule. No enhanced promotion "
            "is justified by this exploratory evidence. See "
            "[development update](DEVELOPMENT_UPDATE.md).", "",
            "### Descriptive heterogeneity", "",
            "The highest observed customer-weighted service in each primary-cohort "
            "stratum is shown below. Ties are retained; each family has only one "
            "underlying parent and should not be interpreted as a general "
            "family-level winner.", "", size_leaders, "", family_leaders, "",
            f"Total recorded sequential-worker wall time was "
            f"{fmt(primary_worker_wall/3600)} h in the primary study and "
            f"{fmt(replica_worker_wall/3600)} h in the new replication. "
            f"The replication recorded {fmt(replica_worker_cpu/3600)} attempted-worker "
            "CPU-hours from all supervisor ledger entries, including failed attempts "
            "and process overhead; "
            f"its persistent charged wall allowance was "
            f"{fmt(replication_budget['charged_seconds']/3600)} h, including setup "
            "and analysis reserves. No historical child CPU time is inferred. "
            f"The maximum recorded decision latency across both cohorts was "
            f"{fmt(max_latency, 3)} s.", "",
            "### Operational trade-offs", "",
            f"On the {len(common)} jointly complete primary scenarios only, the "
            "lowest observed cost or largest observed safety margin by metric is "
            "listed below. These are conditional descriptions and do not imply "
            "the same method is best on all customer sets or statistically "
            "superior on a metric.", "", operating_table, "",
            audit_caption, "",
            "## Figures and tables", "",
            f"The {len(list(PLT.glob('*.png')))} figures in figures/ are 300 dpi PNG with matching SVG. "
            "Tables in tables/ are Markdown with CSV and LaTeX companions. Key displays: "
            "[five-method results](tables/main_five_methods.md), "
            "[independent CPU replication](tables/independent_cpu_replication.md), "
            "[25/50/100-customer results](tables/by_size.md), "
            "[family results](tables/by_family.md), "
            "[paired intervals](tables/parent_clustered_paired_statistics.md), "
            "[primary-endpoint paired intervals](tables/primary_endpoint_paired_statistics.md), "
            "[conditional operations](tables/operational_matched_service.md), "
            "[unconditional operations by cohort](tables/operational_unconditional_by_cohort.md), "
            "[service figure](figures/01_customer_service.png), "
            "[runtime ECDF](figures/08_decision_latency_ecdf.png).",
            ""]),
        "METHODS.md": "\n".join([
            "# Methods and frozen protocol", "",
            "## Common controller", "",
            "All five modes use one event-triggered fleet MPC controller, the same "
            "Desaulniers MP charging physics, the same fixed offline-reference fleet, "
            "the same released-request observations, the same service-first "
            "lexicographic objective, and a five-second optimization-decision budget. "
            "Only the optimizer differs: Completion, MCTS, ALNS, HGS, or ACS. "
            "No optional compiled screen, altered first-action policy, quality policy, "
            "or recovery policy is enabled in the replication.", "",
            "## Independent primary cohort", "",
            "The previously frozen robustness v3 protocol selected six eligible "
            "underlying parents, DoD targets 0.25/0.50/0.75 and seeds 1-5. "
            "Each of the 90 scenarios was run once with each original method in "
            "an isolated sequential worker. Its protocol, manifest and 450 raw "
            "records remain under results/desaulniers/robustness_v3. "
            f"Frozen source fingerprint: {primary_protocol['source_sha256']}.", "",
            "## Prospective CPU replication", "",
            "The new protocol selected the lexicographically first as-yet-unused "
            "published-reference parent in each family, with two each at sizes "
            "25, 50, and 100. DoD 0.50 and seeds 6 and 7 were fixed before worker "
            "execution. The six files are " +
            ", ".join(replication_protocol["config"]["instances"]) + ".",
            "Reference and scenario input files are archived byte-for-byte in inputs/. "
            "Each method runs sequentially in a separate worker process; alternating "
            "method order within paired blocks limits simple order effects. "
            "Other pre-existing Python processes remained on the host, so CPU and "
            "wall measurements are shared-machine observations, not controlled "
            "single-load speed benchmarks. "
            "The wall allowance is 8 hours, worker CPU allowance 12 hours, with "
            "a per-worker watchdog and persistent checkpoint manifest. "
            "No failed worker is silently retried.", "",
            f"Frozen source commit: {replication_protocol['source_commit']}. "
            f"Frozen source fingerprint: {replication_protocol['source_sha256']}. "
            "The protocol and raw manifest bind every scenario, method and result hash.", "",
            "## Outcomes", "",
            "Primary endpoints are customer-weighted service and the fraction of "
            "scenarios serving all customers. Secondary measures include matched "
            "complete-service distance, travel/completion/charging/waiting time, "
            "energy charged/consumed, active EVs, workload balance, time-window "
            "margin, minimum observed battery, worker wall/CPU time, replans, "
            "constructor telemetry, and decision latency. Historical child CPU "
            "time was not recorded and is NA, not inferred.", "",
            "No algorithm was retuned to these prospective scenarios. The archived "
            "opt-in enhancement evidence includes service regressions; no enhanced promotion "
            "is justified and there is no enhanced-method independent final contrast.", ""
        ]),
        "STATISTICAL_ANALYSIS.md": "\n".join([
            "# Statistical analysis", "",
            "The experimental matching unit is a dynamic scenario: identical "
            "underlying instance, DoD, seed, archived reference fleet, and release "
            "schedule for all five methods. A scenario's served-customer "
            "difference is converted to percentage points. Within each underlying "
            "parent, these paired differences are averaged equally across DoD and "
            "seeds; the six parent means are then averaged. The exploratory 95% "
            "interval is the percentile interval from 10,000 bootstrap resamples "
            "of the six parents, fixed random seed 20261026. Wins, ties, and "
            "losses count matched scenarios. Customer-weighted overall service "
            "uses total served divided by total available, so it need not equal "
            "the equally parent-weighted paired difference.", "",
            "The separate primary-endpoint paired table estimates customer-weighted service "
            "and complete-service scenario rate differences in percentage points. For each "
            "of 10,000 paired parent-cluster resamples (seed 20261026), all scenarios of each "
            "sampled parent are retained with multiplicity. The service contrast divides "
            "the summed paired served-count differences by summed customer opportunities; "
            "the completion contrast divides summed paired completion-indicator differences "
            "by the number of sampled scenarios. Percentile intervals use the 2.5th and "
            "97.5th percentiles. These are exploratory analyses, without multiplicity "
            "adjustment, separately for each cohort. The parent-equal contrast below "
            "remains a distinct secondary estimand.", "",
            "Primary-cohort contrasts are listed below. Replication contrasts "
            "are in the linked table; no pooling or retrospective reweighting "
            "was performed.", "", ci_table, "",
            f"The ALNS-HGS interval [{fmt(alns_hgs['low'])}, {fmt(alns_hgs['high'])}] "
            "crosses zero. Six underlying parents per cohort make the bootstrap "
            "fragile, and intervals are not adjusted for multiple comparisons. "
            "A displayed interval excluding zero is descriptive, not a blanket "
            "claim of benchmark-wide superiority. Size and family breakdowns "
            "are descriptive strata, not independent confirmatory tests.",
            "", "[Parent-equal paired table](tables/parent_clustered_paired_statistics.md). "
            "[Primary-endpoint paired table](tables/primary_endpoint_paired_statistics.md)."
        ]),
        "LIMITATIONS.md": "\n".join([
            "# Limitations and negative findings", "",
            "The benchmark subset has only six independent parents in each cohort. "
            "Repeating DoD and seed does not create 90 independent benchmark files. "
            "The replication has only two seeds and one DoD, so it is a check of "
            "direction and feasibility, not a broad new population estimate.", "",
            "The general reference-inventory audit reports 166/168 physical "
            "witnesses. A separate targeted follow-up independently reported "
            "witnesses for the remaining two, but did not retroactively change "
            "historical fleets or releases. All 12 replication scenarios have "
            "their own archived, physically validated full-service references.", "",
            "The generator preserves a feasible full-service clairvoyant reference "
            "under the same fleet. This is not an online competitor and cannot "
            "diagnose which online decision lost a customer. Retrospective timing "
            f"diagnosis classified {diagnosis['categories']['unreachable_at_revelation']} "
            "losses as direct-time unreachable at first reveal and "
            f"{diagnosis['categories']['becomes_time_unreachable']} as becoming "
            "direct-time unreachable later under observed commitments. These "
            "conditional bounds ignore energy, load, and other obligations. "
            "They are not a partition of causal mechanisms or a proof of offline "
            "infeasibility. See audit/SERVICE_LOSS_DIAGNOSIS.md.", "",
            "Optional CPU screening and quality/recovery pilots were not promoted. "
            f"Among {len(dev)} archived development pairs, {dev_gains} enhanced "
            f"runs served more and {dev_losses} served fewer than the original. "
            "The hybrid GPU branch was slower on its actual transfer-inclusive "
            "batches. No performance or service gain from it is claimed. "
            "A new independent enhanced holdout was not opened.", "",
            f"The later 120-run balanced development ablation was exploratory and "
            f"does not justify enhanced promotion: combined service changed by "
            f"{balanced['service_delta']:+d} customers over 30 paired method-runs, "
            f"including {balanced['losses']} service loss. One 100-customer worker "
            "exceeded its initially prespecified whole-worker watchdog without "
            "producing raw output; the failed attempt was retained, and all eight "
            "remaining frozen jobs were completed under a separately documented "
            "900-second technical correction. No optimization-decision limit changed. "
            "The stricter service-preservation gate is post hoc and must not be described "
            "as the registered selection rule. Historical regressions remain disqualifying "
            "for deployment; this reporting correction does not retroactively promote a variant. "
            "See DEVELOPMENT_UPDATE.md.", "",
            "Unconditional distance, time, EV and energy summaries are not "
            "comparative efficiency measures when methods serve different "
            "customer sets. Conditional comparisons use only jointly complete "
            "scenarios; this introduces a restricted, high-feasibility subset. "
            "Fleet end time includes a scheduled common depot-return horizon, "
            "so last customer-service completion is the useful timing comparison; "
            "the horizon-censored end time is shown only for transparency. "
            "Sequential worker wall time is machine-specific; other Python "
            "processes were present and left running. Runtime is a shared-machine "
            "observation, not a controlled hardware benchmark. The five-second limit is "
            "per optimization decision, not per whole scenario.", "",
            "The historical 270-run corrected holdout, 450-run robustness cohort, "
            "60-run replication, 25-pair negative development study and 120-run "
            "balanced development ablation have "
            "different protocols and are never pooled."
        ]),
        "REPRODUCE.md": "\n".join([
            "# Reproduce and verify", "",
            "From the repository root, install requirements.txt in a CPU-only Python "
            "environment. The original five methods require no CUDA stack.", "",
            "1. Restore exact historical inputs and audit the frozen primary cohort:",
            "   python -m scripts.archive_frozen_inputs --restore",
            "   python -m scripts.audit_frozen_studies",
            "   python -m scripts.audit_enhancement_studies",
            "   python -m scripts.audit_reference_inventory",
            "2. Run the full CPU regression suite and record its outcome:",
            "   python -m pytest -q --basetemp results/.pytest_cpu_reproduce "
            "--junitxml results/desaulniers/final_cpu_paper_v1/audit/final_tests.xml",
            "3. Rebuild this paper package from saved raw evidence without running "
            "an optimizer:",
            "   python -m scripts.run_final_cpu_development --freeze",
            "   python -m scripts.complete_final_cpu_development --freeze",
            "   python -m scripts.analyze_final_cpu_development",
            "   python -m scripts.render_final_cpu_paper",
            "4. Verify cumulative execution, tests, evidence and delivery:",
            "   python -m scripts.audit_final_cpu_completion",
            "",
            "Do not delete or overwrite a saved raw record to force a rerun. "
            "All experiment manifests are complete; reproducing the package does not "
            "require another optimization campaign. Every saved record has a "
            "manifest SHA-256; audit/verification.json lists the verified "
            "protocols and generated outputs. The negative hybrid study is "
            "recoverable at Git tag archive/hybrid-gpu-negative-v1."
        ])
    }
    files["DEVELOPMENT_UPDATE.md"] = "\n".join([
        "# Balanced development update", "",
        "This is exploratory development evidence, not part of the independent "
        "510-run primary-plus-replication cohort. Six underlying parents, one per "
        "benchmark family and two at each customer size, were paired on original "
        "versus combined. Four component ablations used a prespecified three-parent "
        "subset. All five methods used the same scenarios, fleet, physics, objective "
        "and five-second decision limit.", "",
        f"All {balanced['records']} saved raw records passed independent physical "
        f"replay and source/scenario/hash checks. The combined variant yielded "
        f"{balanced['service_delta']:+d} served customers across 30 paired "
        f"method-runs ({balanced['gains']} gains, {balanced['losses']} "
        f"{'loss' if balanced['losses'] == 1 else 'losses'}; "
        f"{balanced['harmed_parents']} harmed parents). The frozen selection rule requires "
        "no aggregate service loss, no repeated family harm, and a useful service or "
        "conditional-quality gain. The stricter gate requiring positive aggregate service, "
        "at least two improving parents, no harmed parent, and no method-level aggregate "
        "service loss is post hoc. A single ACS loss is not, by itself, a demonstrated "
        "failure of the frozen rule. No enhanced promotion is justified by this exploratory "
        "evidence; historical regressions remain disqualifying for deployment. No variant "
        "is retroactively promoted and no enhanced independent holdout was opened.", "",
        f"Cumulative charged wall time: {balanced['charged_wall_seconds']/3600:.3f} h "
        f"of the six-hour development allowance; attempted-worker CPU time: "
        f"{balanced['worker_cpu_seconds']/3600:.3f} h, summed over all original and "
        "technical-correction supervisor ledger entries, including failures and process "
        "overhead. One original whole-worker "
        "timeout was preserved and the remaining eight jobs used a separately "
        "frozen 900-second technical correction. The five-second MPC decision "
        "budget did not change.", "",
        f"A separate two-scenario/two-method technical probe found "
        f"{balanced['two_worker_probe']['throughput_ratio']:.2f}x sequential-to-two-worker "
        f"throughput with identical served counts. This is a small shared-machine "
        "engineering result, not controlled paper timing. See the "
        "[probe report](../two_worker_probe_v1/RESULTS.md).", "",
        "See the [paired cases](tables/balanced_development_paired_cases.md), "
        "[variant summary](tables/balanced_development_variant_summary.md), "
        "[service changes](figures/13_balanced_development_service_changes.png), "
        "[CPU ratios](figures/14_balanced_development_cpu_ratio.png), "
        "[source protocol](../final_cpu_development_v1/protocol.json), "
        "[technical correction](../final_cpu_development_v1/technical_extension/protocol.json), "
        "[raw manifest](../final_cpu_development_v1/manifest.json), and "
        "[independent replay inventory](../final_cpu_development_v1/audit/independent_replay.md)."
    ])
    files["FINAL_REPORT.md"] = "\n".join([
        "# Final CPU paper package", "",
        "**Status: complete, provided audit/verification.json reports 510/510 passed.**",
        "", "The original five-method MPC system remains the publication configuration. "
        "The 450-run independent primary cohort and 60-run prospective replication "
        "are complete and separately reported. No enhanced promotion is justified; "
        "no enhanced final claim is made. The stricter development service-preservation "
        "gate was post hoc, not the frozen selection rule. "
        f"The later balanced development ablation observed "
        f"{balanced['service_delta']:+d} net served customers and "
        f"{balanced['losses']} paired service loss(es).",
        "", cohort_methods, "",
        f"Primary ALNS-HGS paired difference: {fmt(alns_hgs['effect'])} pp "
        f"(95% parent-cluster interval [{fmt(alns_hgs['low'])}, "
        f"{fmt(alns_hgs['high'])}]); this does not establish clear "
        "superiority across parents. All raw traces were independently "
        f"replayed and decision latencies checked. The new replication recorded "
        f"{fmt(replica_worker_wall/3600)} worker wall-hours and "
        f"{fmt(replica_worker_cpu/3600)} attempted-worker CPU-hours, including all "
        "supervised attempts and process overhead.", "",
        "Read [paper results](PAPER_RESULTS.md), [methods](METHODS.md), "
        "[statistics](STATISTICAL_ANALYSIS.md), [limitations](LIMITATIONS.md), "
        "[reproduction](REPRODUCE.md), "
        "[balanced development update](DEVELOPMENT_UPDATE.md), "
        "[six-family CPU coverage](CPU_COVERAGE.md), "
        "[service-loss diagnosis](audit/SERVICE_LOSS_DIAGNOSIS.md), "
        "[all audited runs](tables/all_audited_runs.md), and "
        "[the verification inventory](audit/verification.json). "
        "[Every final figure and table](INDEX.md) is indexed separately. "
        "Test and historical-audit outcomes are in "
        "[audit/VALIDATION.md](audit/VALIDATION.md).",
        "", "The GPU-negative study remains on the verified archive tag. "
        "The active project is CPU-only; old frozen studies are retained "
        "as historical evidence, not silently merged into this package."
    ])
    figure_links = [f"- [{path.stem.replace('_', ' ').title()}]"
                    f"(figures/{path.name}) ([SVG](figures/{path.stem}.svg))"
                    for path in sorted(PLT.glob("*.png"))]
    table_links = [f"- [{path.stem.replace('_', ' ').title()}]"
                   f"(tables/{path.name}) ([CSV](tables/{path.stem}.csv), "
                   f"[LaTeX](tables/{path.stem}.tex))"
                   for path in sorted(TABLES.glob("*.md"))]
    files["INDEX.md"] = "\n".join(["# Final figure and table index", "",
        "Each figure is 300 dpi PNG plus editable SVG. Tables are Markdown, "
        "CSV and LaTeX exports from the same audited aggregates.", "",
        "## Figures", "", *figure_links, "", "## Tables", "", *table_links])
    for name, body in files.items():
        writable_path(OUTPUT / name).write_text(body.rstrip() + "\n", encoding="utf-8")


def verify_package(primary, replication, primary_protocol, replication_protocol,
                   diagnosis, balanced):
    from scripts.paper_plot_audit import verify_figures
    graph_audit = verify_figures(OUTPUT)
    from_m = lambda path: sha256(path.read_bytes()).hexdigest()
    figures = sorted(PLT.glob("*.png"))
    vectors = sorted(PLT.glob("*.svg"))
    tables = sorted(TABLES.glob("*.md"))
    figure_stems = {path.stem for path in figures}
    required_tables = {"primary_endpoint_paired_statistics", "parent_clustered_paired_statistics",
                       "operational_unconditional_by_cohort", "operational_matched_service"}
    if (not REQUIRED_FIGURES <= figure_stems or
            figure_stems != {path.stem for path in vectors} or len(tables) < 11 or
            not required_tables <= {path.stem for path in tables} or
            len(list(TABLES.glob("*.csv"))) != len(tables) or
            len(list(TABLES.glob("*.tex"))) != len(tables)):
        raise ValueError("Paper figure/table inventory incomplete")
    for figure in figures:
        with Image.open(figure) as bitmap:
            dpi = bitmap.info.get("dpi", (0, 0))
            if min(dpi) < 299 or min(bitmap.size) < 900:
                raise ValueError(f"Figure lacks publication resolution: {figure}")
        ET.parse(PLT / (figure.stem + ".svg"))
    for document in [*OUTPUT.glob("*.md"), *tables, OUTPUT / "audit" / "SERVICE_LOSS_DIAGNOSIS.md"]:
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if target == "audit/verification.json" and document.parent == OUTPUT:
                continue
            if "://" not in target and not (document.parent / target).exists():
                raise ValueError(f"Broken paper link: {document}: {target}")
    files = sorted(path for path in OUTPUT.rglob("*") if path.is_file() and
                   not any(part.startswith("tmp_tests") or part == "__pycache__"
                           for part in path.relative_to(OUTPUT).parts) and
                   path.name not in {"verification.json", "MISSION_COMPLETION.json", "MISSION_COMPLETION.md",
                                     "repository_inventory.json"})
    inventory = {path.relative_to(OUTPUT).as_posix(): from_m(path) for path in files}
    audit = dict(status="complete", primary_records=len(primary),
                 figure_table_verification=graph_audit,
                 replication_records=len(replication), total_records=len(primary)+len(replication),
                 separately_audited_development_records=balanced["records"],
                 cpu_coverage=balanced["cpu_coverage"],
                 development_protocol_sha256=balanced["protocol_sha256"],
                 development_correction_protocol_sha256=balanced["correction_protocol_sha256"],
                 two_worker_probe_records=balanced["two_worker_probe"]["records"],
                 two_worker_probe_protocol_sha256=balanced["two_worker_probe"]["protocol_sha256"],
                 independent_disk_replay_passed=True, five_second_limit_passed=True,
                 primary_protocol_sha256=from_m(PRIMARY / "protocol.json"),
                 primary_manifest_sha256=from_m(PRIMARY / "manifest.json"),
                 primary_source_sha256=primary_protocol["source_sha256"],
                 replication_protocol_sha256=from_m(OUTPUT / "protocol.json"),
                 replication_manifest_sha256=from_m(OUTPUT / "manifest.json"),
                 replication_source_sha256=replication_protocol["source_sha256"],
                 replication_source_commit=replication_protocol["source_commit"],
                 decision_latency_max_seconds=max(
                     row["features"]["lat_max"] for row in primary+replication),
                 development_diagnosis=diagnosis,
                 png_figures=len(figures), svg_figures=len(vectors),
                 markdown_tables=len(tables), files_sha256=inventory)
    save_json(OUTPUT / "audit" / "verification.json", audit)
    return audit


def build():
    primary, primary_protocol = load_primary()
    replication, replication_protocol = load_replication()
    dev = archived_development()
    output = render_tables(primary, replication, dev)
    render_figures(primary, dev, output)
    balanced = integrate_balanced_development()
    from scripts.analyze_cpu_coverage import analyze as analyze_coverage
    coverage = analyze_coverage()
    balanced["cpu_coverage"] = dict(new_runs=coverage["new_runs"],
                                   raw_records=coverage["raw_records"],
                                   protocol_sha256=coverage["protocol_sha256"],
                                   manifest_sha256=coverage["manifest_sha256"])
    diagnosis = service_loss_diagnosis()
    render_documents(primary, replication, dev, output, diagnosis, primary_protocol,
                     replication_protocol, balanced)
    audit = verify_package(primary, replication, primary_protocol,
                           replication_protocol, diagnosis, balanced)
    print(f"Final CPU paper: {audit['total_records']}/{audit['total_records']} "
          f"independently replayed; {audit['png_figures']} PNG/SVG figures; "
          f"{audit['markdown_tables']} Markdown tables. "
          f"Review {OUTPUT / 'FINAL_REPORT.md'}")


if __name__ == "__main__":
    build()
