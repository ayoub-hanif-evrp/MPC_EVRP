"""Separate bounded resource-decoder witnesses; never alters historical K_ref."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import subprocess
from time import perf_counter

from evrp.instance import load_instance
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, reset_deadline, set_deadline
from evrp.reference import ReferenceSchedule, validate_reference
from evrp.storage import BENCHMARK, ROOT, identifier, load_json, save_json, writable_path
from scripts import extend_mp_reference_coverage as prior

OUTPUT = ROOT/"results/desaulniers/targeted_service_v1/offline_resources"
LIMIT = 120
NAMES = ("r204_21_100", "r208_21_100")


def run():
    files=sorted((ROOT/"evrp").rglob("*.py"))+[Path(__file__),Path(prior.__file__)]
    science=dict(instances=list(NAMES),seconds_per_instance=LIMIT,
                 strategy="same first-feasible offline insertion with opt-in resource_labels_v2",
                 source_sha256=identifier({p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in files}),
                 historical_fleets_replaced=False)
    target=OUTPUT/"protocol.json"
    if target.exists():
        protocol=load_json(target)
        if protocol["scientific"]!=science:
            raise ValueError("Offline witness protocol/source drift")
    else:
        commit=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
        protocol=dict(scientific=science,source_commit=commit)
        save_json(target,protocol)
    records=[]
    for name in NAMES:
        path=OUTPUT/"workers"/f"{name}.json"
        instance=load_instance(BENCHMARK/f"{name}.txt")
        if not path.exists():
            started=perf_counter()
            record=dict(instance=name,instance_sha256=instance.sha256,protocol_identifier=identifier(protocol))
            previous=prior.MPC
            prior.MPC=MPCConfig(route_decoder_version="resource_labels_v2")
            token=set_deadline(perf_counter()+LIMIT)
            try:
                reference=replace(prior.construct(instance),provenance="separate_resource_labels_v2_first_feasible")
                validate_reference(instance,reference)
                artifact=OUTPUT/"references"/f"{name}.json"
                if artifact.exists():
                    raise ValueError("Unmanifested witness exists")
                reference.save(artifact)
                loaded=ReferenceSchedule.load(artifact,instance)
                record.update(status="feasible_reference_found",fleet_size=loaded.fleet_size,
                              reference=artifact.relative_to(ROOT).as_posix(),reference_id=loaded.identifier,
                              reference_sha256=sha256(artifact.read_bytes()).hexdigest())
            except PlanningDeadlineExceeded:
                record.update(status="search_timeout",reason="Bounded search expired; not an infeasibility proof")
            except ValueError as error:
                record.update(status="construction_unresolved",reason=str(error))
            finally:
                reset_deadline(token)
                prior.MPC=previous
            record["seconds"]=perf_counter()-started
            save_json(path,record)
        record=load_json(path)
        if record["protocol_identifier"]!=identifier(protocol):
            raise ValueError("Offline worker identity mismatch")
        if record["status"]=="feasible_reference_found":
            artifact=ROOT/record["reference"]
            if sha256(artifact.read_bytes()).hexdigest()!=record["reference_sha256"]:
                raise ValueError("Offline witness bytes changed")
            loaded=ReferenceSchedule.load(artifact,instance)
            if loaded.identifier!=record["reference_id"]:
                raise ValueError("Offline reference replay mismatch")
        records.append(record)
        save_json(OUTPUT/"manifest.json",dict(records=records,completed_instances=len(records),planned_instances=2,
                  protocol_identifier=identifier(protocol)))
        print(f"Offline resource labels: {name} {record['status']} K={record.get('fleet_size','-')}",flush=True)
    valid=sum(r["status"]=="feasible_reference_found" for r in records)
    lines=["# Two unresolved MP offline reference cases", "",
           f"New independently replayed witnesses: {valid}/2. Combined physical coverage: {166+valid}/168.",
           "Historical failures, fleet sizes, dynamic scenarios and raw experiments are unchanged.",
           "A timeout or bounded construction failure is not a proof of infeasibility.","",
           "| Instance | Status | Separate fleet upper bound | Seconds |","| --- | --- | ---: | ---: |"]
    lines += [f"| {r['instance']} | {r['status']} | {r.get('fleet_size','')} | {r['seconds']:.3f} |" for r in records]
    writable_path(OUTPUT/"RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__=="__main__":
    run()
