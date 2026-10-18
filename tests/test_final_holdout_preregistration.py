"""No final holdout may be selected from incomplete development evidence."""

import json

import pytest

import scripts.preregister_final_holdout as preregistration
import scripts.run_final_holdout as final_runner
from scripts.preregister_final_holdout import family, preregister
from scripts.run_final_holdout import run, validated_protocol
from scripts.analyze_final_holdout import analyze


@pytest.mark.parametrize("name,expected", [
    ("c103_21", "C1"), ("c203_21", "C2"),
    ("r103_21", "R1"), ("r203_21", "R2"),
    ("rc103_21", "RC1"), ("rc203_21", "RC2")])
def test_schneider_family(name, expected):
    assert family(name) == expected


def test_preregistration_refuses_incomplete_development(monkeypatch, tmp_path):
    development = tmp_path / "development"
    analysis = development / "analysis"
    analysis.mkdir(parents=True)
    (development / "manifest.json").write_text(json.dumps(dict(status="development_incomplete",
                                                               records=[])), encoding="utf-8")
    (analysis / "paired_analysis.json").write_text(json.dumps(dict(status="incomplete_development",
                                                                   scenarios=0)), encoding="utf-8")
    monkeypatch.setattr(preregistration, "DEVELOPMENT", development)
    with pytest.raises(ValueError, match="development comparison is not complete"):
        preregister()


def test_final_runner_refuses_uncommitted_or_missing_protocol(monkeypatch, tmp_path):
    monkeypatch.setattr(final_runner, "MARKDOWN", tmp_path / "missing.md")
    monkeypatch.setattr(final_runner, "JSON_OUTPUT", tmp_path / "missing.json")
    with pytest.raises(ValueError, match="has not been preregistered"):
        validated_protocol()
    with pytest.raises(ValueError, match="has not been preregistered"):
        run()
    with pytest.raises(ValueError, match="has not been preregistered"):
        analyze()
