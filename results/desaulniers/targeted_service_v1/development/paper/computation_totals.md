# Scenario-level computation totals, shared machine

Planning hours and process hours are cumulative measured worker totals, not per-decision limits.
More optimization events can increase scenario cost even when every decision respects five seconds.
Process time includes Python startup, simulation, independent audit and raw serialization.

| Engine | Variant | Scenarios | Mean optimization events | Planning hours | Process hours | Median process s | Mean simulation s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MPC_ALNS | A_urgency | 36 | 53.31 | 0.8220 | 0.8336 | 43.627 | 82.435 |
| MPC_ALNS | B_resources | 36 | 49.72 | 0.6787 | 0.6904 | 27.993 | 68.101 |
| MPC_ALNS | C_first_action | 36 | 52.36 | 0.7432 | 0.7546 | 48.567 | 74.552 |
| MPC_ALNS | original | 36 | 52.64 | 0.7613 | 0.7727 | 42.386 | 76.368 |
| MPC_COMPLETION | A_urgency | 36 | 60.53 | 0.0237 | 0.0339 | 1.845 | 2.563 |
| MPC_COMPLETION | B_resources | 36 | 60.78 | 0.0116 | 0.0213 | 1.562 | 1.327 |
| MPC_COMPLETION | C_first_action | 36 | 62.67 | 0.0425 | 0.0528 | 2.493 | 4.455 |
| MPC_COMPLETION | original | 36 | 61.14 | 0.0207 | 0.0308 | 1.761 | 2.256 |
