# Bounded exchange probes and exact replay-cache ablation

Saved roots: 20. Strict canonical improvements: 0.
One-second diagnostic deadlines: 0.
No heuristic failure is called infeasible. Accepted witnesses retain measured busy commitments
and are independently replayed through the original physical transitions.

The cache ablation repeats identical routes five times, checks exact proposal equality, and
reports fixed-work timing only. It is not a claim about online service or whole-pipeline speedup.

| Root | Cached | Seconds | Hits | Misses |
| --- | --- | ---: | ---: | ---: |
| 0 | False | 0.003836 | 0 | 45 |
| 0 | True | 0.001986 | 36 | 9 |
| 1 | False | 0.005355 | 0 | 45 |
| 1 | True | 0.002536 | 36 | 9 |
| 2 | False | 0.007357 | 0 | 45 |
| 2 | True | 0.003588 | 36 | 9 |
| 3 | False | 0.006313 | 0 | 45 |
| 3 | True | 0.002879 | 36 | 9 |
| 4 | False | 0.013590 | 0 | 100 |
| 4 | True | 0.008041 | 80 | 20 |
| 5 | False | 0.015551 | 0 | 100 |
| 5 | True | 0.008863 | 80 | 20 |
