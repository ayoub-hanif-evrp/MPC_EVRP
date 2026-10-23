# Multi-seed Desaulniers MP robustness results

The separately frozen v3 study completed 450/450 audited method runs: five
unchanged MPC optimizers on 90 matched dynamic scenarios from six previously
unused benchmark instances, three target DoD levels, and release seeds 1-5.
All five methods saw the same scenario and fixed reference fleet within each
match. The five-second decision budget, MP physics, and common objective were
unchanged. No scenario was excluded after method execution.

| MPC optimizer | Customer-weighted served | Complete scenarios |
| --- | ---: | ---: |
| Completion | 87.35% | 44.4% |
| MCTS | 92.84% | 50.0% |
| ALNS | 98.95% | 70.0% |
| HGS | 97.47% | 64.4% |
| ACS | 95.98% | 54.4% |

The [full audited summary](SUMMARY.md) gives outcomes by seed, customer size,
instance family, and DoD. Paired gains below weight each matched scenario
equally; the overall service percentages above weight customers, so these
two summaries need not have identical differences.

| Paired service contrast | Mean gain (pp) | Instance-clustered 95% interval (pp) | Win/tie/loss |
| --- | ---: | ---: | ---: |
| MCTS vs Completion | +4.07 | [+1.18, +7.09] | 45/43/2 |
| ALNS vs Completion | +8.33 | [+2.16, +15.07] | 50/40/0 |
| HGS vs Completion | +7.70 | [+2.27, +13.54] | 50/40/0 |
| ACS vs Completion | +6.17 | [+1.58, +11.10] | 47/42/1 |
| ALNS vs HGS | +0.63 | [-0.62, +1.94] | 25/54/11 |

ALNS has the highest observed customer-weighted service and complete-service
rate in this sample. Its paired ALNS-HGS interval crosses zero, so these
data do not establish ALNS superiority over HGS across base instances.
The intervals resample just six base instances while retaining their DoD
and seed repeats. They are descriptive, not multiplicity-adjusted
confirmatory significance tests. In particular, 50-customer cases and the
sampled R2/RC2 families have strong service ceiling effects, while the
100-customer cases separate methods more clearly. The chosen instances
were selected by prospective reference/DoD eligibility, not optimizer
performance, but six instances do not represent the full 168-instance
benchmark distribution.

Every raw record passed file-hash and protocol identity checks, independent
physical replay, the information boundary, and the five-second decision
budget. All recorded feasibility and duplicate-service violation totals
were zero. Pooled decision-latency p95 values range from 0.108 seconds for
Completion to 4.739 seconds for ALNS; the maximum observed latency is
4.796 seconds (HGS). Mean isolated worker time per scenario is 2.9 seconds
for Completion, 70.7 for MCTS, 82.1 for ALNS, 140.7 for HGS, and 105.1
for ACS. These are sequential-machine measurements, not parallel timings.
Distance in the summary is compared only on the 39 scenarios where every
method served all customers; unconditional route lengths would confound
distance with differences in service.

Figures are [service by seed](service_by_seed.png) and
[decision-latency ECDF](runtime_ecdf.png), both PNG at 300 dpi. The
[corrected 270-run final holdout](../paper_v2/RESULTS.md) remains a separate
historical study and is not pooled with v3.

The [environment snapshot](environment.json) was recorded while the new
source was still an uncommitted worktree at Git HEAD `380099c`; that field
is not the executed source revision. The frozen source SHA-256 in the
[protocol](protocol.json), together with dataset/controller/config hashes,
binds every v3 raw result and was checked again by the analyzer. The source
was subsequently committed without changing that fingerprint.

Reproduce the audit and derived Markdown/PNG artifacts from the saved raw
files with `python -m scripts.analyze_desaulniers_robustness --v3`. The
[validation guide](../../../docs/VALIDATION_AND_REPRODUCTION.md) lists the
dependencies and full campaign command.
