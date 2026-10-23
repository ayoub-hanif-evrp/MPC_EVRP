# MPC enhancement development status

This branch is a **separate development study**. The corrected 270-run final
holdout, 450-run robustness study, their raw traces, protocols, objective,
and historical reference fleets are unchanged. The original Completion,
MCTS, ALNS, HGS, and ACS methods remain the primary frozen baselines.

## Measured diagnosis

The [trace audit](diagnostics/REPORT.md) independently replayed all 270
development and 450 historical robustness runs. Every dynamic scenario has
a full-service clairvoyant reference that respects releases, but that reference
is **not an online MPC competitor**. The audit found 389 development and
1,439 robustness unserved-customer observations. Most had no immediately
feasible direct action from a ready vehicle at first visibility; this does
**not** prove physical infeasibility, because charging, later dispatch, or a
different earlier commitment may have worked. Some customers were selected
in a soft route and subsequently unserved. Existing traces lack rejected
insertion candidates, so they do not support a definitive causal attribution.

## Controlled development experiments

Every A/B run below used the same fixed scenario, released requests, K_ref,
service-first objective, original plant, and five-second decision limit.
Raw runs are separately fingerprinted and independently replayed.

| Variant | Development evidence | Conclusion |
| --- | --- | --- |
| [Depot-window waiting](dispatch_pilot/RESULTS.md) | 12 selected-case runs; ALNS changes 0, +2, -1; Completion ties | Mixed; optional, not promoted |
| [Continuous LP charging fallback](decoder_pilot/RESULTS.md) | 12 selected-case runs; ALNS changes -3, 0, 0; Completion ties | Slower, no end-to-end gain; optional, not promoted |
| [ALNS Recovery V2 pilot](alns_recovery_pilot/RESULTS.md) | 12 runs on six loss-selected scenarios; net +3 customers, one regression | Motivated a balanced screen only |
| [ALNS Recovery V2 balanced screen](alns_recovery_screen/RESULTS.md) | 36 runs on 18 development instances, six families x three sizes; 1033/1050 original vs 1034/1050 V2, both 12/18 complete | +0.10 percentage points; instance-bootstrap 95% CI [-0.23, +0.43]; insufficient evidence to promote |

The 18-instance screen used one DoD and one seed per instance and is not an
independent holdout. Recovery V2 improves two R1 cases but loses one RC1
customer; the total worker time increased from 1,743 to 1,822 seconds.
The charging fallback has a synthetic feasibility witness, but the
development insertion probe found no first-decision LP-only witness for
the examined ALNS losses. No method is described as generally improved.

## Offline benchmark coverage

Historical [coverage](../reference_validation/SUMMARY.md) was 120 published
full-charge references, 24 constructed references, and 24 reference-search
timeouts among 168 MP instances. A separate
[partial-charge LP witness study](partial_reference_witnesses/RESULTS.md)
materialized and replayed full-service schedules for six of those timed-out
instances using published SP route orders. This establishes offline MP
feasibility for those six under the repository plant; it does not change the
historical 144-instance reference policy, fleet sizes, dynamic scenarios, or
comparison denominator. The remaining 18 timeouts are not infeasibility proofs.

## Decision and limitations

No new independent enhanced-method evaluation was opened. The development
evidence does not yet justify freezing a stronger variant, and using the old
final/robustness outcomes to select one would contaminate a new claim. HGS,
MCTS, and ACS enhancement variants and a fully crossed shared-component
ablation remain unimplemented. These are explicit unfinished parts of the
requested research program, not hidden positive results.

The next research step is instrumented development-case diagnosis of
rejected insertions and irreversible vehicle commitments, followed by a
predeclared broader development comparison only if a specific mechanism is
supported. A genuinely unused, preregistered holdout belongs **after**
development selection, not before it.

## Reproduction

From the repository root, with `requirements.txt` installed:

```powershell
python -m pytest tests -q --basetemp results/.pytest_enhancement
python -m scripts.diagnose_mpc_enhancement
python -m scripts.construct_partial_reference_witnesses
python -m scripts.analyze_alns_recovery_development
python -m scripts.analyze_alns_recovery_screen
```

The analyzers verify existing manifests and do not launch optimization.
The witness constructor reloads and validates existing artifacts rather than
silently replacing them. The development runners have separate protocols;
do not rerun them merely to reproduce the reports.
