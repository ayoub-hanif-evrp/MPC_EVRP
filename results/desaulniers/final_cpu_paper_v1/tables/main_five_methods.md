# Main Five Methods

Independent robustness v3, 90 matched scenarios, 6 parent instances. Distance uses only scenarios completed by all five methods. The offline gap is to a physically feasible full-service reference, not an online oracle score.

| Method | Runs | Served/total | Service % | Complete/runs | Complete % | Offline service gap | Distance on common complete | Common complete n | Mean worker wall s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COMPLETION | 90 | 4586/5250 | 87.35 | 40/90 | 44.44 | 664 | 995.36 | 39 | 2.93 |
| MCTS | 90 | 4874/5250 | 92.84 | 45/90 | 50.00 | 376 | 1001.41 | 39 | 70.75 |
| ALNS | 90 | 5195/5250 | 98.95 | 63/90 | 70.00 | 55 | 1017.67 | 39 | 82.12 |
| HGS | 90 | 5117/5250 | 97.47 | 58/90 | 64.44 | 133 | 1044.99 | 39 | 140.66 |
| ACS | 90 | 5039/5250 | 95.98 | 49/90 | 54.44 | 211 | 772.34 | 39 | 105.11 |
