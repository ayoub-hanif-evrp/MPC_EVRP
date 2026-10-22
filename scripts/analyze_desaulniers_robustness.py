"""Audit versioned robustness records; summarize only a complete paired grid."""

from collections import defaultdict
from hashlib import sha256
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evrp.audit import decode_result
from evrp.experiments import audit_result, load_config, prepare
from evrp.storage import ROOT, identifier, load_json, writable_path
from scripts.render_desaulniers_paper import clustered_ci, table
from scripts.run_desaulniers_pilot import VIOLATIONS
from scripts.run_desaulniers_robustness import (CONFIG, METHODS, OUTPUT, PILOT, options,
                                                source_hash)


def analyze(pilot=False, v3=False):
    if v3 and pilot:
        raise ValueError("The engineering pilot belongs to the preserved v2 preflight")
    if v3:
        import scripts.run_desaulniers_robustness_v3 as campaign
        directory, config_path = campaign.OUTPUT, campaign.CONFIG
        option_builder, fingerprint = campaign.options, campaign.source_hash
    else:
        directory, config_path = (PILOT if pilot else OUTPUT), CONFIG
        option_builder, fingerprint = options, source_hash
    frozen = load_json(directory / "protocol.json")
    manifest = load_json(directory / "manifest.json")
    config = load_config(config_path)
    if (frozen["source_sha256"] != fingerprint() or
            manifest["protocol_identifier"] != identifier(frozen)):
        raise ValueError("Robustness source or protocol fingerprint mismatch")
    scenarios = {(case["instance"], dod, seed) for case in frozen["selected"]
                 for dod in frozen["dynamicities"] for seed in frozen["scenario_seeds"]}
    expected = {(name, dod, seed, method) for name, dod, seed in scenarios for method in METHODS}
    rows = manifest["records"]
    keys = [(r["instance"], r["dynamicity"], r["seed"], r["method"]) for r in rows]
    excluded = {(r["instance"], r["dynamicity"], r["seed"])
                for r in manifest["ineligible"]}
    if (manifest["planned_runs"] != len(expected) or
            manifest["completed_runs"] != len(rows) or len(keys) != len(set(keys)) or
            not set(keys) <= expected or not excluded <= scenarios or
            set(keys) & {(name, dod, seed, method)
                         for name, dod, seed in excluded for method in METHODS} or
            len(rows) + len(excluded) * len(METHODS) > len(expected)):
        raise ValueError("Robustness manifest has duplicate, missing, or invalid case keys")
    grouped = defaultdict(dict)
    cache = {}
    for row in rows:
        key = row["instance"], row["dynamicity"], row["seed"]
        if key not in cache:
            cache[key] = prepare(row["instance"], option_builder(config, row["dynamicity"],
                                                              row["seed"], "MPC_COMPLETION"))[:3]
        instance, reference, scenario = cache[key]
        path = (ROOT / row["raw"]).resolve()
        if (not path.is_relative_to((directory / "raw").resolve()) or not path.is_file() or
                sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]):
            raise ValueError(f"Missing or corrupted robustness raw file: {row['raw']}")
        raw = load_json(path)
        meta, metrics = raw["metadata"], raw["metrics"]
        if (meta["algorithm"] != row["method"] or
                meta["scenario_identifier"] != row["scenario_id"] != scenario.identifier or
                meta["K_ref"] != row["k_ref"] != reference.fleet_size or
                meta["source_sha256"] != frozen["source_sha256"] or
                meta["dataset_sha256"] != frozen["dataset_sha256"] or
                not meta["isolated_worker"] or
                metrics["customers_served"] != row["customers_served"] or
                metrics["max_optimization_latency"] > 5.0 + 1e-6 or
                any(metrics[v] for v in VIOLATIONS)):
            raise ValueError(f"Robustness raw record identity, outcome, or budget mismatch: {path}")
        audit = audit_result(decode_result(raw), instance, scenario)
        if not all(audit.values()) or audit != meta["independent_audit"]:
            raise ValueError(f"Robustness independent replay failed: {path}")
        grouped[key][row["method"]] = dict(row, metrics=metrics)
    complete = len(rows) + len(excluded) * len(METHODS) == len(expected)
    if manifest["status"] != ("complete" if complete else "partial"):
        raise ValueError("Robustness manifest status is inconsistent")
    lines = [f"# {'Engineering pilot' if pilot else 'Multi-seed robustness v3' if v3 else 'Multi-seed robustness v2'}", "",
             f"Protocol: `{identifier(frozen)}`; audited raw runs: {len(rows)}/{len(expected)}; "
             f"predeclared ineligible scenarios: {len(excluded)}; "
             f"status: {'complete' if complete else 'partial'}.", "",
             "All existing raw files passed SHA-256, identity, five-second budget, and "
             "independent trace replay checks.", ""]
    if not complete:
        lines.append("No cross-method scientific summary is rendered from this incomplete grid.")
    elif pilot:
        lines.extend(["Engineering validation only: one development scenario is not a "
                      "generalizable optimizer comparison. Offline reference coverage "
                      "validation shared the machine during this pilot, so worker times "
                      "are engineering observations, not isolated runtime comparisons.", "",
                      table(["Method", "Served", "Complete", "Worker s"],
                            [(method, grouped[next(iter(grouped))][method]["customers_served"],
                              grouped[next(iter(grouped))][method]["complete_service"],
                              f"{grouped[next(iter(grouped))][method]['metrics']['worker_wall_seconds']:.1f}")
                             for method in METHODS])])
    else:
        if any(set(runs) != set(METHODS) for runs in grouped.values()):
            raise ValueError("Completed robustness grid is not fully paired")
        common = {key for key, runs in grouped.items()
                  if all(runs[m]["complete_service"] for m in METHODS)}
        overall = []
        for method in METHODS:
            data = [runs[method] for runs in grouped.values()]
            matched = [grouped[key][method] for key in common]
            overall.append((method, len(data),
                            f"{100 * sum(r['customers_served'] for r in data) / sum(r['size'] for r in data):.2f}",
                            f"{100 * mean(r['complete_service'] for r in data):.1f}",
                            f"{mean(r['vehicles_activated'] for r in data):.2f}",
                            f"{mean(r['total_distance'] for r in matched):.2f}" if matched else "NA",
                            len(common),
                            f"{mean(r['metrics']['mean_optimization_latency'] for r in data):.3f}",
                            f"{max(r['max_optimization_latency'] for r in data):.3f}"))
        lines.extend(["## Overall", "",
                      "Distance is conditional on the common set of complete-service scenarios.", "",
                      table(["Method", "N", "Served %", "Complete %", "EV mean",
                             "Distance matched", "Matched N", "Mean decision s", "Max decision s"], overall)])
        for label, extract in (("Seed", lambda r: r["seed"]),
                               ("Size", lambda r: r["size"]),
                               ("Family", lambda r: r["family"]),
                               ("Target DoD", lambda r: r["dynamicity"])):
            buckets = defaultdict(list)
            for runs in grouped.values():
                for method, row in runs.items():
                    buckets[extract(row), method].append(row)
            entries = [(group, method, len(buckets[group, method]),
                        f"{100 * sum(r['customers_served'] for r in buckets[group, method]) / sum(r['size'] for r in buckets[group, method]):.2f}",
                        f"{100 * mean(r['complete_service'] for r in buckets[group, method]):.1f}")
                       for group in sorted({group for group, _ in buckets}) for method in METHODS]
            lines.extend([f"## By {label.lower()}", "",
                          table([label, "Method", "N", "Served %", "Complete %"], entries)])
        pairings = [(m, "MPC_COMPLETION") for m in METHODS[1:]] + [("MPC_ALNS", "MPC_HGS")]
        entries = []
        for method, baseline in pairings:
            diffs = [100 * (runs[method]["customers_served"] - runs[baseline]["customers_served"])
                     / runs[method]["size"] for runs in grouped.values()]
            low, high = clustered_ci(grouped, method, baseline)
            entries.append((method, baseline, f"{mean(diffs):+.2f}",
                            f"[{low:+.2f}, {high:+.2f}]", sum(x > 0 for x in diffs),
                            sum(x == 0 for x in diffs), sum(x < 0 for x in diffs)))
        lines.extend(["## Paired contrasts", "",
                      "Descriptive 95% percentile intervals resample base instances (6 clusters), "
                      "retaining all DoD and seed repeats. They are not confirmatory "
                      "multiple-testing-adjusted significance claims.", "",
                      table(["Method", "Baseline", "Mean pp", "Cluster 95% CI pp",
                             "Wins", "Ties", "Losses"], entries)])
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for method in METHODS:
            points = []
            for seed in frozen["scenario_seeds"]:
                data = [row[method] for (_name, _dod, s), row in grouped.items() if s == seed]
                points.append(100 * sum(r["customers_served"] for r in data) /
                              sum(r["size"] for r in data))
            ax.plot(frozen["scenario_seeds"], points, marker="o",
                    label=method.removeprefix("MPC_"))
        ax.set(xlabel="Scenario seed", ylabel="Customers served (%)", ylim=(0, 100))
        ax.legend(ncol=3, frameon=False)
        fig.tight_layout()
        fig.savefig(writable_path(directory / "service_by_seed.png"), dpi=300)
        plt.close(fig)
    writable_path(directory / "SUMMARY.md").write_text("\n".join(lines).rstrip() + "\n",
                                                           encoding="utf-8")
    print(f"Audited {len(rows)}/{len(expected)} robustness runs; complete={complete}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--v3", action="store_true")
    args = parser.parse_args()
    analyze(args.pilot, args.v3)
