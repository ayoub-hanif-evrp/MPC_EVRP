"""Render paper-ready Markdown and PNGs only from the audited final holdout."""

from collections import defaultdict
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evrp.storage import ROOT, load_json
from scripts.analyze_final_holdout import analyze as analyze_final
from scripts.portfolio_selector import CV as SELECTOR_CV
from scripts.preregister_final_holdout import JSON_OUTPUT
from scripts.run_final_holdout import OUTPUT, validated_protocol
from scripts.shadow_portfolio import OUTPUT as SHADOW, SEARCH_METHODS, summarize_shadow


PAPER = OUTPUT / "paper"
ORDER = ("MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS")
COLORS = {
    "MPC_COMPLETION": "#59636e", "MPC_MCTS": "#2474a6",
    "MPC_ALNS": "#12806a", "MPC_HGS": "#bd7b13",
    "MPC_ACS": "#a14851", "MPC_PORTFOLIO": "#755199",
}
FAMILIES = ("C1", "C2", "R1", "R2", "RC1", "RC2")
POLICIES = ("CRITICAL_REGRET", "EARLIEST_DEADLINE", "RESERVE_PRESERVING")


def label(method):
    return "MPC + " + method.removeprefix("MPC_").replace("COMPLETION", "Completion").replace(
        "PORTFOLIO", "Portfolio")


def fmt(value, places=2):
    return "NA" if value is None else f"{value:.{places}f}"


def pct(value):
    return f"{100 * value:.1f}%"


def pp(value):
    return f"{100 * value:+.1f} pp"


def ci(values):
    return f"[{fmt(values[0])}, {fmt(values[1])}]"


def table(path, title, headers, rows, note=""):
    lines = [f"# {title}", "", "| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    if note:
        lines += ["", note]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save(fig, path):
    fig.savefig(path, dpi=320, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def comparisons(report):
    return {(row["left"], row["right"]): row for row in report["comparisons"]
            if row["scope"] == "overall"}


def oriented(rows, left, right):
    if (left, right) in rows:
        return rows[left, right]
    row = rows[right, left]
    return dict(row, service_diff=-row["service_diff"],
                service_ci=[-row["service_ci"][1], -row["service_ci"][0]],
                service_wins=row["service_losses"],
                service_losses=row["service_wins"],
                complete_rate_diff=-row["complete_rate_diff"],
                ev_diff_equal_service=(-row["ev_diff_equal_service"] if
                                       row["ev_diff_equal_service"] is not None else None),
                distance_diff_equal_service_ev=(
                    -row["distance_diff_equal_service_ev"] if
                    row["distance_diff_equal_service_ev"] is not None else None))


def audit_paper_inputs(protocol, manifest, shadow_manifest):
    methods = tuple(protocol["methods"])
    if methods[:5] != ORDER or set(methods) - set(COLORS):
        raise ValueError("Unexpected final method ordering")
    grouped = defaultdict(dict)
    latencies = defaultdict(list)
    mcts_gains = []
    for row in manifest["records"]:
        raw_path = ROOT / row["raw"]
        if sha256(raw_path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError(f"Final raw hash mismatch: {raw_path}")
        raw = load_json(raw_path)
        if raw["metadata"]["number_of_customers"] != 100:
            raise ValueError("Paper service rates require 100-customer instances")
        for decision in raw["decisions"]:
            elapsed = decision.get("optimization_latency_seconds")
            if elapsed is not None:
                latencies[row["method"]].append(elapsed)
            if (row["method"] == "MPC_MCTS" and
                    (decision.get("optimizer") or {}).get("diagnostics") and
                    decision.get("constructor_service") is not None and
                    decision.get("best_service_after_search") is not None):
                mcts_gains.append(max(0, decision["best_service_after_search"] -
                                      decision["constructor_service"]))
        key = (row["instance"], row["dynamicity"], row["scenario_seed"])
        grouped[key][row["method"]] = row
    if len(grouped) != 54 or any(set(runs) != set(methods) for runs in grouped.values()):
        raise ValueError("Paper results require 54 fully paired final scenarios")
    shadow_rows = defaultdict(dict)
    for row in shadow_manifest["rows"]:
        path = ROOT / row["raw"]
        if sha256(path.read_bytes()).hexdigest() != row["raw_sha256"]:
            raise ValueError("Shadow raw hash mismatch")
        raw = load_json(path)
        if not raw["audit_pass"] or raw["snapshot_hash"] != row["snapshot_hash"]:
            raise ValueError("Unaudited shadow result")
        shadow_rows[row["snapshot_hash"]][row["method"]] = raw
    if (len(shadow_rows) != len(shadow_manifest["rows"]) // len(SEARCH_METHODS) or
            any(set(runs) != set(SEARCH_METHODS) for runs in shadow_rows.values())):
        raise ValueError("Paper shadow outcomes are not fully paired")
    return grouped, shadow_rows, latencies, mcts_gains


def shadow_win_counts(shadow_rows):
    counts = {method: dict(unique=0, tied=0, canonical_at_tied_service=0)
              for method in SEARCH_METHODS}
    for runs in shadow_rows.values():
        best_service = min(row["objective"][0] for row in runs.values())
        service_winners = [method for method, row in runs.items()
                           if row["objective"][0] == best_service]
        if len(service_winners) == 1:
            counts[service_winners[0]]["unique"] += 1
        else:
            for method in service_winners:
                counts[method]["tied"] += 1
            best_objective = min(tuple(runs[method]["objective"])
                                 for method in service_winners)
            canonical = [method for method in service_winners
                         if tuple(runs[method]["objective"]) == best_objective]
            if len(canonical) == 1:
                counts[canonical[0]]["canonical_at_tied_service"] += 1
    return counts


def write_tables(report, protocol, grouped, shadow, wins, selector_cv=None):
    out = PAPER / "tables"
    methods = tuple(protocol["methods"])
    overall = {row["method"]: row for row in report["service"] if row["scope"] == "overall"}
    runtime = {row["method"]: row for row in report["runtime"]}
    pairs = comparisons(report)
    portfolio_note = ""
    if "MPC_PORTFOLIO" in methods:
        best_fixed = max(SEARCH_METHODS,
                         key=lambda method: overall[method]["mean_customers_served"])
        row = oriented(pairs, best_fixed, "MPC_PORTFOLIO")
        portfolio_note = (f" Observed best fixed method {label(best_fixed)} minus Portfolio: "
                          f"{fmt(row['service_diff'])} customers per scenario "
                          f"(95% paired bootstrap CI {ci(row['service_ci'])}; "
                          f"W/T/L {row['service_wins']}/{row['service_ties']}/"
                          f"{row['service_losses']}).")
    table(out / "table1_common_mpc.md", "Common event-triggered MPC architecture",
          ("Method", "MPC controller", "Search engine", "Common constructor",
           "Released-only information", "Exact EV decoder", "Decision budget"),
          [(label(method), "Event-triggered", "State-aware selector" if method ==
            "MPC_PORTFOLIO" else method.removeprefix("MPC_") if method !=
            "MPC_COMPLETION" else "None", "Yes", "Yes; audited", "Yes; audited",
            "5 s") for method in methods],
          "All rows use the frozen common controller and the same 100-customer final scenarios.")

    best_served = max(overall[method]["mean_customers_served"] for method in methods)
    table(out / "table2_final_overall_results.md", "Final holdout overall results",
          ("Method", "Customers served, mean (total)", "Service rate",
           "Complete scenarios", "Complete-service rate", "Mean decision latency (s)",
           "p95 latency (s)", "Max latency (s)"),
          [(label(method), ("**" if overall[method]["mean_customers_served"] == best_served else "") +
            f"{overall[method]['mean_customers_served']:.2f} "
            f"({sum(runs[method]['customers_served'] for runs in grouped.values())})" +
            ("**" if overall[method]["mean_customers_served"] == best_served else ""),
            pct(overall[method]["mean_customers_served"] / 100),
            sum(runs[method]["complete_service"] for runs in grouped.values()),
            pct(overall[method]["complete_service_rate"]),
            fmt(runtime[method]["mean_decision_seconds"], 3),
            fmt(runtime[method]["p95_decision_seconds"], 3),
            fmt(runtime[method]["max_decision_seconds"], 3)) for method in methods],
          "54 paired 100-customer scenarios. Bold marks the highest mean customers served; ties share bold."
          + portfolio_note)

    table(out / "table3_vs_completion.md", "Final paired gains over MPC + Completion",
          ("Comparison", "Mean Delta served", "95% bootstrap CI", "Wins", "Ties", "Losses",
           "Delta complete-service rate"),
          [(f"{label(method)} - MPC + Completion", fmt((row := oriented(pairs, method,
            "MPC_COMPLETION"))["service_diff"]), ci(row["service_ci"]), row["service_wins"],
            row["service_ties"], row["service_losses"], pp(row["complete_rate_diff"]))
           for method in methods if method != "MPC_COMPLETION"],
          "Positive Delta served favors the optimizer. Percent-point differences are shown for complete service.")

    search_pairs = list(combinations(SEARCH_METHODS, 2))
    table(out / "table4_optimizer_pairwise.md", "Final search-engine comparisons within MPC",
          ("Comparison (left - right)", "Mean Delta served", "95% bootstrap CI", "W/T/L",
           "Complete-rate difference"),
          [(f"{label(left)} - {label(right)}", fmt((row := oriented(pairs, left,
            right))["service_diff"]), ci(row["service_ci"]),
            f"{row['service_wins']}/{row['service_ties']}/{row['service_losses']}",
            pp(row["complete_rate_diff"])) for left, right in search_pairs],
          "Positive Delta favors the left method. All comparisons are paired across the same 54 scenarios.")

    all_pairs = [(method, "MPC_COMPLETION") for method in methods if method !=
                 "MPC_COMPLETION"] + search_pairs
    if "MPC_PORTFOLIO" in methods:
        all_pairs += [("MPC_PORTFOLIO", method) for method in SEARCH_METHODS]
    table(out / "table5_conditional_efficiency.md", "Conditional fleet and distance efficiency",
          ("Comparison (left - right)", "Equal-service scenarios n",
           "Delta EVs at equal service", "Equal-service + equal-EV scenarios n",
           "Delta distance at equal service/equal EV"),
          [(f"{label(left)} - {label(right)}", (row := oriented(pairs, left,
            right))["equal_service_n"], fmt(row["ev_diff_equal_service"]),
            row["equal_service_ev_n"], fmt(row["distance_diff_equal_service_ev"]))
           for left, right in all_pairs],
          "Negative conditional Delta favors the left method. Distance is compared only when service and EV count tie; NA means no eligible pair.")

    service = {(row["scope"], row["method"]): row for row in report["service"]}
    table(out / "table6_by_dynamicity.md", "Final results by degree of dynamicity",
          ("DoD", "Method", "Mean served", "Service rate", "Complete-service rate"),
          [(f"{dod:.2f}", label(method), fmt((row := service[f"dod_{dod:.2f}",
            method])["mean_customers_served"]), pct(row["mean_customers_served"] / 100),
            pct(row["complete_service_rate"])) for dod in protocol["dynamicity"]
           for method in methods])
    table(out / "table7_by_family.md", "Final results by Schneider family",
          ("Family", "Method", "Mean served", "Service rate", "Complete-service rate"),
          [(family, label(method), fmt((row := service[f"family_{family}",
            method])["mean_customers_served"]), pct(row["mean_customers_served"] / 100),
            pct(row["complete_service_rate"])) for family in FAMILIES for method in methods])

    summary = {row["metric"]: row for row in report["mechanism_summary"]
               if row["scope"] == "overall" and row["method"] == "MPC_MCTS"}
    operators = {(row["diagnostic"], row["label"]): row["total"]
                 for row in report["operator_summary"]
                 if row["scope"] == "overall" and row["method"] == "MPC_MCTS"}
    calls = max((row["calls"] for row in summary.values()), default=0)
    metrics = ["iterations", "nodes_expanded", "service_improvements",
               "objective_only_improvements", "service_gain_over_constructor",
               "exact_decoded_options", "ejection_chains_generated",
               "ejection_chains_selected"]
    mechanism_rows = [("MCTS calls", calls)] + [(name.replace("_", " ").title(),
                       fmt(summary[name]["total"], 0) if name in summary else "NA")
                      for name in metrics]
    mechanism_rows += [("KEEP_CONSTRUCTOR selections",
                        fmt(operators.get(("root_control_selection", "KEEP_CONSTRUCTOR"), 0), 0)),
                       ("Alternative-root-control selections",
                        fmt(operators.get(("root_control_selection", "OTHER_CONTROL"), 0), 0))]
    mechanism_rows += [(f"{name.replace('_', ' ').title()} rollout usage",
                        fmt(operators.get(("rollout_policy_usage", name), 0), 0))
                       for name in POLICIES]
    mechanism_rows += [(f"{name.replace('_', ' ').title()} rollout improvements",
                        fmt(operators.get(("rollout_policy_improvements", name), 0), 0))
                       for name in POLICIES]
    table(out / "table8_mcts_mechanisms.md", "MCTS mechanism diagnostics on final holdout",
          ("Metric", "Total"), mechanism_rows,
          "Counts are summed over instrumented MCTS optimizer calls. Policy-specific rollout improvements include service and objective-only gains; the frozen trace does not split these by policy. Service gain is over the common constructor.")

    shadow_headers = ("Snapshots", "SBS", "SBS planned service", "VBS planned service",
                      "VBS-SBS gain", "VBS win fraction", "Unique service wins: MCTS",
                      "Unique service wins: ALNS", "Unique service wins: HGS",
                      "Unique service wins: ACS", "Portfolio gate")
    shadow_row = (shadow["snapshots"], label(shadow["sbs"]),
                  shadow["sbs_planned_customers_served"], shadow["vbs_planned_customers_served"],
                  shadow["vbs_minus_sbs_served"], pct(shadow["vbs_service_win_fraction"]),
                  *[wins[method]["unique"] for method in SEARCH_METHODS],
                  "PASS" if shadow["portfolio_gate_passed"] else "FAIL")
    shadow_note = "VBS is an analysis-only oracle on identical frozen MPC states, not a deployable controller."
    if "MPC_PORTFOLIO" in methods:
        validation = selector_cv["instance_grouped"]["aggregate"]
        shadow_headers += ("Portfolio planned service (instance CV)", "Portfolio regret to VBS")
        shadow_row += (validation["planned_service"], validation["regret_to_vbs"])
        shadow_note += " Portfolio values are out-of-instance development CV, not final-holdout outcomes."
    table(out / "table9_shadow_sbs_vbs.md", "Frozen common-state SBS/VBS study",
          shadow_headers, [shadow_row], shadow_note)

    table(out / "supp_table_per_scenario.md", "Supplement: all final paired scenarios",
          ("Instance", "DoD", "Seed", *[method.removeprefix("MPC_") + " served"
            for method in methods]),
          [(key[0], f"{key[1]:.2f}", key[2],
            *[grouped[key][method]["customers_served"] for method in methods])
           for key in sorted(grouped)])
    return overall, runtime, pairs, summary, operators


def architecture(path, methods):
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")

    def box(x, y, width, height, text, color="#ffffff", edge="#8b959d", size=10):
        ax.add_patch(FancyBboxPatch((x - width / 2, y - height / 2), width, height,
                                    boxstyle="round,pad=0.008,rounding_size=0.007",
                                    facecolor=color, edgecolor=edge, linewidth=1.1))
        ax.text(x, y, text, ha="center", va="center", fontsize=size,
                color="#1f2328" if color == "#ffffff" else "white")

    def arrow(x0, y0, x1, y1):
        ax.annotate("", (x1, y1), (x0, y0),
                    arrowprops=dict(arrowstyle="->", color="#65717c", lw=1.1))

    box(.5, .92, .48, .08, "Measured fleet state + released requests")
    box(.5, .78, .42, .08, "Event-triggered MPC", color="#263c4a")
    box(.5, .64, .4, .08, "Common constructor")
    arrow(.5, .875, .5, .825)
    arrow(.5, .735, .5, .685)
    xs = np.linspace(.1, .9, len(methods))
    for x, method in zip(xs, methods):
        text = "Completion\n(no search)" if method == "MPC_COMPLETION" else method[4:]
        box(x, .47, .15, .09, text, color=COLORS[method], edge=COLORS[method])
        arrow(.5, .59, x, .53)
        arrow(x, .42, .5, .34)
    box(.5, .28, .4, .08, "Exact EV validation")
    box(.5, .15, .4, .08, "Execute first control")
    arrow(.5, .235, .5, .195)
    ax.text(.5, .055, "Next event  ->  observe and replan", ha="center", fontsize=10)
    save(fig, path)


def write_figures(report, protocol, overall, runtime, pairs, summary, operators,
                  shadow, wins, latencies, mcts_gains, selector_cv=None):
    out = PAPER / "figures"
    methods = tuple(protocol["methods"])
    labels = [label(method) for method in methods]
    colors = [COLORS[method] for method in methods]
    architecture(out / "fig1_mpc_architecture.png", methods)

    search = [method for method in methods if method != "MPC_COMPLETION"]
    rows = [oriented(pairs, method, "MPC_COMPLETION") for method in search]
    effects = np.array([row["service_diff"] for row in rows])
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    for index, (method, effect, row) in enumerate(zip(search, effects, rows)):
        lower, upper = row["service_ci"]
        ax.hlines(index, lower, upper, color=COLORS[method], lw=1.8)
        ax.vlines((lower, upper), index - .07, index + .07, color=COLORS[method], lw=1.2)
        ax.plot(effect, index, "o", color=COLORS[method], markersize=7)
    ax.axvline(0, color="#59636e", lw=1)
    ax.set_yticks(range(len(search)), [label(method) for method in search])
    ax.invert_yaxis()
    ax.set_xlabel("Mean paired change in customers served (95% bootstrap CI)")
    ax.grid(axis="x", color="#e6e9ec", linewidth=.6)
    save(fig, out / "fig2_service_gain_vs_completion.png")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), sharey=True)
    service = [overall[method]["mean_customers_served"] for method in methods]
    complete = [100 * overall[method]["complete_service_rate"] for method in methods]
    for ax, values, title in zip(axes, (service, complete),
                                 ("A. Customers served", "B. Complete-service rate")):
        bars = ax.bar(range(len(methods)), values, color=colors, width=.7)
        ax.set(xlim=(-.6, len(methods) - .4), ylim=(0, 100), ylabel="Percent of scenarios / customers",
               title=title)
        ax.set_xticks(range(len(methods)), labels, rotation=32, ha="right")
        ax.grid(axis="y", color="#edf0f2", linewidth=.5)
        ax.set_axisbelow(True)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, max(2, value - 4), f"{value:.1f}%",
                    ha="center", va="center", fontsize=8,
                    color="white" if value > 20 else "#1f2328")
    axes[0].set_ylabel("Service rate (%)")
    axes[1].set_ylabel("Complete-service rate (%)")
    fig.tight_layout()
    save(fig, out / "fig3_service_performance.png")

    by_scope = {(row["scope"], row["method"]): row for row in report["service"]}
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    for method in methods:
        y = [by_scope[f"dod_{dod:.2f}", method]["mean_customers_served"]
             for dod in protocol["dynamicity"]]
        ax.plot(protocol["dynamicity"], y, marker="o", lw=1.7,
                color=COLORS[method], label=label(method))
    ax.set(xlabel="Degree of dynamicity", ylabel="Mean service rate (%)",
           xticks=protocol["dynamicity"], ylim=(0, 100))
    ax.grid(axis="y", color="#edf0f2", linewidth=.6)
    ax.legend(ncol=2, fontsize=8, loc="lower left")
    save(fig, out / "fig4_dynamicity.png")

    matrix = np.array([[by_scope[f"family_{family}", method]["mean_customers_served"]
                        for method in methods] for family in FAMILIES])
    fig, ax = plt.subplots(figsize=(9.2, 5))
    image = ax.imshow(matrix, cmap="YlGnBu", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(methods)), labels, rotation=28, ha="right")
    ax.set_yticks(range(len(FAMILIES)), FAMILIES)
    for i in range(len(FAMILIES)):
        for j in range(len(methods)):
            ax.text(j, i, f"{matrix[i, j]:.1f}%", ha="center", va="center",
                    fontsize=9, color="white" if matrix[i, j] > 65 else "#1f2328")
    fig.colorbar(image, ax=ax, label="Mean service rate (%)")
    save(fig, out / "fig5_family_heatmap.png")

    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    for method in search:
        values = np.sort(latencies[method])
        ax.step(values, np.arange(1, len(values) + 1) / len(values), where="post",
                color=COLORS[method], lw=1.6, label=label(method))
    ax.axvline(5, color="#9b2836", linestyle="--", linewidth=1.1, label="5 s deadline")
    ax.set(xlabel="Decision optimization latency (seconds)", ylabel="Fraction of decisions",
           xlim=(0, 5.1), ylim=(0, 1.01))
    ax.grid(color="#edf0f2", linewidth=.6)
    ax.legend(loc="lower right", fontsize=8)
    save(fig, out / "fig6_runtime.png")

    fig, ax = plt.subplots(figsize=(9.4, 4.8))
    xs = np.arange(len(SEARCH_METHODS))
    categories = (("unique", "Unique service winner", 1, ""),
                  ("tied", "Tied best service", .45, ""),
                  ("canonical_at_tied_service", "Canonical winner at tied service", 1, "//"))
    for idx, (key, _, alpha, hatch) in enumerate(categories):
        for method_index, method in enumerate(SEARCH_METHODS):
            ax.bar(xs[method_index] + (idx - 1) * .24, wins[method][key],
                   width=.23, color=COLORS[method], alpha=alpha, hatch=hatch)
    ax.set_xticks(xs, [label(method) for method in SEARCH_METHODS])
    ax.set_ylabel("Frozen common-state snapshots")
    ax.grid(axis="y", color="#edf0f2", linewidth=.6)
    ax.set_axisbelow(True)
    from matplotlib.patches import Patch
    ax.legend([Patch(facecolor="#59636e", alpha=alpha, hatch=hatch)
               for _, _, alpha, hatch in categories],
              [title for _, title, _, _ in categories], fontsize=8)
    save(fig, out / "fig7_shadow_optimizer_wins.png")

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    levels = [shadow["sbs_planned_customers_served"],
              shadow["vbs_planned_customers_served"]]
    level_labels = ["SBS", "VBS\n(analysis-only oracle)"]
    level_colors = [COLORS[shadow["sbs"]], "#77838c"]
    if "MPC_PORTFOLIO" in methods:
        levels.append(selector_cv["instance_grouped"]["aggregate"]["planned_service"])
        level_labels.append("Portfolio\n(instance-group CV)")
        level_colors.append(COLORS["MPC_PORTFOLIO"])
    bars = ax.bar(level_labels, levels, color=level_colors, width=.55)
    ax.set_ylabel("Planned customers served across frozen snapshots")
    ax.set_ylim(0, max(levels) * 1.14 if max(levels) else 1)
    for bar, value in zip(bars, levels):
        ax.text(bar.get_x() + bar.get_width() / 2, value, str(value),
                ha="center", va="bottom", fontsize=10)
    ax.grid(axis="y", color="#edf0f2", linewidth=.6)
    ax.set_axisbelow(True)
    save(fig, out / "fig8_sbs_vbs_portfolio.png")

    fig, axes = plt.subplots(2, 2, figsize=(11.2, 7.6))
    policy_labels = [name.replace("_", " ").title() for name in POLICIES]
    usage = [operators.get(("rollout_policy_usage", name), 0) for name in POLICIES]
    axes[0, 0].bar(range(3), usage, color=COLORS["MPC_MCTS"])
    axes[0, 0].set_xticks(range(3), policy_labels, rotation=20, ha="right")
    axes[0, 0].set(title="A. Rollout policy usage", ylabel="Recorded count")
    improvements = [summary.get(name, {}).get("total", 0) for name in
                    ("service_improvements", "objective_only_improvements")]
    axes[0, 1].bar(["Service", "Tie-break objective"], improvements,
                   color=[COLORS["MPC_MCTS"], "#88a5b3"])
    axes[0, 1].set(title="B. Best-plan improvements", ylabel="Recorded improvements")
    root = [operators.get(("root_control_selection", "KEEP_CONSTRUCTOR"), 0),
            operators.get(("root_control_selection", "OTHER_CONTROL"), 0)]
    axes[1, 0].bar(["Keep constructor", "Alternative control"], root,
                   color=[COLORS["MPC_COMPLETION"], COLORS["MPC_MCTS"]])
    axes[1, 0].set(title="C. Selected root control", ylabel="MCTS calls")
    gains = [sum(value == 0 for value in mcts_gains),
             sum(value == 1 for value in mcts_gains),
             sum(value >= 2 for value in mcts_gains)]
    axes[1, 1].bar(["0", "1", "2+"], gains, color=COLORS["MPC_MCTS"])
    axes[1, 1].set(title="D. Service gain over constructor", xlabel="Customers",
                   ylabel="MCTS calls")
    for ax in axes.flat:
        ax.grid(axis="y", color="#edf0f2", linewidth=.5)
        ax.set_axisbelow(True)
    fig.tight_layout()
    save(fig, out / "fig9_mcts_mechanisms.png")


def write_results(report, protocol, overall, runtime, pairs, shadow, wins, selector_cv=None):
    methods = tuple(protocol["methods"])
    best = max(methods, key=lambda method: overall[method]["mean_customers_served"])
    best_gain = oriented(pairs, best, "MPC_COMPLETION") if best != "MPC_COMPLETION" else None
    ci_text = (f"{fmt(best_gain['service_diff'])} customers (95% paired bootstrap CI "
               f"{ci(best_gain['service_ci'])})" if best_gain else "not applicable")
    evidence = ("the nominal scenario-bootstrap interval excludes zero" if best_gain and
                best_gain["service_ci"][0] > 0
                else "the interval includes zero, so the direction remains uncertain"
                if best_gain else "no optimizer exceeded the baseline mean")
    family_scope = {row["scope"]: row for row in report["service"]
                    if row["method"] == best and row["scope"].startswith("family_")}
    family_best = max(FAMILIES, key=lambda family: family_scope[f"family_{family}"][
        "mean_customers_served"])
    lines = ["# Final holdout Results", "",
             "## 1. Experimental validity", "",
             f"The final evidence comprises {report['scenarios']} fully paired 100-customer scenarios "
             f"and {report['records']} isolated, independently audited runs. All reported decision "
             "latencies meet the 5 s limit. The common event-triggered MPC architecture and "
             "frozen method definitions are in [Table 1](tables/table1_common_mpc.md) and "
             "[Figure 1](figures/fig1_mpc_architecture.png).", "",
             "## 2. Does combinatorial optimization improve MPC?", "",
             f"The highest observed final mean service was {label(best)}. Its paired gain over MPC + "
             f"Completion was {ci_text}; {evidence}. The full comparisons, including losses and "
             "ties, are in [Table 3](tables/table3_vs_completion.md) and "
             "[Figure 2](figures/fig2_service_gain_vs_completion.png). These intervals do not "
             "adjust for selecting the best observed method or for clustering by benchmark instance.", "",
             "## 3. Optimization engines inside MPC", "",
             "[Table 2](tables/table2_final_overall_results.md) and "
             "[Figure 3](figures/fig3_service_performance.png) show service and complete-service "
             "rates on the final holdout. Search-engine pairwise differences and their confidence "
             "intervals appear in [Table 4](tables/table4_optimizer_pairwise.md). A confidence "
             "interval crossing zero is not evidence of a reliable ordering. " +
             ("The frozen Portfolio is also compared directly with the best fixed optimizer "
              f"({label(best)}) in Table 2; its difference should be interpreted by the paired "
              "interval, not only by the observed mean. " if "MPC_PORTFOLIO" in methods else "") +
             "The six selected instances limit generalization.", "",
             "## 4. Impact of dynamicity", "",
             "The descriptive service-rate response at DoD 0.25, 0.50, and 0.75 is shown in "
             "[Table 6](tables/table6_by_dynamicity.md) and "
             "[Figure 4](figures/fig4_dynamicity.png). Lines summarize scenarios at each DoD; "
             "they are not an independent causal estimate of dynamicity.", "",
             "## 5. Impact of Schneider family", "",
             f"For {label(best)}, the highest descriptive family mean was in {family_best}. "
             "All six families, including those where a method loses, appear in "
             "[Table 7](tables/table7_by_family.md) and "
             "[Figure 5](figures/fig5_family_heatmap.png).", "",
             "## 6. Conditional EV/distance efficiency", "",
             "EV differences are reported only for equal-service pairs, and distance differences "
             "only when both service and activated EV count tie. See "
             "[Table 5](tables/table5_conditional_efficiency.md). Unconditional mean distance "
             "is deliberately not ranked.", "",
             "## 7. Real-time suitability", "",
             "[Table 2](tables/table2_final_overall_results.md) reports mean, p95, and maximum "
             "decision latency; [Figure 6](figures/fig6_runtime.png) shows the full search-engine "
             "latency distributions against the 5 s deadline. These are measured controller "
             "decisions, not isolated optimizer microbenchmarks.", "",
             "## 8. MCTS mechanism analysis", "",
             "Final-run policy use, aggregate service and tie-break improvements, root-control selection, and "
             "service gain over the constructor are documented in "
             "[Table 8](tables/table8_mcts_mechanisms.md) and "
             "[Figure 9](figures/fig9_mcts_mechanisms.png). Policy-specific service improvements "
             "cannot be identified from the frozen diagnostic counters; policy improvements in "
             "Table 8 include objective-only gains.", "",
             "## 9. Common-state optimizer complementarity", "",
             "The four engines were evaluated independently on identical frozen observable MPC "
             "states. Unique service winners, tied best-service states, and canonical winners "
             "within service ties appear in [Figure 7](figures/fig7_shadow_optimizer_wins.png). "
             "The canonical category is a subset of tied best-service states, not an additional "
             "disjoint count.", "",
             "## 10. SBS/VBS and portfolio decision", "",
             f"The frozen common-state study had {shadow['snapshots']} snapshots. Its gate "
             f"{'passed' if shadow['portfolio_gate_passed'] else 'failed'}; "
             "VBS is an analysis-only oracle. " +
             ("The frozen selector passed both grouped-CV deployment checks; its out-of-instance "
              "planned-service result in Table 9 is development evidence, while its deployed "
              "performance is in the final-holdout Tables 2-5. "
              if "MPC_PORTFOLIO" in methods else
              "No portfolio was included in the final holdout. ") +
             "See [Table 9](tables/table9_shadow_sbs_vbs.md) and "
             "[Figure 8](figures/fig8_sbs_vbs_portfolio.png).", "",
             "## 11. Final conclusions from the holdout", "",
             "The headline comparisons are the paired, preregistered final-holdout results in "
             "[Tables 2-4](tables/table2_final_overall_results.md) and "
             "[Figure 2](figures/fig2_service_gain_vs_completion.png), not development scores. "
             "Per-scenario outcomes, including all losses, are in "
             "[Supplement Table](tables/supp_table_per_scenario.md). Generalization beyond the "
             "six selected Schneider instances, three DoD levels, and fixed 5 s implementation "
             "budget remains untested.", "",
             "## Figure captions", "",
             "- [Figure 1](figures/fig1_mpc_architecture.png): Event-triggered MPC is common; "
             "Completion omits additional search while four engines optimize the same constructor.",
             "- [Figure 2](figures/fig2_service_gain_vs_completion.png): Positive paired gains "
             "favor optimization; bars show 95% scenario-bootstrap intervals.",
             "- [Figure 3](figures/fig3_service_performance.png): Absolute 0-100% axes prevent "
             "small service differences from appearing artificially large.",
             "- [Figure 4](figures/fig4_dynamicity.png): Descriptive service-rate means by DoD.",
             "- [Figure 5](figures/fig5_family_heatmap.png): Mean service rate by family and MPC variant.",
             "- [Figure 6](figures/fig6_runtime.png): Decision-latency ECDF and 5 s deadline.",
             "- [Figure 7](figures/fig7_shadow_optimizer_wins.png): Identical-state service and "
             "canonical win counts; tied and canonical categories overlap by definition.",
             "- [Figure 8](figures/fig8_sbs_vbs_portfolio.png): Planned service for SBS and "
             "analysis-only VBS on frozen snapshots; any portfolio bar is held-out-instance "
             "development CV, not a final-holdout result.",
             "- [Figure 9](figures/fig9_mcts_mechanisms.png): Final-holdout MCTS mechanism counts.", "",
             "## Provenance", "",
             f"Source SHA-256: `{protocol['source_sha256']}`. Final preregistration SHA-256: "
             f"`{sha256(JSON_OUTPUT.read_bytes()).hexdigest()}`. Development data are not mixed "
             "into the final tables; [Table 1](tables/table1_common_mpc.md) states the common design.", ""]
    (PAPER / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


def render():
    protocol = validated_protocol()
    report = analyze_final()
    shadow = load_json(SHADOW / "sbs_vbs_gate.json")
    selector_cv = load_json(SELECTOR_CV) if shadow["portfolio_gate_passed"] else None
    manifest = load_json(OUTPUT / "manifest.json")
    shadow_manifest = load_json(SHADOW / "manifest.json")
    if report["status"] != "complete_final_holdout" or report["records"] != len(manifest["records"]):
        raise ValueError("Audited final holdout incomplete")
    grouped, shadow_rows, latencies, mcts_gains = audit_paper_inputs(
        protocol, manifest, shadow_manifest)
    selection = load_json(SHADOW / "selection.json")
    snapshots = {row["state_hash"]: row for row in selection["snapshots"]}
    if set(snapshots) != set(shadow_rows) or summarize_shadow(shadow_rows, snapshots) != shadow:
        raise ValueError("Frozen shadow gate differs from audited common-state outcomes")
    if len(shadow_rows) != shadow["snapshots"]:
        raise ValueError("Shadow snapshot count differs from audited summary")
    wins = shadow_win_counts(shadow_rows)
    if any(wins[method]["unique"] != shadow["unique_service_wins"][method]
           for method in SEARCH_METHODS):
        raise ValueError("Shadow win counts disagree with audited SBS/VBS summary")
    (PAPER / "figures").mkdir(parents=True, exist_ok=True)
    (PAPER / "tables").mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11,
                         "axes.labelsize": 10, "figure.facecolor": "white",
                         "axes.facecolor": "white", "savefig.facecolor": "white"})
    overall, runtime, pairs, summary, operators = write_tables(
        report, protocol, grouped, shadow, wins, selector_cv)
    write_figures(report, protocol, overall, runtime, pairs, summary, operators,
                  shadow, wins, latencies, mcts_gains, selector_cv)
    write_results(report, protocol, overall, runtime, pairs, shadow, wins, selector_cv)
    return PAPER


if __name__ == "__main__":
    print(render())
