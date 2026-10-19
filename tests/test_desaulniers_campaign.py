"""The larger development design is paired and leaves a separate holdout."""

from evrp.experiments import load_config
from evrp.storage import ROOT
from scripts.run_desaulniers_campaign import CONFIG, METHODS, options, selected_instances


def test_development_design_is_frozen_and_separate_from_holdout():
    config = load_config(CONFIG)
    selected = selected_instances(config)
    assert len(selected) == 18
    assert {(case["family"], case["size"]) for case in selected} == {
        (family, size) for family in config["families"] for size in (25, 50, 100)}
    assert all(case["instance"] != case["reserved_untouched"] for case in selected)
    assert len({case["reserved_untouched"] for case in selected}) == 18
    assert set(config["methods"]) == METHODS
    assert set(config["dynamicities"]) == {0.25, 0.5, 0.75}
    assert config["scenario_seeds"] == [0]
    assert (ROOT / config["base_controller"]).is_file()


def test_methods_share_controller_and_budget():
    config = load_config(CONFIG)
    name = selected_instances(config)[0]["instance"]
    runs = [options(config, name, 0.25, 0, method) for method in config["methods"]]
    assert {row["algorithm"] for row in runs} == METHODS
    common = [{key: value for key, value in row.items() if key != "algorithm"}
              for row in runs]
    assert all(row == common[0] for row in common)
    assert common[0]["total_planning_time_limit"] == 5.0
    assert common[0]["fleet_mode"] == "fixed_reference"
