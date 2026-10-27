"""Focused checks for paired, parent-clustered paper summaries."""

import pytest

from scripts.render_final_cpu_paper import METHODS, aggregate, cluster_ci, paired


def row(parent, case, method, served, total=100):
    return dict(parent=parent, case=case, method=method,
                features=dict(served=served, total=total,
                              complete=int(served == total), wall=1.0, cpu=0.5))


def test_paired_requires_all_five_methods():
    rows = [row("c1", ("c1", .5, 1), method, 99) for method in METHODS[:-1]]
    with pytest.raises(ValueError, match="Missing method"):
        paired(rows)


def test_paired_rejects_duplicate_method():
    rows = [row("c1", ("c1", .5, 1), method, 99) for method in METHODS]
    with pytest.raises(ValueError, match="Duplicate method"):
        paired(rows + [rows[0]])


def test_cluster_bootstrap_resamples_parents_not_scenarios():
    rows = []
    for parent, mcts in (("c1", 90), ("r1", 100)):
        for seed in (1, 2, 3):
            case = (parent, .5, seed)
            for method in METHODS:
                served = mcts if method == "MPC_MCTS" else 90
                rows.append(row(parent, case, method, served))
    result = cluster_ci(paired(rows), "MPC_MCTS", "MPC_COMPLETION", seed=11)
    assert result["parents"] == 2
    assert result["scenarios"] == 6
    assert result["effect"] == 5
    assert (result["wins"], result["ties"], result["losses"]) == (3, 3, 0)
    assert result["low"] == 0
    assert result["high"] == 10


def test_customer_weighted_aggregate_uses_denominators():
    rows = [row("c1", ("a", .5, 1), "MPC_MCTS", 25, total=25),
            row("r1", ("b", .5, 1), "MPC_MCTS", 50, total=100)]
    result = aggregate(rows)
    assert result["served"] == 75
    assert result["total"] == 125
    assert result["service"] == 60
    assert result["complete_rate"] == 50
