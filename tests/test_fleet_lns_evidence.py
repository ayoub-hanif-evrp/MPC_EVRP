"""The development tables must remain tied to exact audited result files."""

from copy import deepcopy
import json

import pytest

from scripts.fleet_lns_evidence import MANIFEST, TABLES, render_tables, verify, winner


def test_frozen_evidence_manifest_and_tables():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    verify(manifest)
    assert TABLES.read_text(encoding="utf-8") == render_tables(manifest)
    assert len(manifest["static"]) == 6
    assert len(manifest["dynamic"]) == 12
    assert len(manifest["hybrid_static_partial"]) == 3


def test_frozen_evidence_rejects_changed_file_hash():
    manifest = deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
    manifest["static"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Changed result file"):
        verify(manifest)


def test_lexicographic_winner_prioritizes_service():
    rolling = {"customers_served": 100, "vehicles_activated": 5, "total_distance": 800}
    hybrid = {"customers_served": 99, "vehicles_activated": 4, "total_distance": 700}
    assert winner(rolling, hybrid) == "Rolling: service"
