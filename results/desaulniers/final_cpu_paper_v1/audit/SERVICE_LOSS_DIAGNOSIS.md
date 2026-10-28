# Service-loss mechanisms and proof status

Retrospective development evidence only. These cases were selected by missed-service outcomes and must not tune the independent cohorts.

Source event diagnosis: results/desaulniers/reliability_v2/diagnosis/events.json (SHA-256 eb4f7f32eb6f8785cd80e8f6bfdf7ac4a0b38385ff5a64232a837c3cb648fc43). Source plan-transition probes: results/desaulniers/publication_development/instrumented_v1/loss_transition_probes.csv (SHA-256 7d87d20622d7cba26ad90e319779c8fe3f6336a5a5a6af8842121e6f3ea329eb).

| Mechanism | Observed count | Evidence label |
| --- | ---: | --- |
| Optimistic direct-time arrival impossible at first reveal | 15 | Conditional timing certificate given observed commitments; not offline impossibility |
| Direct-time opportunity disappears later | 113 | Conditional timing certificate at the later measured state; association, not causal proof |
| Customer still feasibly insertable when omitted | 0 proven among 5 probed plan drops | Bounded probes found no additional service witness; global feasibility remains unknown |
| Previously planned customer lost by reassignment | 5 traced drops; 4 of 5 preserved immediate service count | Recorded plan transition, not a closed-loop causal effect |
| Charging/energy reconstruction affected omission | 104,486 bounded decoder failures in three instrumented runs | Decoder event counts, not missed-customer counts or proof of energy infeasibility |
| Deadline or weak candidate caused omission | 0 recorded dominated selected decisions | No positive causal witness; wall-clock search may still affect later trajectories |

The direct-time bound ignores battery, load, other obligations and safe return. A positive bound never proves a feasible EV route. No unreleased customer was supplied to the controller. The six mechanisms overlap in time and are not an exhaustive partition of the 128 missed customers.
