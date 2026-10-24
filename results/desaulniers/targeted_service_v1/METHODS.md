# Targeted service-improvement study

This is a separate development extension of frozen main commit
`4d1298669455edd1efb82232a69375e55cfb3a62`, not a correction or replacement of
the original final holdout. No historical raw results or protocols change.

## Candidate definitions

- Original: original constructor, decoder and dispatch, with the same tested
  initialization safety fallback and exact forced-choice coordination used in
  every candidate. Original search engines and settings remain unchanged.
- A_urgency: reserve 0.3 seconds of the existing two-second constructor phase
  for deadline-aware, decoded-option regret insertion and bounded existing
  ejection/reinsertion. Up to four urgent uncovered requests, eight screened
  positions each, and three rounds. Accept only canonical improvements with
  complete physical replay. Save validated progress if the local probe expires.
- B_resources: replace route reconstruction only with optimistic backward
  time-window bounds, incremental forward resources, same-stage Pareto
  dominance, geometric station ordering and exact useful linear charge targets.
  Cheap direct routes are tried first; bounded backtracking keeps 12 labels.
  Targets include slack-limited charge and energy for short customer blocks.
  There is no generic per-candidate LP. Bounded truncation is heuristic, not
  an infeasibility certificate. The original decoder remains the default.
- C_first_action: reserve 0.3 seconds from the optimizer for a 0.25-second
  ready-EV first-control comparison. Busy physical actions stay fixed; only
  their future after-state suffixes can change. At most 12 alternative complete
  continuations are independently replayed and scored. Only strict improvement
  of the existing canonical objective can change dispatch. Diagnostic screening
  counts after hypothetical commitments are necessary conditions only.

No combined variant is tested or selected. No objective weight, lexicographic
priority, fleet, charging policy, physical transition, dynamic release, event
trigger, search iteration limit or total five-second limit is changed.
Constructor ownership references are retained for route-instability scoring;
the candidate cannot gain by silently changing that score's reference plan.

## Design and selection

The frozen YAML defines six development parents, each at 25/50/100 customers,
with seeds 0 and 1: 36 matched scenarios. DoD 0.25/0.75 alternates by size index
plus seed, a balanced fractional design, not the full seed-by-DoD factorial.
Seed/DoD effects within one benchmark file are confounded; their strata are
descriptive. Ineligible DoD cases are excluded symmetrically before workers.

Each scenario has Completion and ALNS, each with original/A/B/C: 288 planned
runs before eligibility exclusions. One worker runs at a time. Unrelated
machine workloads are left running as requested; timing is shared-machine,
not an isolated-machine certification. Every worker is audited and each raw
file is bound by SHA-256, scenario, fleet, protocol and source fingerprints.
An external 3,900-second worker watchdog retains failure evidence. A 12-hour
campaign watchdog pauses only between complete scenarios, with exact resume.

Promotion requires ALNS parent-clustered 95% service lower bound above zero,
nonnegative complete-service gain, nonnegative 100-customer gain, nonnegative
gain in each seed, no aggregate service regression for Completion, independent
physical/information audits, and every decision within five seconds. Bootstrap
resamples underlying parents, retaining size/seed/DoD variants together.
Contrasts are exploratory, unadjusted development evidence, not final proof.

If multiple candidates pass, select highest ALNS total service gain, then
complete-service gain, then variant name. Only then open the six separately
reserved, previously unused parents; preflight checks all committed manifests
for exposure. Evaluate original and the selected common component with all
five engines on identical scenarios. No tuning follows holdout exposure.
If none passes, all candidates remain disabled and no new holdout is opened.

## Compatible research foundations

[Desaulniers et al. (2016)](https://doi.org/10.1287/opre.2016.1535) motivates
resource propagation and dominance. The exact benchmark physical model is
preserved; the bounded heuristic decoder is not an exact pricing algorithm.

[Zheng, Liu and Ong](https://arxiv.org/html/2410.19580v2) motivates coordinated
station/charge decisions. Their simultaneous pickup-delivery model is
different and is not imported into this delivery-only benchmark.

[Bent and Van Hentenryck (2007)](https://www.ijcai.org/Abstract/07/293) provides
online control context, not justification for observing future requests.
Earlier unsuccessful waiting policies are not repeated here.

The [2024 dynamic ALNS paper](https://doi.org/10.1016/j.cie.2024.110122) was
identified as relevant, but full text was inaccessible. This implementation
does not claim to reproduce its algorithm.
