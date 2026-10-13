# Frozen Paper Benchmark Protocol

Date: 2026-10-13. This protocol was specified after the audited development
results and before inspecting any results of the six named dynamic holdout
instances. **The external benchmark plan was finalized after development but
before any holdout result was inspected.** The 2026 development verdict was
negative against historical Rolling-LNS; this protocol does not relabel that
result as a win. No MPC, MCTS, objective, trigger, charging decoder, constructor,
ejection, rollout, depth, branching, or five-second control-budget changes are
permitted. Frozen top-level `evrp/*.py` SHA-256:
`4cdead8ab9956362ba9921c0818b7bcc9690487ab11ba001d087abebe43176b6`.

## Scientific question and hierarchy

Does fleet-level MCTS materially improve the *same* event-triggered MPC
controller in dynamic EVRPTW while preserving real-time suitability? Primary
paired ablation: `FLEET_MPC_MCTS` minus `FLEET_MPC_COMPLETION_ONLY` in customers
served. `RH_REGRET` is the second dynamic comparator under the same released
information, measured EV states, immutable busy actions, `K_ref`, event triggers,
and five-second per-decision limit. The previous Rolling-LNS data stay visible as
historical/supplementary internal evidence, not a headline external baseline.

Common *evaluation* order, distinct from internal `J_A`/`J_B`: service first;
only at equal service compare activated EV count; only at equal service *and*
EV count compare distance; report runtime separately. Do not compare distance
or EVs across unequal-service pairs. Internal risk-control objectives guide the
controller but are never imputed to external solutions.

## Grids and eligibility

- Controller config: `configs/paper_controller.yaml`, copied from an audited
  frozen development run except the case-specific seed, dynamicity and method.
- Static instances: `c101_21,c201_21,r101_21,r201_21,rc101_21,rc201_21`;
  controller algorithm seeds 0-9, DoD=0, fixed physical `K_ref`.
- RoutingBlocks EVRPTW-PR static: same six instances, 10 independent seeds
  0-9, whole-run budgets 5, 30, 300 seconds; upstream example parameters
  unchanged except the required instance fleet cap override to `K_ref`.
  It enters tables only if the package runs, full instance equivalence passes,
  and each returned node order has an independent feasible charging witness
  and physical replay. Package/install failure yields **missing**, not zero.
  The official example's search limit includes costly initial construction;
  measured runtime may exceed the nominal limit. Such runs remain in the audit
  but are excluded from budget-respecting solution-quality statistics. Official
  solver exceptions are recorded as failed attempts, not imputed outcomes.
- pyevrp 0.2.1 is not a fair comparator because its bundled loader and greedy
  charging/fleet semantics fail the compatibility audit. A non-equivalent
  qualitative result, if ever run, must be segregated and never ranked.
- Small cases: `c101C5,c103C5,c206C5,c208C5`; published CPLEX *reference*
  values are contextual. A percentage gap is shown only with matching full
  customer service, EV count, and physical charging model. No optimality claim
  follows from a published number alone.
- Development paired RH-Regret supplement: six development instances, DoD=0.5,
  scenario seeds 0-1, using frozen historical MPC-MCTS/completion records.
- Dynamic holdout, **once after protocol commit and clean-tree verification**:
  `c109_21,c208_21,r112_21,r211_21,rc108_21,rc208_21`, DoD=0.25/0.50/0.75,
  scenario seeds 0/1/2, all three predeclared dynamic methods. Runs sharing a
  case must have the same scenario hash. No tuning or method change after
  holdout execution starts. Interrupted runs may resume only under the same
  freeze SHA/config and are not a second statistical draw.

`configs/paper_campaign.yaml` is the exact grid. The runner records the
committed protocol Git SHA, both config SHA-256 hashes, frozen source SHA-256,
and each raw-result SHA-256 in `results/paper` manifests. Any changed commit,
config, source, or dirty tree blocks holdout resume.

## Statistical reporting

Primary holdout endpoints: customers served, complete-service rate, paired
MCTS-minus-completion and MCTS-minus-RH service differences, win/tie/loss,
and a paired bootstrap percentile 95% CI (10,000 case-pair resamples, RNG seed
0). Secondary EV differences are conditional on equal service; distance
differences additionally require equal EV count. Incomplete service remains
in primary statistics. Report the number eligible for each conditional metric.
No multiplicity-adjusted significance claim is planned.

Real-time report: mean/p95/max optimization latency, whole-instance wall time,
and exact fraction of calls <=5 s **only if per-call latencies exist**. When
only run-level max is retained, max<=5 proves 100%; otherwise the fraction is
unavailable, not estimated. MCTS contribution: service/EV/distance/objective
improving calls, root-to-final gain, nodes, iterations, rollouts, all derived
from raw decision records. Existing dev data are not holdout evidence.

## External runtime interpretation

The controller's five seconds is **per event decision** and may accumulate
substantially more than five seconds per static instance. An external 5-second
whole-instance run is therefore *not* equal total compute. External 5/30/300
second results are offline solution-quality context, with 30/300 seconds
explicitly offline. Same-compute claims require matching total wall budgets and
are not made by this protocol. RoutingBlocks and pyevrp do not qualify for
dynamic RH comparison; no depot-restart surrogate is allowed.

## Provenance and citations

Raw records, table CSVs/Markdown, PNG figures only (per prior user request),
compatibility report, and environment details live under `results/paper/`.
Tables and figures are programmatically generated; no manual result editing.

- Schneider, Stenger, Goeke (2014), *Transportation Science* 48(4):500-520,
  DOI [10.1287/trsc.2013.0490](https://doi.org/10.1287/trsc.2013.0490).
- Keskin and Catay (2016), *Transportation Research Part C* 65:111-127,
  DOI [10.1016/j.trc.2016.01.013](https://doi.org/10.1016/j.trc.2016.01.013).
- Klein and Schiffer (2024), *INFORMS Journal on Computing* 36(4):966-973,
  DOI [10.1287/ijoc.2023.0104](https://doi.org/10.1287/ijoc.2023.0104).
