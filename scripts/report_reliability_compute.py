"""Read-only runtime forensics for the user-stopped, incomplete campaign."""

from collections import defaultdict
from hashlib import sha256
from statistics import mean, median

from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.run_reliability_study import OUTPUT, variants_for, source_hash


def aggregate(rows):
    return dict(runs=len(rows), worker_hours=sum(r["process_seconds"] for r in rows)/3600,
        planning_hours=sum(r["metrics"]["total_planning_time"] for r in rows)/3600,
        optimization_calls=sum(r["metrics"]["optimization_triggers"] for r in rows),
        mean_worker_seconds=mean(r["process_seconds"] for r in rows),
        median_worker_seconds=median(r["process_seconds"] for r in rows),
        maximum_worker_seconds=max(r["process_seconds"] for r in rows),
        maximum_decision_seconds=max(r["metrics"]["max_optimization_latency"] for r in rows))


def estimate_remaining(protocol, records):
    by_key = defaultdict(list)
    by_method = defaultdict(list)
    done = set()
    for row in records:
        i, method, variant = row["case_index"], row["method"], row["variant"]
        if (i, method, variant) in done:
            raise ValueError("Duplicate checkpoint row")
        done.add((i, method, variant))
        size = protocol["cases"][i]["customers"]
        by_key[method, variant, size].append(row["process_seconds"])
        by_method[method].append(row["process_seconds"])
    jobs = []
    for i, info in enumerate(protocol["cases"]):
        for method in protocol["config"]["methods"]:
            for variant in variants_for(protocol["config"], info["case"], method, "development", None):
                if (i, method, variant) in done:
                    continue
                exact = by_key.get((method, variant, info["customers"]))
                sample = exact or by_method.get(method)
                if not sample:
                    raise ValueError("No defensible observed cost for a required method")
                jobs.append(dict(case_index=i, method=method, variant=variant, customers=info["customers"],
                                 observed_group_runs=len(sample), exact_size_variant_group=bool(exact),
                                 mean_seconds=mean(sample), median_seconds=median(sample)))
    return dict(remaining_jobs=len(jobs), mean_based_hours=sum(j["mean_seconds"] for j in jobs)/3600,
                median_based_hours=sum(j["median_seconds"] for j in jobs)/3600,
                caveat="Planning estimates, not confidence bounds. Only C1/C2 parents have run; "
                       "untested R/RC families and changing shared-machine load can change cost substantially.", jobs=jobs)


def report():
    manifest = load_json(OUTPUT/"development/manifest.json")
    protocol = load_json(OUTPUT/"development/protocol.json")
    records = manifest["records"]
    if manifest["protocol_identifier"] != identifier(protocol) or len(records) != manifest["completed_runs"]:
        raise ValueError("Protocol/manifest mismatch")
    hashes = {}
    for row in records:
        path = ROOT/row["raw"]
        digest = sha256(path.read_bytes()).hexdigest()
        if digest != row["raw_sha256"] or not all(row["independent_audit"].values()):
            raise ValueError("Saved evidence hash or worker audit mismatch")
        hashes[row["raw"]] = digest
    totals = aggregate(records)
    groups, sizes = defaultdict(list), defaultdict(list)
    for row in records:
        groups[row["method"]].append(row)
        sizes[protocol["cases"][row["case_index"]]["customers"]].append(row)
    estimate = estimate_remaining(protocol, records)
    ratio = totals["planning_hours"] / totals["worker_hours"]
    summary = dict(totals=totals, planning_fraction=ratio, by_method={k:aggregate(v) for k,v in groups.items()},
                   by_size={k:aggregate(v) for k,v in sizes.items()}, estimate=estimate,
                   raw_sha256=hashes, manifest_sha256=sha256((OUTPUT/"development/manifest.json").read_bytes()).hexdigest(),
                   frozen_source_unchanged=source_hash() == protocol["source_sha256"],
                   scientific_status="Incomplete development, stopped by user for computation cost; no promotion or final inference")
    save_json(OUTPUT/"compute_review/analysis.json", summary)
    lines = ["# Compute-cost review: user-stopped campaign", "",
        f"Saved runs: {len(records)}/{manifest['planned_runs']}. Remaining: {estimate['remaining_jobs']}.",
        "The user stopped this study for computational cost, not based on interim algorithm outcomes.",
        "No experiment was restarted or optimization engine executed for this report.",
        "All saved raw byte hashes and recorded worker audit flags were checked; this is not another full physical replay.",
        "Scientific source/protocol, raw files, releases, reference fleets and historical final results are unchanged.", "",
        "## Where the time went", "",
        f"Cumulative process time: {totals['worker_hours']:.3f} h; planning: {totals['planning_hours']:.3f} h "
        f"({100*ratio:.2f}%). Planning triggered {totals['optimization_calls']:,} times.",
        f"Longest whole worker: {totals['maximum_worker_seconds']:.1f} s. Maximum decision: {totals['maximum_decision_seconds']:.6f} s.",
        "Five seconds is a limit for one MPC decision, not a whole scenario. A scenario can replan dozens or hundreds of times.",
        "The remaining process overhead includes audit and serialization. Even eliminating it completely cannot remove most runtime.", "",
        "| Engine | Runs | Worker hours | Planning hours | Calls | Mean worker s | Median worker s |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, rows in groups.items():
        d = aggregate(rows)
        lines.append(f"| {name} | {d['runs']} | {d['worker_hours']:.3f} | {d['planning_hours']:.3f} | "
                     f"{d['optimization_calls']} | {d['mean_worker_seconds']:.2f} | {d['median_worker_seconds']:.2f} |")
    lines += ["", "## Why 12 hours did not finish it", "",
        "The frozen design requires 960 original/flex comparisons, 96 Completion-specific runs and 60 cache ablations.",
        "The configured limit was soft: the runner finishes every method for its current scenario before pausing.",
        "Consequently an expensive scenario can carry execution beyond 12 hours. It was not a hard wall-clock cutoff.",
        f"The {estimate['remaining_jobs']}-job remainder projects to {estimate['mean_based_hours']:.1f} h using observed method/variant/size means, "
        f"or {estimate['median_based_hours']:.1f} h using medians. These are cost estimates, not confidence intervals.",
        "Only C1/C2 parents are represented so far. Never treat these estimates as guarantees for R/RC families.", "",
        "## What to change next, without silently changing the frozen study", "",
        "1. Keep this campaign stopped and archive its partial results. Do not label 361 runs a completed preregistered study.",
        "2. Retain the already completed primary study for the paper; the new enhancements remain optional and unpromoted.",
        "3. Before any new campaign, preregister a strict total compute budget and gate expensive engine comparisons behind a small fixed screen.",
        "   Prioritize the predeclared ALNS/Completion research question before a large five-engine grid; use untouched parents for any new claim.",
        "   Do not choose or drop scenarios based on this partial study's observed service outcomes.",
        "4. Make admission budget-aware: estimate the next complete paired block and refuse to start it if it exceeds remaining allowance.",
        "   A genuinely hard cutoff requires a whole-worker watchdog that preserves interrupted evidence; never turn interruption into a valid result.",
        "5. Use the existing profiles to target reconstruction/transition work, not plots. The one small-case profile is not representative speedup evidence.",
        "   Exact replay memoization has a separate ablation already. It does not eliminate unique route construction and is not a demonstrated global fix.",
        "6. Concurrent scenarios can reduce elapsed throughput time only as a separately labeled methodology, not midstream isolated-timing evidence.",
        "   Fewer search iterations, smaller horizons, fewer events, or a lower decision budget would change the comparison and require a new version.", "",
        "No new experiment, holdout, algorithm redesign, automatic restart or GitHub push has been started."]
    writable_path(OUTPUT/"compute_review/RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(f"Verified {len(records)} raw hashes. Planning {100*ratio:.2f}% of {totals['worker_hours']:.3f} worker hours.",flush=True)
    print(f"Unexecuted remainder mean/median cost estimates: {estimate['mean_based_hours']:.1f}/{estimate['median_based_hours']:.1f} h; no optimization run.",flush=True)


if __name__ == "__main__":
    report()
