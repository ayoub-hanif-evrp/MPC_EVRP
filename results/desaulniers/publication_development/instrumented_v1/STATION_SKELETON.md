# Selective charging-station skeleton recovery probe

Each diagnostic probe preserves the selected fleet's customer orders and
each changed route's existing station order, inserts one missed customer,
and solves continuous linear charge quantities. It uses only the recorded
observable root, including after-states of busy actions. Successful routes
are replayed through the original plant and safe-return validator.

Each root has at most five seconds of offline diagnostic work. A failure
under this bounded search is not proof of infeasibility.

| Instance | Customer | Time | Outcome | LPs tried |
| --- | --- | ---: | --- | ---: |
| r101_21_25 | C67 | 94.630 | no_bounded_skeleton_witness | 0 |
| r101_21_100 | C65 | 38.736 | no_bounded_skeleton_witness | 0 |
| r101_21_100 | C72 | 104.778 | no_bounded_skeleton_witness | 0 |
| c101_21_100 | C18 | 388.353 | no_bounded_skeleton_witness | 4 |
| c101_21_100 | C45 | 421.240 | no_bounded_skeleton_witness | 0 |
