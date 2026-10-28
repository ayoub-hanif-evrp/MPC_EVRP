# Final CPU paper package

**Status: complete, provided audit/verification.json reports 510/510 passed.**

The original five-method MPC system remains the publication configuration. The 450-run independent primary cohort and 60-run prospective replication are complete and separately reported. No enhanced promotion is justified; no enhanced final claim is made. The stricter development service-preservation gate was post hoc, not the frozen selection rule. The later balanced development ablation observed +3 net served customers and 1 paired service loss(es).

| Method | Primary service | Primary complete | Replication service | Replication complete |
| --- | --- | --- | --- | --- |
| COMPLETION | 87.35% | 40/90 | 90.57% | 4/12 |
| MCTS | 92.84% | 45/90 | 93.86% | 7/12 |
| ALNS | 98.95% | 63/90 | 98.71% | 6/12 |
| HGS | 97.47% | 58/90 | 97.14% | 6/12 |
| ACS | 95.98% | 49/90 | 97.14% | 7/12 |

Primary ALNS-HGS paired difference: 0.63 pp (95% parent-cluster interval [-0.62, 1.94]); this does not establish clear superiority across parents. All raw traces were independently replayed and decision latencies checked. The new replication recorded 1.80 worker wall-hours and 1.79 attempted-worker CPU-hours, including all supervised attempts and process overhead.

Read [paper results](PAPER_RESULTS.md), [methods](METHODS.md), [statistics](STATISTICAL_ANALYSIS.md), [limitations](LIMITATIONS.md), [reproduction](REPRODUCE.md), [balanced development update](DEVELOPMENT_UPDATE.md), [six-family CPU coverage](CPU_COVERAGE.md), [service-loss diagnosis](audit/SERVICE_LOSS_DIAGNOSIS.md), [all audited runs](tables/all_audited_runs.md), and [the verification inventory](audit/verification.json). [Every final figure and table](INDEX.md) is indexed separately. Test and historical-audit outcomes are in [audit/VALIDATION.md](audit/VALIDATION.md).

The GPU-negative study remains on the verified archive tag. The active project is CPU-only; old frozen studies are retained as historical evidence, not silently merged into this package.
