# Event-level service-loss diagnosis

Misses examined: 128.

All original targeted development trajectories; no new optimization and no holdout tuning.
Direct-time bounds ignore energy, load, other obligations and safe return. A zero is a
conditional measured-state timing certificate, not offline infeasibility or a causal proof.
Idle waits are interruptible; charge, serve and return commitments are not.

| Category | Misses |
| --- | ---: |
| becomes_time_unreachable | 113 |
| unreachable_at_revelation | 15 |

Feasible-route misses require a separately replayed route witness. No such witness is
claimed from an optimistic arrival count. Unknown cases remain unknown.

| Instance | Method | Customer | Release | Due | Category | First zero time |
| --- | --- | --- | ---: | ---: | --- | ---: |
| c101_21_50 | MPC_COMPLETION | C53 | 374.730 | 511.000 | becomes_time_unreachable | 445.25 |
| c101_21_50 | MPC_COMPLETION | C56 | 298.990 | 410.000 | becomes_time_unreachable | 361.0 |
| c101_21_50 | MPC_COMPLETION | C78 | 497.202 | 731.000 | becomes_time_unreachable | 681.4 |
| c101_21_50 | MPC_COMPLETION | C89 | 918.467 | 989.000 | becomes_time_unreachable | 994.0 |
| c101_21_100 | MPC_COMPLETION | C17 | 409.050 | 711.000 | becomes_time_unreachable | 667.8725 |
| c101_21_100 | MPC_COMPLETION | C2 | 185.311 | 553.000 | becomes_time_unreachable | 500.25 |
| c101_21_100 | MPC_COMPLETION | C28 | 348.439 | 510.000 | becomes_time_unreachable | 493.13249999999994 |
| c101_21_100 | MPC_COMPLETION | C36 | 124.398 | 346.000 | becomes_time_unreachable | 292.39 |
| c101_21_100 | MPC_COMPLETION | C40 | 77.466 | 199.000 | becomes_time_unreachable | 180.01250000000002 |
| c101_21_100 | MPC_COMPLETION | C42 | 111.525 | 289.000 | becomes_time_unreachable | 206.0 |
| c101_21_100 | MPC_COMPLETION | C45 | 394.780 | 475.000 | becomes_time_unreachable | 452.3425 |
| c101_21_100 | MPC_COMPLETION | C53 | 69.880 | 511.000 | becomes_time_unreachable | 480.78 |
| c101_21_100 | MPC_COMPLETION | C6 | 146.729 | 741.000 | becomes_time_unreachable | 736.625 |
| c101_21_100 | MPC_COMPLETION | C7 | 300.392 | 836.000 | becomes_time_unreachable | 805.2900000000001 |
| c101_21_100 | MPC_COMPLETION | C78 | 624.989 | 731.000 | becomes_time_unreachable | 722.4749999999999 |
| c101_21_100 | MPC_ALNS | C18 | 0.000 | 601.000 | becomes_time_unreachable | 572.24 |
| c101_21_100 | MPC_ALNS | C45 | 394.780 | 475.000 | becomes_time_unreachable | 445.0 |
| c101_21_100 | MPC_COMPLETION | C15 | 718.115 | 789.000 | becomes_time_unreachable | 768.32 |
| c101_21_100 | MPC_COMPLETION | C31 | 353.314 | 517.000 | becomes_time_unreachable | 509.39 |
| c101_21_100 | MPC_COMPLETION | C37 | 307.754 | 619.000 | becomes_time_unreachable | 607.39 |
| c101_21_100 | MPC_COMPLETION | C39 | 169.049 | 440.000 | becomes_time_unreachable | 417.39 |
| c101_21_100 | MPC_COMPLETION | C56 | 173.348 | 410.000 | becomes_time_unreachable | 353.0 |
| c101_21_100 | MPC_COMPLETION | C68 | 344.097 | 420.000 | becomes_time_unreachable | 384.86 |
| c101_21_100 | MPC_COMPLETION | C69 | 345.137 | 516.000 | becomes_time_unreachable | 479.11 |
| c101_21_100 | MPC_COMPLETION | C7 | 636.838 | 836.000 | becomes_time_unreachable | 819.31 |
| c101_21_100 | MPC_COMPLETION | C77 | 397.673 | 600.000 | becomes_time_unreachable | 564.945 |
| c101_21_100 | MPC_COMPLETION | C80 | 616.535 | 689.000 | becomes_time_unreachable | 646.0 |
| c101_21_100 | MPC_COMPLETION | C81 | 749.920 | 823.000 | becomes_time_unreachable | 779.0271386088034 |
| c101_21_100 | MPC_COMPLETION | C84 | 484.785 | 710.000 | becomes_time_unreachable | 647.0 |
| c101_21_100 | MPC_COMPLETION | C85 | 656.307 | 809.000 | becomes_time_unreachable | 777.4100000000001 |
| c101_21_100 | MPC_COMPLETION | C88 | 774.936 | 895.000 | becomes_time_unreachable | 863.32 |
| c101_21_100 | MPC_COMPLETION | C92 | 333.732 | 519.000 | becomes_time_unreachable | 471.33500000000004 |
| c101_21_100 | MPC_COMPLETION | C94 | 200.125 | 423.000 | becomes_time_unreachable | 359.0 |
| c101_21_100 | MPC_COMPLETION | C95 | 185.772 | 330.000 | becomes_time_unreachable | 321.5 |
| c101_21_100 | MPC_ALNS | C80 | 616.535 | 689.000 | becomes_time_unreachable | 646.0 |
| c201_21_25 | MPC_COMPLETION | C3 | 86.004 | 290.000 | becomes_time_unreachable | 126.0 |
| c201_21_100 | MPC_COMPLETION | C56 | 1486.606 | 1737.000 | becomes_time_unreachable | 1718.9199990000002 |
| c201_21_100 | MPC_COMPLETION | C73 | 869.006 | 1288.000 | becomes_time_unreachable | 1258.5411864123282 |
| c201_21_100 | MPC_COMPLETION | C80 | 913.754 | 1387.000 | becomes_time_unreachable | 1291.0 |
| c201_21_100 | MPC_COMPLETION | C85 | 590.507 | 903.000 | becomes_time_unreachable | 815.255001 |
| r101_21_25 | MPC_COMPLETION | C25 | 26.790 | 147.000 | becomes_time_unreachable | 85.83999999999999 |
| r101_21_25 | MPC_COMPLETION | C77 | 88.479 | 160.000 | becomes_time_unreachable | 153.0 |
| r101_21_25 | MPC_COMPLETION | C79 | 23.030 | 100.000 | becomes_time_unreachable | 85.83999999999999 |
| r101_21_25 | MPC_COMPLETION | C47 | 120.634 | 166.000 | becomes_time_unreachable | 142.0 |
| r101_21_25 | MPC_COMPLETION | C50 | 68.257 | 128.000 | becomes_time_unreachable | 103.56 |
| r101_21_25 | MPC_COMPLETION | C8 | 12.608 | 37.000 | unreachable_at_revelation | 12.607570930667594 |
| r101_21_25 | MPC_ALNS | C8 | 12.608 | 37.000 | unreachable_at_revelation | 12.607570930667594 |
| r101_21_50 | MPC_COMPLETION | C38 | 44.010 | 73.000 | unreachable_at_revelation | 44.00964738100629 |
| r101_21_50 | MPC_COMPLETION | C43 | 32.512 | 53.000 | unreachable_at_revelation | 32.511832293853324 |
| r101_21_50 | MPC_COMPLETION | C51 | 117.619 | 188.000 | becomes_time_unreachable | 160.0 |
| r101_21_50 | MPC_COMPLETION | C61 | 14.966 | 39.000 | unreachable_at_revelation | 14.965598151157266 |
| r101_21_50 | MPC_ALNS | C38 | 44.010 | 73.000 | unreachable_at_revelation | 44.00964738100629 |
| r101_21_50 | MPC_ALNS | C43 | 32.512 | 53.000 | unreachable_at_revelation | 32.511832293853324 |
| r101_21_50 | MPC_ALNS | C61 | 14.966 | 39.000 | unreachable_at_revelation | 14.965598151157266 |
| r101_21_50 | MPC_COMPLETION | C38 | 32.325 | 73.000 | becomes_time_unreachable | 39.0 |
| r101_21_50 | MPC_COMPLETION | C7 | 45.186 | 98.000 | becomes_time_unreachable | 60.0 |
| r101_21_50 | MPC_COMPLETION | C72 | 104.612 | 121.000 | becomes_time_unreachable | 108.06 |
| r101_21_50 | MPC_COMPLETION | C9 | 58.457 | 80.000 | becomes_time_unreachable | 59.0 |
| r101_21_100 | MPC_COMPLETION | C14 | 65.491 | 167.000 | becomes_time_unreachable | 148.0 |
| r101_21_100 | MPC_COMPLETION | C42 | 72.450 | 157.000 | becomes_time_unreachable | 143.77000000000004 |
| r101_21_100 | MPC_COMPLETION | C46 | 34.696 | 60.000 | becomes_time_unreachable | 37.0 |
| r101_21_100 | MPC_COMPLETION | C51 | 153.237 | 188.000 | becomes_time_unreachable | 180.94 |
| r101_21_100 | MPC_COMPLETION | C70 | 13.584 | 59.000 | becomes_time_unreachable | 39.11 |
| r101_21_100 | MPC_COMPLETION | C71 | 19.226 | 127.000 | becomes_time_unreachable | 104.42 |
| r101_21_100 | MPC_COMPLETION | C72 | 49.435 | 121.000 | becomes_time_unreachable | 107.0 |
| r101_21_100 | MPC_COMPLETION | C78 | 86.205 | 104.000 | unreachable_at_revelation | 86.20544676796963 |
| r101_21_100 | MPC_COMPLETION | C85 | 72.382 | 103.000 | becomes_time_unreachable | 91.47500000000001 |
| r101_21_100 | MPC_ALNS | C73 | 0.000 | 146.000 | becomes_time_unreachable | 129.0 |
| r101_21_100 | MPC_COMPLETION | C15 | 103.835 | 124.000 | becomes_time_unreachable | 107.0 |
| r101_21_100 | MPC_COMPLETION | C39 | 32.812 | 60.000 | becomes_time_unreachable | 37.0 |
| r101_21_100 | MPC_COMPLETION | C65 | 56.377 | 78.000 | becomes_time_unreachable | 58.0 |
| r101_21_100 | MPC_COMPLETION | C67 | 103.252 | 153.000 | becomes_time_unreachable | 138.75 |
| r101_21_100 | MPC_COMPLETION | C76 | 146.683 | 193.000 | becomes_time_unreachable | 169.0 |
| r101_21_100 | MPC_COMPLETION | C78 | 90.464 | 104.000 | becomes_time_unreachable | 96.80000000000001 |
| r101_21_100 | MPC_COMPLETION | C79 | 84.492 | 100.000 | becomes_time_unreachable | 87.44 |
| r101_21_100 | MPC_COMPLETION | C86 | 75.481 | 109.000 | becomes_time_unreachable | 97.0 |
| r101_21_100 | MPC_COMPLETION | C99 | 124.692 | 148.000 | becomes_time_unreachable | 138.24 |
| r101_21_100 | MPC_ALNS | C78 | 90.464 | 104.000 | becomes_time_unreachable | 92.0 |
| r101_21_100 | MPC_ALNS | C79 | 84.492 | 100.000 | becomes_time_unreachable | 87.44 |
| r101_21_100 | MPC_ALNS | C88 | 139.502 | 176.000 | becomes_time_unreachable | 167.27394938993518 |
| rc101_21_25 | MPC_COMPLETION | C21 | 12.674 | 185.000 | becomes_time_unreachable | 170.0875 |
| rc101_21_25 | MPC_COMPLETION | C44 | 6.125 | 66.000 | unreachable_at_revelation | 6.125295468276308 |
| rc101_21_25 | MPC_COMPLETION | C72 | 10.834 | 136.000 | becomes_time_unreachable | 100.0 |
| rc101_21_25 | MPC_COMPLETION | C75 | 45.471 | 95.000 | becomes_time_unreachable | 72.27000000000001 |
| rc101_21_25 | MPC_COMPLETION | C38 | 52.125 | 120.000 | becomes_time_unreachable | 59.5 |
| rc101_21_25 | MPC_COMPLETION | C44 | 35.196 | 66.000 | unreachable_at_revelation | 35.19640400323234 |
| rc101_21_25 | MPC_COMPLETION | C51 | 126.822 | 179.000 | becomes_time_unreachable | 169.44750000000002 |
| rc101_21_25 | MPC_ALNS | C38 | 52.125 | 120.000 | unreachable_at_revelation | 52.1246912001306 |
| rc101_21_25 | MPC_ALNS | C44 | 35.196 | 66.000 | unreachable_at_revelation | 35.19640400323234 |
| rc101_21_25 | MPC_ALNS | C74 | 34.011 | 149.000 | becomes_time_unreachable | 131.4875 |
| rc101_21_50 | MPC_COMPLETION | C23 | 88.898 | 119.000 | becomes_time_unreachable | 89.0 |
| rc101_21_50 | MPC_COMPLETION | C39 | 80.893 | 130.000 | unreachable_at_revelation | 80.89329084976094 |
| rc101_21_50 | MPC_COMPLETION | C43 | 44.206 | 137.000 | becomes_time_unreachable | 96.82855098955484 |
| rc101_21_50 | MPC_COMPLETION | C47 | 32.570 | 94.000 | becomes_time_unreachable | 61.0 |
| rc101_21_50 | MPC_COMPLETION | C48 | 141.611 | 184.000 | becomes_time_unreachable | 157.74 |
| rc101_21_50 | MPC_COMPLETION | C67 | 150.427 | 204.000 | becomes_time_unreachable | 200.54 |
| rc101_21_50 | MPC_COMPLETION | C72 | 47.971 | 136.000 | becomes_time_unreachable | 103.77000000000001 |
| rc101_21_50 | MPC_COMPLETION | C87 | 32.191 | 88.000 | becomes_time_unreachable | 78.2475 |
| rc101_21_50 | MPC_ALNS | C39 | 80.893 | 130.000 | unreachable_at_revelation | 80.89329084976094 |
| rc101_21_50 | MPC_COMPLETION | C2 | 29.442 | 114.000 | becomes_time_unreachable | 94.8875 |
| rc101_21_50 | MPC_COMPLETION | C3 | 82.171 | 143.000 | becomes_time_unreachable | 94.8875 |
| rc101_21_50 | MPC_COMPLETION | C7 | 84.391 | 132.000 | becomes_time_unreachable | 94.8875 |
| rc101_21_50 | MPC_COMPLETION | C72 | 72.352 | 136.000 | becomes_time_unreachable | 119.1 |
| rc101_21_50 | MPC_COMPLETION | C73 | 92.879 | 125.000 | becomes_time_unreachable | 99.0 |
| rc101_21_50 | MPC_COMPLETION | C87 | 20.326 | 88.000 | becomes_time_unreachable | 59.0 |
| rc101_21_50 | MPC_COMPLETION | C89 | 102.141 | 159.000 | becomes_time_unreachable | 129.0 |
| rc101_21_50 | MPC_ALNS | C73 | 92.879 | 125.000 | becomes_time_unreachable | 99.0 |
| rc101_21_100 | MPC_COMPLETION | C20 | 81.373 | 149.000 | becomes_time_unreachable | 142.5675 |
| rc101_21_100 | MPC_COMPLETION | C26 | 55.289 | 133.000 | becomes_time_unreachable | 112.0 |
| rc101_21_100 | MPC_COMPLETION | C34 | 68.016 | 182.000 | becomes_time_unreachable | 163.67999999999998 |
| rc101_21_100 | MPC_COMPLETION | C6 | 39.347 | 135.000 | becomes_time_unreachable | 123.61 |
| rc101_21_100 | MPC_COMPLETION | C71 | 33.343 | 80.000 | becomes_time_unreachable | 54.0 |
| rc101_21_100 | MPC_COMPLETION | C77 | 67.465 | 120.000 | becomes_time_unreachable | 104.52999999999999 |
| rc101_21_100 | MPC_COMPLETION | C17 | 152.086 | 189.000 | becomes_time_unreachable | 185.0 |
| rc101_21_100 | MPC_COMPLETION | C23 | 73.839 | 119.000 | becomes_time_unreachable | 110.88000000000001 |
| rc101_21_100 | MPC_COMPLETION | C3 | 86.764 | 143.000 | becomes_time_unreachable | 122.99288399767131 |
| rc101_21_100 | MPC_COMPLETION | C39 | 99.429 | 130.000 | becomes_time_unreachable | 120.0 |
| rc101_21_100 | MPC_COMPLETION | C49 | 80.230 | 115.000 | becomes_time_unreachable | 83.8775 |
| rc101_21_100 | MPC_COMPLETION | C68 | 76.269 | 129.000 | becomes_time_unreachable | 108.6884137043051 |
| rc101_21_100 | MPC_COMPLETION | C76 | 39.134 | 85.000 | becomes_time_unreachable | 58.0 |
| rc101_21_100 | MPC_COMPLETION | C8 | 93.414 | 125.000 | becomes_time_unreachable | 112.76288399767132 |
| rc101_21_100 | MPC_COMPLETION | C81 | 154.714 | 187.000 | becomes_time_unreachable | 161.85999999999999 |
| rc101_21_100 | MPC_COMPLETION | C84 | 51.780 | 103.000 | becomes_time_unreachable | 83.8775 |
| rc101_21_100 | MPC_COMPLETION | C85 | 57.883 | 95.000 | becomes_time_unreachable | 83.8775 |
| rc101_21_100 | MPC_COMPLETION | C88 | 79.854 | 124.000 | becomes_time_unreachable | 100.30583696114476 |
| rc101_21_100 | MPC_COMPLETION | C89 | 108.408 | 159.000 | becomes_time_unreachable | 121.0 |
| rc101_21_100 | MPC_ALNS | C17 | 152.086 | 189.000 | becomes_time_unreachable | 179.01999999999998 |
| rc101_21_100 | MPC_ALNS | C8 | 93.414 | 125.000 | becomes_time_unreachable | 114.21 |
