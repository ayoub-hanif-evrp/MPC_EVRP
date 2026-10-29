"""Result inventory must classify conservatively and leave evidence untouched."""

import json
from pathlib import PurePosixPath

from scripts.maintenance.inventory_results import classify, inventory_results


def test_dispositions_keep_evidence_and_review_unknowns():
    assert classify(PurePosixPath("desaulniers/robustness_v3/raw/run.json.gz"))[0] == "KEEP_ACTIVE"
    assert classify(PurePosixPath("desaulniers/targeted_service_v1/FINAL_REPORT.md"))[0] == "KEEP_ACTIVE"
    assert classify(PurePosixPath("desaulniers/reliability_v2/raw/run.json.gz"))[0] == "ARCHIVE"
    assert classify(PurePosixPath("desaulniers/reliability_v2/raw/new.json.gz"), False)[0] == "REVIEW"
    assert classify(PurePosixPath("desaulniers/unknown/raw/run.json.gz"))[0] == "REVIEW"
    assert classify(PurePosixPath("desaulniers/unknown/interrupted.json.tmp"))[0] == "REMOVE_CANDIDATE"


def test_inventory_is_read_only_and_links_nearest_metadata(tmp_path):
    root = tmp_path / "results"
    campaign = root / "desaulniers" / "robustness_v3"
    raw = campaign / "raw" / "run.json.gz"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"raw evidence")
    (campaign / "protocol.json").write_text(json.dumps({"study": "frozen", "source_sha256": "abc"}))
    (campaign / "manifest.json").write_text(json.dumps({"completed_runs": 1, "planned_runs": 1}))
    (root / "unexpected.bin").write_bytes(b"unknown")
    before = {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
              for p in root.rglob("*") if p.is_file()}

    first = inventory_results(root, {"desaulniers/robustness_v3/raw/run.json.gz"})
    second = inventory_results(root, {"desaulniers/robustness_v3/raw/run.json.gz"})
    after = {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
             for p in root.rglob("*") if p.is_file()}

    assert first == second
    assert before == after
    assert [row["path"] for row in first["files"]] == sorted(before)
    raw_entry = next(row for row in first["files"] if row["path"].endswith("run.json.gz"))
    assert (raw_entry["bytes"], raw_entry["file_type"], raw_entry["git_tracked"]) == (12, "json.gz", True)
    assert raw_entry["experiment"] == "desaulniers/robustness_v3"
    assert first["experiments"][raw_entry["experiment"]]["protocol"]["source_sha256"] == "abc"
    assert first["experiments"][raw_entry["experiment"]]["manifest"]["completed_runs"] == 1
    assert first["campaigns"]["robustness_v3"]["tracked_files"] == 1
    assert next(row for row in first["files"] if row["path"] == "unexpected.bin")["disposition"] == "REVIEW"
