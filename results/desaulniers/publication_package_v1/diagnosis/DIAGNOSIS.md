# Instrumented development diagnosis

These are development diagnostic runs. Each raw record has a source-frozen
protocol, matched scenario identity, SHA-256 manifest, and independent plant
replay. Instrumentation consumes decision time, so these timings do not
estimate uninstrumented algorithm performance.

| Instance | DoD | Served | Trace events | Missed-customer plan drops |
| --- | ---: | ---: | ---: | ---: |
| r101_21_25 | 0.75 | 23 | 41286 | 1 |
| r101_21_100 | 0.75 | 94 | 1303097 | 2 |
| c101_21_100 | 0.25 | 98 | 853183 | 2 |

Dropped trace events: 0. Decisions with a recorded, fully
scored optimizer candidate better than the selected objective: 0.

## Measured rejection events

| Screening reason | Events |
| --- | ---: |
| time_window | 1351596 |
| capacity | 12150 |

| Decoder outcome | Events (including cache hits) |
| --- | ---: |
| feasible | 267060 |
| bounded_decoder_failure | 104486 |

## Missed-customer plan transitions

| Stage | Recovery probe result | Transitions |
| --- | --- | ---: |
| optimizer | no_bounded_recovery_witness | 5 |

Recovery probes use the exact recorded root, including after-states of
immutable busy actions, all currently observable requests, and the selected
fleet suffixes. A witness preserves every customer in the selected suffixes
and inserts an additional missed customer. Bounded failure or timeout does
not prove infeasibility. Counts are diagnostic transitions, not independent
benchmark samples; they do not establish the closed-loop benefit of a fix.

Of these 5 transitions, 4 preserve the same immediate service
count while replacing a previously planned customer. The canonical
objective allows such a swap when its lower-priority terms improve.
This motivates a separate search variant retaining incumbent coverage
during equal-service improvements; its benefit requires new paired runs.
