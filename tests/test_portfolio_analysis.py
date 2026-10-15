"""Mechanism summaries preserve optimizer-specific evidence and scopes."""

from scripts.analyze_portfolio_development import (family_subtype, mechanism_record,
                                                   plot_development, summarize_mechanisms)


def test_family_subtype_parses_all_schneider_groups():
    assert [family_subtype(name) for name in
            ("c101_21", "c201_21", "r101_21", "r201_21", "rc101_21", "rc201_21")] == [
                "C1", "C2", "R1", "R2", "RC1", "RC2"]


def test_mechanism_summary_separates_scopes_and_operator_evidence():
    mcts = mechanism_record(
        dict(method="MPC_MCTS", instance="c101_21", dynamicity=0.25),
        dict(constructor_service=8, best_service_after_search=9,
             optimizer=dict(diagnostics=dict(iterations=10, nodes_expanded=7,
                 service_improvements=1, objective_only_improvements=2,
                 rollout_count=10, rollout_policy_usage={"CRITICAL_REGRET": 6,
                                                          "EARLIEST_DEADLINE": 4},
                 rollout_policy_improvements={"CRITICAL_REGRET": 1},
                 root_control_statistics={"KEEP_CONSTRUCTOR": {"visits": 0},
                                          "selected": {"visits": 7}},
                 selected_root_control="selected"))))
    alns = mechanism_record(
        dict(method="MPC_ALNS", instance="rc201_21", dynamicity=0.75),
        dict(constructor_service=7, best_service_after_search=9,
             optimizer=dict(diagnostics=dict(iterations=12, improving_moves=3,
                 destroy_counts={"random": 8}, repair_counts={"regret": 8},
                 destroy_weights={"random": 1.5}, repair_weights={"regret": 2.0}))))
    summary, operators = summarize_mechanisms([mcts, alns])
    lookup = {(row["scope"], row["method"], row["metric"]): row for row in summary}
    assert lookup[("family_C1", "MPC_MCTS", "root_control_alternatives")]["total"] == 2
    assert lookup[("dod_0.25", "MPC_MCTS", "selected_root_visits")]["total"] == 7
    assert lookup[("overall", "MPC_MCTS", "service_gain_over_constructor")]["total"] == 1
    assert lookup[("family_RC2", "MPC_ALNS", "service_gain_over_constructor")]["total"] == 2
    assert any(row["scope"] == "dod_0.25" and row["diagnostic"] == "rollout_policy_usage"
               and row["label"] == "CRITICAL_REGRET" and row["total"] == 6
               for row in operators)
    assert any(row["scope"] == "family_RC2" and row["kind"] == "weights"
               and row["label"] == "random" and row["mean_per_recorded_call"] == 1.5
               for row in operators)


def test_development_figures_are_png_only(tmp_path):
    methods = ("MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS")
    scopes = ("overall", "family_C1", "family_C2", "family_R1", "family_R2",
              "family_RC1", "family_RC2", "dod_0.25", "dod_0.50", "dod_0.75")
    service = [dict(scope=scope, method=method, mean_customers_served=90 + index,
                    complete_service_rate=0.5 + index * 0.1)
               for scope in scopes for index, method in enumerate(methods)]
    comparisons = [dict(scope="overall", left="MPC_COMPLETION", right=method,
                        service_diff=-index, service_ci=[-index - 0.5, -index + 0.5])
                   for index, method in enumerate(methods[1:], 1)]
    latencies = {method: [0.1, 1.0, 4.5] for method in methods}
    operators = [dict(scope="overall", method="MPC_MCTS", diagnostic=diagnostic,
                      label=policy, total=total)
                 for diagnostic, total in (("rollout_policy_usage", 10),
                                           ("rollout_policy_improvements", 2))
                 for policy in ("CRITICAL_REGRET", "EARLIEST_DEADLINE",
                                "RESERVE_PRESERVING")]
    plot_development(tmp_path, methods, service, comparisons, latencies, operators)
    figures = list(tmp_path.iterdir())
    assert len(figures) == 8
    assert all(path.suffix == ".png" and path.stat().st_size > 0 for path in figures)
