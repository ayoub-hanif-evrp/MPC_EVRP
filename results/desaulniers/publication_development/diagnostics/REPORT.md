# First-visible ALNS insertion audit

Development losses only, read from hash-checked frozen traces. The probe
reconstructs ready-vehicle states and selected soft routes at the first
decision where each missed customer is visible. Each customer has a
two-second direct-insertion and two-second ejection-chain diagnostic
deadlines. Feasible means the original route decoder
and plant replay accept a one-customer insertion preserving the other
customers in that ready vehicle's selected suffix. It does not prove that
the original constructor examined that exact route or that the customer
would ultimately be served in closed loop.

| Outcome | Missed customers |
| --- | ---: |
| feasible_in_top3 | 1 |
| no_bounded_insertion_witness | 8 |
| no_ready_vehicle | 18 |
| selected_soft_plan | 6 |

Among 18 first-visible no-ready losses, 7 had at least one EV in its initial depot-dispatch action at that decision. This is a temporal correlation, not evidence that waiting would have served the customer.

A screening rejection without an independently decoded witness is
not proof of infeasibility. Busy vehicles and alternative route orders
are not exhaustively searched. See the CSV for measured details.

Soft-plan disappearance is recorded for 11 distinct losses
across the decision timelines. This is a trace observation, not proof
that the preceding physical action caused the disappearance. Full
per-decision rows are in `alns_loss_timelines.csv`.
