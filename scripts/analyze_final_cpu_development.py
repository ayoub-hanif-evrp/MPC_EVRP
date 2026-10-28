"""Independently replay and report the frozen paired development ablation."""

import csv
from collections import defaultdict
from hashlib import sha256
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.audit import decode_result
from evrp.experiments import audit_result
from evrp.instance import load_instance, travel_time, energy
from evrp.scenario import DynamicScenario
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, writable_path
from scripts.run_final_cpu_development import OUTPUT, verify_raw


def _table(name, rows):
    if not rows:
        return
    path = OUTPUT / name
    fields = tuple(rows[0])
    with writable_path(path.with_suffix(".csv")).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = ["| " + " | ".join(fields) + " |",
             "| " + " | ".join("---" for _ in fields) + " |"]
    lines.extend("| " + " | ".join(str(row[key]) for key in fields) + " |" for row in rows)
    writable_path(path.with_suffix(".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    escape = lambda value: str(value).replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")
    tex = ["\\begin{tabular}{" + "l" * len(fields) + "}", "\\hline",
           " & ".join(map(escape, fields)) + " " + "\\" * 2, "\\hline"]
    tex.extend(" & ".join(escape(row[key]) for key in fields) + " " + "\\" * 2 for row in rows)
    tex.extend(["\\hline", "\\end{tabular}"])
    writable_path(path.with_suffix(".tex")).write_text("\n".join(tex) + "\n", encoding="utf-8")


def _figure(name, fig):
    plt.rcParams["svg.hashsalt"] = "mpc-evrp-balanced-development-v1"
    fig.tight_layout()
    fig.savefig(writable_path(OUTPUT / "figures" / f"{name}.png"), dpi=300, facecolor="white")
    vector = writable_path(OUTPUT / "figures" / f"{name}.svg")
    fig.savefig(vector, facecolor="white", metadata={"Date": None})
    vector.write_text("\n".join(line.rstrip() for line in
                                vector.read_text(encoding="utf-8").splitlines()) + "\n",
                      encoding="utf-8")
    from scripts.paper_plot_audit import record_figure
    record_figure(fig, OUTPUT / "figures" / f"{name}.png", OUTPUT / "audit/figure_data" / f"{name}.json")
    plt.close(fig)


def analyze():
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    specs = {spec["id"]: spec for block in protocol["blocks"] for spec in block["jobs"]}
    if (manifest["protocol_identifier"] != identifier(protocol) or len(specs) != 120 or
            len(manifest["records"]) != manifest["completed_runs"] or
            len({row["id"] for row in manifest["records"]}) != manifest["completed_runs"]):
        raise ValueError("Development protocol/manifest mismatch")
    data = {}
    audited = []
    for row in manifest["records"]:
        spec = specs[row["id"]]
        path = ROOT / row["raw"]
        if (path != OUTPUT / "raw" / f"{spec['id']}.json.gz" or
                sha256(path.read_bytes()).hexdigest() != row["sha256"]):
            raise ValueError("Development raw path/hash mismatch")
        raw = load_json(path)
        verify_raw(protocol, spec, raw)
        info = protocol["selected"][spec["index"]]
        instance = load_instance(BENCHMARK / f"{info['instance']}.txt")
        scenario = DynamicScenario.load(ROOT / info["scenario"]["path"], instance)
        if instance.sha256 != info["instance_sha256"] or scenario.identifier != info["scenario_id"]:
            raise ValueError("Development instance/scenario drift")
        if not all(audit_result(decode_result(raw["result"]), instance, scenario).values()):
            raise ValueError(f"Independent physical replay failed: {spec['id']}")
        metrics = raw["result"]["metrics"]
        p = instance.infrastructure.parameters
        route_travel = sum(travel_time(instance.geometry.by_id[step["before"]["location"]["id"]],
                                       instance.geometry.by_id[step["after"]["location"]["id"]], p)
                           for step in raw["result"]["steps"] if step["distance"])
        route_energy = sum(energy(instance.geometry.by_id[step["before"]["location"]["id"]],
                                  instance.geometry.by_id[step["after"]["location"]["id"]], p)
                           for step in raw["result"]["steps"] if step["distance"])
        last_service = max((step["after"]["time"] for step in raw["result"]["steps"]
                            if step["served"] is not None), default=0.0)
        datum = dict(case=spec["index"], family=info["family"], size=info["size"],
                     method=spec["method"], variant=spec["variant"],
                     served=metrics["customers_served"], complete=int(metrics["complete_service"]),
                     unserved=tuple(sorted(raw["result"]["unserved_customers"])),
                     distance=metrics["total_distance"], travel=route_travel,
                     consumed_energy=route_energy, charged_energy=metrics["total_energy_charged"],
                     charging_time=metrics["total_charging_time"], waiting_time=metrics["total_waiting_time"],
                     vehicles=metrics["vehicles_activated"], last_service=last_service,
                     wall=raw["worker_wall_seconds"], cpu=raw["worker_cpu_seconds"],
                     max_latency=metrics["max_optimization_latency"],
                     p95_latency=metrics["p95_optimization_latency"])
        key = datum["case"], datum["method"], datum["variant"]
        if key in data:
            raise ValueError("Duplicate development method/variant")
        data[key] = datum
        audited.append(dict(job=spec["id"], raw_sha256=row["sha256"],
                            physical_replay="pass", max_latency_seconds=round(datum["max_latency"], 6)))
    _table("audit/independent_replay", audited)
    if len(data) != 120:
        writable_path(OUTPUT / "RESULTS.md").write_text(
            f"# Incomplete development ablation\n\nAudited {len(data)}/120 frozen runs. "
            "No variant selection or independent confirmation is permitted.\n", encoding="utf-8")
        return
    methods = protocol["config"]["methods"]
    variants = ("recovery", "first_action", "quality", "cpu", "combined")
    if set(protocol["variants"]) != {*variants, "original"}:
        raise ValueError("Frozen development variant set changed")
    paired = []
    for index in range(6):
        for method in methods:
            base = data[index, method, "original"]
            for variant in (variants if index in (0, 2, 4) else ("combined",)):
                other = data[index, method, variant]
                matched = base["unserved"] == other["unserved"]
                paired.append(dict(case=index, family=base["family"], size=base["size"],
                                   method=method, variant=variant,
                                   served_original=base["served"], served_variant=other["served"],
                                   served_delta=other["served"] - base["served"],
                                   complete_delta=other["complete"] - base["complete"],
                                   same_served_set=int(matched),
                                   distance_delta_if_matched=round(other["distance"] - base["distance"], 3)
                                   if matched else "NA",
                                   travel_delta_if_matched=round(other["travel"] - base["travel"], 3)
                                   if matched else "NA",
                                   charged_energy_delta_if_matched=round(
                                       other["charged_energy"] - base["charged_energy"], 3) if matched else "NA",
                                   consumed_energy_delta_if_matched=round(
                                       other["consumed_energy"] - base["consumed_energy"], 3) if matched else "NA",
                                   charging_time_delta_if_matched=round(
                                       other["charging_time"] - base["charging_time"], 3) if matched else "NA",
                                   waiting_delta_if_matched=round(
                                       other["waiting_time"] - base["waiting_time"], 3) if matched else "NA",
                                   vehicles_delta_if_matched=other["vehicles"] - base["vehicles"]
                                   if matched else "NA",
                                   last_service_delta_if_matched=round(
                                       other["last_service"] - base["last_service"], 3) if matched else "NA",
                                   cpu_ratio=round(other["cpu"] / base["cpu"], 3) if base["cpu"] else "NA"))
    _table("tables/paired_cases", paired)
    summary = []
    for variant in variants:
        for method in methods:
            values = [row for row in paired if row["variant"] == variant and row["method"] == method]
            matched = [row["distance_delta_if_matched"] for row in values if row["same_served_set"]]
            summary.append(dict(variant=variant, method=method, pairs=len(values),
                                served_delta=sum(row["served_delta"] for row in values),
                                wins=sum(row["served_delta"] > 0 for row in values),
                                ties=sum(row["served_delta"] == 0 for row in values),
                                losses=sum(row["served_delta"] < 0 for row in values),
                                complete_delta=sum(row["complete_delta"] for row in values),
                                matched_distance_n=len(matched),
                                matched_distance_delta_mean=round(mean(matched), 3) if matched else "NA",
                                cpu_ratio_mean=round(mean(row["cpu_ratio"] for row in values), 3)))
    _table("tables/variant_summary", summary)
    short = {method: method.removeprefix("MPC_") for method in methods}
    colors = {"recovery": "#237f64", "first_action": "#416c98", "quality": "#a66741",
              "cpu": "#7c6697", "combined": "#39444a"}
    fig, ax = plt.subplots(figsize=(10, 4.4))
    xs = list(range(len(methods)))
    width = .15
    for i, variant in enumerate(variants):
        vals = [next(row["served_delta"] for row in summary
                     if row["variant"] == variant and row["method"] == method) for method in methods]
        ax.bar([x + (i - 2) * width for x in xs], vals, width,
               label=f"{variant.replace('_', ' ')} (n={6 if variant == 'combined' else 3} parents)",
               color=colors[variant])
    ax.axhline(0, color="#333333", linewidth=.8)
    ax.set_xticks(xs, [short[method] for method in methods])
    ax.set(ylabel="Paired served-customer change (development cases)",
           title="Exploratory service changes by optimizer")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, .5), fontsize=8)
    _figure("development_service_changes", fig)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    cpu = [next(row["cpu_ratio_mean"] for row in summary
                if row["variant"] == "combined" and row["method"] == method) for method in methods]
    bars = ax.bar([short[method] for method in methods], cpu, color="#416c98")
    ax.axhline(1, color="#333333", linewidth=.8, linestyle="--")
    ax.bar_label(bars, fmt="%.2f", padding=2, fontsize=8)
    ax.set(ylabel="Combined / original worker CPU ratio",
           title="Paired combined-policy CPU cost")
    _figure("development_cpu_ratio", fig)
    combined = [row for row in paired if row["variant"] == "combined"]
    delta = sum(row["served_delta"] for row in combined)
    method_delta = {method: sum(row["served_delta"] for row in combined if row["method"] == method)
                    for method in methods}
    positive = len({row["case"] for row in combined if row["served_delta"] > 0})
    harmed = len({row["case"] for row in combined if row["served_delta"] < 0})
    conservative_screen = delta > 0 and positive >= 2 and harmed == 0 and all(
        value >= 0 for value in method_delta.values())
    lines = ["# Balanced CPU development ablation", "",
             "Exploratory source-frozen development evidence, not independent confirmation. "
             "Six families and two cases per size pair original with combined. Component ablations "
             "use fixed cases 0/2/4, one per size. All five methods share physics, objective and "
             "five-second decision budget. Case size is customers; distance is benchmark distance, "
             "travel/charging/waiting/service completion are benchmark time units, energy is benchmark "
             "energy, CPU is worker process seconds, and latency is seconds. A paired row represents "
             "one scenario and one optimizer; the same parent never counts as independent twice.", "",
             f"Independent replay: {len(audited)}/120 raw files passed.",
             f"Combined service change: {delta:+d} customers over 30 paired method-runs; "
             f"positive parents {positive}/6, harmed parents {harmed}/6.",
             "Method-specific service changes: " + ", ".join(
                 f"{key} {value:+d}" for key, value in method_delta.items()) + ".",
             f"Post hoc conservative service screen: {'PASS' if conservative_screen else 'FAIL'}.", "",
             "The frozen protocol states: " + protocol["selection_rule"] + ". "
             "It does not define numerical thresholds for useful gains or repeated family harm. "
             "The analysis implementation subsequently required a positive aggregate gain, "
             "two improving parents, zero harmed parents and no harmed method. That is a "
             "stricter, post hoc screen, not the preregistered acceptance rule. A single ACS "
             "loss therefore does not by itself establish failure of the registered rule. "
             "The original methods are retained because the limited development evidence "
             "and earlier regressions do not establish a repeatable improvement. No variant "
             "is retrospectively promoted from this analysis.", "",
             "See [paired cases](tables/paired_cases.md), [variant summary](tables/variant_summary.md), "
             "[independent replay](audit/independent_replay.md), "
             "[service figure](figures/development_service_changes.png), and "
             "[CPU figure](figures/development_cpu_ratio.png).", "",
             "Conditional distance is reported only for identical served-customer sets. "
             "A failed bounded insertion is not a proof of EV infeasibility."]
    writable_path(OUTPUT / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    analyze()
