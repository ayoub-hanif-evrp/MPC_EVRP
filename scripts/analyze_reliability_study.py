"""Independent replay and parent-level uncertainty for the new comparison only."""

from collections import defaultdict
from hashlib import sha256

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from evrp.audit import decode_result
from evrp.experiments import audit_result
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.run_reliability_study import (OUTPUT, inputs, raw_path, variants_for, verify)


def table(path, title, headers, rows):
    lines = [f"# {title}", "", "| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(map(str, row)) + " |" for row in rows]
    writable_path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def interval(rows, numerator, denominator, config):
    parents = sorted({r["parent"] for r in rows})
    values = np.array([[sum(numerator(r) for r in rows if r["parent"] == p),
                        sum(denominator(r) for r in rows if r["parent"] == p)] for p in parents])
    if len(values) < 2:
        raise ValueError("Independent-parent inference requires at least two parents")
    rng = np.random.default_rng(config["bootstrap_seed"])
    draws = values[rng.integers(0, len(values), size=(config["bootstrap_draws"], len(values)))].sum(axis=1)
    ratios = draws[:, 0] / draws[:, 1]
    alpha = (1 - config["confidence_level"]) / 2
    return np.quantile(ratios, [alpha, 1-alpha]).tolist()


def summarize(rows, config):
    sizes = sum(r["size"] for r in rows)
    hundred = [r for r in rows if r["size"] == 100]
    summary = dict(method=rows[0]["method"], variant=rows[0]["variant"], scenarios=len(rows),
        parents=len({r["parent"] for r in rows}), original_service=sum(r["old"] for r in rows)/sizes,
        enhanced_service=sum(r["new"] for r in rows)/sizes,
        original_complete=sum(r["old_complete"] for r in rows)/len(rows),
        enhanced_complete=sum(r["new_complete"] for r in rows)/len(rows),
        service_gain=sum(r["delta"] for r in rows),
        complete_gain=sum(r["new_complete"]-r["old_complete"] for r in rows),
        seed_gains={str(s): sum(r["delta"] for r in rows if r["seed"] == s) for s in config["seeds"]},
        wins=sum(r["delta"]>0 for r in rows), ties=sum(r["delta"]==0 for r in rows), losses=sum(r["delta"]<0 for r in rows),
        parent_service_interval=interval(rows, lambda r: r["delta"], lambda r: r["size"], config),
        parent_complete_interval=interval(rows, lambda r: r["new_complete"]-r["old_complete"], lambda r: 1, config),
        hundred_service_gain=sum(r["delta"] for r in hundred),
        hundred_original_service=sum(r["old"] for r in hundred)/(100*len(hundred)),
        hundred_enhanced_service=sum(r["new"] for r in hundred)/(100*len(hundred)),
        hundred_original_complete=sum(r["old_complete"] for r in hundred)/len(hundred),
        hundred_enhanced_complete=sum(r["new_complete"] for r in hundred)/len(hundred),
        hundred_complete_interval=interval(hundred, lambda r: r["new_complete"]-r["old_complete"], lambda r: 1, config))
    return summary


def promotion(summaries, config):
    checks = {}
    for method, variant in (("MPC_ALNS", "flex_exchange"), ("MPC_COMPLETION", "completion_first_action")):
        rows = [s for s in summaries if (s["method"], s["variant"]) == (method, variant)]
        if not rows:
            continue
        s = rows[0]
        checks[variant] = dict(hundred_complete_interval=s["hundred_complete_interval"][0] > 0,
            service_interval=s["parent_service_interval"][0] >= 0 if variant == "flex_exchange" else s["parent_service_interval"][0] > 0,
            overall_complete=s["complete_gain"] >= 0,
            each_seed=all(v >= 0 for v in s["seed_gains"].values()), service_gain=s["service_gain"] >= 0,
            hundred_service=s["hundred_service_gain"] >= 0, all_parents=s["parents"] == len(config["development_parents"]))
    passing = [v for v in ("flex_exchange", "completion_first_action") if v in checks and all(checks[v].values())]
    return dict(promoted=passing[0] if passing else None, checks=checks,
                familywise_policy="Two primary contrasts; Bonferroni 97.5% two-sided parent intervals; fixed priority flex then Completion")


def analyze(stage):
    directory = OUTPUT / stage
    protocol, manifest = (load_json(directory/name) for name in ("protocol.json", "manifest.json"))
    config = protocol["config"]
    expected = {(i, method, variant) for i, info in enumerate(protocol["cases"]) for method in config["methods"]
                for variant in variants_for(config, info["case"], method, stage, protocol["selected"])}
    if (manifest["status"] != "complete" or manifest["protocol_identifier"] != identifier(protocol) or
            manifest["completed_runs"] != len(expected) or manifest["planned_runs"] != len(expected)):
        raise ValueError("Final analysis requires every preregistered run")
    indexed, times, timing_rows = {}, defaultdict(list), []
    for row in manifest["records"]:
        key = row["case_index"], row["method"], row["variant"]
        if key in indexed or key not in expected:
            raise ValueError("Duplicate or out-of-design raw")
        path = raw_path(stage, protocol, *key)
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Raw bytes changed")
        raw = load_json(path)
        verify(raw, protocol, *key)
        instance, scenario = inputs(protocol["cases"][key[0]])
        audit = audit_result(decode_result(raw), instance, scenario)
        if not all(audit.values()) or audit != row["independent_audit"] or raw["metrics"] != row["metrics"]:
            raise ValueError("Independent disk replay disagrees with manifest")
        indexed[key] = raw
        times[key[1:]].extend(d["optimization_latency_seconds"] for d in raw["decisions"]
                             if d.get("optimization_latency_seconds") is not None)
    if set(indexed) != expected:
        raise ValueError("Missing paired records")
    groups, pairs = defaultdict(list), []
    for (i, method, variant), raw in indexed.items():
        if variant == "original":
            continue
        baseline = indexed[i, method, "original"]
        old, new = baseline["metrics"], raw["metrics"]
        info = protocol["cases"][i]
        row = dict(case_index=i, method=method, variant=variant, parent=info["parent"], size=info["customers"],
                   dod=info["case"][1], seed=info["case"][2], old=old["customers_served"], new=new["customers_served"],
                   delta=new["customers_served"]-old["customers_served"], old_complete=int(old["complete_service"]),
                   new_complete=int(new["complete_service"]), old_distance=old["total_distance"], new_distance=new["total_distance"],
                   old_evs=old["vehicles_activated"], new_evs=new["vehicles_activated"],
                   same_served_set=set(baseline["unserved_customers"]) == set(raw["unserved_customers"]),
                   old_process_seconds=baseline["metrics"]["worker_wall_seconds"], new_process_seconds=new["worker_wall_seconds"])
        groups[method, variant].append(row)
        pairs.append(row)
    summaries = [summarize(rows, config) for rows in groups.values()]
    if stage == "development":
        selection = promotion(summaries, config)
    else:
        primary = "MPC_ALNS" if protocol["selected"] == "flex_exchange" else "MPC_COMPLETION"
        s = next(s for s in summaries if s["method"] == primary and s["variant"] == protocol["selected"])
        supported = (s["hundred_complete_interval"][0] > 0 and s["parent_service_interval"][0] >= 0 and
                     s["service_gain"] >= 0 and s["hundred_service_gain"] >= 0 and s["complete_gain"] >= 0)
        selection = dict(promoted=None, independently_supported=protocol["selected"] if supported else None,
                         role="Independent final confirmation; a failed confirmation retains the original system")
    selection["audited_runs"] = len(indexed)
    paper = directory / "paper"
    table(paper/"service.md", "Matched new-study service and complete service",
          ["Method", "Variant", "Parents", "Scenarios", "Original service %", "New service %", "Original complete %", "New complete %", "Win/tie/loss"],
          [[s["method"], s["variant"], s["parents"], s["scenarios"], f"{100*s['original_service']:.3f}",
            f"{100*s['enhanced_service']:.3f}", f"{100*s['original_complete']:.2f}", f"{100*s['enhanced_complete']:.2f}",
            f"{s['wins']}/{s['ties']}/{s['losses']}"] for s in summaries])
    table(paper/"uncertainty.md", "Parent-clustered intervals (97.5%; primary multiplicity policy)",
          ["Method", "Variant", "Service pp interval", "Complete pp interval", "100-customer complete pp interval"],
          [[s["method"], s["variant"], *[f"[{100*s[k][0]:+.3f}, {100*s[k][1]:+.3f}]" for k in
            ("parent_service_interval", "parent_complete_interval", "hundred_complete_interval")]] for s in summaries])
    table(paper/"hundred_customers.md", "100-customer outcomes", ["Method", "Variant", "Original service %", "New service %", "Original complete %", "New complete %"],
          [[s["method"], s["variant"], *[f"{100*s[k]:.3f}" for k in ("hundred_original_service", "hundred_enhanced_service",
            "hundred_original_complete", "hundred_enhanced_complete")]] for s in summaries])
    table(paper/"pairs.md", "All paired gains and regressions", list(pairs[0]), [list(row.values()) for row in pairs])
    for (method, variant), values in sorted(times.items()):
        runs = [r for key, r in indexed.items() if key[1:] == (method, variant)]
        timing_rows.append([method, variant, len(values), f"{np.mean(values):.6f}", f"{np.percentile(values,95):.6f}",
            f"{max(values):.6f}", sum(r["metrics"]["total_deadline_events"] for r in runs),
            f"{sum(r['metrics']['worker_wall_seconds'] for r in runs)/3600:.4f}",
            f"{sum(r['metrics']['total_planning_time'] for r in runs)/3600:.4f}",
            sum(d.get("proposal_memo", {}).get("hits", 0) for r in runs for d in r["decisions"]),
            sum(d.get("proposal_memo", {}).get("misses", 0) for r in runs for d in r["decisions"]),
            sum((d.get("targeted_control") or {}).get("candidates", 0) for r in runs for d in r["decisions"]
                if isinstance((d.get("targeted_control") or {}).get("candidates", 0), int)),
            sum((d.get("targeted_control") or {}).get("selected", 0) for r in runs for d in r["decisions"])])
    table(paper/"runtime.md", "Shared-machine latency; deadline events are not budget violations",
          ["Method", "Variant", "Decisions", "Mean s", "p95 s", "Max s", "Optimizer deadline events", "Worker hours",
           "Planning hours", "Memo hits", "Memo misses", "Exchange candidates", "Strict selected improvements"], timing_rows)
    conditional = []
    for key, rows in groups.items():
        paired = [r for r in rows if r["same_served_set"]]
        conditional.append([*key, len(paired), sum(r["new_distance"]-r["old_distance"] for r in paired),
                            sum(r["new_evs"]-r["old_evs"] for r in paired)])
    table(paper/"conditional_efficiency.md", "Efficiency only on identical served sets",
          ["Method", "Variant", "Matched sets", "Distance delta sum", "Activated-EV delta sum"], conditional)
    for field, title in (("dod", "DoD"), ("size", "Customer size"), ("parent", "Independent parent")):
        strata = []
        for key, rows in groups.items():
            for value in sorted({r[field] for r in rows}):
                subset = [r for r in rows if r[field] == value]
                strata.append([*key, value, len(subset), sum(r["delta"] for r in subset),
                               sum(r["new_complete"]-r["old_complete"] for r in subset)])
        table(paper/f"by_{field}.md", f"Paired outcomes by {title}", ["Method", "Variant", title, "Scenarios", "Service gain", "Complete gain"], strata)
    fig, ax = plt.subplots(figsize=(12, max(5, .36*len(summaries))))
    for index, s in enumerate(summaries):
        point = 100*(s["enhanced_service"]-s["original_service"])
        lo, hi = (100*x for x in s["parent_service_interval"])
        ax.plot([lo, hi], [index, index], color="#267a66")
        ax.plot(point, index, "o", color="#267a66")
    ax.set(yticks=range(len(summaries)), yticklabels=[f"{s['method']} / {s['variant']}" for s in summaries],
           xlabel="Paired service change (pp), parent 97.5% interval")
    ax.axvline(0, color="#b44345", linestyle="--")
    fig.tight_layout()
    fig.savefig(writable_path(paper/"service.png"), dpi=300)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 6))
    for key, values in sorted(times.items()):
        values = sorted(values)
        ax.step(values, np.arange(1, len(values)+1)/len(values), where="post", label=" / ".join(key))
    ax.axvline(5, color="#b44345", linestyle="--")
    ax.set(xlabel="End-to-end decision seconds, shared machine", ylabel="ECDF")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(writable_path(paper/"runtime.png"), dpi=300)
    plt.close(fig)
    save_json(directory/"analysis.json", dict(protocol_identifier=identifier(protocol), summaries=summaries,
        pairs=pairs, selection=selection, independently_audited=len(indexed),
        manifest_sha256=sha256((directory/"manifest.json").read_bytes()).hexdigest()))
    print(f"Independently replayed {len(indexed)} {stage} runs; promotion={selection['promoted']}", flush=True)
    return selection


def report(status):
    lines = ["# Reliability study V2", "", status, "", "## Evidence and limits", "",
        "Historical final and robustness studies, and the completed targeted study, remain immutable.",
        "New development: 12 independent parent cases; all at 100 customers plus one smaller size per parent.",
        "The size panel is partial, not a full parent-size factorial. DoD and seed are fully crossed per file.",
        "One new flexibility-guided exchange mechanism, a cache ablation, and a prospective Completion-only",
        "V1 control comparison were frozen before new outcomes. No arbitrary waiting or future-demand inputs.",
        "Two primary promotion contrasts use 97.5% parent bootstrap intervals; other engine effects are exploratory.",
        "Development promotion is not final superiority. Shared-machine timing is not isolated certification.", "",
        "See diagnosis/RESULTS.md and diagnosis/profile.json for measured bounds and profiling, not causal claims.", ""]
    for stage in ("development", "holdout"):
        path = OUTPUT/stage/"manifest.json"
        if not path.exists():
            continue
        m = load_json(path)
        lines += [f"## {stage.title()}", "", f"Runs: {m['completed_runs']}/{m['planned_runs']}; status: {m['status']}.", ""]
        analysis = OUTPUT/stage/"analysis.json"
        if analysis.exists():
            d = load_json(analysis)
            if d["manifest_sha256"] != sha256(path.read_bytes()).hexdigest():
                raise ValueError("Analysis is stale")
            for s in d["summaries"]:
                lines += [f"- {s['method']} / {s['variant']}: service {100*s['original_service']:.3f}% to "
                    f"{100*s['enhanced_service']:.3f}%; complete {100*s['original_complete']:.2f}% to "
                    f"{100*s['enhanced_complete']:.2f}%; W/T/L {s['wins']}/{s['ties']}/{s['losses']}."]
            lines += ["", f"Selection: {d['selection']['promoted']}. See paper/uncertainty.md for all intervals.", ""]
            if stage == "holdout":
                lines += [f"Independently supported enhancement: {d['selection']['independently_supported']}.", ""]
    if not (OUTPUT/"holdout/analysis.json").exists():
        lines += ["No completed new independent final result is claimed. Original ALNS remains the paper's primary system.", ""]
    lines += ["## Reproduce", "", "```powershell", "python -m pytest -q", "python -u -m scripts.run_reliability_study", "```", "",
              "Use the recorded source commit. Valid raw files are byte-checked and reused; source drift fails closed.",
              "Each invocation pauses at a scenario boundary after 12 hours. No earlier campaigns are rerun."]
    writable_path(OUTPUT/"FINAL_REPORT.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    artifacts = []
    for path in sorted(OUTPUT.rglob("*")):
        if path.suffix not in {".png", ".md"}:
            continue
        if path.suffix == ".png":
            with Image.open(path) as img:
                if min(img.info.get("dpi", (0, 0))) < 299.9 or all(a == b for a, b in img.convert("RGB").getextrema()):
                    raise ValueError("Invalid publication PNG")
        artifacts.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha256(path.read_bytes()).hexdigest()))
    save_json(OUTPUT/"paper_inventory.json", dict(artifacts=artifacts))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("development", "holdout"), default="development")
    args = parser.parse_args()
    analyze(args.stage)
    report("Analysis rebuilt from complete independently replayed evidence.")
