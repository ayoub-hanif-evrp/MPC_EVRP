# CPU Six Family Pairs

Exploratory development: six parents, one per family, two per size, DoD 0.5 seed 3; 30 original/cache pairs. Original raw and 15 earlier CPU runs are reused; 15 missing-family CPU runs were preregistered separately. Sequential shared-machine timings were obtained at different dates; ratios are observations, not controlled hardware speedups. CPU intervals resample six parent blocks (10,000 draws, seed 20261028). Distance differences use identical served-customer sets only. Historical cache regressions remain evidence against a universal service-preservation claim.

| Parent | Family | Customers | Method | Original served | Cache served | Served delta | Original complete | Cache complete | Original CPU s | Cache CPU s | Original wall s | Cache wall s | Identical served set | Conditional distance delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c101 | C1 | 25 | COMPLETION | 22 | 22 | 0 | 0 | 0 | 0.438 | 0.375 | 0.332 | 0.266 | True | 0.000 |
| c101 | C1 | 25 | MCTS | 25 | 25 | 0 | 1 | 1 | 12.047 | 8.516 | 12.041 | 8.629 | True | 0.000 |
| c101 | C1 | 25 | ALNS | 25 | 25 | 0 | 1 | 1 | 1.594 | 1.203 | 1.507 | 1.146 | True | 0.000 |
| c101 | C1 | 25 | HGS | 25 | 25 | 0 | 1 | 1 | 12.156 | 7.359 | 12.143 | 7.418 | True | 0.000 |
| c101 | C1 | 25 | ACS | 25 | 25 | 0 | 1 | 1 | 2.109 | 1.562 | 2.121 | 1.604 | True | 0.000 |
| c201 | C2 | 50 | COMPLETION | 49 | 49 | 0 | 0 | 0 | 1.656 | 1.500 | 1.515 | 1.440 | True | 0.000 |
| c201 | C2 | 50 | MCTS | 50 | 50 | 0 | 1 | 1 | 119.719 | 109.328 | 120.830 | 110.737 | True | 141.870 |
| c201 | C2 | 50 | ALNS | 50 | 50 | 0 | 1 | 1 | 113.906 | 96.250 | 115.515 | 97.423 | True | -135.400 |
| c201 | C2 | 50 | HGS | 50 | 50 | 0 | 1 | 1 | 124.000 | 118.000 | 125.324 | 119.076 | True | -218.820 |
| c201 | C2 | 50 | ACS | 50 | 50 | 0 | 1 | 1 | 61.922 | 21.266 | 62.736 | 21.244 | True | 0.000 |
| r101 | R1 | 100 | COMPLETION | 84 | 84 | 0 | 0 | 0 | 2.578 | 1.938 | 2.509 | 1.833 | True | 0.000 |
| r101 | R1 | 100 | MCTS | 90 | 90 | 0 | 0 | 0 | 16.984 | 12.094 | 17.062 | 12.089 | True | 0.000 |
| r101 | R1 | 100 | ALNS | 97 | 97 | 0 | 0 | 0 | 73.234 | 53.953 | 73.822 | 54.446 | True | 0.000 |
| r101 | R1 | 100 | HGS | 97 | 97 | 0 | 0 | 0 | 283.078 | 257.125 | 285.992 | 259.882 | False | NA |
| r101 | R1 | 100 | ACS | 89 | 89 | 0 | 0 | 0 | 216.172 | 202.016 | 218.515 | 203.507 | True | 0.000 |
| r201 | R2 | 25 | COMPLETION | 25 | 25 | 0 | 1 | 1 | 1.078 | 0.922 | 0.960 | 0.934 | True | 0.000 |
| r201 | R2 | 25 | MCTS | 25 | 25 | 0 | 1 | 1 | 29.141 | 19.219 | 29.443 | 19.217 | True | -45.470 |
| r201 | R2 | 25 | ALNS | 25 | 25 | 0 | 1 | 1 | 34.281 | 19.781 | 34.520 | 19.720 | True | -67.600 |
| r201 | R2 | 25 | HGS | 25 | 25 | 0 | 1 | 1 | 39.484 | 28.109 | 39.672 | 28.218 | True | -17.690 |
| r201 | R2 | 25 | ACS | 25 | 25 | 0 | 1 | 1 | 5.031 | 2.672 | 5.008 | 2.581 | True | 0.000 |
| rc101 | RC1 | 50 | COMPLETION | 42 | 42 | 0 | 0 | 0 | 0.844 | 0.578 | 0.787 | 0.580 | True | 0.000 |
| rc101 | RC1 | 50 | MCTS | 50 | 50 | 0 | 1 | 1 | 20.438 | 13.516 | 20.589 | 13.695 | True | 0.000 |
| rc101 | RC1 | 50 | ALNS | 49 | 49 | 0 | 0 | 0 | 11.000 | 5.969 | 11.018 | 6.141 | True | 0.000 |
| rc101 | RC1 | 50 | HGS | 48 | 48 | 0 | 0 | 0 | 42.734 | 30.125 | 43.214 | 30.382 | True | 0.000 |
| rc101 | RC1 | 50 | ACS | 47 | 47 | 0 | 0 | 0 | 26.594 | 21.078 | 26.750 | 21.359 | True | 0.000 |
| rc201 | RC2 | 100 | COMPLETION | 100 | 100 | 0 | 1 | 1 | 5.641 | 2.375 | 5.660 | 2.358 | True | 0.000 |
| rc201 | RC2 | 100 | MCTS | 100 | 100 | 0 | 1 | 1 | 236.578 | 233.234 | 238.782 | 234.322 | True | 261.170 |
| rc201 | RC2 | 100 | ALNS | 100 | 100 | 0 | 1 | 1 | 225.375 | 220.906 | 227.557 | 221.510 | True | -29.120 |
| rc201 | RC2 | 100 | HGS | 100 | 100 | 0 | 1 | 1 | 230.109 | 226.828 | 232.013 | 227.414 | True | -167.500 |
| rc201 | RC2 | 100 | ACS | 100 | 100 | 0 | 1 | 1 | 215.656 | 202.125 | 217.816 | 202.679 | True | 350.530 |
