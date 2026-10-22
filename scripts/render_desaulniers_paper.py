"""Render paper tables and PNG figures from the immutable corrected final study."""

from collections import defaultdict
from random import Random
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.storage import ROOT, load_json, writable_path
from scripts.verify_desaulniers_final import OUTPUT, verify


PAPER = ROOT / "results/desaulniers/paper_v2"
METHODS = ("MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS")
COLORS = ("#555b66", "#2377a5", "#1b8b62", "#a65f28", "#8058a5")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(map(str, row)) + " |" for row in rows]) + "\n"


def write(name, title, note, headers, rows):
    writable_path(PAPER / name).write_text(
        f"# {title}\n\n{note}\n\n{table(headers, rows)}", encoding="utf-8")


def clustered_ci(grouped, method, baseline, draws=10000):
    clusters = defaultdict(list)
    for (name, _dod, _seed), runs in grouped.items():
        clusters[name].append(100 * (runs[method]["customers_served"] -
                                     runs[baseline]["customers_served"]) / runs[method]["size"])
    values = list(clusters.values())
    rng = Random(2016)
    sampled = sorted(mean(x for cluster in (values[rng.randrange(len(values))]
                                          for _ in values) for x in cluster)
                     for _ in range(draws))
    return sampled[int(.025 * draws)], sampled[int(.975 * draws)]


def grouped_rows(grouped, key):
    buckets = defaultdict(list)
    for (_name, dod, _seed), runs in grouped.items():
        for method, row in runs.items():
            buckets[(key(row, dod), method)].append(row)
    rows = []
    for group in sorted({g for g, _ in buckets}):
        for method in METHODS:
            data = buckets[group, method]
            rows.append((group, method.removeprefix("MPC_"), len(data),
                         f"{100 * sum(r['customers_served'] for r in data) / sum(r['size'] for r in data):.2f}",
                         f"{100 * mean(r['complete_service'] for r in data):.1f}"))
    return rows


def render():
    verify()
    manifest = load_json(OUTPUT / "manifest.json")
    grouped = defaultdict(dict)
    for row in manifest["records"]:
        raw = load_json(ROOT / row["raw"])
        enriched = dict(row, metrics=raw["metrics"])
        grouped[row["instance"], row["dynamicity"], row["seed"]][row["method"]] = enriched
    common = {key for key, runs in grouped.items()
              if all(runs[m]["complete_service"] for m in METHODS)}
    from evrp.instance import discover_instances
    from scripts.run_desaulniers_pilot import family_of
    paths = discover_instances()
    write("table1_benchmark.md", "Table 1. Benchmark", "Static Desaulniers format-1 files paired with "
          "validated format-2 arcs. MP permits partial recharge; station-to-station arcs are absent.",
          ["Family", "25", "50", "100", "Stations", "Policy"],
          [(family, *(sum(family_of(p.stem) == family and p.stem.endswith(f"_{size}")
                           for p in paths) for size in (25, 50, 100)), 21, "MP")
           for family in ("C1", "C2", "R1", "R2", "RC1", "RC2")])
    protocol = load_json(OUTPUT / "protocol.json")
    write("table2_protocol.md", "Table 2. Corrected final protocol", "Historical final evidence; "
          "the original 10-run partial campaign is preserved separately. "
          "Hardware model was not recorded in the frozen protocol and must not be guessed.",
          ["Item", "Value"],
          [("Optimizers", ", ".join(m.removeprefix("MPC_") for m in METHODS)),
           ("Matched scenarios", len(grouped)), ("Base instances", len(protocol["selected"])),
           ("Seed", "0"), ("DoD", "0.25, 0.50, 0.75"),
           ("Decision limit", "5 s"), ("Fleet", "fixed feasible offline K_ref per scenario"),
           ("Execution", "isolated sequential worker processes"),
           ("Hardware", "not recorded in frozen protocol")])
    overall = []
    for method in METHODS:
        rows = [r[method] for r in grouped.values()]
        conditional = [grouped[key][method] for key in common]
        metrics = [r["metrics"] for r in rows]
        overall.append((method.removeprefix("MPC_"), len(rows),
                        f"{100 * sum(r['customers_served'] for r in rows) / sum(r['size'] for r in rows):.2f}",
                        f"{100 * mean(r['complete_service'] for r in rows):.1f}",
                        f"{mean(r['vehicles_activated'] for r in rows):.2f}",
                        f"{mean(r['total_distance'] for r in conditional):.2f}" if conditional else "NA",
                        len(common), f"{mean(m['mean_optimization_latency'] for m in metrics):.3f}",
                        f"{max(m['max_optimization_latency'] for m in metrics):.3f}",
                        "0 replay violations"))
    write("table3_overall.md", "Table 3. Overall MPC performance", "Customer service is weighted by "
          "customer opportunities. Distance is restricted to the same scenarios on which all five methods "
          "achieved complete service; unconditional distance is not ranked.",
          ["Method", "N", "Served %", "Complete %", "EV mean", "Distance matched", "Matched N",
           "Mean decision s", "Max decision s", "Audit"], overall)
    write("table4_size.md", "Table 4. Performance by size", "Final holdout; service weighted "
          "by customer opportunities within each size.",
          ["Customers", "Method", "N", "Served %", "Complete %"],
          grouped_rows(grouped, lambda row, dod: row["size"]))
    write("table5_dod.md", "Table 5. Performance by target DoD", "Final holdout; target "
          "dynamicity can differ slightly from realized dynamicity due to exact-count rounding.",
          ["Target DoD", "Method", "N", "Served %", "Complete %"],
          grouped_rows(grouped, lambda row, dod: dod))
    write("table7_family.md", "Table 7. Performance by instance family", "Final holdout; "
          "only three base instances per family, so differences are descriptive.",
          ["Family", "Method", "N", "Served %", "Complete %"],
          grouped_rows(grouped, lambda row, dod: row["family"]))
    comparisons = [(m, "MPC_COMPLETION") for m in METHODS[1:]] + [("MPC_ALNS", "MPC_HGS")]
    paired = []
    for method, baseline in comparisons:
        differences = [100 * (r[method]["customers_served"] - r[baseline]["customers_served"])
                       / r[method]["size"] for r in grouped.values()]
        low, high = clustered_ci(grouped, method, baseline)
        paired.append((method.removeprefix("MPC_"), baseline.removeprefix("MPC_"), len(differences),
                       f"{mean(differences):+.2f}", f"[{low:+.2f}, {high:+.2f}]",
                       sum(x > 0 for x in differences), sum(x == 0 for x in differences),
                       sum(x < 0 for x in differences)))
    write("table6_paired.md", "Table 6. Paired service differences", "Percentage-point differences "
          "are equally weighted across 54 matched scenarios. Percentile 95% intervals resample "
          "18 base instances, retaining all three DoD scenarios per sampled instance "
          "(10,000 draws, seed 2016). Intervals are descriptive; five displayed contrasts "
          "are not multiple-testing-adjusted confirmatory claims.",
          ["Method", "Baseline", "N", "Mean pp", "Cluster 95% CI pp", "Wins", "Ties", "Losses"], paired)

    def finish(fig, name):
        fig.tight_layout()
        fig.savefig(writable_path(PAPER / f"{name}.png"), dpi=300)
        plt.close(fig)

    for field, groups, filename, xlabel in (
            ("size", (25, 50, 100), "service_by_size", "Customers per instance"),
            ("dynamicity", (.25, .5, .75), "service_by_dod", "Target DoD")):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for method, color in zip(METHODS, COLORS):
            values = []
            for group in groups:
                rows = [r[method] for r in grouped.values() if
                        (r[method]["size"] if field == "size" else r[method]["dynamicity"]) == group]
                values.append(100 * sum(r["customers_served"] for r in rows) /
                              sum(r["size"] for r in rows))
            ax.plot(groups, values, marker="o", color=color, label=method.removeprefix("MPC_"))
        ax.set(xlabel=xlabel, ylabel="Customers served (%)", ylim=(0, 100))
        ax.set_xticks(groups)
        ax.legend(ncol=3, frameon=False)
        finish(fig, filename)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar([m.removeprefix("MPC_") for m in METHODS],
           [100 * mean(r[m]["complete_service"] for r in grouped.values()) for m in METHODS],
           color=COLORS)
    ax.set(ylabel="Scenarios with complete service (%)", ylim=(0, 100))
    finish(fig, "complete_service")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = [f"{a} vs {b}" for a, b, *_ in paired]
    estimates = [float(row[3]) for row in paired]
    lows = [float(row[4].split(",")[0][1:]) for row in paired]
    highs = [float(row[4].split(",")[1][:-1]) for row in paired]
    ax.errorbar(estimates, range(len(paired)),
                xerr=[[v - lo for v, lo in zip(estimates, lows)],
                      [hi - v for v, hi in zip(estimates, highs)]], fmt="o", color="#23698b",
                capsize=3)
    ax.axvline(0, color="#555b66", linewidth=1)
    ax.set_yticks(range(len(paired)), labels)
    ax.invert_yaxis()
    ax.set(xlabel="Paired service difference (percentage points)")
    finish(fig, "paired_service")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for method, color in zip(METHODS, COLORS):
        values = sorted(r[method]["metrics"]["max_optimization_latency"] for r in grouped.values())
        ax.step(values, [(i + 1) / len(values) for i in range(len(values))], where="post",
                color=color, label=method.removeprefix("MPC_"))
    ax.axvline(5, color="#555b66", linestyle="--", label="5 s limit")
    ax.set(xlabel="Maximum decision latency per run (s)", ylabel="Fraction of runs", ylim=(0, 1.02))
    ax.legend(ncol=3, frameon=False)
    finish(fig, "runtime_ecdf")
    alns_completion = paired[1]
    alns_hgs = paired[-1]
    writable_path(PAPER / "RESULTS.md").write_text(
        "# Corrected final MP results\n\n"
        "This directory reports the immutable 270-run corrected final holdout, not the original "
        "10-run partial campaign and not the new robustness study. Raw traces were independently "
        "replayed before rendering. All five methods use the same event-triggered MPC framework, "
        "objective, fixed reference fleet, dynamic requests, and five-second decision limit.\n\n"
        "Overall customer-weighted service rates are 92.19% Completion, 96.00% MCTS, "
        "99.14% ALNS, 98.89% HGS, and 98.19% ACS. "
        f"ALNS versus Completion gains {alns_completion[3]} percentage points on equally "
        f"weighted paired scenarios (instance-clustered 95% CI {alns_completion[4]}). "
        f"ALNS versus HGS is {alns_hgs[3]} percentage points "
        f"(95% CI {alns_hgs[4]}), so the observed mean ranking alone does not establish "
        "ALNS superiority over HGS. These descriptive intervals are not multiplicity-adjusted "
        "confirmatory tests. "
        "The static published solutions define feasible offline reference fleets, not "
        "online objective comparators. One release seed and 18 base instances limit "
        "generalization; the separately versioned multi-seed study is designed to "
        "test this limitation and is not yet evidence until complete.\n\n"
        "Figures are PNG only, 300 dpi. Tables are Markdown only. "
        "Distance comparisons use only common complete-service scenarios.\n",
        encoding="utf-8")
    print(f"Rendered {len(grouped)} matched corrected-final scenarios", flush=True)


if __name__ == "__main__":
    render()
