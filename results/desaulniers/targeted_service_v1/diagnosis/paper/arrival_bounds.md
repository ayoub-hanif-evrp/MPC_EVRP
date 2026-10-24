# Optimistic arrival bounds around actual first commitments

Counts ignore energy, remaining payload, other customer obligations and terminal return.
A positive count is not a feasible insertion witness. A zero count means no measured
origin meets even this optimistic time test under the stated immutable commitments;
it is not an infeasibility claim about the original offline instance or all prior controls.
Busy origins already represent immutable-action after-states. Ready origins are then
advanced through the selected first action only, without revealing future requests.
No eventually missed target is itself served by these first commitments.

| Instance | Target | Root time | Optimistic EV count before / after | Earliest service bound before / after | Due |
| --- | --- | ---: | --- | --- | ---: |
| r101_21_25 | C67 | 0.000 | 9 / 9 | 143.000 / 143.000 | 153.000 |
| r101_21_25 | C8 | 21.232 | 0 / 0 | 47.482 / 47.482 | 37.000 |
| r101_21_25 | C67 | 86.843 | 4 / 3 | 143.000 / 143.000 | 153.000 |
| r101_21_25 | C67 | 94.630 | 2 / 2 | 143.000 / 143.000 | 153.000 |
| r101_21_100 | C65 | 8.391 | 12 / 11 | 68.000 / 68.000 | 78.000 |
| r101_21_100 | C61 | 18.258 | 0 / 0 | 41.190 / 41.190 | 39.000 |
| r101_21_100 | C19 | 36.408 | 0 / 0 | 62.670 / 62.670 | 58.000 |
| r101_21_100 | C65 | 38.382 | 2 / 2 | 74.010 / 74.010 | 78.000 |
| r101_21_100 | C65 | 38.736 | 2 / 2 | 74.010 / 74.010 | 78.000 |
| r101_21_100 | C72 | 64.905 | 9 / 9 | 111.000 / 111.000 | 121.000 |
| r101_21_100 | C78 | 81.324 | 3 / 3 | 94.000 / 94.000 | 104.000 |
| r101_21_100 | C72 | 103.546 | 1 / 1 | 119.050 / 119.050 | 121.000 |
| r101_21_100 | C72 | 104.778 | 1 / 1 | 119.050 / 119.050 | 121.000 |
| r101_21_100 | C25 | 126.006 | 0 / 0 | 147.417 / 147.417 | 147.000 |
| c101_21_100 | C18 | 0.000 | 12 / 12 | 557.000 / 557.000 | 601.000 |
| c101_21_100 | C18 | 387.780 | 12 / 12 | 557.000 / 557.000 | 601.000 |
| c101_21_100 | C18 | 388.353 | 12 / 12 | 557.000 / 557.000 | 601.000 |
| c101_21_100 | C45 | 394.780 | 5 / 5 | 423.240 / 423.240 | 475.000 |
| c101_21_100 | C45 | 409.050 | 3 / 3 | 423.240 / 423.240 | 475.000 |
| c101_21_100 | C45 | 421.240 | 3 / 2 | 423.240 / 468.810 | 475.000 |
