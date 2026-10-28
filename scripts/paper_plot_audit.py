"""Capture plotted coordinates and compare them with publication tables."""

import csv
from hashlib import sha256
from pathlib import Path

from matplotlib.collections import PathCollection
import numpy as np

from evrp.storage import load_json, save_json

METHODS = ("COMPLETION", "MCTS", "ALNS", "HGS", "ACS")


def record_figure(figure, png, target):
    axes = []
    for axis in figure.axes:
        axes.append(dict(title=axis.get_title(),
                         bars=[float(patch.get_height()) for patch in axis.patches],
                         lines=[dict(label=line.get_label(), x=np.asarray(line.get_xdata()).tolist(),
                                     y=np.asarray(line.get_ydata()).tolist()) for line in axis.lines],
                         scatter=[dict(label=item.get_label(), points=np.asarray(item.get_offsets()).tolist())
                                  for item in axis.collections if isinstance(item, PathCollection)]))
    save_json(target, dict(png_sha256=sha256(Path(png).read_bytes()).hexdigest(), axes=axes))


def verify_figures(paper):
    def table(name):
        with (paper / "tables" / f"{name}.csv").open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    plots = {}
    for png in sorted((paper / "figures").glob("*.png")):
        data = load_json(paper / "audit/figure_data" / f"{png.stem}.json")
        if data["png_sha256"] != sha256(png.read_bytes()).hexdigest():
            raise ValueError(f"Figure changed after coordinate capture: {png.name}")
        plots[int(png.stem.split("_", 1)[0])] = data["axes"]

    def equal(actual, expected):
        if len(actual) != len(expected) or not np.allclose(actual, expected, rtol=0, atol=.0051):
            raise ValueError("Plotted coordinates disagree with the numerical table")

    main = {row["Method"]: row for row in table("main_five_methods")}
    for number, field in ((1, "Service %"), (2, "Complete %"),
                          (6, "Distance on common complete"), (7, "Mean worker wall s")):
        equal(plots[number][0]["bars"], [float(main[method][field]) for method in METHODS])
    for number, name, key, values in ((3, "by_size", "Size", ("25", "50", "100")),
                                      (4, "by_family", "Family", ("C1", "C2", "R1", "R2", "RC1", "RC2")),
                                      (5, "dynamism_seed", "Value", ("0.25", "0.5", "0.75"))):
        rows = table(name)
        indexed = {(row["Method"], row[key]): float(row["Service %"]) for row in rows
                   if number != 5 or row["Stratum"] == "dod"}
        equal(plots[number][0]["bars"], [indexed[method, value] for method in METHODS for value in values])
    computation = {row["Method"]: row for row in table("computational_performance") if row["Cohort"] == "primary v3"}
    ecdfs = {line["label"]: line for line in plots[8][0]["lines"]}
    for method in METHODS:
        xs, ys = np.asarray(ecdfs[method]["x"]), np.asarray(ecdfs[method]["y"])
        if not len(xs) or (np.diff(xs) < 0).any() or max(xs) > 5 + 1e-6:
            raise ValueError("Invalid plotted latency ECDF")
        equal(ys, np.arange(1, len(xs)+1)/len(xs))
        equal([xs.mean(), np.percentile(xs, 95), xs.max()],
              [float(computation[method][key]) for key in ("Decision mean s", "Decision p95 s", "Decision max s")])
    for item in plots[9][0]["scatter"]:
        equal(item["points"][0], [float(main[item["label"]][key]) for key in ("Mean worker wall s", "Service %")])
    operating = {row["Method"]: row for row in table("operational_matched_service")}
    for axis, field in zip(plots[10], ("Energy consumed", "Energy charged", "Active EVs")):
        equal(axis["bars"], [float(operating[method][field]) for method in METHODS])
    ablation = table("development_ablation")
    pairs = plots[11][0]["scatter"]
    position = 0
    for row in ablation:
        count = int(row["Pairs"])
        deltas = [item["points"][0][1] for item in pairs[position:position+count]]
        position += count
        equal([sum(deltas), sum(value > 0 for value in deltas), sum(value == 0 for value in deltas),
               sum(value < 0 for value in deltas)],
              [float(row[key]) for key in ("Service delta", "Wins", "Ties", "Losses")])
    if position != len(pairs):
        raise ValueError("Unaccounted development plot points")
    for stage, axis in enumerate(plots[12]):
        selected = ablation[stage*5:(stage+1)*5]
        equal(axis["bars"], [float(row[key]) for key in ("Wins", "Ties", "Losses") for row in selected])
    balanced = table("balanced_development_variant_summary")
    equal(plots[13][0]["bars"], [float(row["served_delta"]) for row in balanced])
    equal(plots[14][0]["bars"], [float(row["cpu_ratio_mean"]) for row in balanced if row["variant"] == "combined"])
    cached = table("cpu_six_family_summary")
    equal(plots[15][0]["bars"], [int(row["Cache served/total"].split("/")[0])-
                                int(row["Original served/total"].split("/")[0]) for row in cached])
    points = next(line for line in plots[15][1]["lines"] if len(line["y"]) == 5)
    equal(points["y"], [float(row["Cache/original CPU ratio"]) for row in cached])
    return dict(figures=len(plots), actual_coordinates_captured=True, figure_table_agreement=True,
                numerical_table_rounding_tolerance=.0051)
