# Final holdout Results

## 1. Experimental validity

The final evidence comprises 54 fully paired 100-customer scenarios and 324 isolated, independently audited runs. All reported decision latencies meet the 5 s limit. The common event-triggered MPC architecture and frozen method definitions are in [Table 1](tables/table1_common_mpc.md) and [Figure 1](figures/fig1_mpc_architecture.png).

## 2. Does combinatorial optimization improve MPC?

The highest observed final mean service was MPC + ALNS. Its paired gain over MPC + Completion was 5.07 customers (95% paired bootstrap CI [3.89, 6.33]); the nominal scenario-bootstrap interval excludes zero. The full comparisons, including losses and ties, are in [Table 3](tables/table3_vs_completion.md) and [Figure 2](figures/fig2_service_gain_vs_completion.png). These intervals do not adjust for selecting the best observed method or for clustering by benchmark instance.

## 3. Optimization engines inside MPC

[Table 2](tables/table2_final_overall_results.md) and [Figure 3](figures/fig3_service_performance.png) show service and complete-service rates on the final holdout. Search-engine pairwise differences and their confidence intervals appear in [Table 4](tables/table4_optimizer_pairwise.md). A confidence interval crossing zero is not evidence of a reliable ordering. The frozen Portfolio is also compared directly with the best fixed optimizer (MPC + ALNS) in Table 2; its difference should be interpreted by the paired interval, not only by the observed mean. The six selected instances limit generalization.

## 4. Impact of dynamicity

The descriptive service-rate response at DoD 0.25, 0.50, and 0.75 is shown in [Table 6](tables/table6_by_dynamicity.md) and [Figure 4](figures/fig4_dynamicity.png). Lines summarize scenarios at each DoD; they are not an independent causal estimate of dynamicity.

## 5. Impact of Schneider family

For MPC + ALNS, the highest descriptive family mean was in C2. All six families, including those where a method loses, appear in [Table 7](tables/table7_by_family.md) and [Figure 5](figures/fig5_family_heatmap.png).

## 6. Conditional EV/distance efficiency

EV differences are reported only for equal-service pairs, and distance differences only when both service and activated EV count tie. See [Table 5](tables/table5_conditional_efficiency.md). Unconditional mean distance is deliberately not ranked.

## 7. Real-time suitability

[Table 2](tables/table2_final_overall_results.md) reports mean, p95, and maximum decision latency; [Figure 6](figures/fig6_runtime.png) shows the full search-engine latency distributions against the 5 s deadline. These are measured controller decisions, not isolated optimizer microbenchmarks.

## 8. MCTS mechanism analysis

Final-run policy use, aggregate service and tie-break improvements, root-control selection, and service gain over the constructor are documented in [Table 8](tables/table8_mcts_mechanisms.md) and [Figure 9](figures/fig9_mcts_mechanisms.png). Policy-specific service improvements cannot be identified from the frozen diagnostic counters; policy improvements in Table 8 include objective-only gains.

## 9. Common-state optimizer complementarity

The four engines were evaluated independently on identical frozen observable MPC states. Unique service winners, tied best-service states, and canonical winners within service ties appear in [Figure 7](figures/fig7_shadow_optimizer_wins.png). The canonical category is a subset of tied best-service states, not an additional disjoint count.

## 10. SBS/VBS and portfolio decision

The frozen common-state study had 396 snapshots. Its gate passed; VBS is an analysis-only oracle. The frozen selector passed both grouped-CV deployment checks; its out-of-instance planned-service result in Table 9 is development evidence, while its deployed performance is in the final-holdout Tables 2-5. See [Table 9](tables/table9_shadow_sbs_vbs.md) and [Figure 8](figures/fig8_sbs_vbs_portfolio.png).

## 11. Final conclusions from the holdout

The headline comparisons are the paired, preregistered final-holdout results in [Tables 2-4](tables/table2_final_overall_results.md) and [Figure 2](figures/fig2_service_gain_vs_completion.png), not development scores. Per-scenario outcomes, including all losses, are in [Supplement Table](tables/supp_table_per_scenario.md). Generalization beyond the six selected Schneider instances, three DoD levels, and fixed 5 s implementation budget remains untested.

## Figure captions

- [Figure 1](figures/fig1_mpc_architecture.png): Event-triggered MPC is common; Completion omits additional search while four engines optimize the same constructor.
- [Figure 2](figures/fig2_service_gain_vs_completion.png): Positive paired gains favor optimization; bars show 95% scenario-bootstrap intervals.
- [Figure 3](figures/fig3_service_performance.png): Absolute 0-100% axes prevent small service differences from appearing artificially large.
- [Figure 4](figures/fig4_dynamicity.png): Descriptive service-rate means by DoD.
- [Figure 5](figures/fig5_family_heatmap.png): Mean service rate by family and MPC variant.
- [Figure 6](figures/fig6_runtime.png): Decision-latency ECDF and 5 s deadline.
- [Figure 7](figures/fig7_shadow_optimizer_wins.png): Identical-state service and canonical win counts; tied and canonical categories overlap by definition.
- [Figure 8](figures/fig8_sbs_vbs_portfolio.png): Planned service for SBS and analysis-only VBS on frozen snapshots; any portfolio bar is held-out-instance development CV, not a final-holdout result.
- [Figure 9](figures/fig9_mcts_mechanisms.png): Final-holdout MCTS mechanism counts.

## Provenance

Source SHA-256: `3c6ffdfb5ab86190ff6c45e7eaf063dcdb6c80508bf46c6849269342e718628b`. Final preregistration SHA-256: `2ac8471833084b6549a3cca879805b457e91775be62fd09b80df04ce6a57bf5f`. Development data are not mixed into the final tables; [Table 1](tables/table1_common_mpc.md) states the common design.
