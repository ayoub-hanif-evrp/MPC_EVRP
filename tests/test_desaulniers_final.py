"""The reserved Desaulniers holdout is disjoint and protocol-bound."""

import pytest

from evrp.experiments import load_config
from scripts import run_desaulniers_final as final


def test_final_selection_uses_only_reserved_instances():
    config = load_config(final.CONFIG)
    selected = final.selected_instances(config)
    assert len(selected) == 18
    assert len({row["instance"] for row in selected}) == 18
    assert all(row["instance"] != row["development_instance"] for row in selected)
    assert {(row["family"], row["size"]) for row in selected} == {
        (family, size) for family in config["families"] for size in config["sizes"]}


def test_final_methods_share_settings_and_five_second_budget():
    config = load_config(final.CONFIG)
    name = final.selected_instances(config)[0]["instance"]
    runs = [final.options(config, name, 0.25, 0, method) for method in config["methods"]]
    assert {row["algorithm"] for row in runs} == final.METHODS
    common = [{key: value for key, value in row.items() if key != "algorithm"}
              for row in runs]
    assert all(row == common[0] for row in common)
    assert common[0]["total_planning_time_limit"] == 5.0
    assert common[0]["fleet_mode"] == "fixed_reference"


def test_final_requires_completed_development(monkeypatch):
    monkeypatch.setattr(final, "load_json", lambda _: {"status": "development_partial"})
    with pytest.raises(ValueError, match="Development must complete"):
        final.require_completed_development()
