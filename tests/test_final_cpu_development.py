"""The exploratory ablation must preserve the common controller contract."""

from dataclasses import asdict

from evrp.experiments import load_config, simulation_config
from scripts.run_final_cpu_development import (ABLATION_CASES, CONFIG, VARIANTS,
                                               run_options)
from scripts.run_desaulniers_pilot import family_of


def test_fixed_balanced_grid():
    config = load_config(CONFIG)
    assert len(config["instances"]) == 6
    assert {family_of(name) for name in config["instances"]} == {
        "C1", "C2", "R1", "R2", "RC1", "RC2"}
    assert sorted(int(name.rsplit("_", 1)[1]) for name in config["instances"]) == [
        25, 25, 50, 50, 100, 100]
    assert ABLATION_CASES == {0, 2, 4}
    assert set(VARIANTS) == {"original", "recovery", "first_action", "quality", "cpu", "combined"}
    assert 6 * 5 * 2 + len(ABLATION_CASES) * 5 * 4 == 120


def test_variants_keep_common_physics_and_budget():
    config = load_config(CONFIG)
    name = config["instances"][0]
    method = "MPC_ALNS"
    baseline = asdict(simulation_config(run_options(config, name, method, "original")))
    mutable = {"constructor_policy", "service_recovery_policy", "first_action_policy",
               "quality_policy", "proposal_cache_policy"}
    for variant in VARIANTS:
        other = asdict(simulation_config(run_options(config, name, method, variant)))
        assert {key for key in baseline if baseline[key] != other[key]} <= mutable
        assert other["total_planning_time_limit"] == 5.0
        assert other["algorithm"] == method
