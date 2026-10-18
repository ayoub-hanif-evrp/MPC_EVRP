"""Train a frozen, observable-state selector after the shadow gate passes."""

from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from time import perf_counter

import numpy as np

from evrp.optimizers import OptimizerDiagnostics
from evrp.storage import ROOT, load_json
from scripts.run_portfolio_campaign import source_hash
from scripts.shadow_portfolio import (_features, _payload, OUTPUT as SHADOW,
                                      SEARCH_METHODS, snapshot_protocol_hash)


OUTPUT = ROOT / "results" / "portfolio" / "selector"
MODEL = OUTPUT / "model.json"
CV = OUTPUT / "grouped_cv.json"
DECISION = OUTPUT / "DECISION.md"
METHOD = "MPC_PORTFOLIO"
FEATURES = ("time_fraction", "pending", "uncovered", "zero_option", "one_option",
            "tw_pressure", "min_battery_fraction", "control_risk", "flexibility_risk")
MAX_DEPTH = 3
MIN_LEAF = 15


def selector_sha256():
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8"))


def _committed_bytes(path):
    import subprocess

    relative = path.relative_to(ROOT).as_posix()
    committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
    if committed != path.read_bytes():
        raise ValueError(f"Frozen artifact differs byte-for-byte from HEAD: {relative}")
    return committed


def shadow_training_data():
    selection_path = SHADOW / "selection.json"
    gate_path = SHADOW / "sbs_vbs_gate.json"
    selection = load_json(selection_path)
    gate = load_json(gate_path)
    manifest = load_json(SHADOW / "manifest.json")
    if (selection["status"] != "frozen_selection" or
            selection["scenario_count"] != 66 or
            selection["snapshot_count"] != 396 or
            selection["source_sha256"] != source_hash() or
            selection["snapshot_protocol_sha256"] != snapshot_protocol_hash() or
            manifest["status"] != "shadow_complete" or
            manifest["source_sha256"] != source_hash() or
            manifest["selection_sha256"] != sha256(_committed_bytes(selection_path)).hexdigest() or
            gate["snapshots"] != 396 or not gate["portfolio_gate_passed"] or
            not gate["vbs_is_analysis_only"]):
        raise ValueError("Complete committed PASS-gate shadow evidence required")
    _committed_bytes(gate_path)
    snapshots = {row["state_hash"]: row for row in selection["snapshots"]}
    grouped = {key: {} for key in snapshots}
    for row in manifest["rows"]:
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Shadow raw SHA-256 mismatch")
        raw = load_json(path)
        if (row["snapshot_hash"] not in grouped or row["method"] not in SEARCH_METHODS or
                row["method"] in grouped[row["snapshot_hash"]] or
                not raw["audit_pass"] or raw["snapshot_hash"] != row["snapshot_hash"] or
                raw["method"] != row["method"] or raw["objective"] != row["objective"] or
                raw["source_sha256"] != source_hash() or
                raw["selection_sha256"] != manifest["selection_sha256"]):
            raise ValueError("Unpaired, stale, or unaudited shadow outcome")
        grouped[row["snapshot_hash"]][row["method"]] = raw
    if len(manifest["rows"]) != 396 * len(SEARCH_METHODS) or any(
            set(runs) != set(SEARCH_METHODS) for runs in grouped.values()):
        raise ValueError("Selector requires 396 fully paired shadow states")
    return selection, gate, manifest, snapshots, grouped


def _matrix(snapshots):
    rows = list(snapshots.values())
    values = np.array([[row["features"][name] for name in FEATURES] for row in rows], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Non-finite observable feature")
    return rows, values


def _target(runs, sbs):
    best_service = min(row["objective"][0] for row in runs.values())
    winners = [method for method, row in runs.items() if row["objective"][0] == best_service]
    if sbs in winners:
        return sbs
    return min(winners, key=lambda method: (tuple(runs[method]["objective"]), method))


def _tree():
    from sklearn.tree import DecisionTreeClassifier

    return DecisionTreeClassifier(max_depth=MAX_DEPTH, min_samples_leaf=MIN_LEAF,
                                  random_state=0)


def _score_predictions(rows, predicted, snapshots, grouped, sbs):
    selected = 0
    baseline = 0
    oracle = 0
    wins = losses = ties = 0
    choices = {method: 0 for method in SEARCH_METHODS}
    for row, method in zip(rows, predicted):
        runs = grouped[row["state_hash"]]
        pending = row["features"]["pending"]
        served = pending - runs[method]["objective"][0]
        sbs_served = pending - runs[sbs]["objective"][0]
        best_served = pending - min(raw["objective"][0] for raw in runs.values())
        selected += served
        baseline += sbs_served
        oracle += best_served
        choices[method] += 1
        wins += served > sbs_served
        losses += served < sbs_served
        ties += served == sbs_served
    return dict(states=len(rows), planned_service=selected, sbs_planned_service=baseline,
                vbs_planned_service=oracle, gain_over_sbs=selected - baseline,
                regret_to_vbs=oracle - selected, service_wins=wins,
                service_ties=ties, service_losses=losses, selected_counts=choices)


def _cross_validate(rows, matrix, labels, groups, snapshots, grouped, sbs):
    from sklearn.model_selection import LeaveOneGroupOut

    heldout = [None] * len(rows)
    folds = []
    for train, test in LeaveOneGroupOut().split(matrix, labels, groups):
        model = _tree().fit(matrix[train], labels[train])
        predicted = model.predict(matrix[test])
        for index, method in zip(test, predicted):
            if heldout[index] is not None:
                raise ValueError("CV assigned one state twice")
            heldout[index] = str(method)
        fold = _score_predictions([rows[index] for index in test], predicted,
                                  snapshots, grouped, sbs)
        fold["heldout_group"] = str(groups[test[0]])
        folds.append(fold)
    if any(value is None for value in heldout):
        raise ValueError("CV did not predict every frozen state")
    return dict(folds=folds, aggregate=_score_predictions(
        rows, heldout, snapshots, grouped, sbs))


def _serialize_tree(model, node=0):
    tree = model.tree_
    if tree.children_left[node] == tree.children_right[node]:
        return {"method": str(model.classes_[int(np.argmax(tree.value[node][0]))])}
    return dict(feature=FEATURES[int(tree.feature[node])],
                threshold=float(tree.threshold[node]),
                left=_serialize_tree(model, int(tree.children_left[node])),
                right=_serialize_tree(model, int(tree.children_right[node])))


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


def train():
    if any(path.exists() for path in (MODEL, CV, DECISION)):
        raise FileExistsError("Selector already frozen; do not retrain after inspection")
    selection, gate, manifest, snapshots, grouped = shadow_training_data()
    rows, matrix = _matrix(snapshots)
    sbs = gate["sbs"]
    labels = np.array([_target(grouped[row["state_hash"]], sbs) for row in rows])
    scenarios = np.array([row["scenario_id"] for row in rows])
    instances = np.array([row["instance_sha256"] for row in rows])
    scenario_cv = _cross_validate(rows, matrix, labels, scenarios, snapshots, grouped, sbs)
    instance_cv = _cross_validate(rows, matrix, labels, instances, snapshots, grouped, sbs)
    deploy = (scenario_cv["aggregate"]["gain_over_sbs"] > 0 and
              instance_cv["aggregate"]["gain_over_sbs"] > 0)
    fitted = _tree().fit(matrix, labels)
    model = dict(status="frozen_selector", deploy=deploy, method=METHOD,
                 base_source_sha256=source_hash(), selector_source_sha256=selector_sha256(),
                 shadow_selection_sha256=sha256((SHADOW / "selection.json").read_bytes()).hexdigest(),
                 shadow_manifest_sha256=sha256((SHADOW / "manifest.json").read_bytes()).hexdigest(),
                 shadow_gate_sha256=sha256((SHADOW / "sbs_vbs_gate.json").read_bytes()).hexdigest(),
                 features=list(FEATURES), sbs=sbs, max_depth=MAX_DEPTH,
                 min_samples_leaf=MIN_LEAF, training_states=len(rows), tree=_serialize_tree(fitted))
    if any(predict(model, row["features"]) != str(expected)
           for row, expected in zip(rows, fitted.predict(matrix))):
        raise AssertionError("Serialized selector differs from trained tree")
    cv = dict(status="complete_grouped_cv", selector_source_sha256=selector_sha256(),
              base_source_sha256=source_hash(), training_states=len(rows),
              rule="Deploy only if both scenario- and instance-held-out aggregate service gains over SBS are positive",
              scenario_grouped=scenario_cv, instance_grouped=instance_cv,
              deploy=deploy)
    _write_json(CV, cv)
    _write_json(MODEL, model)
    lines = ["# Frozen state-aware selector decision", "",
             "A depth-3 decision tree with minimum leaf size 15 uses nine observable MPC-state features.",
             "Tied best-service labels prefer the frozen SBS, MPC + HGS. No final holdout state was used.", "",
             "| Grouped validation | States | Planned service | SBS service | Gain | Wins/Ties/Losses |",
             "| --- | ---: | ---: | ---: | ---: | --- |"]
    for label, result in (("Held-out scenario", scenario_cv["aggregate"]),
                          ("Held-out instance", instance_cv["aggregate"])):
        lines.append(f"| {label} | {result['states']} | {result['planned_service']} | "
                     f"{result['sbs_planned_service']} | {result['gain_over_sbs']} | "
                     f"{result['service_wins']}/{result['service_ties']}/{result['service_losses']} |")
    lines += ["", f"Portfolio deployment: **{'YES' if deploy else 'NO'}**.",
              "The VBS remains analysis-only; grouped CV determines deployment without tuning the four engines.", ""]
    DECISION.write_bytes("\n".join(lines).encode("utf-8"))
    return cv, model


class PortfolioOptimizer:
    name = METHOD

    def __init__(self, model, config, factory):
        self.model = model
        self.config = config
        self.factory = factory

    def optimize(self, context):
        started = perf_counter()
        features = _features(_payload(context))
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

    if model["status"] != "frozen_selector" or not model["deploy"]:
        raise ValueError("Only a deployable frozen selector may run")
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


if __name__ == "__main__":
    result, model = train()
    print("portfolio_deploy", model["deploy"],
          "scenario_cv_gain", result["scenario_grouped"]["aggregate"]["gain_over_sbs"],
          "instance_cv_gain", result["instance_grouped"]["aggregate"]["gain_over_sbs"])
