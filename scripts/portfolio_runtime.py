"""Runtime adapter for a separately trained, frozen MPC optimizer selector.

No selector trained on another benchmark may be deployed on Desaulniers data.
This module preserves the existing observable features and optimizer dispatch;
training and evaluation require a new development protocol.
"""

from contextlib import contextmanager
from dataclasses import replace
from math import isfinite
from time import perf_counter

from evrp.fleet_mcts import _FleetProblem
from evrp.optimizers import OptimizerDiagnostics


METHOD = "MPC_PORTFOLIO"
SEARCH_METHODS = ("MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS")
FEATURES = ("time_fraction", "pending", "uncovered", "zero_option", "one_option",
            "tw_pressure", "min_battery_fraction", "control_risk", "flexibility_risk")


def observable_features(context):
    problem = _FleetProblem(dict(context.origins), context.observation, context.mpc, 3, 2)
    root = problem.initial(dict(context.constructor_routes))
    ranked = problem._criticality(root.sequences)
    depot_due = context.observation.infrastructure.depot.due
    battery = context.observation.infrastructure.parameters.battery
    min_tw_slack = min((context.observation.customer_by_id[c].due -
                        context.observation.time for c in problem.pending), default=0)
    return dict(time_fraction=min(1.0, context.observation.time / max(1.0, depot_due)),
                uncovered=int(root.score[0]),
                zero_option=sum(row[1] == 0 for row in ranked),
                one_option=sum(row[1] == 1 for row in ranked),
                tw_pressure=1.0 - min(1.0, max(0.0, min_tw_slack) /
                                      max(1.0, depot_due - context.observation.time)),
                min_battery_fraction=min((state.battery / battery for state in context.origins.values()),
                                         default=1.0),
                control_risk=root.components["control_risk"],
                flexibility_risk=root.components["flexibility_risk"],
                pending=len(problem.pending))


def predict(model, features):
    node = model["tree"]
    while "method" not in node:
        value = features[node["feature"]]
        if not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError("Portfolio received invalid observable feature")
        node = node["left"] if value <= node["threshold"] else node["right"]
    if node["method"] not in SEARCH_METHODS:
        raise ValueError("Selector chose an unknown search engine")
    return node["method"]


class PortfolioOptimizer:
    name = METHOD

    def __init__(self, model, config, factory):
        self.model = model
        self.config = config
        self.factory = factory

    def optimize(self, context):
        started = perf_counter()
        features = observable_features(context)
        method = predict(self.model, features)
        result = self.factory(method, self.config).optimize(context)
        diagnostics = dict(result.diagnostics.values)
        diagnostics.update(portfolio_selected_engine=method,
                           portfolio_observable_features={key: features[key] for key in FEATURES})
        return replace(result, runtime=perf_counter() - started,
                       diagnostics=OptimizerDiagnostics(diagnostics))


@contextmanager
def portfolio_runtime(model):
    import evrp.optimizers as optimizers
    import evrp.simulator as simulator

    if (model.get("status") != "frozen_selector" or not model.get("deploy") or
            model.get("dataset") != "Desaulniers et al. 2016" or
            model.get("charging_policy") != "MP" or
            tuple(model.get("features", ())) != FEATURES):
        raise ValueError("A deployable Desaulniers MP selector is required")
    original = optimizers.create_optimizer
    for algorithms in (simulator.OPTIMIZER_ALGORITHMS,
                       simulator.COMMON_CONSTRUCTOR_ALGORITHMS, simulator.ALGORITHMS):
        algorithms.add(METHOD)

    def factory(name, config):
        if name == METHOD:
            return PortfolioOptimizer(model, config, original)
        return original(name, config)

    optimizers.create_optimizer = factory
    try:
        yield
    finally:
        optimizers.create_optimizer = original
        for algorithms in (simulator.OPTIMIZER_ALGORITHMS,
                           simulator.COMMON_CONSTRUCTOR_ALGORITHMS, simulator.ALGORITHMS):
            algorithms.discard(METHOD)
