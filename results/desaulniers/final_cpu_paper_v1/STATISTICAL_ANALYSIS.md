# Statistical analysis

The experimental matching unit is a dynamic scenario: identical underlying instance, DoD, seed, archived reference fleet, and release schedule for all five methods. A scenario's served-customer difference is converted to percentage points. Within each underlying parent, these paired differences are averaged equally across DoD and seeds; the six parent means are then averaged. The exploratory 95% interval is the percentile interval from 10,000 bootstrap resamples of the six parents, fixed random seed 20261026. Wins, ties, and losses count matched scenarios. Customer-weighted overall service uses total served divided by total available, so it need not equal the equally parent-weighted paired difference.

Primary-cohort contrasts are listed below. Replication contrasts are in the linked table; no pooling or retrospective reweighting was performed.

| Contrast | Difference pp | 95% cluster interval pp | Win/tie/loss |
| --- | --- | --- | --- |
| MCTS vs COMPLETION | 4.067 | [1.178, 7.244] | 45/43/2 |
| ALNS vs COMPLETION | 8.333 | [2.156, 15.267] | 50/40/0 |
| HGS vs COMPLETION | 7.700 | [2.411, 13.689] | 50/40/0 |
| ACS vs COMPLETION | 6.167 | [1.578, 11.300] | 47/42/1 |
| ALNS vs HGS | 0.633 | [-0.622, 1.944] | 25/54/11 |

The ALNS-HGS interval [-0.62, 1.94] crosses zero. Six underlying parents per cohort make the bootstrap fragile, and intervals are not adjusted for multiple comparisons. A displayed interval excluding zero is descriptive, not a blanket claim of benchmark-wide superiority. Size and family breakdowns are descriptive strata, not independent confirmatory tests.

[Complete paired table](tables/parent_clustered_paired_statistics.md).
