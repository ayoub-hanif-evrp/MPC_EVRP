"""Audit the complete Desaulniers MP holdout and render paired final results."""

from collections import defaultdict
from random import Random
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.experiments import load_config
from evrp.storage import writable_path
from scripts.analyze_desaulniers_campaign import _table, analyze
from scripts.run_desaulniers_final import CONFIG, OUTPUT, protocol


def cluster_interval(grouped, method, reference, draws=10000):
    by_instance = defaultdict(list)
    for (instance, _dod, _seed), methods in grouped.items():
        by_instance[instance].append(methods[method]["customers_served"] -
                                     methods[reference]["customers_served"])
    clusters = list(by_instance.values())
    rng = Random(2016)
    estimates = []
    for _ in range(draws):
        sample = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        estimates.append(mean(value for group in sample for value in group))
    estimates.sort()
    return estimates[int(0.025 * draws)], estimates[int(0.975 * draws)]


def render():
    frozen = protocol(load_config(CONFIG))
    grouped = analyze(frozen, OUTPUT, "final_complete")
    methods = frozen["methods"]
    rows = []
    for method in methods:
        if method == "MPC_COMPLETION":
            continue
        diffs = [runs[method]["customers_served"] - runs["MPC_COMPLETION"]["customers_served"]
                 for runs in grouped.values()]
        low, high = cluster_interval(grouped, method, "MPC_COMPLETION")
        rows.append((method, len(diffs), f"{mean(diffs):.2f}", f"[{low:.2f}, {high:.2f}]",
                     sum(x > 0 for x in diffs), sum(x == 0 for x in diffs),
                     sum(x < 0 for x in diffs)))
    path = OUTPUT / "SUMMARY.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n## Instance-clustered paired uncertainty\n\n")
        stream.write("Bootstrap resamples benchmark instances, retaining their DoD scenarios "
                     "together (10,000 draws, fixed seed). Intervals are descriptive 95% "
                     "percentile intervals; no final-outcome tuning was performed.\n\n")
        stream.write(_table(["Method", "Paired N", "Mean gain vs Completion", "95% CI",
                             "Wins", "Ties", "Losses"], rows) + "\n")

    fig, ax = plt.subplots(figsize=(9, 5))
    for method in methods:
        points = []
        for dod in frozen["dynamicities"]:
            runs = [case[method] for (_name, level, _seed), case in grouped.items()
                    if level == dod]
            points.append(100 * sum(r["customers_served"] for r in runs) /
                          sum(r["customers"] for r in runs))
        ax.plot(frozen["dynamicities"], points, marker="o", label=method.removeprefix("MPC_"))
    ax.set(xlabel="Target degree of dynamicity", ylabel="Customers served (%)",
           title="Desaulniers MP final holdout")
    ax.set_xticks(frozen["dynamicities"])
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(writable_path(OUTPUT / "figures/service_by_dod.png"), dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    render()
