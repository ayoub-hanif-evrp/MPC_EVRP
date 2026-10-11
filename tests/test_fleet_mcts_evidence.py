"""Fleet-MCTS static evidence must include and independently audit every run."""

from copy import deepcopy
import json

import pytest

from scripts.fleet_mcts_evidence import MANIFEST, TABLE, render, verify


def test_fleet_mcts_static_manifest_replays_independent_audit():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    verify(manifest)
    assert TABLE.read_text(encoding="utf-8") == render(manifest)
    assert len(manifest["runs"]) == 9


def test_fleet_mcts_manifest_rejects_changed_raw_hash():
    manifest = deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
    manifest["runs"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Changed static evidence"):
        verify(manifest)


def test_table_preserves_failed_attempts_without_metrics():
    manifest = deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
    row = manifest["runs"][0]
    row.update(status="failed", audit_errors=["synthetic failure"], served=None,
               evs=None, distance=None, planning_seconds=None,
               p95_event_seconds=None, max_event_seconds=None)
    assert "failed/fail" in render(manifest)
