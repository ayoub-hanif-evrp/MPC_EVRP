"""The risk-aware campaign must retain failed attempts and replay its audits."""

from copy import deepcopy
import json

import pytest

from scripts.risk_aware_fleet_evidence import MANIFEST, TABLE, render, verify


def test_risk_aware_manifest_replays_every_trace_audit():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    verify(manifest)
    assert TABLE.read_text(encoding="utf-8") == render(manifest)
    assert manifest["gates"]["static_pass"]
    assert manifest["gates"]["static_served"] == 600
    assert not manifest["gates"]["dynamic_gate_pass"]
    assert manifest["gates"]["dynamic_pairs"] == 4
    assert any(row["served"] < 100 for row in manifest["runs"])


def test_risk_aware_manifest_rejects_changed_hash():
    manifest = deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
    manifest["runs"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="changed"):
        verify(manifest)
