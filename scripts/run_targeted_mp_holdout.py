"""Conditional untouched-parent holdout with an explicitly frozen MP witness policy.

The development runner is unchanged. Its provisional legacy-reference holdout
preflight is not suitable for three reserved 100-customer instances. This
separate protocol uses already audited witnesses, never new reference search.
"""

import argparse
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from time import perf_counter

from evrp.experiments import audit_result, prepare, simulation_config
from evrp.reference_extensions import INVENTORY
from evrp.simulator import EventDrivenSimulator
from evrp.storage import ROOT, benchmark_hashes, identifier, load_json, save_json
from scripts import run_targeted_service as development

OUTPUT=development.OUTPUT
STAGE="holdout"


def source_hash():
    return identifier(dict(development_source=development.source_hash(),
                           holdout_runner_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                           orchestrator_sha256=sha256((ROOT/"scripts/complete_targeted_study.py").read_bytes()).hexdigest(),
                           audited_mp_inventory_sha256=sha256(INVENTORY.read_bytes()).hexdigest()))


def checked_selection():
    manifest=load_json(OUTPUT/"development/manifest.json")
    analysis=load_json(OUTPUT/"development/analysis.json")
    protocol=load_json(OUTPUT/"development/protocol.json")
    selection=analysis["selection"]
    if (manifest["status"]!="complete" or manifest["completed_runs"]!=manifest["planned_runs"] or
            analysis["independent_audited_runs"]!=manifest["completed_runs"] or
            selection["development_protocol_identifier"]!=identifier(protocol) or
            selection["development_manifest_sha256"]!=sha256((OUTPUT/"development/manifest.json").read_bytes()).hexdigest()):
        raise ValueError("Development selection is incomplete or unaudited")
    variant=selection["selected_variant"]
    if variant is None or not all(selection["checks"][variant].values()):
        raise ValueError("No candidate earned a new holdout")
    return protocol,selection


def freeze():
    original,selection=checked_selection()
    config=original["scientific"]["config"]
    config={**config,"common":{**config["common"],"reference_policy":"mp_witness_v1"}}
    science=dict(config=config,stage=STAGE,source_sha256=source_hash(),
                 dataset_sha256=identifier(benchmark_hashes()),methods=config["holdout_methods"],
                 variants=["original",selection["selected_variant"]],
                 parent_partition=original["scientific"]["parent_partition"],selection=selection,
                 reference_policy="mp_witness_v1",
                 protocol_amendment="Reserved MP-only reference witnesses; frozen before online holdout outcomes")
    target=OUTPUT/STAGE/"protocol.json"
    if target.exists():
        saved=load_json(target)
        if any(saved["scientific"].get(k)!=v for k,v in science.items()):
            raise ValueError("Existing holdout protocol differs; preserve and investigate")
        development.restore_inputs(saved)
        return saved
    seen=set()
    for path in (ROOT/"results/desaulniers").rglob("manifest.json"):
        for row in load_json(path).get("records",[]):
            if row.get("instance") and row.get("raw"):
                seen.add(row["instance"].rsplit("_",1)[0])
    if set(config["reserved_parents"]) & seen:
        raise ValueError("A reserved parent has prior online results")
    cases,excluded,inputs=[],[],{}
    inventory={r["instance"]:r for r in load_json(INVENTORY)["rows"]}
    for case in development.design_cases(config,config["reserved_parents"]):
        try:
            instance,reference,scenario,scenario_path=prepare(case[0],development.options(config,case,"MPC_COMPLETION","original"))
        except ValueError as error:
            if "DoD is ineligible" not in str(error):
                raise
            excluded.append(dict(case=case,reason=str(error)))
            continue
        row=inventory[instance.name]
        if row.get("artifact"):
            reference_path=ROOT/row["artifact"]
        else:
            reference_path=OUTPUT/"holdout_input_cache"/f"{instance.name}_{reference.identifier[:16]}.json"
            if not reference_path.exists():
                reference.save(reference_path)
            if load_json(reference_path).get("identifier")!=reference.identifier:
                raise ValueError("Derived published-reference cache conflict")
        for path,kind,obj in ((reference_path,"reference_schedules",reference),(scenario_path,"scenarios",scenario)):
            inputs[str(path)]=development.archive_input(path,kind,obj,instance)
        cases.append(dict(case=case,scenario_id=scenario.identifier,reference_id=reference.identifier,
                          k_ref=reference.fleet_size,customers=len(instance.customers),
                          instance_sha256=instance.sha256,parent=case[0].rsplit("_",1)[0]))
    science.update(cases=cases,excluded=excluded,inputs=list(inputs.values()))
    commit=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    frozen=dict(scientific=science,source_commit=commit,python=sys.version,timing_conditions=config["timing_conditions"])
    save_json(target,frozen)
    return frozen


def worker(index,method,variant):
    frozen=load_json(OUTPUT/STAGE/"protocol.json")
    science=frozen["scientific"]
    if science["source_sha256"]!=source_hash():
        raise ValueError("MP holdout source drift")
    if method not in science["methods"] or variant not in science["variants"]:
        raise ValueError("Out-of-design holdout worker")
    info=science["cases"][index]
    target=development.target_path(STAGE,frozen,index,method,variant)
    if target.exists():
        raise ValueError("Never overwrite existing holdout evidence")
    started=perf_counter()
    options=development.options(science["config"],info["case"],method,variant)
    instance,reference,scenario,_=prepare(info["case"][0],options)
    if reference.identifier!=info["reference_id"] or scenario.identifier!=info["scenario_id"]:
        raise ValueError("Holdout inputs differ from preregistration")
    result=EventDrivenSimulator(instance,scenario,simulation_config(options)).run()
    audit=audit_result(result,instance,scenario)
    result.metrics["worker_wall_seconds"]=perf_counter()-started
    result.metadata.update(source_sha256=source_hash(),frozen_source_commit=frozen["source_commit"],
                           targeted_protocol_identifier=identifier(frozen),campaign_variant=variant,
                           independent_audit=audit,isolated_worker=True,timing_conditions=frozen["timing_conditions"])
    raw=asdict(result)
    development.verify(raw,frozen,index,method,variant)
    save_json(target,raw)


def run(frozen, deadline=None):
    science=frozen["scientific"]
    target=OUTPUT/STAGE/"manifest.json"
    old=load_json(target) if target.exists() else None
    if old and old["protocol_identifier"]!=identifier(frozen):
        raise ValueError("Holdout manifest protocol drift")
    records={(r["case_index"],r["method"],r["variant"]):r for r in old["records"]} if old else {}
    if old and len(records)!=len(old["records"]):
        raise ValueError("Duplicate holdout run")
    total=len(science["cases"])*len(science["methods"])*len(science["variants"])
    deadline=min(deadline if deadline is not None else float("inf"),perf_counter()+10*3600)
    for index,info in enumerate(science["cases"]):
        if perf_counter()>deadline:
            return False
        for method in science["methods"]:
            for variant in science["variants"]:
                key=index,method,variant
                path=development.target_path(STAGE,frozen,*key)
                if key in records:
                    if sha256(path.read_bytes()).hexdigest()!=records[key]["raw_sha256"]:
                        raise ValueError("Saved holdout bytes changed")
                    development.verify(load_json(path),frozen,*key)
                    continue
                if path.exists():
                    raise ValueError("Unmanifested holdout raw preserved for investigation")
                command=[sys.executable,"-u","-m","scripts.run_targeted_mp_holdout","--worker",str(index),method,variant]
                started=perf_counter()
                try:
                    subprocess.run(command,cwd=ROOT,check=True,timeout=science["config"]["whole_worker_timeout_seconds"])
                except (subprocess.SubprocessError,OSError) as error:
                    save_json(OUTPUT/STAGE/"failures"/f"{index}_{method}_{variant}.json",
                              dict(command=command,error=repr(error),protocol_identifier=identifier(frozen)))
                    raise
                raw=load_json(path)
                development.verify(raw,frozen,*key)
                records[key]=dict(case_index=index,instance=info["case"][0],case=info["case"],parent=info["parent"],
                                  method=method,variant=variant,raw=path.relative_to(ROOT).as_posix(),
                                  raw_sha256=sha256(path.read_bytes()).hexdigest(),metrics=raw["metrics"],
                                  independent_audit=raw["metadata"]["independent_audit"],
                                  process_wall_seconds=perf_counter()-started)
                save_json(target,dict(protocol_identifier=identifier(frozen),planned_runs=total,completed_runs=len(records),
                          status="complete" if len(records)==total else "partial",records=list(records.values())))
                print(f"MP holdout {len(records)}/{total} {info['case']} {method} {variant}: "
                      f"served={raw['metrics']['customers_served']}",flush=True)
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker",nargs=3)
    args=parser.parse_args()
    if args.worker:
        index,method,variant=args.worker
        return worker(int(index),method,variant)
    from scripts.analyze_targeted_service import analyze,finalize
    analyze("development")
    frozen=freeze()
    if not run(frozen):
        return print("MP holdout paused at a scenario boundary; resume this same command")
    analyze("holdout")
    finalize(frozen["scientific"]["selection"])


if __name__=="__main__":
    main()
