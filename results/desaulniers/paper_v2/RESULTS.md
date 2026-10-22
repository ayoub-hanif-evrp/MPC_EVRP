# Corrected final MP results

This directory reports the immutable 270-run corrected final holdout, not the original 10-run partial campaign and not the new robustness study. Raw traces were independently replayed before rendering. All five methods use the same event-triggered MPC framework, objective, fixed reference fleet, dynamic requests, and five-second decision limit.

Overall customer-weighted service rates are 92.19% Completion, 96.00% MCTS, 99.14% ALNS, 98.89% HGS, and 98.19% ACS. ALNS versus Completion gains +7.83 percentage points on equally weighted paired scenarios (instance-clustered 95% CI [+3.57, +12.63]). ALNS versus HGS is +0.07 percentage points (95% CI [-0.89, +0.93]), so the observed mean ranking alone does not establish ALNS superiority over HGS. These descriptive intervals are not multiplicity-adjusted confirmatory tests. The static published solutions define feasible offline reference fleets, not online objective comparators. One release seed and 18 base instances limit generalization; the separately versioned multi-seed study is designed to test this limitation and is not yet evidence until complete.

Figures are PNG only, 300 dpi. Tables are Markdown only. Distance comparisons use only common complete-service scenarios.
