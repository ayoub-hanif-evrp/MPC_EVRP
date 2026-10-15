"""No final holdout may be selected from incomplete development evidence."""

import pytest

from scripts.preregister_final_holdout import family, preregister
from scripts.run_final_holdout import run, validated_protocol
from scripts.analyze_final_holdout import analyze


@pytest.mark.parametrize("name,expected", [
    ("c103_21", "C1"), ("c203_21", "C2"),
    ("r103_21", "R1"), ("r203_21", "R2"),
    ("rc103_21", "RC1"), ("rc203_21", "RC2")])
def test_schneider_family(name, expected):
    assert family(name) == expected


def test_preregistration_refuses_incomplete_development():
    with pytest.raises(ValueError, match="development comparison is not complete"):
        preregister()


def test_final_runner_refuses_uncommitted_or_missing_protocol():
    with pytest.raises(ValueError, match="has not been preregistered"):
        validated_protocol()
    with pytest.raises(ValueError, match="has not been preregistered"):
        run()
    with pytest.raises(ValueError, match="has not been preregistered"):
        analyze()
