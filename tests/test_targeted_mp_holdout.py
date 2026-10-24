from copy import deepcopy
from hashlib import sha256

import pytest

from evrp.storage import identifier,save_json
from scripts import run_targeted_mp_holdout as holdout
from scripts.run_targeted_service import CONFIG,options
from evrp.experiments import load_config,simulation_config


def test_reserved_mp_policy_changes_only_offline_input_policy():
    original=load_config(CONFIG)
    amended=deepcopy(original)
    amended["common"]["reference_policy"]="mp_witness_v1"
    case=["r202_21_100",.25,0]
    for method in original["holdout_methods"]:
        for variant in original["variants"]:
            old=options(original,case,method,variant)
            new=options(amended,case,method,variant)
            assert {k for k in old.keys()|new.keys() if old.get(k)!=new.get(k)}=={"reference_policy"}
            assert simulation_config(old)==simulation_config(new)


def test_mp_holdout_never_opens_without_completed_promoted_development(tmp_path,monkeypatch):
    monkeypatch.setattr(holdout,"OUTPUT",tmp_path)
    protocol=dict(scientific={"frozen":True})
    manifest=dict(status="complete",completed_runs=288,planned_runs=288)
    save_json(tmp_path/"development/protocol.json",protocol)
    save_json(tmp_path/"development/manifest.json",manifest)
    selection=dict(selected_variant=None,checks={},development_protocol_identifier=identifier(protocol),
                   development_manifest_sha256=sha256((tmp_path/"development/manifest.json").read_bytes()).hexdigest())
    save_json(tmp_path/"development/analysis.json",dict(selection=selection,independent_audited_runs=288))
    with pytest.raises(ValueError,match="No candidate"):
        holdout.checked_selection()
    selection.update(selected_variant="B_resources",checks={"B_resources":{"budget":True}})
    save_json(tmp_path/"development/analysis.json",dict(selection=selection,independent_audited_runs=288))
    assert holdout.checked_selection()[1]["selected_variant"]=="B_resources"
    save_json(tmp_path/"development/manifest.json",{**manifest,"completed_runs":287})
    with pytest.raises(ValueError,match="incomplete"):
        holdout.checked_selection()
