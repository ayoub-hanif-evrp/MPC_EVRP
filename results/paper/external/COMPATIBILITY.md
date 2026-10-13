# External EVRPTW Compatibility Audit

Audit date: 2026-10-13. Proposed controller is frozen at source SHA-256
`4cdead8ab9956362ba9921c0818b7bcc9690487ab11ba001d087abebe43176b6`.
The machine-readable gate is `evrp/external/compatibility.py`; route order is
independently validated by `evrp/external/replay.py`. `K_ref` is read from each
existing reference schedule, never inferred from an external solver.

| Feature | Our model | RoutingBlocks official EVRPTW example | pyevrp 0.2.1 | Exact match? |
|---|---|---|---|---|
| Coordinates/distances | Euclidean float | Euclidean float | Euclidean float in direct Model mapping | Both for direct mapping |
| Travel time | distance / speed | velocity * distance | distance / speed | RoutingBlocks only when speed=1; all six selected files use 1 |
| Customer service | Schneider service | Parsed service | Direct Model mapping | Both for direct mapping |
| Demands | Schneider demand | Parsed demand | Direct Model mapping | Both for direct mapping |
| Capacity | C payload | C payload | Direct Model mapping | Both for direct mapping |
| Customer TW | Hard ready/due | ADPTW vertex windows | Model windows | Both at data level |
| Depot horizon | Hard return deadline | Depot vertex due | Depot window, validator checks arrival | RoutingBlocks; pyevrp bundled solver unproven |
| Battery | Q energy units | Q converted to recharge-time units | Direct Model mapping | Both at data level |
| Linear energy | r * distance | r * distance / recharge rate in time units | Direct Model mapping | Both at data level |
| Charging rate | charge time = energy * g | rate=1/g | Direct Model mapping rate=1/g | Both at data level |
| Partial recharge | Continuous | ADPTW EVRPTW-PR example | Bundled GreedyInsertion charges to full | RoutingBlocks only |
| Multiple station visits | Allowed | Intermediate station visits | Not established for bundled greedy | RoutingBlocks only |
| Fleet upper bound | Fixed K_ref | Upstream parser defaults to one EV/customer; adapter overrides to K_ref | Model num_available, but bundled greedy does not enforce it | RoutingBlocks with audited override only |
| Safe depot return | Every activated EV must return | Depot-ended routes | Bundled greedy appends depot | RoutingBlocks after independent replay; pyevrp not enough |

## Verdict

- **RoutingBlocks** is conditionally eligible for the six *static* instances:
  each case must pass full parsed-node/arc/parameter equivalence, the adapter
  must set `fleet_size=K_ref`, and every returned route must pass our independent
  time/energy/capacity/depot replay. Its upstream 0.2.1 source SHA is
  `2d2ee06c79b5d458b1aeeafd95a2b42b5441079a` (MIT). An isolated
  Python 3.11.15 environment runs its pinned 0.2.1 Windows wheel. Its official
  example requires pydantic 2 despite a `pydantic~=1.10` requirements file.
  A 100-customer c101_21 seed-0 smoke route served all 100 with 12 EVs and
  passed independent physical replay. The official small c101C5 example
  crashed after attempting an infeasible vehicle-count reduction; no external
  algorithm changes were made. Search-budget overshoot during initialization
  is recorded and disqualifies a run from budget-respecting quality statistics.
- **pyevrp 0.2.1** (MIT, pinned PyPI wheel SHA-256
  `020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377`)
  has an equivalent *direct Model data mapping*, but its advertised
  `SchneiderLoader` raises `DataError: No data found in file` on the repository's
  `D0/S0/C...` Schneider format. Its bundled GreedyInsertion uses full charging,
  ignores its random seed for tie-breaking, and does not enforce `num_available`
  while constructing routes. It is **not an exact fair static comparator** and
  will not be entered in the primary static comparison. A separately labelled
  secondary reference is possible only with explicit Model mapping and replay.
- **Neither package qualifies as a dynamic rolling-horizon baseline**. Their
  documented/static route models do not provide an equivalence-preserving way
  to represent heterogeneous current EV location, time, residual battery/load,
  immutable busy actions, unreleased customers, and the common final depot at
  each event. No fictitious depot restart is used. The dynamic primary methods
  remain Fleet MPC-MCTS, completion-only, and RH-Regret.

The official RoutingBlocks example exposes node orders but not per-station
charge quantities. Our replay solves a *continuous charging witness for that
unchanged node order*, then applies the repository's independent transitions.
This proves physical feasibility of the route order, not equality to an
unpublished internal charge schedule. It does not improve the route order or
replace the external search.

Source evidence: [RoutingBlocks repository](https://github.com/tumBAIS/RoutingBlocks),
[official EVRPTW example](https://github.com/tumBAIS/RoutingBlocks/tree/main/examples/evrptw),
[pyevrp 0.2.1 release](https://pypi.org/project/pyevrp/).
