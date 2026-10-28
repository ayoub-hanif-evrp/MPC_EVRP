# Balanced CPU development ablation

Exploratory source-frozen development evidence, not independent confirmation. Six families and two cases per size pair original with combined. Component ablations use fixed cases 0/2/4, one per size. All five methods share physics, objective and five-second decision budget. Case size is customers; distance is benchmark distance, travel/charging/waiting/service completion are benchmark time units, energy is benchmark energy, CPU is worker process seconds, and latency is seconds. A paired row represents one scenario and one optimizer; the same parent never counts as independent twice.

Independent replay: 120/120 raw files passed.
Combined service change: +3 customers over 30 paired method-runs; positive parents 2/6, harmed parents 1/6.
Method-specific service changes: MPC_COMPLETION +1, MPC_MCTS +1, MPC_ALNS +1, MPC_HGS +1, MPC_ACS -1.
Post hoc conservative service screen: FAIL.

The frozen protocol states: Promote only a variant with no aggregate service loss, no repeated family harm, and a useful service or conditional-quality gain; otherwise keep original. It does not define numerical thresholds for useful gains or repeated family harm. The analysis implementation subsequently required a positive aggregate gain, two improving parents, zero harmed parents and no harmed method. That is a stricter, post hoc screen, not the preregistered acceptance rule. A single ACS loss therefore does not by itself establish failure of the registered rule. The original methods are retained because the limited development evidence and earlier regressions do not establish a repeatable improvement. No variant is retrospectively promoted from this analysis.

See [paired cases](tables/paired_cases.md), [variant summary](tables/variant_summary.md), [independent replay](audit/independent_replay.md), [service figure](figures/development_service_changes.png), and [CPU figure](figures/development_cpu_ratio.png).

Conditional distance is reported only for identical served-customer sets. A failed bounded insertion is not a proof of EV infeasibility.
