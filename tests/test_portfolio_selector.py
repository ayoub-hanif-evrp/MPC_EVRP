"""The selector uses observable features and leaves the frozen MPC source alone."""

import numpy as np
import pytest

from evrp.simulator import SimulationConfig
from scripts.portfolio_selector import (FEATURES, METHOD, _cross_validate,
                                        _serialize_tree, _target, _tree,
                                        portfolio_runtime, predict)


def test_service_first_target_prefers_sbs_on_service_ties():
    runs = {"MPC_HGS": {"objective": [0, 8, 12]},
            "MPC_ALNS": {"objective": [0, 7, 10]},
            "MPC_MCTS": {"objective": [1, 5, 5]},
            "MPC_ACS": {"objective": [2, 1, 1]}}
    assert _target(runs, "MPC_HGS") == "MPC_HGS"
    runs["MPC_HGS"]["objective"][0] = 1
    assert _target(runs, "MPC_HGS") == "MPC_ALNS"


def test_serialized_tree_matches_sklearn_and_rejects_bad_features():
    matrix = np.array([[index, index % 3, 1, 0, 0, .5, .8, .1, .2]
                       for index in range(80)], dtype=float)
    labels = np.array(["MPC_HGS" if index < 40 else "MPC_ALNS" for index in range(80)])
    fitted = _tree().fit(matrix, labels)
    model = {"tree": _serialize_tree(fitted)}
    assert all(predict(model, dict(zip(FEATURES, row))) == expected
               for row, expected in zip(matrix, fitted.predict(matrix)))
    with pytest.raises(ValueError, match="invalid observable feature"):
        predict(model, dict(zip(FEATURES, [float("nan")] + list(matrix[0, 1:]))))


def test_grouped_cv_predicts_each_state_once():
    rows = []
    grouped = {}
    for group in range(4):
        for index in range(20):
            state = f"state-{group}-{index}"
            features = {key: 0. for key in FEATURES}
            features.update(time_fraction=(group * 20 + index) / 80,
                            pending=10, uncovered=1)
            rows.append(dict(state_hash=state, features=features))
            grouped[state] = {
                "MPC_HGS": {"objective": [0 if group < 2 else 1, 0, 0]},
                "MPC_ALNS": {"objective": [1 if group < 2 else 0, 0, 0]},
                "MPC_MCTS": {"objective": [2, 0, 0]},
                "MPC_ACS": {"objective": [2, 0, 0]},
            }
    matrix = np.array([[row["features"][key] for key in FEATURES] for row in rows])
    labels = np.array([_target(grouped[row["state_hash"]], "MPC_HGS") for row in rows])
    groups = np.array([index // 20 for index in range(80)])
    result = _cross_validate(rows, matrix, labels, groups, {}, grouped, "MPC_HGS")
    assert len(result["folds"]) == 4
    assert result["aggregate"]["states"] == 80
    assert sum(fold["states"] for fold in result["folds"]) == 80


def test_portfolio_adapter_registration_is_scoped():
    model = dict(status="frozen_selector", deploy=True, tree={"method": "MPC_HGS"})
    with pytest.raises(ValueError, match="Invalid simulation configuration"):
        SimulationConfig(algorithm=METHOD)
    with portfolio_runtime(model):
        assert SimulationConfig(algorithm=METHOD).algorithm == METHOD
    with pytest.raises(ValueError, match="Invalid simulation configuration"):
        SimulationConfig(algorithm=METHOD)
