"""Consolidated independently replayed engineering report; no optimizer runs."""

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from statistics import mean
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from evrp.audit import decode_result
from evrp.experiments import audit_result
from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.performance_engineering_worker import OUTPUT, load_case
from scripts.run_performance_engineering import verify_raw


def markdown(headers, rows):
    return ["| "+" | ".join(headers)+" |","| "+" | ".join("---" for _ in headers)+" |"]+[
        "| "+" | ".join(str(v) for v in row)+" |" for row in rows]


def build():
    protocol, manifest = (load_json(OUTPUT/name) for name in ("protocol.json","manifest.json"))
    specs = {j["id"]:j for b in protocol["blocks"] for j in b["jobs"]}
    if manifest["protocol_identifier"] != identifier(protocol):
        raise ValueError("Report protocol mismatch")
    records, raw_by_id = {}, {}
    prepared = {}
    physical_audits = 0
    for row in manifest["records"]:
        if row["id"] in records or row["id"] not in specs:
            raise ValueError("Duplicate or unplanned result")
        path=ROOT/row["raw"]
        if sha256(path.read_bytes()).hexdigest()!=row["sha256"]:
            raise ValueError("Finished evidence bytes changed")
        raw=load_json(path)
        verify_raw(raw,protocol,specs[row["id"]])
        if raw["kind"] in {"pilot","profile"}:
            index=raw["case_index"]
            if index not in prepared:
                prepared[index]=load_case(protocol,index)
            instance,scenario=prepared[index]
            audit=audit_result(decode_result(raw["result"]),instance,scenario)
            if not all(audit.values()) or audit!=raw["result"]["metadata"]["independent_audit"]:
                raise ValueError("Independent disk physical replay disagrees with worker")
            physical_audits+=1
        records[row["id"]],raw_by_id[row["id"]]=row,raw
    micros={}
    for i in range(len(protocol["cases"])):
        for variant in protocol["config"]["micro_variants"]:
            key=f"micro_{i}_MPC_COMPLETION_{variant}"
            if key in raw_by_id:
                micros[i,variant]=raw_by_id[key]
        if all((i,v) in micros for v in protocol["config"]["micro_variants"]):
            checks=[[p["checksum"] for p in micros[i,v]["fixed_work"]["phases"]] for v in protocol["config"]["micro_variants"]]
            if any(v!=checks[0] for v in checks[1:]):
                raise ValueError("Fixed-work physical/objective mismatch")
    pilot={(r["case_index"],r["method"],r["variant"]):r for r in raw_by_id.values() if r["kind"]=="pilot"}
    pairs=[]
    for i,info in enumerate(protocol["cases"]):
        for method in protocol["config"]["methods"]:
            if not all((i,method,v) in pilot for v in protocol["config"]["variants"]):
                continue
            old,new=(pilot[i,method,v] for v in protocol["config"]["variants"])
            old_record,new_record=(records[r["job_id"]] for r in (old,new))
            a,b=old["result"]["metrics"],new["result"]["metrics"]
            if (old["result"]["metadata"]["scenario_identifier"]!=new["result"]["metadata"]["scenario_identifier"] or
                    old["result"]["metadata"]["K_ref"]!=new["result"]["metadata"]["K_ref"]):
                raise ValueError("Unmatched inputs in pilot pair")
            pairs.append(dict(case=info["case"],method=method,size=int(info["case"][0].rsplit("_",1)[1]),
                original_wall=old_record["execution"]["elapsed_seconds"], optimized_wall=new_record["execution"]["elapsed_seconds"],
                original_cpu=old_record["execution"]["cpu_seconds"], optimized_cpu=new_record["execution"]["cpu_seconds"],
                original_planning=a["total_planning_time"],optimized_planning=b["total_planning_time"],
                original_served=a["customers_served"],optimized_served=b["customers_served"],
                original_complete=a["complete_service"],optimized_complete=b["complete_service"],
                original_triggers=a["optimization_triggers"],optimized_triggers=b["optimization_triggers"],
                same_served_set=set(old["result"]["unserved_customers"])==set(new["result"]["unserved_customers"]),
                original_distance=a["total_distance"],optimized_distance=b["total_distance"]))
    micro_rows=[]
    for (i,v),r in sorted(micros.items()):
        for p in r["fixed_work"]["phases"]:
            baseline=next(x for x in micros[i,"original"]["fixed_work"]["phases"] if x["phase"]==p["phase"])
            micro_rows.append([protocol["cases"][i]["case"][0],p["phase"],v,f"{p['wall_seconds']:.6f}",
                               f"{p['cpu_seconds']:.6f}",f"{baseline['wall_seconds']/max(p['wall_seconds'],1e-12):.2f}"])
    groups=defaultdict(list)
    for row in pairs:
        groups[row["method"]].append(row)
    summaries=[]
    for method,rows in groups.items():
        opportunities=sum(r["size"] for r in rows)
        old_wall=sum(r["original_wall"] for r in rows)
        new_wall=sum(r["optimized_wall"] for r in rows)
        old_cpu=sum(r["original_cpu"] or 0 for r in rows)
        new_cpu=sum(r["optimized_cpu"] or 0 for r in rows)
        summaries.append(dict(method=method,pairs=len(rows),original_seconds=old_wall,optimized_seconds=new_wall,
            wall_speedup=old_wall/max(new_wall,1e-12),original_cpu=old_cpu,optimized_cpu=new_cpu,cpu_speedup=old_cpu/max(new_cpu,1e-12),
            original_service=sum(r["original_served"] for r in rows)/opportunities,
            optimized_service=sum(r["optimized_served"] for r in rows)/opportunities,
            original_complete=mean(r["original_complete"] for r in rows),optimized_complete=mean(r["optimized_complete"] for r in rows),
            service_delta=sum(r["optimized_served"]-r["original_served"] for r in rows)))
    timings,stages,reuse,counts=[],[],[],[]
    for (i,method,variant),raw in sorted(pilot.items()):
        result=raw["result"]
        latencies=[d["optimization_latency_seconds"] for d in result["decisions"] if d.get("optimization_latency_seconds") is not None]
        memo_counts=Counter()
        for d in result["decisions"]:
            memo_counts.update(d.get("proposal_memo",{}).get("incremental_counts",{}))
        hits=sum(d.get("proposal_memo",{}).get("hits",0) for d in result["decisions"])
        misses=sum(d.get("proposal_memo",{}).get("misses",0) for d in result["decisions"])
        roots=[d.get("optimization_root_hash") for d in result["decisions"] if d.get("optimization_latency_seconds") is not None]
        roots=[r for r in roots if r is not None]
        unchanged=sum(d.get("optimizer_kept_constructor") is True for d in result["decisions"])
        label=f"{protocol['cases'][i]['case'][0]} / {method} / {variant}"
        timings.append([label,len(latencies),f"{mean(latencies):.6f}",f"{np.percentile(latencies,95):.6f}",f"{max(latencies):.6f}"])
        t=raw["timing"]
        serialization=load_json(OUTPUT/"serialization"/f"{raw['job_id']}.json")
        execution=records[raw["job_id"]]["execution"]
        startup=max(0,execution["elapsed_seconds"]-raw["worker_wall_seconds"]-serialization["seconds"])
        stages.append([label,*[f"{t[k]:.4f}" for k in ("preparation_seconds","constructor_seconds","optimizer_seconds",
            "final_validation_seconds","nonplanning_simulation_seconds","audit_seconds")],f"{serialization['seconds']:.4f}",f"{startup:.4f}"])
        reuse.append([label,len(roots)-len(set(roots)),unchanged,hits,misses,memo_counts["transition_hits"],
                      memo_counts["transition_misses"],memo_counts["greedy_customers_reused"],memo_counts["label_customers_reused"],
                      memo_counts["objective_hits"]])
        counter=raw["measurements"]["counts"]
        counts.append([label,*[counter.get(k,0) for k in ("route_build_requests","charging_decoder_calls","fleet_decode_requests",
             "distinct_route_decodes_within_problem","objective_requests","objective_computations")],raw["global_route_cache"]["hits"],raw["global_route_cache"]["misses"]])
    hotspots=defaultdict(lambda:[0,0.0,0.0])
    hotspot_rows=[]
    for raw in raw_by_id.values():
        if "profile" not in raw:
            continue
        selected=sorted(raw["profile"],key=lambda r:-r["own_seconds"])[:10]
        for f in selected:
            label=f"{Path(f['file']).name}:{f['function']}"
            key=(raw["case_index"],raw["method"],raw["variant"],label)
            value=hotspots[key]
            value[0]+=f["calls"]
            value[1]+=f["own_seconds"]
            value[2]+=f["cumulative_seconds"]
    for key,v in sorted(hotspots.items(),key=lambda x:-x[1][1]):
        i,method,variant,label=key
        hotspot_rows.append([protocol["cases"][i]["case"][0],method,variant,label,v[0],f"{v[1]:.6f}",f"{v[2]:.6f}"])
    allocation_rows=[]
    for raw in raw_by_id.values():
        if raw["kind"]=="allocation":
            allocation_rows.append([protocol["cases"][raw["case_index"]]["case"][0],raw["variant"],
                raw["allocation"]["current_bytes"],raw["allocation"]["peak_bytes"]])
    budget=load_json(OUTPUT/"budget.json")
    tests=[]
    if (OUTPUT/"tests.xml").exists():
        tests=[r.attrib for r in ET.parse(OUTPUT/"tests.xml").getroot().iter("testsuite")]
    data=dict(protocol_identifier=identifier(protocol),manifest_sha256=sha256((OUTPUT/"manifest.json").read_bytes()).hexdigest(),
              status=manifest["status"],independently_replayed_scenarios=physical_audits,pairs=pairs,summaries=summaries,
              completed_jobs=len(records),planned_jobs=protocol["planned_jobs"],tests=tests,
              default_policy="original",no_automatic_holdout=True)
    save_json(OUTPUT/"analysis.json",data)
    lines=["# Performance engineering: consolidated technical report","",
        f"Status: {manifest['status']}; {len(records)}/{protocol['planned_jobs']} diagnostic/pilot workers saved; {len(pairs)}/15 complete unprofiled pairs.",
        f"Execution source: `{protocol['source_commit']}`. Shared machine, fresh sequential processes, one native thread per worker.",
        "This is a three-parent development engineering pilot, not a new independent final study. The original policy remains the default.","",
        "## 1. Why the earlier study was expensive","",
        "The stopped Reliability V2 study performed 28,843 optimization calls: 13.567 of 13.692 worker hours were planning (99.09%).",
        "Its 1,116-run grid multiplied full scenarios by five engines and multiple variants before effectiveness was established.",
        "Five seconds bounds one MPC decision, not a full scenario. Its prior 12-hour control was a soft scenario-boundary pause.",
        "All 361 Reliability V2 raws, protocols, stop marker and historical primary results are preserved; that campaign was not resumed.","",
        "## 2. Exact implementation changes","",
        "- Optional `proposal_cache_policy=incremental_v1`; original and prior cache-only (`root_v1`) implementations remain runnable.",
        "- Reuse exact greedy MPC prefix states and the original bounded charging decoder's complete prefix frontiers. Prefix choices do not depend on later customers.",
        "- Precompute each current customer's nearest-safe energy once per decoder stage. Prune only prohibited inter-station arcs or station paths that violate time windows even with zero charging time.",
        "- Cache exact planning transitions, including failure reason/message, under complete physical state/action/require-return keys.",
        "  Frozen observations are held strongly by decision-local identity, preventing recycled IDs or cross-observation reuse without repeatedly hashing all visible customers.",
        "- Cache the unchanged evaluator's entire score/component result for identical sequences/actions/costs and constructor ownership anchors.",
        "  No floating-point summation order or lexicographic priority changes. Existing route/criticality/screen caches already handle unchanged route contributions.",
        "- Every cache is bounded and closed at a decision boundary or exception. Deadlines precede planning cache hits. No event is suppressed and no optimizer strategy or iteration count is reduced.",
        "- The independent plant/auditor in evrp/model.py and canonical evrp/optimizers/objective.py are unchanged.","",
        "## 3. Tests and fixed-work equivalence","",
        f"Test suite evidence: {tests}.",
        f"Independently replayed saved profile/pilot trajectories: {physical_audits}. All accepted route microbenchmarks are also replayed by the uncached original transition.",
        "Tests cover randomized and boundary charging routes, MP topology, complete observation/config invalidation, exact fixed-work optimizer results for all five engines, deadlines and finite cache caps.",
        "Original/cache-only/incremental microchecksums must agree before pilot admission. Wall-clock-limited search need not produce identical trajectories.","",
        "### Fixed-work measurements","",
        "One first-observation root per size, at most 12 unique candidates and eight-service prefixes. Forced fallback and repeated-score phases deliberately isolate bottlenecks; they do not establish a general scenario speedup.",""]
    lines+=markdown(["Instance","Phase","Variant","Wall s","CPU s","Wall speedup vs original"],micro_rows)
    lines += ["","### Python allocation probes (separate from timing runs)",""]
    lines += markdown(["Instance","Variant","Current bytes","Peak bytes"],allocation_rows)
    lines += ["","## 4. Unprofiled original versus optimized scenarios","",
        "Three prespecified previously seen eligible cases: 25, 50 and 100 customers. Identical archived scenario/ref/fleet and full original parameters; matched pair order alternates.",
        "Both variants use the same lightweight operation counters. cProfile and tracemalloc run in different workers and are never pooled into pilot runtimes.",""]
    lines+=markdown(["Method","Pairs","Original process s","Optimized process s","Wall ratio","Original CPU s","Optimized CPU s","CPU ratio","Original service %","Optimized service %","Original complete %","Optimized complete %"],
        [[s["method"],s["pairs"],*[f"{s[k]:.3f}" for k in ("original_seconds","optimized_seconds","wall_speedup","original_cpu","optimized_cpu","cpu_speedup")],
          *[f"{100*s[k]:.3f}" for k in ("original_service","optimized_service","original_complete","optimized_complete")]] for s in summaries])
    lines += ["","### Every matched case, including regressions",""]
    lines+=markdown(["Instance","Method","Original / optimized served","Original / optimized complete","Original / optimized process s"],
        [[r["case"][0],r["method"],f"{r['original_served']} / {r['optimized_served']}",f"{r['original_complete']} / {r['optimized_complete']}",
          f"{r['original_wall']:.3f} / {r['optimized_wall']:.3f}"] for r in pairs])
    lines += ["","### Decision latency, not whole-scenario cost",""]
    lines+=markdown(["Case / method / variant","Decisions","Mean s","p95 s","Max s"],timings)
    lines += ["","## 5. Where CPU work is reused","",
        "Repeated ownership alone does not define an identical physical/observable root and is never used to skip a meaningful event.",
        "Returning the constructor unchanged does not prove another search was useless or that early stopping is harmless.",""]
    lines+=markdown(["Case / method / variant","Repeated root hashes","Constructor unchanged","Replay hits","Replay misses","Transition hits","Transition misses","Greedy customers reused","Label customers reused","Objective hits"],reuse)
    lines += ["","### Route and objective call counts","",
        "Distinct route decodes are distinct keys within each immutable fleet problem; counts summed across problems may repeat equivalent roots. Global LRU misses are not claimed as globally unique routes.",""]
    lines+=markdown(["Case / method / variant","Build requests","Charging fallbacks","Fleet decode requests","Distinct problem decodes","Score requests","Score computations","Global route LRU hits","Global route LRU misses"],counts)
    lines += ["","## 6. Phase costs","",
        "Disjoint high-level measurements: input preparation, constructor, optimizer, final replay, nonplanning simulation, independent audit, serialization and startup/polling residual.",
        "Nonplanning simulation includes event processing, state hashing and physical dispatch. The startup residual also includes process teardown and monitor granularity.",
        "Nested cProfile cumulative times below overlap; they must not be added as a time partition.",""]
    lines+=markdown(["Case / method / variant","Prepare s","Constructor s","Optimizer s","Final validation s","Nonplanning simulation s","Audit s","Serialize s","Startup/residual s"],stages)
    lines += ["","### Size- and method-specific hotspot ranking","",
        "Sorted by own time within bounded separate profiles. Completion uses full scenarios; other engines use one saved root and the unchanged iteration settings with the usual 4.75-second inner allowance. Profiling perturbs search.",""]
    lines+=markdown(["Instance","Engine","Variant","Function","Calls","Own s","Cumulative s"],hotspot_rows)
    lines += ["","## 7. Hard budget and affordable future design","",
        f"Planned conservative upper allowances plus reporting: {protocol['estimated_upper_seconds_including_report']:.1f}/7200 s; jobs: {protocol['planned_jobs']}; full unprofiled simulations: 30.",
        f"Worker max(elapsed,CPU) charged before this reporting worker: {budget['charged_seconds']:.3f} s. Final accounting, including this report, is in budget.json.",
        "A complete paired block is admitted only when its full remaining upper allowance plus a reporting reserve fits.",
        "The monitor checks elapsed and actual worker CPU, kills only its owned timed-out worker, and records incomplete evidence/logs. Failed, interrupted or unmanifested jobs never silently rerun.",
        "Historical exact-case cost estimates are doubled plus startup margin and a worker floor; these are conservative estimates, not guarantees. Actual watchdogs enforce the hard limit.",
        "Keep future work staged: fixed-work correctness and profiling first, then a prespecified small matched pilot, then explicit review. No automatic holdout or five-engine multi-seed expansion."]
    if pairs:
        avg_cost=mean(r["original_wall"]+r["optimized_wall"] for r in pairs)
        lines += [f"Observed mean paired-method process cost: {avg_cost:.1f} s. A future 6-parent x 3-size x 2-DoD x 2-seed x 5-engine paired study would have 360 paired blocks (720 simulations),",
                  f"projecting about {360*avg_cost/3600:.1f} shared-machine process hours at this pilot's mix. This is a scenario-mix extrapolation, not a reliable forecast; preflight must use size/method-specific bounds."]
    lines += ["","## 8. Recommendation and limitations","",
        "Original policy stays the default. Exact evaluator speedups demonstrate less work for a fixed workload, but time-limited optimizers can spend the same five seconds exploring more candidates.",
        "Consequently faster kernels do not guarantee shorter scenario time, better closed-loop service or fewer planning calls. Inspect every regression above before any method-wide rollout.",
        "Only three previously seen parents and one seed/DoD per file were tested. Shared-machine load, profiler perturbation, fresh-process startup and bounded Python caches limit generalization.",
        "The prior root-v1 cache is explicitly benchmarked; a larger cache is not automatically faster. No statistically independent new paper superiority claim or final holdout is made.",
        "No adaptive early stop, fewer events, reduced search or objective approximation was introduced. Such policies would require separate names and new evaluation.","",
        "## 9. Reproduction","","```powershell","python -m pytest -q",
        "python -m scripts.run_performance_engineering --freeze","python -u -m scripts.run_performance_engineering",
        "python -m scripts.report_performance_engineering","```","",
        "Use the recorded execution source. Completed hash-verified outputs are reused; the persistent 7200-second allowance cannot be extended by rerunning the command.",
        "The standalone report command is read-only scientific analysis, not a new optimization campaign. Keep Reliability V2 STOP_REQUESTED.json intact."]
    writable_path(OUTPUT/"FINAL_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    if micros:
        fig,axes=plt.subplots(1,3,figsize=(13,4))
        for ax,i in zip(axes,range(len(protocol["cases"]))):
            variants=[v for v in protocol["config"]["micro_variants"] if (i,v) in micros]
            values=[sum(p["wall_seconds"] for p in micros[i,v]["fixed_work"]["phases"] if p["phase"]!="repeated_exact_objective") for v in variants]
            ax.bar([v.replace("incremental_v1","incremental").replace("root_v1","memo") for v in variants],values,
                   color=["#687887","#b98c31","#267a66"][:len(values)])
            ax.set(title=protocol["cases"][i]["case"][0],ylabel="Unique-route + forced-fallback wall seconds")
        fig.tight_layout()
        fig.savefig(writable_path(OUTPUT/"fixed_work.png"),dpi=300)
        plt.close(fig)
    if summaries:
        fig,axes=plt.subplots(1,2,figsize=(12,4))
        x=np.arange(len(summaries))
        for offset,prefix,label,color in ((-.18,"original","Original","#687887"),(.18,"optimized","Incremental","#267a66")):
            axes[0].bar(x+offset,[s[prefix+"_seconds"] for s in summaries],.36,label=label,color=color)
            axes[1].bar(x+offset,[100*s[prefix+"_service"] for s in summaries],.36,label=label,color=color)
        for ax in axes:
            ax.set(xticks=x,xticklabels=[s["method"].replace("MPC_","") for s in summaries])
            ax.legend(fontsize=8)
        axes[0].set(ylabel="Total unprofiled process seconds (three cases)")
        axes[1].set(ylabel="Customers served (%)",ylim=(0,101))
        fig.tight_layout()
        fig.savefig(writable_path(OUTPUT/"pilot.png"),dpi=300)
        plt.close(fig)
    artifacts=[]
    for path in sorted(OUTPUT.rglob("*.png"))+sorted(OUTPUT.rglob("*.md")):
        if path.suffix==".png":
            with Image.open(path) as image:
                if min(image.info.get("dpi",(0,0)))<299.9 or all(lo==hi for lo,hi in image.convert("RGB").getextrema()):
                    raise ValueError("Blank or low-resolution figure")
        artifacts.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha256(path.read_bytes()).hexdigest()))
    save_json(OUTPUT/"paper_inventory.json",dict(artifacts=artifacts))
    print(f"Consolidated report: {len(pairs)} paired scenarios, {physical_audits} independent disk replays; defaults remain original",flush=True)


if __name__=="__main__":
    build()
