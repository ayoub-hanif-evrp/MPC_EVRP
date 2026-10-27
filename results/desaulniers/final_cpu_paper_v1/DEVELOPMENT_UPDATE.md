# Balanced development update

This is exploratory development evidence, not part of the independent 510-run primary-plus-replication cohort. Six underlying parents, one per benchmark family and two at each customer size, were paired on original versus combined. Four component ablations used a prespecified three-parent subset. All five methods used the same scenarios, fleet, physics, objective and five-second decision limit.

All 120 saved raw records passed independent physical replay and source/scenario/hash checks. The combined variant yielded +3 served customers across 30 paired method-runs (4 gains, 1 loss; 1 harmed parent). The ACS loss rejects promotion under the service-preservation gate. No enhanced independent holdout was opened.

Cumulative charged wall time: 2.051 h of the six-hour development allowance; worker CPU time: 1.944 h. One original whole-worker timeout was preserved and the remaining eight jobs used a separately frozen 900-second technical correction. The five-second MPC decision budget did not change.

A separate two-scenario/two-method technical probe found 1.50x sequential-to-two-worker throughput with identical served counts. This is a small shared-machine engineering result, not controlled paper timing. See the [probe report](../two_worker_probe_v1/RESULTS.md).

See the [paired cases](tables/balanced_development_paired_cases.md), [variant summary](tables/balanced_development_variant_summary.md), [service changes](figures/13_balanced_development_service_changes.png), [CPU ratios](figures/14_balanced_development_cpu_ratio.png), [source protocol](../final_cpu_development_v1/protocol.json), [technical correction](../final_cpu_development_v1/technical_extension/protocol.json), [raw manifest](../final_cpu_development_v1/manifest.json), and [independent replay inventory](../final_cpu_development_v1/audit/independent_replay.md).
