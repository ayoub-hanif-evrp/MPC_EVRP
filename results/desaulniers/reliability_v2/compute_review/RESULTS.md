# Compute-cost review: user-stopped campaign

Saved runs: 361/1116. Remaining: 755.
The user stopped this study for computational cost, not based on interim algorithm outcomes.
No experiment was restarted or optimization engine executed for this report.
All saved raw byte hashes and recorded worker audit flags were checked; this is not another full physical replay.
Scientific source/protocol, raw files, releases, reference fleets and historical final results are unchanged.

## Where the time went

Cumulative process time: 13.692 h; planning: 13.567 h (99.09%). Planning triggered 28,843 times.
Longest whole worker: 709.9 s. Maximum decision: 4.832696 s.
Five seconds is a limit for one MPC decision, not a whole scenario. A scenario can replan dozens or hundreds of times.
The remaining process overhead includes audit and serialization. Even eliminating it completely cannot remove most runtime.

| Engine | Runs | Worker hours | Planning hours | Calls | Mean worker s | Median worker s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MPC_COMPLETION | 97 | 0.549 | 0.519 | 8556 | 20.36 | 6.57 |
| MPC_MCTS | 66 | 2.040 | 2.017 | 5314 | 111.27 | 63.37 |
| MPC_ALNS | 66 | 3.002 | 2.979 | 4390 | 163.74 | 111.40 |
| MPC_HGS | 66 | 4.713 | 4.688 | 5462 | 257.09 | 228.93 |
| MPC_ACS | 66 | 3.388 | 3.364 | 5121 | 184.79 | 152.33 |

## Why 12 hours did not finish it

The frozen design requires 960 original/flex comparisons, 96 Completion-specific runs and 60 cache ablations.
The configured limit was soft: the runner finishes every method for its current scenario before pausing.
Consequently an expensive scenario can carry execution beyond 12 hours. It was not a hard wall-clock cutoff.
The 755-job remainder projects to 29.3 h using observed method/variant/size means, or 26.5 h using medians. These are cost estimates, not confidence intervals.
Only C1/C2 parents are represented so far. Never treat these estimates as guarantees for R/RC families.

## What to change next, without silently changing the frozen study

1. Keep this campaign stopped and archive its partial results. Do not label 361 runs a completed preregistered study.
2. Retain the already completed primary study for the paper; the new enhancements remain optional and unpromoted.
3. Before any new campaign, preregister a strict total compute budget and gate expensive engine comparisons behind a small fixed screen.
   Prioritize the predeclared ALNS/Completion research question before a large five-engine grid; use untouched parents for any new claim.
   Do not choose or drop scenarios based on this partial study's observed service outcomes.
4. Make admission budget-aware: estimate the next complete paired block and refuse to start it if it exceeds remaining allowance.
   A genuinely hard cutoff requires a whole-worker watchdog that preserves interrupted evidence; never turn interruption into a valid result.
5. Use the existing profiles to target reconstruction/transition work, not plots. The one small-case profile is not representative speedup evidence.
   Exact replay memoization has a separate ablation already. It does not eliminate unique route construction and is not a demonstrated global fix.
6. Concurrent scenarios can reduce elapsed throughput time only as a separately labeled methodology, not midstream isolated-timing evidence.
   Fewer search iterations, smaller horizons, fewer events, or a lower decision budget would change the comparison and require a new version.

No new experiment, holdout, algorithm redesign, automatic restart or GitHub push has been started.
