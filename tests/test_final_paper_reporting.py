"""Paper renderer contracts without opening the preregistered holdout."""

from itertools import combinations

from PIL import Image
import pytest

import scripts.render_final_paper as paper


def test_oriented_comparison_preserves_paired_direction():
    row = dict(service_diff=-2, service_ci=[-3, -1], service_wins=1,
               service_ties=2, service_losses=3, complete_rate_diff=-.25,
               ev_diff_equal_service=1.5, distance_diff_equal_service_ev=-4)
    result = paper.oriented({("MPC_COMPLETION", "MPC_MCTS"): row},
                            "MPC_MCTS", "MPC_COMPLETION")
    assert result["service_diff"] == 2
    assert result["service_ci"] == [1, 3]
    assert (result["service_wins"], result["service_ties"], result["service_losses"]) == (3, 2, 1)
    assert result["ev_diff_equal_service"] == -1.5
    assert result["distance_diff_equal_service_ev"] == 4


def test_shadow_wins_are_from_identical_state_objectives():
    methods = paper.SEARCH_METHODS
    shadow = {
        "unique": {methods[0]: {"objective": [0, 3, 9]},
                   methods[1]: {"objective": [1, 1, 1]},
                   methods[2]: {"objective": [2, 1, 1]},
                   methods[3]: {"objective": [2, 1, 1]}},
        "tie": {methods[0]: {"objective": [0, 3, 9]},
                methods[1]: {"objective": [0, 2, 9]},
                methods[2]: {"objective": [1, 1, 1]},
                methods[3]: {"objective": [1, 1, 1]}},
    }
    wins = paper.shadow_win_counts(shadow)
    assert wins[methods[0]]["unique"] == 1
    assert wins[methods[0]]["tied"] == 1
    assert wins[methods[1]]["canonical_at_tied_service"] == 1
    assert wins[methods[2]]["unique"] == 0


def test_renderer_refuses_unregistered_holdout(monkeypatch, tmp_path):
    monkeypatch.setattr(paper, "PAPER", tmp_path / "paper")
    monkeypatch.setattr(paper, "validated_protocol",
                        lambda: (_ for _ in ()).throw(ValueError("not preregistered")))
    with pytest.raises(ValueError, match="not preregistered"):
        paper.render()
    assert not (tmp_path / "paper").exists()


def test_paper_outputs_are_png_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "PAPER", tmp_path)
    protocol_path = tmp_path / "PRE_REGISTERED_PROTOCOL.json"
    protocol_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paper, "JSON_OUTPUT", protocol_path)
    (tmp_path / "figures").mkdir()
    (tmp_path / "tables").mkdir()
    methods = paper.ORDER
    grouped = {}
    for family in paper.FAMILIES:
        for dod in (.25, .5, .75):
            for seed in range(3):
                grouped[(f"synthetic_{family}", dod, seed)] = {
                    method: dict(customers_served=90 + index, complete_service=False)
                    for index, method in enumerate(methods)}
    scopes = ["overall"] + [f"family_{family}" for family in paper.FAMILIES] + [
        f"dod_{dod:.2f}" for dod in (.25, .5, .75)]
    service = [dict(scope=scope, method=method,
                    mean_customers_served=90 + index, complete_service_rate=0)
               for scope in scopes for index, method in enumerate(methods)]
    comparisons = [dict(scope="overall", left=left, right=right,
                        service_diff=methods.index(left) - methods.index(right),
                        service_ci=[methods.index(left) - methods.index(right) - .5,
                                    methods.index(left) - methods.index(right) + .5],
                        service_wins=0, service_ties=0, service_losses=54,
                        complete_rate_diff=0, equal_service_n=0,
                        ev_diff_equal_service=None, equal_service_ev_n=0,
                        distance_diff_equal_service_ev=None)
                   for left, right in combinations(methods, 2)]
    runtime = [dict(method=method, mean_decision_seconds=1 + index * .2,
                    p95_decision_seconds=2 + index * .2, max_decision_seconds=3 + index * .2)
               for index, method in enumerate(methods)]
    report = dict(scenarios=54, records=270, service=service, comparisons=comparisons, runtime=runtime,
                  mechanism_summary=[], operator_summary=[])
    protocol = dict(methods=list(methods), dynamicity=[.25, .5, .75],
                    source_sha256="synthetic-source")
    shadow = dict(snapshots=264, sbs="MPC_MCTS", sbs_planned_customers_served=23000,
                  vbs_planned_customers_served=23100, vbs_minus_sbs_served=100,
                  vbs_service_win_fraction=.1, portfolio_gate_passed=False)
    wins = {method: dict(unique=1, tied=2, canonical_at_tied_service=1)
            for method in paper.SEARCH_METHODS}
    overall, runtimes, pairs, summary, operators = paper.write_tables(
        report, protocol, grouped, shadow, wins)
    paper.write_figures(report, protocol, overall, runtimes, pairs, summary,
                        operators, shadow, wins,
                        {method: [1., 2., 3.] for method in methods}, [0, 1, 2])
    paper.write_results(report, protocol, overall, runtimes, pairs, shadow, wins)
    figures = list((tmp_path / "figures").iterdir())
    tables = list((tmp_path / "tables").iterdir())
    assert len(figures) == 9 and all(path.suffix == ".png" for path in figures)
    assert len(tables) == 10 and all(path.suffix == ".md" for path in tables)
    for path in figures:
        with Image.open(path) as image:
            assert image.size[0] > 1000
            assert image.info["dpi"][0] >= 299
    completion = (tmp_path / "tables" / "table3_vs_completion.md").read_text()
    assert "MPC + ACS - MPC + Completion | 4.00 | [3.50, 4.50]" in completion
    results = (tmp_path / "RESULTS.md").read_text()
    assert "## 11. Final conclusions from the holdout" in results
    assert "figures/fig9_mcts_mechanisms.png" in results
