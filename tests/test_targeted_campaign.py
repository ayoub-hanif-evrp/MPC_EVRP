from copy import deepcopy
from hashlib import sha256

import pytest

from evrp.experiments import load_config, simulation_config
from evrp.storage import save_json
from scripts import run_targeted_service as campaign


def test_targeted_design_keeps_parent_partition_and_original_budgets():
    config=load_config(campaign.CONFIG)
    cases=campaign.design_cases(config,config["development_parents"])
    assert len(cases)==36 and len({tuple(case) for case in cases})==36
    assert not set(config["development_parents"]) & set(config["reserved_parents"])
    assert {case[1] for case in cases}=={.25,.75}
    assert {case[2] for case in cases}=={0,1}
    for variant in config["variants"]:
        for method in config["holdout_methods"]:
            effective=simulation_config(campaign.options(config,cases[0],method,variant))
            assert effective.total_planning_time_limit==5
            assert effective.fleet_mode=="fixed_reference"
            assert effective.mpc.charging_mode=="partial"
            assert effective.dispatch_policy=="original"


def test_targeted_verify_rejects_budget_audit_and_pair_identity_mutation():
    protocol=dict(scientific=dict(source_sha256="source",cases=[dict(scenario_id="scenario",k_ref=3)]))
    from evrp.storage import identifier
    raw=dict(metadata=dict(targeted_protocol_identifier=identifier(protocol),source_sha256="source",
                           scenario_identifier="scenario",K_ref=3,algorithm="MPC_ALNS",
                           campaign_variant="original",independent_audit={"physical":True}),
             metrics={**{k:0 for k in campaign.VIOLATIONS},"max_optimization_latency":4.9})
    campaign.verify(raw,protocol,0,"MPC_ALNS","original")
    for section,key,value in (("metadata","K_ref",4),("metadata","scenario_identifier","other"),
                              ("metadata","independent_audit",{"physical":False}),
                              ("metrics","max_optimization_latency",5.01),
                              ("metrics","hidden_information_violations",1)):
        corrupt=deepcopy(raw)
        corrupt[section][key]=value
        with pytest.raises(ValueError):
            campaign.verify(corrupt,protocol,0,"MPC_ALNS","original")


def test_restore_refuses_conflicting_exact_cache(tmp_path,monkeypatch):
    monkeypatch.setattr(campaign,"ROOT",tmp_path)
    artifact=tmp_path/"inputs/reference.json"
    target=tmp_path/"results/reference_schedules/reference.json"
    save_json(artifact,{"frozen":True})
    record=dict(artifact="inputs/reference.json",cache="results/reference_schedules/reference.json",
                sha256=sha256(artifact.read_bytes()).hexdigest())
    protocol=dict(scientific=dict(inputs=[record]))
    campaign.restore_inputs(protocol)
    assert target.read_bytes()==artifact.read_bytes()
    save_json(target,{"frozen":False})
    with pytest.raises(ValueError,match="conflict"):
        campaign.restore_inputs(protocol)
    assert target.read_bytes()!=artifact.read_bytes()
