import pytest
import yaml

from scripts.run_publication_campaign import configuration, options


def design(**overrides):
    return dict(study="test", output="results/desaulniers/publication_development/test",
                cases=[["r101_21_25", .75, 0]], methods=["MPC_ALNS"],
                variants={"original": overrides})


def test_publication_variant_cannot_change_physical_or_scenario_parameters(tmp_path):
    for override in ({"dynamicity": .25}, {"total_planning_time_limit": 10},
                     {"fleet_mode": "unlimited"}, {"algorithm": "MPC_ACS"}):
        path = tmp_path / "design.yaml"
        path.write_text(yaml.safe_dump(design(**override)), encoding="utf-8")
        with pytest.raises(ValueError, match="physical, release, fleet or budget"):
            configuration(path)


def test_publication_variants_retain_five_second_limit():
    config = design(planning_trace=True)
    run = options(config, config["cases"][0], "MPC_ALNS", "original")
    assert run["total_planning_time_limit"] == 5.0
    assert run["algorithm"] == "MPC_ALNS"
    assert run["dynamicity"] == .75


def test_publication_campaign_rejects_duplicate_methods(tmp_path):
    config = design()
    config["methods"] *= 2
    path = tmp_path / "design.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="design"):
        configuration(path)
