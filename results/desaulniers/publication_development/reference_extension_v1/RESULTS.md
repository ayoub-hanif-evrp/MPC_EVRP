# Separate MP reference coverage extension

This offline study uses the original partial-charge route decoder to
construct and immediately save a first full-service feasible reference.
Every successful schedule was independently reloaded and replayed.
Fleet sizes are heuristic upper bounds, not optimal fleet counts. They
are not substituted into any historical online comparison or scenario.

Additional references found: 16/18. Combined physical
witness coverage: 166/168 (144 historical references plus six
separate published-route partial-charge witnesses and this extension).

| Instance | Status | Fleet size | Distance | Seconds |
| --- | --- | ---: | ---: | ---: |
| c204_21_100 | feasible_reference_found | 4 | 1306.21 | 43.0 |
| r202_21_100 | feasible_reference_found | 4 | 1528.22 | 16.9 |
| r203_21_100 | feasible_reference_found | 3 | 1265.16 | 29.3 |
| r204_21_100 | search_timeout |  |  | 120.1 |
| r204_21_50 | feasible_reference_found | 2 | 845.8900000000001 | 26.5 |
| r205_21_100 | feasible_reference_found | 4 | 1835.94 | 65.0 |
| r206_21_100 | feasible_reference_found | 5 | 1663.82 | 55.6 |
| r207_21_100 | feasible_reference_found | 3 | 1182.97 | 85.0 |
| r208_21_100 | search_timeout |  |  | 120.1 |
| r208_21_50 | feasible_reference_found | 2 | 663.3 | 47.5 |
| r209_21_100 | feasible_reference_found | 4 | 1623.9 | 102.8 |
| r209_21_50 | feasible_reference_found | 2 | 904.66 | 33.5 |
| r210_21_100 | feasible_reference_found | 5 | 1776.39 | 98.4 |
| rc202_21_100 | feasible_reference_found | 4 | 2123.48 | 21.0 |
| rc203_21_100 | feasible_reference_found | 5 | 1936.94 | 35.4 |
| rc204_21_100 | feasible_reference_found | 4 | 1706.19 | 78.1 |
| rc206_21_100 | feasible_reference_found | 4 | 2215.58 | 20.5 |
| rc207_21_100 | feasible_reference_found | 4 | 1844.63 | 36.0 |

Unresolved construction and timeout records are not proofs of physical infeasibility.
