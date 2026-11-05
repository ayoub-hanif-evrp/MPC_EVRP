# V3A paired development pilot: no charging exposure

The [prespecified eight episodes](PILOT_PROTOCOL.md) completed sequentially in 0.099 seconds of aggregate runner wall time. The full records, source digests, raw-trajectory paths and checksums are in [PILOT_RESULTS.json](PILOT_RESULTS.json). All eight trajectories passed the independent event replay, had zero physical violations, zero failures/timeouts and decision maxima below 0.000081 seconds (five-second limit). There were no fallbacks.

| Dataset A parent | Charger capacity | Independent: served / announced | Endogenous: served / announced | Accepted promises broken (each) | Station charges (each) | Queue waiting (each) | Matched-service distance (each) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `c101_25_2` | Original two per station | 19/25 | 19/25 | 6 | 0 | 0 | 531 |
| `c101_25_2` | Derived one per station | 19/25 | 19/25 | 6 | 0 | 0 | 531 |
| `r101_25_2` | Original two per station | 14/25 | 14/25 | 11 | 0 | 0 | 323 |
| `r101_25_2` | Derived one per station | 14/25 | 14/25 | 11 | 0 | 0 | 323 |

All 25 requests were announced and accepted in each episode. The two planning models made **zero different decision actions** in the four paired comparisons. Charging cost was 159.3 on C and 96.9 on R in both models and both capacities; it was entirely depot recharge cost. Resource conflicts and queue waiting were zero. Conditional operating costs are directly comparable within each pair because served-customer counts and identities match. Per-episode worker wall time ranged from 0.0032 to 0.0053 seconds; Windows `process_time` resolution made some CPU values report zero, so these short CPU measurements should not be interpreted as precise speed comparisons.

The conclusion is limited: this pilot cannot estimate the effect of endogenous public-charger contention because its trajectories never used public charging. The likely mechanism is the current depot-refill assumption combined with the conservative one-customer direct-return rule, but the pilot does not identify a causal contribution of either. No optimizer superiority, population result, or paper-ready effect is claimed.

The five-second per-decision limit and ten-minute episode cap are checked when policy calls and events return; they are not operating-system preemption of a stuck Python call. Every observed call was many orders of magnitude below both limits. A future expensive optimizer pilot should use a separate worker process with a hard external watchdog.

The exactly checkable toy tests independently show the physical mechanism. Under a fixed two-EV charging itinerary, one charger makes the second EV wait three time units and miss a customer's deadline (1/2 served); two chargers start simultaneously and serve 2/2. A separate observable-state toy has one charger busy until time 10 and another free: independent planning chooses the nearer busy station, while explicit busy-time planning chooses the free station. Those examples show *possible* decision differences; they are not substitutes for an exposed benchmark pilot.

Next study: prespecify a new development protocol that creates legitimate public-charger demand without tuning to these eight outcomes, preferably by modeling depot charging time/capacity or using a transparent fixed energy/route regime. Validate that regime against the source's unspecified depot-time semantics, then compare the same two planners in the same finite-capacity plant. Keep the historical five-method and final CPU studies frozen. A new optimizer is not justified by this pilot.
