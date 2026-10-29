"""Cleanup must stay inside disposable, untracked results caches."""

import json
from pathlib import Path

import pytest

import scripts.maintenance.clean_generated_results as cleaner
from scripts.maintenance.clean_generated_results import apply_cleanup, plan_cleanup


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "results").mkdir()
    return tmp_path


def test_dry_run_then_apply_then_repeat(repo):
    pytest_file = repo / "results" / ".pytest_run" / "test_case" / "output.txt"
    cache_file = repo / "results" / "paper" / "__pycache__" / "module.pyc"
    evidence = repo / "results" / "paper" / "protocol.json"
    for path, data in ((pytest_file, b"test output"), (cache_file, b"cache"),
                       (evidence, b"unique evidence")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    before = [(p, p.read_bytes(), p.stat().st_mtime_ns) for p in (pytest_file, cache_file, evidence)]

    plan = plan_cleanup(repo, tracked=set())
    assert (plan["total_files"], plan["total_bytes"]) == (2, 16)
    assert [(p, p.read_bytes(), p.stat().st_mtime_ns) for p in (pytest_file, cache_file, evidence)] == before

    result = apply_cleanup(plan, repo, tracked=set())
    assert (result["total_files_removed"], result["total_bytes_removed"]) == (2, 16)
    assert result["errors"] == []
    assert not pytest_file.exists() and not cache_file.exists()
    assert evidence.read_bytes() == b"unique evidence"
    assert plan_cleanup(repo, tracked=set())["total_files"] == 0
    assert apply_cleanup(plan_cleanup(repo, tracked=set()), repo, tracked=set())["total_files_removed"] == 0


def test_cli_defaults_to_dry_run_and_requires_apply(repo, monkeypatch, capsys):
    path = repo / "results" / ".pytest_run" / "cache.txt"
    path.parent.mkdir()
    path.write_bytes(b"generated")
    monkeypatch.setattr(cleaner, "tracked_results", lambda _: set())
    cleaner.main([], repo_root=repo)
    preview = json.loads(capsys.readouterr().out)
    assert preview["mode"] == "dry_run" and preview["total_files"] == 1
    assert path.exists()
    cleaner.main(["--apply"], repo_root=repo)
    applied = json.loads(capsys.readouterr().out)
    assert applied["outcome"]["total_files_removed"] == 1
    assert not path.exists()


def test_tracked_file_rejects_entire_candidate(repo):
    path = repo / "results" / ".pytest_run" / "tracked.json"
    path.parent.mkdir()
    path.write_bytes(b"keep")
    plan = plan_cleanup(repo, tracked={"results/.pytest_run/tracked.json"})
    assert plan["candidates"] == []
    assert "Git-tracked" in plan["rejected"][0]["reason"]
    assert apply_cleanup(plan, repo, tracked=set())["total_files_removed"] == 0
    assert path.read_bytes() == b"keep"


@pytest.mark.parametrize("value", ["results/paper", "results/final/raw", "results/targeted_study",
                                        "results/../data",
                                        "data/benchmark", "../outside", "results/.pytest_run/child"])
def test_unapproved_paths_are_rejected(repo, value):
    with pytest.raises(ValueError):
        plan_cleanup(repo, requested=[value], tracked=set())


def test_changed_candidate_is_not_removed(repo):
    path = repo / "results" / ".pytest_run" / "out.txt"
    path.parent.mkdir()
    path.write_bytes(b"first")
    plan = plan_cleanup(repo, tracked=set())
    path.write_bytes(b"later data")
    outcome = apply_cleanup(plan, repo, tracked=set())
    assert outcome["total_files_removed"] == 0
    assert "changed" in outcome["errors"][0]["reason"]
    assert path.read_bytes() == b"later data"


def test_link_inside_candidate_is_rejected(repo, tmp_path):
    candidate = repo / "results" / ".pytest_run"
    candidate.mkdir()
    outside = tmp_path.parent / (tmp_path.name + "_outside.txt")
    outside.write_bytes(b"important")
    try:
        (candidate / "linked.txt").symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks unavailable on this Windows environment")
    plan = plan_cleanup(repo, tracked=set())
    assert plan["candidates"] == []
    assert "Linked" in plan["rejected"][0]["reason"]
    assert outside.read_bytes() == b"important"


def test_linked_candidate_and_parent_are_rejected(repo, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "_outside_dir")
    outside.mkdir()
    try:
        (repo / "results" / ".pytest_run").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks unavailable on this Windows environment")
    plan = plan_cleanup(repo, tracked=set())
    assert plan["candidates"] == []
    assert "Linked" in plan["rejected"][0]["reason"]
    assert outside.is_dir()


def test_junction_guard_rejects_candidate_without_link_privileges(repo, monkeypatch):
    candidate = repo / "results" / ".pytest_run"
    candidate.mkdir()
    original = cleaner._linked
    monkeypatch.setattr(cleaner, "_linked", lambda path: path == candidate or original(path))
    plan = plan_cleanup(repo, tracked=set())
    assert plan["candidates"] == []
    assert "Linked" in plan["rejected"][0]["reason"]
    assert candidate.is_dir()


def test_non_cache_tmp_evidence_is_retained(repo):
    path = repo / "results" / "final" / "raw" / "interrupted.json.tmp"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"failure evidence")
    assert plan_cleanup(repo, tracked=set())["total_files"] == 0
    assert path.read_bytes() == b"failure evidence"


def test_verification_pytest_fixtures_only(repo):
    fixture = repo / "results" / "verification" / "pytest_old" / "test_example0" / "run.json"
    report = repo / "results" / "verification" / "pytest_report.xml"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"test fixture")
    report.write_bytes(b"historical report")
    plan = plan_cleanup(repo, tracked=set())
    assert plan["total_files"] == 1
    assert apply_cleanup(plan, repo, tracked=set())["total_files_removed"] == 1
    assert not fixture.exists()
    assert report.read_bytes() == b"historical report"


def test_verification_pytest_tree_with_other_evidence_is_rejected(repo):
    tree = repo / "results" / "verification" / "pytest_old"
    tree.mkdir(parents=True)
    (tree / "protocol.json").write_bytes(b"potential evidence")
    plan = plan_cleanup(repo, tracked=set())
    assert plan["candidates"] == []
    assert "non-pytest" in plan["rejected"][0]["reason"]
    assert (tree / "protocol.json").read_bytes() == b"potential evidence"


def test_legacy_t_pytest_tree_is_removed(repo):
    fixture = repo / "results" / "t20261018full" / "test_example0" / "run.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"test fixture")
    plan = plan_cleanup(repo, tracked=set())
    assert plan["total_files"] == 1
    assert apply_cleanup(plan, repo, tracked=set())["total_files_removed"] == 1
    assert not fixture.exists()


def test_legacy_t_tree_with_research_protocol_is_rejected(repo):
    tree = repo / "results" / "t20261018full"
    tree.mkdir()
    (tree / "protocol.json").write_bytes(b"research")
    plan = plan_cleanup(repo, tracked=set())
    assert plan["candidates"] == []
    assert "non-pytest" in plan["rejected"][0]["reason"]
    assert (tree / "protocol.json").read_bytes() == b"research"


def test_readonly_empty_cache_directory_is_removed(repo):
    cache = repo / "results" / ".pytest_readonly"
    cache.mkdir()
    cache.chmod(0o555)
    plan = plan_cleanup(repo, tracked=set())
    assert plan["total_files"] == 0
    outcome = apply_cleanup(plan, repo, tracked=set())
    assert outcome["errors"] == []
    assert not cache.exists()
