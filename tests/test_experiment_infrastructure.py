"""Future-study inspection is safe, read-only, and baseline-only."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from yaml import YAMLError

from scripts.experiments.inspect_study import BASELINE_METHODS, inspect
from scripts.experiments.paths import artifact_path, output_dir, resolve_config, study_path


@pytest.fixture
def repo(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "base.yaml").write_text("charging_mode: partial\nfleet_mode: fixed_reference\nalgorithm: OLD\n")
    (configs / "study.yaml").write_text(
        "base_controller: configs/base.yaml\n"
        "methods: [MPC_COMPLETION, MPC_MCTS, MPC_ALNS, MPC_HGS, MPC_ACS]\n"
        "charging_policy: MP\ntotal_planning_time_limit: 5.0\n"
    )
    return tmp_path


@pytest.mark.parametrize("name", ["development_v1", "pilot-2", "a", "r2c1_2026"])
def test_valid_study_names(repo, name):
    assert study_path(name, repo) == repo / "results" / "research_v2" / name


@pytest.mark.parametrize("name", ["", ".", "..", "../outside", "a/b", "a\\b", "C:evil",
                                      "/absolute", "con", "a..b", "a b", "a_", "a-", "x" * 81])
def test_invalid_study_names(repo, name):
    with pytest.raises(ValueError):
        study_path(name, repo)


def test_config_paths_are_root_relative_or_absolute(repo, monkeypatch):
    expected = repo / "configs" / "study.yaml"
    monkeypatch.chdir(repo.parent)
    assert resolve_config("configs/study.yaml", repo) == expected
    assert resolve_config(expected, repo) == expected
    for unsafe in ("../configs/study.yaml", "C:\\elsewhere\\study.yaml", "configs/../study.yaml"):
        with pytest.raises(ValueError):
            resolve_config(unsafe, repo)
    if os.name != "nt":
        with pytest.raises(ValueError):
            resolve_config("configs\\study.yaml", repo)


def test_outputs_stay_in_workspace_and_do_not_overwrite(repo):
    workspace = repo / "results" / "research_v2"
    for kind in ("baseline", "proposed", "ablations", "validation", "paper"):
        assert output_dir("study_1", kind, repo).is_relative_to(workspace)
        assert artifact_path("study_1", kind, "run.json", repo).is_relative_to(workspace)
    with pytest.raises(ValueError):
        output_dir("study_1", "../paper", repo)
    for filename in ("../run.json", "a/b", "a\\b", "NUL.json", ".hidden"):
        with pytest.raises(ValueError):
            artifact_path("study_1", "baseline", filename, repo)
    existing = workspace / "study_1" / "baseline" / "run.json"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        artifact_path("study_1", "baseline", "run.json", repo)
    assert existing.read_bytes() == b"original"


def test_linked_workspace_is_rejected(repo, tmp_path):
    (repo / "results").mkdir()
    outside = tmp_path.parent / (tmp_path.name + "_outside")
    outside.mkdir()
    try:
        (repo / "results" / "research_v2").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable")
    with pytest.raises(ValueError, match="Linked"):
        study_path("pilot", repo)


def test_config_symlink_escape_is_rejected(repo, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "_external.yaml")
    outside.write_text("methods: []\n")
    try:
        (repo / "configs" / "link.yaml").symlink_to(outside)
    except OSError:
        pytest.skip("File symlinks are unavailable")
    with pytest.raises(ValueError):
        resolve_config("configs/link.yaml", repo)


@pytest.mark.parametrize("method", sorted(BASELINE_METHODS))
def test_all_five_methods_preview_without_writes(repo, method):
    before = sorted(str(p.relative_to(repo)) for p in repo.rglob("*"))
    summary = inspect("development_v1", "configs/study.yaml", method, repo)
    after = sorted(str(p.relative_to(repo)) for p in repo.rglob("*"))
    assert before == after
    assert not (repo / "results").exists()
    assert summary["algorithm"] == {"value": method, "source": "command_line"}
    assert summary["settings"]["total_planning_time_limit"] == {"value": 5.0, "source": "study_config"}
    assert summary["settings"]["fleet_mode"] == {"value": "fixed_reference", "source": "base_controller"}
    assert summary["settings"]["sizes"] == {"value": None, "source": "not_specified"}


@pytest.mark.parametrize("method", ["UNKNOWN", "MPC_ALNS_SLAD", "MPC_ALNS_RECOVERY_V2", "mpc_alns"])
def test_nonbaseline_methods_rejected(repo, method):
    with pytest.raises(ValueError, match="five baseline"):
        inspect("development_v1", "configs/study.yaml", method, repo)


def test_method_must_be_configured(repo):
    (repo / "configs" / "study.yaml").write_text("methods: [MPC_ALNS]\n")
    with pytest.raises(ValueError, match="not listed"):
        inspect("pilot", "configs/study.yaml", "MPC_MCTS", repo)


@pytest.mark.parametrize("content", ["- not a mapping\n", "[broken\n", "null\n"])
def test_invalid_config_rejected(repo, content):
    (repo / "configs" / "study.yaml").write_text(content)
    with pytest.raises((ValueError, YAMLError)):
        inspect("pilot", "configs/study.yaml", "MPC_ALNS", repo)
    assert not (repo / "results").exists()


def test_cli_from_other_directory_is_read_only(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    command = [sys.executable, "-m", "scripts.experiments.inspect_study", "--study", "development_v1",
               "--config", "configs/desaulniers_mp_development.yaml", "--method", "MPC_ALNS"]
    result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    summary = json.loads(result.stdout)
    assert summary["algorithm"]["value"] == "MPC_ALNS"
    assert summary["settings"]["total_planning_time_limit"]["value"] == 5.0
    assert summary["outputs"]["baseline"].startswith(str(root / "results" / "research_v2"))
    assert not (root / "results" / "research_v2" / "development_v1").exists()
