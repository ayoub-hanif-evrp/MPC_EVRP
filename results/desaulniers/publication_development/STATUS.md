# Publication enhancement: development checkpoint

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

## Research decision

The prior generic LP charging fallback, depot-window waiting, and ALNS
Recovery V2 also lacked credible balanced gains. The new probe provides no
evidence that simply widening top-three insertion or adding bounded
ejection chains at first visibility will solve the examined ALNS misses.
There is still no defensible enhanced configuration to freeze. Consequently
no new independent final holdout or original-versus-enhanced final table
exists, and the historical rates must not be mixed with selected development
pilot outcomes. The original paper package remains the valid result set.

To claim a stronger system, the remaining work is to capture rejected
candidate and commitment evidence at consequential replans, develop a
different mechanism from that evidence, test it across balanced development
instances and seeds, and only then preregister genuinely unused evaluation
instances. The 18 unresolved offline reference searches are also separate
coverage limitations, not online-method failures or infeasibility proofs.

## Reproduction

```powershell
python -m pytest tests -q --basetemp results/.pytest_publication
python -m scripts.probe_development_insertions
python -m scripts.analyze_reserve_dispatch_pilot
```

The last two commands are read-only with respect to raw traces. The reserve
runner is `python -m scripts.run_reserve_dispatch_pilot`; it reuses only
hash-matched existing results and refuses source/protocol drift. Do not rerun
optimization merely to reproduce the report.
