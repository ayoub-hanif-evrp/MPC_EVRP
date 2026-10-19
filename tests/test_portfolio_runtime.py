"""The optional selector cannot silently reuse the Schneider-trained model."""

import pytest

from evrp.simulator import SimulationConfig
from scripts.portfolio_runtime import FEATURES, METHOD, portfolio_runtime, predict


def test_tree_prediction_uses_observable_features_only():
    model = {"tree": {"feature": "time_fraction", "threshold": 0.5,
                      "left": {"method": "MPC_ALNS"},
                      "right": {"method": "MPC_HGS"}}}
    features = dict.fromkeys(FEATURES, 0.0)
    assert predict(model, features) == "MPC_ALNS"
    features["time_fraction"] = 0.7
    assert predict(model, features) == "MPC_HGS"
    features["time_fraction"] = float("nan")
    with pytest.raises(ValueError, match="invalid observable feature"):
        predict(model, features)


def test_portfolio_registration_requires_new_dataset_model_and_is_scoped():
    model = dict(status="frozen_selector", deploy=True, tree={"method": "MPC_HGS"},
                 features=list(FEATURES), dataset="Desaulniers et al. 2016",
                 charging_policy="MP")
    with pytest.raises(ValueError, match="Invalid simulation configuration"):
        SimulationConfig(algorithm=METHOD)
    with pytest.raises(ValueError, match="Desaulniers MP selector"):
        with portfolio_runtime(dict(model, dataset="Schneider")):
            pass
    with portfolio_runtime(model):
        assert SimulationConfig(algorithm=METHOD).algorithm == METHOD
    with pytest.raises(ValueError, match="Invalid simulation configuration"):
        SimulationConfig(algorithm=METHOD)
