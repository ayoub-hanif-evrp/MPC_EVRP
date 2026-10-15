"""No final holdout may be selected from incomplete development evidence."""

import pytest

from scripts.preregister_final_holdout import family, preregister


@pytest.mark.parametrize("name,expected", [
    ("c103_21", "C1"), ("c203_21", "C2"),
    ("r103_21", "R1"), ("r203_21", "R2"),
    ("rc103_21", "RC1"), ("rc203_21", "RC2")])
def test_schneider_family(name, expected):
    assert family(name) == expected


def test_preregistration_refuses_incomplete_development():
    with pytest.raises(ValueError, match="development comparison is not complete"):
        preregister()
