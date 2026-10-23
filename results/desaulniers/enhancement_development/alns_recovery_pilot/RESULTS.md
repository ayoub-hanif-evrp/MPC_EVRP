# ALNS recovery v2: selected development pilot

Six **seen, loss-selected** scenarios, not a representative sample or independent evaluation. Original ALNS and Recovery V2 ran in isolated processes with the original decoder, original dispatch policy, identical scenarios/K_ref, unchanged objective, and five-second decisions. Every raw trace has a manifest hash and independent replay.

| Instance | DoD | Original | Recovery v2 | Change | Worker time original / v2 (s) | Max decision latency original / v2 (s) |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| c101_21_100 | 0.25 | 98/100 | 99/100 | +1 | 71.4 / 108.1 | 4.641 / 4.644 |
| r101_21_100 | 0.5 | 97/100 | 97/100 | +0 | 38.2 / 60.4 | 1.771 / 1.742 |
| r101_21_100 | 0.75 | 94/100 | 95/100 | +1 | 39.9 / 93.5 | 0.667 / 1.355 |
| r101_21_50 | 0.5 | 47/50 | 49/50 | +2 | 7.7 / 22.8 | 0.384 / 1.106 |
| r101_21_50 | 0.75 | 47/50 | 47/50 | +0 | 5.9 / 17.7 | 0.177 / 0.521 |
| rc101_21_25 | 0.75 | 22/25 | 21/25 | -1 | 1.9 / 3.8 | 0.100 / 0.328 |

Net paired gain: +3 customers over 6 selected scenarios; mean change +0.50. Median worker-time ratio 2.16x.

This pilot supports further **balanced development screening**, not selection or final-paper superiority claims. The 25-customer regression and runtime costs must remain visible. No independent holdout was opened.
