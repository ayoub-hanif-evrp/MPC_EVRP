# Desaulniers 2016 MP Dataset Semantics

## Local sources

The bundle is `data/opre.2016.1535-sm-data/`, with 168 paired format-1
`.txt` and format-2 `.inst` instances, plus published route files under
`solutions/SF`, `solutions/MF`, `solutions/SP`, and `solutions/MP`.
These labels mean single/multiple and full/partial charging, respectively.
The selected online policy is **MP**. The instance files are shared by all
four policy variants; the policy is fixed in the experiment configuration.

| Format-1 field | Internal value | Format-2 validation |
| --- | --- | --- |
| Node ID/type, x/y | `Location` | Same ID/type in `NODES` and all published arcs |
| Demand, ready, due, service | `Location` | Demand/window scaled by 100; arc time includes service at tail |
| Vehicle load capacity | `Parameters.capacity` | `CAPACITY` |
| Fuel tank capacity Q | Time-equivalent battery `ceil(100 * alpha * Q) / 100` | `BATTERY` |
| Consumption rate g | `alpha * g` in time-equivalent energy units | Arc energy |
| Inverse refueling rate alpha | Encoded into energy; internal charging time per energy unit is 1 | Arc energy |
| Average velocity | `Parameters.speed` | Arc travel time |

The published data have unit consumption rate and speed. For Euclidean
coordinate distance `d`, the loader uses the bundle's upward two-decimal
rounding `ceil(100*x - 1e-9)/100`: cost/distance is rounded `d`, travel
time is rounded `d`, and time-equivalent energy is independently rounded
`alpha*d`. **Energy is not computed from the rounded cost.** The loader
checks every one of the 1,163,456 published arcs across all 168 instances
against these calculations. The `.inst` graph omits station-to-station
arcs; the plant therefore forbids them. Station visits are otherwise
unrestricted in count and may charge partially or fully.

The common objective retains its service-first, risk-aware lexicographic
priorities. Distance remains published travel cost in original units;
energy and capacity use the same time-equivalent transformation, so their
normalized ratios retain their meaning. The linear charge duration is
unchanged after transformation. These changes affect all optimizers,
constructor routes, simulator transitions, and independent replay equally.

## Offline reference and dynamicization

`MF` and `SF` published full-charge routes are independently replayed through
the common plant and accepted only when they serve each customer once,
return every EV, and satisfy battery, capacity, time windows, station arcs,
and reported route/recharge counts. A full-charge route is feasible under
the more permissive MP policy, but it is **not** an MP-optimality claim.
No published route or unpublished future customer enters the online
observation. When no valid full-charge route file is available, the
existing constructive reference solver is the fallback. The MF/SF union
covers 120/168 instances: 56/56 at size 25, 48/56 at size 50, and
16/56 at size 100. The remaining 48 require a constructed reference. The
independent `scripts.validate_desaulniers_coverage` audit records each
instance's published replay or bounded fallback result in
`results/desaulniers/reference_validation/coverage.csv`; unresolved search
must not be misreported as physical infeasibility.
Separately, published SP/MP node orders exist for some instances without
SF/MF routes. The diagnostic `scripts.audit_desaulniers_partial_solutions`
finds continuous-charge witnesses and independently replays them under MP.
These witnessable orders are not silently substituted for the frozen
SF/MF-or-constructed `K_ref` policy, because the published files do not
encode the same charge trace and changing references would change the
historical scenarios.
The broader development runner stops on a reference failure instead of
silently removing that instance from the comparison.

The scenario generator preserves that offline schedule by releasing each
selected request no later than its reference predecessor departure.
Exact-count DoD 0.25, 0.50, and 0.75 correspond to half-up counts and
may realize a slightly different fraction on 25/50 customers. A target
requiring more eligible requests than the reference permits is rejected,
not silently reduced. `K_ref` and the scenario hash are fixed across
methods.

## Evidence boundaries

The pilot and 270-run campaign are development data. The corrected final
holdout is complete at 270 audited runs after a separately preserved ten-run
partial protocol and auditor-only erratum. The initial robustness-v2
preflight was rejected for DoD 0.75 ineligibility before method execution;
the eligible multi-seed robustness-v3 study is separately fingerprinted and
must not be pooled with either final
campaign. None reuse Schneider raw results, preregistration, or a
Schneider-trained Portfolio selector. Published static costs are not compared
directly to this project's dynamic MPC objective.
