# Publication development: evidence and decisions

This branch continues research from `bad3934`. The corrected final holdout,
robustness-v3 campaign, original development traces, and their protocols and
manifests are unchanged. Original MPC Completion, MCTS, ALNS, HGS, and ACS
remain runnable and unchanged in their default configurations.

## Measured mechanism

The [first-visible ALNS audit](diagnostics/REPORT.md) examined all 33 missed
customers in the frozen development ALNS traces. It hash-checked raw files,
reconstructed observable first-decision states, and tested original-decoder
insertion options for selected ready-vehicle suffixes. Outcomes: 18 had no
ready EV; six were already in a soft plan; one had an exact feasible
top-three insertion; eight had no bounded insertion witness. No feasible
beyond-top-three option, screen false negative, or bounded ejection-chain
witness was found in these particular first-visible probes. This does not
establish physical impossibility, or rule out a different route order or
later recovery. Eleven missed customers disappeared from soft plans at a
later decision; those transitions and their triggers are in the timeline CSV.

Seven of the 18 no-ready first-visible observations overlapped an EV's first
depot-dispatch action. This motivated a narrow reserve experiment, not a
causal claim that waiting would recover those customers.

## Controlled reserve pilot

`depot_slack_reserve_v2` is an explicit, opt-in dispatch variant. At most one
unused depot EV is kept interruptibly idle for at most five time units if a
full replay shows its selected route still serves the same currently visible
customers. It uses no future customer information. The original policy is
the default; the canonical objective, fixed fleet, physical model, and
five-second decision budget are unchanged.

The [12-run selected-case pilot](reserve_pilot/RESULTS.md) compared original
and reserve dispatch for Completion and ALNS on matched 25-, 50-, and
100-customer development cases. All raw traces were independently replayed,
hash-verified, and within five seconds per decision. Paired changes were
Completion `-1, 0, 0` and ALNS `+1, -3, -2` customers; no scenario changed
to complete service. The reserve policy is **not promoted**.

## Instrumented diagnosis and balanced screen

The [instrumented study](instrumented_v1/DIAGNOSIS.md) captured 2,197,566
observable planning events across three development runs, with zero dropped
events. It records action commitments, route origins, screening exclusions,
decode failures, evaluated candidates and selected plans. Five missed-customer
plan drops occurred during optimization; four replaced one customer with
another at equal immediate coverage. No fully scored recorded candidate
dominated the selected ALNS objective at those roots.

Original-decoder insertion/ejection probes, [station-skeleton LP probes](instrumented_v1/STATION_SKELETON.md),
and [small-route reordering](instrumented_v1/LOCAL_REORDERING.md) found no
additional service-preserving witness at the five recorded roots under their
limits. A failed heuristic or local exhaustive neighborhood is not a global
infeasibility proof.

ALNS Stable V3 explicitly restricts equal-service best-incumbent replacements
to the same customer set, while retaining canonical scoring and allowing
strict service increases. The [six-run pilot](stable_pilot_v1/RESULTS.md) had
one win, one tie and one loss, for net zero. The subsequent predeclared
[balanced screen](stable_screen_v1/RESULTS.md) completed all 36 runs across six
families and three sizes: original ALNS served 1,033/1,050 customers; Stable V3
served 1,032/1,050. Both completed 12/18 scenarios. Wins/ties/losses were
0/17/1. The parent-clustered service interval is [-0.29, 0.00] percentage
points. The frozen promotion criterion was not satisfied.

Earlier waiting, generic LP decoding and Recovery V2 experiments are retained
in the [prior development record](../enhancement_development/STATUS.md).
They also did not support promotion. No unsuccessful components are combined
or silently substituted into the original methods.

## Runtime and reference engineering

Synthetic tests reproduce initialization timeout crashes in ALNS, HGS and ACS.
An explicit validated-incumbent fallback fixes those cases without changing
the original control path. An exact forced retained-route coordination switch
avoids redundant MILP calls only when no combinatorial choice remains.
The [coordination probe](coordination_probe_v1/RESULTS.md) requires route equality
with the original solver; the [all-engine runtime validation](runtime_validation_v1/RESULTS.md)
reports service and timing effects separately. These are implementation
checks, not a claim of general service superiority.

Separate first-feasible MP reference construction addresses the 18 unresolved
offline searches. The [complete inventory](audits/REFERENCE_INVENTORY.md) reports
all 168 parses, independently replayed witnesses, fleet upper bounds and DoD
eligibility. The opt-in `mp_witness_v1` reference policy never changes historical
fleets or releases. Search failures and timeouts remain explicit evidence.

## Scientific decision and reporting

The [consolidated package](../publication_package_v1/RESULTS.md) includes the
[completion report](../publication_package_v1/FINAL_REPORT.md), original final
results, separate robustness results, failed ablations, runtime validation,
conditional fleet/charging efficiency, parent-instance statistical sensitivity,
reference inventory, audits and reproduction commands. Paper figures are PNG
at 300 dpi or higher and tables are Markdown.

No development search enhancement met its promotion rule. Therefore the
original framework remains the supported service-performance configuration;
there is no fabricated enhanced-method final holdout. Further service gains
are an open research problem, not an uncompleted background campaign.

## Reproduction

```powershell
python -m pytest tests -q --basetemp results/.pytest_publication
python -m scripts.archive_frozen_inputs --restore
python -m scripts.audit_frozen_studies
python -m scripts.audit_enhancement_studies
python -m scripts.audit_reference_inventory
python -m scripts.analyze_publication_pair --config configs/publication_stable_screen_v1.yaml
python -m scripts.analyze_runtime_validation
python -m scripts.render_publication_package
```

These commands use existing raw evidence. Frozen optimization runners require
their exact executed source revisions; do not edit protocols to bypass drift.
Do not rerun optimization merely to reproduce the report.
