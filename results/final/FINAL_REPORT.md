# Final Risk-Aware Fleet MPC-MCTS Development Report

## Status and provenance

**Development gate: FAIL. Holdout: not run or inspected.** The frozen experimental
source was Git commit `6a1ab7ea1944a8f06665a72a3da3d90462a93f9b` with
source SHA-256 `b56e69e4c049ea47553b0c1c1a4b4f09ab766fd3d5755afa25573f299c9eabfd`.
All 6 static and 24 development records completed, and all 30 passed the
independent structural, physics, and information audit. The [manifest](summaries/raw_sha256_manifest.json)
binds each included raw file to its SHA-256, source, scenario, and run identity.
The [compressed raw archive](raw/frozen_records_6a1ab7e.tar.gz) contains exactly
those 30 files; its SHA-256 is
`a18d762a142865f71014c3f86197f39ff0b8e70106642e0b4eee9a21d7993d8b`.
Earlier files in `raw/static/` from superseded commits are excluded by the
analysis script. The six development scenarios have target and realized DoD 0.5,
scenario seeds 0/1, algorithm seed 0, and fixed reference fleet K_ref shared
within each pair. Conditions were run sequentially for isolated timing.

The corrected method retains fleet-level MPC and MCTS. No LNS follows MCTS;
`ROLLING_LNS` is the conventional comparator. MCTS searches assignment,
sequence, and fleet restructuring while the decoder handles charging and exact
route feasibility. The controller uses only released customers and immutable
busy-vehicle commitments.

## Frozen objective

Final plan selection uses lexicographic minimization, never the scalar tree
reward. For uncovered released customers:

`J_A = lexmin(U, screened_Z0, screened_Z1, R_TW, R_BAT, R_CAP, D_normalized)`.

The zero/one counts are forward/backward *screened* insertion gaps, not exact
feasible-option counts. At full current coverage:

`J_B = lexmin(R_FLEX, V, C_OP, D, R_STAB)`, with
`R_FLEX = (R_TW + R_BAT + R_CAP + R_TIME)/4`.

For active vehicle `k`, the time reserve is
`clip((T_end - T_finish,k)/(T_end - t), 0, 1)`; `R_TIME` is one minus its
active-vehicle mean. `C_OP` is the mean of normalized distance, route duration,
charging time, waiting time, TW risk, battery risk, and route-balance risk.
The bounded MCTS reward is search guidance only. The hard event budget is five
seconds with a common 20 ms cooperative-stop guard and approximately 50 ms
reserved internally for final replay.

## Verification and static results

- Full suite: **287 passed**, recorded in `results/verification/pytest.xml`.
- Four Schneider small-case reference validations: **4/4 passed** in
  [reference_validation.csv](reference_validation/reference_validation.csv).
- Static frozen-commit Fleet validation: **600/600 customers served** on all
  six development instances; all six independent audits passed.
- Static timing caveat: two decision events exceeded five seconds; maximum
  **5.0143 s**. Static service validity does not erase the timing violation.

## Dynamic development

The full 12-pair DoD 0.5 development grid is complete. Fleet MPC-MCTS served
**1005/1200** customers versus **782/1200** for Rolling-LNS: **6 wins, 1 tie,
5 losses** on service. This aggregate advantage is heavily driven by very
low Rolling-LNS service on type-2 cases. Fleet itself had severe individual
collapses, including **57/100** on `r201_21` seed 1, **63/100** on `rc201_21`
seed 1, and **71/100** on `c101_21` seed 1 and `r101_21` seed 0.

| Instance | Seed 0 Fleet/LNS | Seed 1 Fleet/LNS |
| --- | ---: | ---: |
| c101_21 | 79/85 | 71/90 |
| c201_21 | 100/29 | 100/37 |
| r101_21 | 71/100 | 82/97 |
| r201_21 | 100/38 | 57/34 |
| rc101_21 | 82/99 | 100/100 |
| rc201_21 | 100/36 | 63/37 |

Fleet completed service in 5/12 runs; Rolling-LNS in 2/12. C1, R1, and RC1
mostly favor Rolling-LNS, while C2, R2, and RC2 favor Fleet in aggregate.
The detailed [paired CSV](tables/development_pairs.csv),
[LaTeX table](tables/development_service.tex), and
[service-difference PNG](figures/service_delta_by_pair.png) retain every case.
The [family PNG](figures/service_by_family.png) shows the type-1/type-2 split;
both PNGs have source CSVs in `figures/`.

**Conditional secondary outcomes.** Exactly one pair had equal service:
`rc101_21` seed 1, where both served 100, but Fleet activated 21 EVs versus
Rolling-LNS's 19. No pair had both equal service and equal EV count, so there
is **no eligible paired distance comparison**. Unconditional EV or distance
means are not used to rank the methods.

The planned full-coverage Fleet flexibility risk averaged **0.4786** and its
operational-risk cost **0.3676** across the 11 runs with at least one
full-coverage MCTS decision (mean of run means). One run had no such decision;
its value is undefined, not zero. These are internal normalized planned
objectives, not directly comparable to a Rolling-LNS objective measured on
the same scale. Realized distance is retained in the paired CSV.

**Computation.** Fleet completed **347,365 MCTS iterations** and expanded
**271,761 nodes** across 1,950 decision epochs. Its recorded service-phase
search totaled 1,303.67 s and full-coverage search 3,081.85 s. Final replay
validation totaled 0.984 s; 455 decisions used an already validated deadline
fallback. The largest per-run p95 was **4.9832 s** for Fleet and **4.9959 s**
for Rolling-LNS; these are maxima of run-level p95 values, not pooled p95s.
Maximum individual events were **5.0284 s** and **5.0256 s**, respectively.
Fleet had **14/1,950** overrun events and Rolling-LNS **10/1,615**. The
five-second ceiling was therefore not strictly met by either method.

## Gate and interpretation

The preregistered aggregate-service, win/loss, multi-family, and audit checks
passed. The **no-severe-collapse** check failed (Fleet minimum 57/100), and
the **strict event-latency** check failed. Consequently the development gate
**failed**, the untouched holdout was **not run**, and no holdout comparison is
claimed. The paper hypothesis of a robust, deadline-compliant dynamic
advantage for Risk-Aware Fleet MPC-MCTS is **not supported by this complete
development grid**, despite the favorable aggregate customer count.

The main limitations are strong type-1 dynamic service losses, extreme
type-2 Rolling-LNS degradation that makes aggregate comparison fragile,
optimistic screened rather than exact insertion-option counts, cooperative
Python timing that occasionally crosses the nominal budget, and only two
correlated scenario seeds per instance. No individual seed, fleet size, or
holdout result was used for retuning after this campaign.
