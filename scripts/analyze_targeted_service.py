"""Independent replay, parent-clustered paired inference and PNG-only reporting."""

import argparse
from collections import defaultdict
from hashlib import sha256
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from evrp.audit import decode_result
from evrp.experiments import audit_result, prepare
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.analyze_alns_recovery_screen import _interval
from scripts.run_desaulniers_pilot import family_of
from scripts.run_targeted_service import OUTPUT, options, verify, restore_inputs


def table(path, title, headers, rows):
    lines = [f"# {title}", "", "| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(x) for x in row) + " |" for row in rows)
    writable_path(path).write_text("\n".join(lines)+"\n", encoding="utf-8")


def analyze(stage):
    output = OUTPUT / stage
    protocol, manifest = (load_json(output / name) for name in ("protocol.json", "manifest.json"))
    science = protocol["scientific"]
    expected = len(science["cases"]) * len(science["methods"]) * len(science["variants"])
    if (manifest["status"] != "complete" or manifest["protocol_identifier"] != identifier(protocol) or
            manifest["completed_runs"] != expected or manifest["planned_runs"] != expected or
            len(manifest["records"]) != expected):
        raise ValueError("Analysis requires the complete frozen design")
    restore_inputs(protocol)
    indexed, latencies = {}, defaultdict(list)
    for row in manifest["records"]:
        index, method, variant = key = row["case_index"], row["method"], row["variant"]
        if key in indexed or index not in range(len(science["cases"])) or method not in science["methods"] or variant not in science["variants"]:
            raise ValueError("Duplicate or out-of-design run")
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Raw byte mismatch")
        raw = load_json(path)
        verify(raw, protocol, *key)
        info = science["cases"][index]
        instance, reference, scenario, _ = prepare(info["case"][0], options(science["config"], info["case"], method, variant))
        if instance.sha256 != info["instance_sha256"] or reference.identifier != info["reference_id"]:
            raise ValueError("Paired inputs changed")
        independent = audit_result(decode_result(raw), instance, scenario)
        if not all(independent.values()) or independent != row["independent_audit"] or row["metrics"] != raw["metrics"]:
            raise ValueError("Independent replay/manifest disagreement")
        indexed[key] = raw
        latencies[method, variant].extend(d["optimization_latency_seconds"] for d in raw["decisions"]
                                         if d.get("optimization_latency_seconds") is not None)
    pairs, summaries = [], []
    for method in science["methods"]:
        for variant in science["variants"]:
            if variant == "original":
                continue
            group = []
            for index, info in enumerate(science["cases"]):
                old, new = (indexed[index, method, v]["metrics"] for v in ("original", variant))
                row = dict(method=method, variant=variant, instance=info["case"][0], dod=info["case"][1],
                           seed=info["case"][2], parent=info["parent"], family=family_of(info["case"][0]),
                           size=info["customers"], old=old["customers_served"], new=new["customers_served"],
                           delta=new["customers_served"]-old["customers_served"],
                           old_complete=int(old["complete_service"]), new_complete=int(new["complete_service"]),
                           old_distance=old["total_distance"], new_distance=new["total_distance"],
                           old_evs=old["vehicles_activated"], new_evs=new["vehicles_activated"],
                           old_seconds=old["worker_wall_seconds"], new_seconds=new["worker_wall_seconds"])
                group.append(row)
            clusters = defaultdict(lambda: [0, 0, 0, 0])
            for row in group:
                cluster = clusters[row["parent"]]
                for j, value in enumerate((row["delta"], row["size"], row["new_complete"]-row["old_complete"], 1)):
                    cluster[j] += value
            values = list(clusters.values())
            service_ci = _interval(values, [v[0] for v in values], [v[1] for v in values])
            full_ci = _interval(values, [v[2] for v in values], [v[3] for v in values])
            opportunities = sum(row["size"] for row in group)
            summary = dict(method=method, variant=variant, scenarios=len(group), parents=len(clusters),
                           opportunities=opportunities, original_service=sum(r["old"] for r in group)/opportunities,
                           enhanced_service=sum(r["new"] for r in group)/opportunities,
                           service_gain=sum(r["delta"] for r in group),
                           service_change=sum(r["delta"] for r in group)/opportunities,
                           complete_gain=sum(r["new_complete"]-r["old_complete"] for r in group),
                           original_complete=mean(r["old_complete"] for r in group),
                           enhanced_complete=mean(r["new_complete"] for r in group),
                           parent_service_ci=service_ci, parent_complete_ci=full_ci,
                           hundred_customer_gain=sum(r["delta"] for r in group if r["size"]==100),
                           seed_gains={str(seed): sum(r["delta"] for r in group if r["seed"]==seed)
                                       for seed in science["config"]["seeds"]},
                           wins=sum(r["delta"]>0 for r in group), ties=sum(r["delta"]==0 for r in group),
                           losses=sum(r["delta"]<0 for r in group))
            summaries.append(summary)
            pairs.extend(group)
    checks, eligible = {}, []
    if stage == "development":
        rule = science["config"]["selection"]
        for summary in summaries:
            if summary["method"] != rule["primary_method"]:
                continue
            variant = summary["variant"]
            completion = next(s for s in summaries if s["variant"]==variant and s["method"]=="MPC_COMPLETION")
            check = dict(parent_service_ci=summary["parent_service_ci"][0] > rule["parent_service_95_ci_lower_above"],
                         complete_service=summary["complete_gain"]>=rule["complete_service_change_at_least"],
                         hundred_customer_service=summary["hundred_customer_gain"]>=rule["hundred_customer_gain_at_least"],
                         both_seeds=all(v>=rule["gain_in_each_seed_at_least"] for v in summary["seed_gains"].values()),
                         completion_control=completion["service_gain"]>=rule["completion_baseline_total_gain_at_least"],
                         independent_audits=True, five_second_budget=all(max(t)<=5+1e-6 for t in latencies.values()))
            checks[variant] = check
            if all(check.values()):
                eligible.append(summary)
    selected = sorted(eligible, key=lambda s: (-s["service_gain"], -s["complete_gain"], s["variant"]))
    selection = dict(selected_variant=selected[0]["variant"] if selected else None,
                     development_protocol_identifier=identifier(protocol),
                     development_manifest_sha256=sha256((output/"manifest.json").read_bytes()).hexdigest(), checks=checks)
    timing = []
    for (method, variant), times in latencies.items():
        raws = [raw for (i, m, v), raw in indexed.items() if m==method and v==variant]
        timing.append(dict(method=method, variant=variant, decisions=len(times), mean=mean(times),
                           p95=float(np.quantile(times,.95)), maximum=max(times),
                           deadline_events=sum(raw["metrics"]["total_deadline_events"] for raw in raws),
                           probe_deadlines=sum(bool(d.get("targeted_control", {}).get("deadline_reached"))
                                for raw in raws for d in raw["decisions"] if d.get("targeted_control")),
                           constructor_probe_deadlines=sum(bool(d.get("targeted_constructor", {}).get("deadline_reached"))
                                for raw in raws for d in raw["decisions"] if d.get("targeted_constructor"))))
    save_json(output / "analysis.json", dict(protocol_identifier=identifier(protocol), independent_audited_runs=expected,
              summaries=summaries, pairs=pairs, timing=timing, selection=selection))
    paper = output/"paper"
    table(paper/"service.md", "Matched customer and complete service",
          ["Engine", "Candidate", "Original service %", "Candidate service %", "Original complete %", "Candidate complete %", "W/T/L", "100-customer gain"],
          [[s["method"], s["variant"], f"{100*s['original_service']:.3f}", f"{100*s['enhanced_service']:.3f}",
            f"{100*s['original_complete']:.2f}", f"{100*s['enhanced_complete']:.2f}",
            f"{s['wins']}/{s['ties']}/{s['losses']}", s["hundred_customer_gain"]] for s in summaries])
    table(paper/"uncertainty.md", "Underlying-parent bootstrap uncertainty (exploratory)",
          ["Engine", "Candidate", "Parents", "Service change pp", "95% CI pp", "Complete-service 95% CI pp"],
          [[s["method"],s["variant"],s["parents"],f"{100*s['service_change']:+.3f}",
            str([round(100*x,3) for x in s["parent_service_ci"]]),
            str([round(100*x,3) for x in s["parent_complete_ci"]])] for s in summaries])
    table(paper/"paired_scenarios.md", "Every paired outcome, including regressions",
          ["Engine","Candidate","Instance","DoD","Seed","Original","Candidate","Change"],
          [[r[k] for k in ("method","variant","instance","dod","seed","old","new","delta")] for r in pairs])
    stratified = []
    for summary in summaries:
        group = [r for r in pairs if (r["method"],r["variant"])==(summary["method"],summary["variant"])]
        for field in ("family","size","dod","seed"):
            for value in sorted({r[field] for r in group}):
                rows = [r for r in group if r[field]==value]
                denominator = sum(r["size"] for r in rows)
                stratified.append([summary["method"],summary["variant"],field,value,len(rows),
                                   f"{100*sum(r['old'] for r in rows)/denominator:.3f}",
                                   f"{100*sum(r['new'] for r in rows)/denominator:.3f}",
                                   sum(r["delta"] for r in rows)])
    table(paper/"strata.md", "Size, family, dynamicity and seed (descriptive)",
          ["Engine","Candidate","Stratum","Value","Scenarios","Original %","Candidate %","Customer gain"], stratified)
    efficiency = []
    for summary in summaries:
        rows = [r for r in pairs if (r["method"],r["variant"])==(summary["method"],summary["variant"])
                and r["old_complete"] and r["new_complete"]]
        efficiency.append([summary["method"],summary["variant"],len(rows),
                           *[round(mean(r[k] for r in rows),3) if rows else "NA" for k in
                             ("old_distance","new_distance","old_evs","new_evs")]])
    table(paper/"conditional_efficiency.md", "Distance and EVs only on common full-service scenarios",
          ["Engine","Candidate","Common complete","Original distance","Candidate distance","Original EVs","Candidate EVs"],efficiency)
    table(paper/"runtime.md", "Shared-machine end-to-end decision timing",
          ["Engine","Variant","Decisions","Mean s","p95 s","Max s","Deadline events","Control probe deadlines","Constructor probe deadlines"],
          [[r["method"],r["variant"],r["decisions"],*[f"{r[k]:.6f}" for k in ("mean","p95","maximum")],
            r["deadline_events"],r["probe_deadlines"],r["constructor_probe_deadlines"]] for r in timing])
    table(paper/"promotion.md", "Prespecified development promotion checks",
          ["Candidate","Check","Passed"], [[variant,k,v] for variant,c in checks.items() for k,v in c.items()])
    fig, axes = plt.subplots(1, len(science["methods"]), figsize=(6*len(science["methods"]),4), squeeze=False)
    for ax, method in zip(axes[0], science["methods"]):
        rows = [s for s in summaries if s["method"]==method]
        y = np.array([100*s["service_change"] for s in rows])
        # Percentile cluster intervals can be asymmetric around the observed mean.
        ax.scatter(range(len(rows)), y, color="#267a66", zorder=3)
        for index,s in enumerate(rows):
            ax.vlines(index,100*s["parent_service_ci"][0],100*s["parent_service_ci"][1],color="#267a66")
        ax.axhline(0,color="#b44345",linestyle="--")
        ax.set(xticks=range(len(rows)),xticklabels=[s["variant"] for s in rows],ylabel="Service change (pp), parent 95% CI",title=method)
        ax.tick_params(axis="x",labelrotation=30)
    fig.tight_layout()
    fig.savefig(writable_path(paper/"paired_service.png"),dpi=300)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9,5))
    for (method,variant),times in latencies.items():
        times=np.sort(times)
        ax.step(times,np.arange(1,len(times)+1)/len(times),where="post",label=f"{method} / {variant}")
    ax.axvline(5,color="#b44345",linestyle="--",label="5 s limit")
    ax.set(xlabel="End-to-end planning latency (s), shared machine",ylabel="ECDF",ylim=(0,1.01))
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(writable_path(paper/"runtime_ecdf.png"),dpi=300)
    plt.close(fig)
    for path in paper.glob("*.png"):
        with Image.open(path) as img:
            if min(img.info.get("dpi",(0,0))) < 299.9:
                raise ValueError("Paper PNG does not satisfy 300 dpi")
    text = [f"# {stage.title()} targeted-service results", "",f"Complete and independently audited: {expected}/{expected} runs.",
            f"Matched scenarios: {len(science['cases'])}; underlying parents: {len({c['parent'] for c in science['cases']})}.",
            f"Timing: {protocol['timing_conditions']}.", "",
            "The fractional development design alternates DoD by size index and seed. All methods see identical",
            "scenarios, but seed/DoD effects within one benchmark file are confounded. Stratified estimates are descriptive.",
            "Parent bootstrap resamples six whole parent cases, keeping sizes, seeds and DoD together.",
            "The three candidate contrasts are exploratory and unadjusted; promotion is a gate for a new",
            "independent evaluation, not a claim of general superiority. Never reuse final holdout for tuning.","",
            f"Selected candidate: {selection['selected_variant'] if stage=='development' else science['selection']['selected_variant']}.",
            "No new holdout is opened when the development gate fails. Original feature defaults remain disabled.","",
            "See paper/service.md, uncertainty.md, paired_scenarios.md, strata.md, conditional_efficiency.md, runtime.md and promotion.md.", ""]
    writable_path(output/"RESULTS.md").write_text("\n".join(text),encoding="utf-8")
    print(f"{stage}: independently audited {expected}; selected={selection['selected_variant']}",flush=True)
    return selection


def finalize(selection):
    development = load_json(OUTPUT/"development/analysis.json")
    lines = ["# Final targeted MPC service-improvement report", "",
             f"Frozen development source: `{load_json(OUTPUT/'development/protocol.json')['source_commit']}`.",
             f"Independent development audits: {development['independent_audited_runs']}.","",
             "## What changed", "",
             "Three separately switched common components were compared with the original control: A,",
             "urgency/true-regret bounded service recovery; B, incremental time bounds and MP resource-label",
             "reconstruction with exact useful charge targets; C, independently replayed first-control alternatives.",
             "Original Completion/MCTS/ALNS/HGS/ACS, event triggers, canonical objective, physics, K_ref,",
             "released-information boundary and five-second end-to-end budget are preserved.", "",
             "## What the evidence supports", ""]
    for s in development["summaries"]:
        lines += [f"- {s['method']} / {s['variant']}: service {100*s['original_service']:.3f}% to "
                  f"{100*s['enhanced_service']:.3f}%; complete {100*s['original_complete']:.2f}% to "
                  f"{100*s['enhanced_complete']:.2f}%; wins/ties/losses {s['wins']}/{s['ties']}/{s['losses']}; "
                  f"100-customer gain {s['hundred_customer_gain']:+d}; parent 95% service interval "
                  f"[{100*s['parent_service_ci'][0]:+.3f}, {100*s['parent_service_ci'][1]:+.3f}] pp."]
    if selection["selected_variant"] is None:
        lines += ["", "**No candidate passed the prespecified promotion checks.** All three stay disabled by default.",
                  "The original frozen primary study remains the strongest supported published system.",
                  "There is no enhanced final holdout or superiority claim. This is a completed negative development study."]
    else:
        holdout = load_json(OUTPUT/"holdout/analysis.json")
        lines += ["",f"Development selected **{selection['selected_variant']}** before exposing the new reserved parents.",
                  f"New independent holdout audits: {holdout['independent_audited_runs']}.",
                  "The holdout is reported in full in holdout/paper/service.md and uncertainty.md.",
                  "Only a positive holdout ALNS parent interval with no complete-service loss supports a superiority claim."]
    lines += ["", "## Diagnosis and reference coverage", "",
              "The retrospective diagnosis evaluated 20 observable decision roots and 108 first-control alternatives.",
              "Twenty-six alternatives were physically validated; none improved the canonical plan. Eighty-two",
              "bounded reconstruction failures are not physical infeasibility proofs. This does not establish",
              "which action would have improved eventual service, and unobserved future requests are never used.",
              "The two formerly unresolved offline cases are separately investigated under offline_resources/.",
              "Any new witness is a separate physical upper bound, never a replacement historical fleet.","",
              "## Publication limits", "",
              "Historical primary results and original 270/450-run studies are immutable. This extension uses six",
              "development parents, not 18 independent size variants. Bootstrap uncertainty is exploratory;",
              "shared-machine timing is not isolated real-time certification. A valid negative result is useful",
              "but does not establish a stronger routing method or guarantee publication acceptance.","",
              "## Reproduction", "",
              "```powershell", "python -m scripts.run_targeted_service --restore development",
              "python -u -m scripts.run_targeted_service", "python -m scripts.analyze_targeted_service --stage development",
              "python -m scripts.investigate_targeted_references", "python -m pytest -q", "```", "",
              "The runner validates source/data/config hashes and reuses exact saved raw bytes. A mismatched source",
              "fails closed; check out the recorded execution commit before resuming or reproducing optimization.",
              "Analysis replays every raw route independently. Paper tables are Markdown and figures PNG at 300 dpi.", ""]
    writable_path(OUTPUT/"FINAL_REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    artifacts = []
    for path in sorted(OUTPUT.rglob("*.md"))+sorted(OUTPUT.rglob("*.png")):
        artifacts.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha256(path.read_bytes()).hexdigest()))
    save_json(OUTPUT/"paper_inventory.json",dict(artifacts=artifacts))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",choices=("development","holdout"),default="development")
    args=parser.parse_args()
    selection=analyze(args.stage)
    if args.stage=="development" and (selection["selected_variant"] is None or (OUTPUT/"holdout/analysis.json").exists()):
        finalize(selection)
