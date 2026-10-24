"""Read-only 168-case replay, merging new witnesses without replacing old evidence."""

from hashlib import sha256

from evrp.instance import discover_instances, load_instance
from evrp.reference import ReferenceConfig, ReferenceSchedule, published_full_reference, validate_reference
from evrp.scenario import generate
from evrp.storage import ROOT, identifier, load_json, save_json, verify_text_digest, writable_path

OUTPUT=ROOT/"results/desaulniers/targeted_service_v1"
PRIOR=ROOT/"results/desaulniers/publication_development/audits/reference_inventory.json"


def audit():
    old=load_json(PRIOR)
    previous={r["instance"]:r for r in old["rows"]}
    manifest=load_json(OUTPUT/"offline_resources/manifest.json")
    protocol=load_json(OUTPUT/"offline_resources/protocol.json")
    if (manifest["protocol_identifier"]!=identifier(protocol) or
            manifest["completed_instances"]!=manifest["planned_instances"] or len(manifest["records"])!=2):
        raise ValueError("Offline reference extension is incomplete")
    extra={r["instance"]:r for r in manifest["records"]}
    if len(extra)!=2 or set(extra)!={"r204_21_100","r208_21_100"}:
        raise ValueError("Offline extension membership mismatch")
    rows=[]
    for path in discover_instances():
        instance=load_instance(path)
        prior=previous[instance.name]
        if instance.sha256!=prior["instance_sha256"]:
            raise ValueError("Benchmark bytes changed")
        if prior["physical_witness"]:
            source="preserved_prior_inventory"
            if prior.get("artifact"):
                artifact=ROOT/prior["artifact"]
                verify_text_digest(artifact,prior["artifact_sha256"])
                reference=ReferenceSchedule.load(artifact,instance)
            else:
                artifact=None
                reference=published_full_reference(instance,ReferenceConfig())
            if reference is None or reference.identifier!=prior["reference_id"]:
                raise ValueError("Prior reference canonical identity mismatch")
        else:
            record=extra[instance.name]
            worker=OUTPUT/"offline_resources/workers"/f"{instance.name}.json"
            if load_json(worker)!=record or record["protocol_identifier"]!=identifier(protocol):
                raise ValueError("New witness worker/manifest mismatch")
            if record["status"]!="feasible_reference_found":
                raise ValueError("New witness is not a successful physical reference")
            artifact=ROOT/record["reference"]
            if sha256(artifact.read_bytes()).hexdigest()!=record["reference_sha256"]:
                raise ValueError("New witness bytes changed")
            reference=ReferenceSchedule.load(artifact,instance)
            if reference.identifier!=record["reference_id"]:
                raise ValueError("New reference canonical identity mismatch")
            source="separate_resource_labels_v2"
        validate_reference(instance,reference)
        eligibility={}
        for dod in (0,.25,.5,.75):
            try:
                scenario=generate(instance,reference,seed=1,dynamicity=dod)
            except ValueError as error:
                if not str(error).startswith("Target DoD is ineligible"):
                    raise
                eligibility[str(dod)]=dict(eligible=False,reason=str(error))
                continue
            if any(dict(scenario.customer_release_times)[c]>t+1e-8 for c,t in reference.predecessor_departures.items()):
                raise ValueError("Clairvoyant reference would dispatch before a release")
            eligibility[str(dod)]=dict(eligible=True,scenario_id=scenario.identifier)
        rows.append(dict(instance=instance.name,instance_sha256=instance.sha256,source=source,
                         physical_witness=True,reference_id=reference.identifier,fleet_size=reference.fleet_size,
                         historical_reference_policy=prior["historical_reference_policy"],
                         artifact=artifact.relative_to(ROOT).as_posix() if artifact else None,
                         artifact_sha256=sha256(artifact.read_bytes()).hexdigest() if artifact else None,
                         dynamicity_preflight=eligibility))
    if len(rows)!=168 or len({r["instance"] for r in rows})!=168:
        raise ValueError("Inventory must contain 168 unique instances")
    save_json(OUTPUT/"reference_inventory.json",dict(instances=168,physically_witnessed=168,
              historical_reference_policy=sum(r["historical_reference_policy"] for r in rows),
              prior_inventory_sha256=sha256(PRIOR.read_bytes()).hexdigest(),rows=rows))
    lines=["# Independently replayed complete physical witness inventory","",
           "Parsed/arc-validated and independently replayed: 168/168. Historical reference policy remains 144.",
           "The new witnesses are separate upper bounds and never replace historical experiment fleets.",
           "Eligible reference-preserving releases were checked at DoD 0, .25, .5 and .75.","",
           "| Instance | Source | Fleet upper bound | DoD .25/.5/.75 eligible |","| --- | --- | ---: | --- |"]
    lines.extend(f"| {r['instance']} | {r['source']} | {r['fleet_size']} | "
                 f"{' / '.join(str(r['dynamicity_preflight'][str(d)]['eligible']) for d in (.25,.5,.75))} |" for r in rows)
    writable_path(OUTPUT/"REFERENCE_INVENTORY.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("All 168 physical references replayed; historical fleets unchanged",flush=True)


if __name__=="__main__":
    audit()
