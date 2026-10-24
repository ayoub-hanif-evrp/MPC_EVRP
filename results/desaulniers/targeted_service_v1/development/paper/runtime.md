# Shared-machine end-to-end decision timing

| Engine | Variant | Decisions | Mean s | p95 s | Max s | Deadline events | Control probe deadlines | Constructor probe deadlines |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MPC_COMPLETION | original | 2201 | 0.033807 | 0.124433 | 2.014792 | 0 | 0 | 0 |
| MPC_COMPLETION | A_urgency | 2179 | 0.039125 | 0.129832 | 1.997658 | 0 | 0 | 8 |
| MPC_COMPLETION | B_resources | 2188 | 0.019004 | 0.041941 | 2.015074 | 0 | 0 | 0 |
| MPC_COMPLETION | C_first_action | 2256 | 0.067846 | 0.340759 | 2.265421 | 0 | 199 | 0 |
| MPC_ALNS | original | 1895 | 1.446245 | 4.750401 | 4.796795 | 612 | 0 | 0 |
| MPC_ALNS | A_urgency | 1919 | 1.542060 | 4.750498 | 4.806845 | 661 | 0 | 9 |
| MPC_ALNS | B_resources | 1790 | 1.364895 | 4.731605 | 4.752377 | 492 | 0 | 0 |
| MPC_ALNS | C_first_action | 1885 | 1.419367 | 4.701004 | 4.740300 | 452 | 244 | 0 |
