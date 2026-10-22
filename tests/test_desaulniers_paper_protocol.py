"""Fast checks on the separate reporting and robustness-study design."""

from evrp.experiments import load_config
from evrp.instance import load_instance
from evrp.reference import ReferenceConfig, published_full_reference
from evrp.scenario import generate
from evrp.storage import BENCHMARK
from scripts.render_desaulniers_paper import clustered_ci
from scripts.run_desaulniers_robustness import CONFIG, METHODS, selected
from scripts.run_desaulniers_robustness_v3 import CONFIG as CONFIG_V3
import scripts.validate_desaulniers_coverage as coverage


def test_instance_cluster_bootstrap_keeps_dod_repeats_together():
    grouped = {}
    for instance, difference in (("a", 1), ("b", -1)):
        for dod in (.25, .5, .75):
            grouped[instance, dod, 0] = {
                "MPC_ALNS": {"customers_served": 50 + difference, "size": 100},
                "MPC_HGS": {"customers_served": 50, "size": 100},
            }
    assert clustered_ci(grouped, "MPC_ALNS", "MPC_HGS", draws=10000) == (-1, 1)


def test_robustness_selection_balanced_and_disjoint():
    config = load_config(CONFIG_V3)
    cases = selected(config)
    assert len(cases) == 6
    assert {r["family"] for r in cases} == {"C1", "C2", "R1", "R2", "RC1", "RC2"}
    assert sorted(r["size"] for r in cases) == [25, 25, 50, 50, 100, 100]
    assert len(cases) * len(config["dynamicities"]) * len(config["scenario_seeds"]) * len(METHODS) == 450
    for case in cases:
        instance = load_instance(BENCHMARK / f"{case['instance']}.txt")
        reference = published_full_reference(instance, ReferenceConfig())
        assert reference is not None
        assert generate(instance, reference, seed=1, dynamicity=.75).target_DoD == .75


def test_rejected_v2_preflight_is_preserved():
    config = load_config(CONFIG)
    assert selected(config)


def test_coverage_csv_accepts_checkpoint_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage, "OUTPUT", tmp_path)
    row = dict.fromkeys(coverage.FIELDS, "")
    row.update(instance="c101_21_25", family="C1", customers=25, stations=21,
               parsed=True, arcs_consistent=True, published_mp_feasible=True,
               reference_valid=True, format1_sha256="checkpoint-only")
    assert coverage.render([row])["inspected"] == 1
    assert "c101_21_25" in (tmp_path / "coverage.csv").read_text(encoding="utf-8")
