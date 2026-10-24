# Small-route customer reordering probe

At each missed-customer plan drop, enumerate time-screened permutations
of one selected route's customers plus the target (at most eight total).
Every witness uses the original decoder and plant, preserving all other
fleet routes and hard commitments. Each root has five seconds of offline
diagnostic computation. No witness or timeout does not prove infeasibility.

| Instance | Customer | Outcome | Eligible routes | DFS nodes | Exact decodes |
| --- | --- | --- | ---: | ---: | ---: |
| r101_21_25 | C67 | no_bounded_reordering_witness | 9 | 20 | 0 |
| r101_21_100 | C65 | no_bounded_reordering_witness | 20 | 118 | 0 |
| r101_21_100 | C72 | no_bounded_reordering_witness | 20 | 72 | 0 |
| c101_21_100 | C18 | no_bounded_reordering_witness | 12 | 508 | 2 |
| c101_21_100 | C45 | no_bounded_reordering_witness | 12 | 320 | 0 |
