# Event-triggered fleet MPC on Desaulniers MP instances

## Design and scope

The primary, independently frozen Desaulniers MP robustness study contains 90 matched dynamic scenarios and 450 original-method simulations, spanning six underlying benchmark parents, three target degrees of dynamism, and five release seeds. The separate prospective CPU replication contains 12 scenarios and 60 original-method simulations on six previously unused parents at target DoD 0.50 and seeds 6 and 7. The cohorts are reported separately and never pooled.

## Results

| Method | Primary service | Primary complete | Replication service | Replication complete |
| --- | --- | --- | --- | --- |
| COMPLETION | 87.35% | 40/90 | 90.57% | 4/12 |
| MCTS | 92.84% | 45/90 | 93.86% | 7/12 |
| ALNS | 98.95% | 63/90 | 98.71% | 6/12 |
| HGS | 97.47% | 58/90 | 97.14% | 6/12 |
| ACS | 95.98% | 49/90 | 97.14% | 7/12 |

The primary cohort has 5250 customer opportunities per method. ALNS had the highest observed primary customer-weighted service (98.95%) and complete-service frequency (63/90). MCTS improved paired service over Completion by 4.07 percentage points (parent-clustered exploratory 95% interval [1.18, 7.24]). The ALNS-HGS difference was 0.63 percentage points ([-0.62, 1.94]); its interval includes zero, so superiority across benchmark parents is not established.

### Paired primary contrasts

| Contrast | Difference pp | 95% cluster interval pp | Win/tie/loss |
| --- | --- | --- | --- |
| MCTS vs COMPLETION | 4.067 | [1.178, 7.244] | 45/43/2 |
| ALNS vs COMPLETION | 8.333 | [2.156, 15.267] | 50/40/0 |
| HGS vs COMPLETION | 7.700 | [2.411, 13.689] | 50/40/0 |
| ACS vs COMPLETION | 6.167 | [1.578, 11.300] | 47/42/1 |
| ALNS vs HGS | 0.633 | [-0.622, 1.944] | 25/54/11 |

The 100%-service offline reference is physically feasible with the same reference fleet on each generated scenario. The online methods do not know unreleased requests; the service gap is therefore an offline-reference gap, not a claim of an online oracle optimum. Distance and energy comparisons use only the 39 primary scenarios where all five methods served everyone. They are conditional comparisons, not unconditional efficiency rankings.

The opt-in compiled CPU and quality/recovery pilots are development evidence only: 0 service gains and 3 service losses in 25 matched cases. Their service losses prevented promotion. The replication therefore tests the original methods, not an improved controller.

### Descriptive heterogeneity

The highest observed customer-weighted service in each primary-cohort stratum is shown below. Ties are retained; each family has only one underlying parent and should not be interpreted as a general family-level winner.

| SIZE | Highest observed service | Service % |
| --- | --- | --- |
| 25 | HGS | 99.33 |
| 50 | ALNS/HGS/ACS | 100.00 |
| 100 | ALNS | 98.57 |

| FAMILY | Highest observed service | Service % |
| --- | --- | --- |
| C1 | ALNS | 99.47 |
| C2 | ALNS/HGS/ACS | 100.00 |
| R1 | ALNS | 97.67 |
| R2 | COMPLETION/MCTS/ALNS/HGS/ACS | 100.00 |
| RC1 | HGS | 98.67 |
| RC2 | COMPLETION/MCTS/ALNS/HGS/ACS | 100.00 |

Total recorded sequential-worker wall time was 10.04 h in the primary study and 1.80 h in the new replication. The replication recorded 1.79 worker CPU-hours; its persistent charged wall allowance was 1.97 h, including setup and analysis reserves. No historical child CPU time is inferred. The maximum recorded decision latency across both cohorts was 4.796 s.

### Operational trade-offs

On the 39 jointly complete primary scenarios only, the lowest observed cost or largest observed safety margin by metric is listed below. These are conditional descriptions and do not imply the same method is best on all customer sets or statistically superior on a metric.

| Conditional metric | Best observed mean | Value |
| --- | --- | --- |
| Route distance (benchmark units) | ACS | 772.34 |
| Travel time (benchmark time units) | ACS | 772.34 |
| Last service completion (benchmark time units) | HGS | 1384.50 |
| Charging time (benchmark time units) | ACS | 230.03 |
| Charged energy (battery units) | ACS | 230.03 |
| Travel energy (battery units) | ACS | 475.98 |
| Waiting time (benchmark time units) | HGS | 3935.42 |
| Active EVs | ALNS/HGS | 2.90 |
| Vehicle load SD (customers) | HGS | 6.64 |
| Minimum TW margin (benchmark time units) | ACS | 3.91 |
| Minimum battery (battery units) | ALNS | 3.23 |

Every saved record used here was SHA-256 checked against its frozen manifest and independently replayed for physical feasibility, information boundaries, duplicate service, and deadline compliance. All recorded optimization decisions met the five-second limit.

## Figures and tables

The 12 numbered figures in figures/ are 300 dpi PNG with matching SVG. Tables in tables/ are Markdown with CSV and LaTeX companions. Key displays: [five-method results](tables/main_five_methods.md), [independent CPU replication](tables/independent_cpu_replication.md), [25/50/100-customer results](tables/by_size.md), [family results](tables/by_family.md), [paired intervals](tables/parent_clustered_paired_statistics.md), [conditional operations](tables/operational_matched_service.md), [service figure](figures/01_customer_service.png), [runtime ECDF](figures/08_decision_latency_ecdf.png).
