# Interpreting the targeted extension

## Keep the cohorts separate

The original corrected final holdout contains 270 audited runs, 54 matched
scenarios, 18 benchmark files and six underlying parent cases. Original
ALNS served 99.14% of customers and completed 81.48% of scenarios; Completion
served 92.19% and completed 35.19%. These are frozen primary-study results.
The separate 450-run, multi-seed robustness cohort has ALNS service 98.95%
and complete service 70.00%. Do not pool these cohorts or compare their
percentages directly against the new development percentage as a causal gain.

The targeted study uses paired original/A/B/C runs on a different, declared
development grid. Every claimed candidate effect must use its matched
original run on the identical scenario, not the historical aggregate above.

## Evidence versus explanation

The retrospective loss ledger contains 20 root/customer rows covering ten
eventual misses from three instrumented development runs. Five selected rows
show a constructor-planned customer absent from the selected optimizer plan.
No selected target is listed in an invalid retained suffix; one row has an optimizer deadline.
These counts depend on loss-selected root sampling and do not establish a
causal service-loss mechanism or population failure rates.

The 108 next-control probes comprise 26 validated continuations and 82 bounded
reconstruction failures, with no strict canonical improvement. This is not
evidence that all feasible actions were enumerated or that future-aware
control could not serve the customer. Charging failures are attempted
connections; screen and decoder counts are heuristic calls, not missed-customer
counts or mathematical infeasibility proofs. See diagnosis/paper/loss_ledger.md.

The two successful new offline witnesses close physical coverage to 168/168.
They do not reduce any historical online fleet or retroactively modify request
releases. All 168 schedules were reloaded, replayed, and checked for legal
clairvoyant dispatch under eligible generated releases. See REFERENCE_INVENTORY.md.

## Runtime and uncertainty

All methods retain their full configured iterations and the same five-second
end-to-end decision cap. Extra constructor/control work consumes that same
budget; it is not added outside the cap. Local diagnostic probe deadlines,
optimizer deadlines, worker wall time and actual end-to-end decision latency
are different measures and must not be conflated.

Study workers are sequential, but the machine is shared with unrelated work.
The raw latencies are observed compliance on this machine, not exclusive-machine
real-time certification or a universal hardware speedup. The temporary system
awake request does not alter search settings or permanent power configuration.
Environment details are saved in execution_conditions.json.

The development design has six independent parents, not 36 independent
instances. Parent bootstrap keeps related size, seed and DoD variants together.
Intervals are exploratory and unadjusted across three candidate comparisons.
The development gate only authorizes a new independent evaluation; it does not
establish final superiority. A failed gate leaves the original system active.

## Conditional holdout input-policy amendment

Before opening any new online holdout outcomes, structural reference preflight
identified c202_21_100, r202_21_100 and rc202_21_100 as unavailable under the
legacy reference search. Existing independently audited MP witnesses cover
all three. The separate conditional holdout therefore freezes the explicit
`mp_witness_v1` policy. It never starts another legacy offline search, selects
parents by online performance, changes an online algorithm, or replaces any
historical fleet. All original/enhanced comparisons on a new scenario share
exactly its preregistered witness and K_ref. The development protocol, sources,
selection criteria and raw bytes are unchanged.

The correct complete/resume entry point for this amended future phase is:

```powershell
python -u -m scripts.complete_targeted_study
```

It reuses all existing development records, audits the development selection,
and opens the new MP-input-policy holdout only if promotion was earned. Use one
campaign parent at a time. The original provisional legacy holdout entry point
is retained as source evidence, not the command for the amended holdout.

## Reproduce the additional read-only reporting

```powershell
python -m scripts.audit_targeted_inventory
python -m scripts.report_targeted_losses
python -m scripts.render_targeted_supplement
```

The supplement regenerates readable diagnostic labels and adds complete-service
and 100-customer figures from the saved independently audited aggregates.
No command above runs an optimizer or changes frozen raw results. Publication
tables are Markdown and figures PNG at 300 dpi; internal JSON remains available.
