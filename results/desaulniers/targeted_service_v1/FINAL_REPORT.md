# Final targeted MPC service-improvement report

Frozen development source: `3302cd8285840d237f6b64bd96bd267002759790`.
Independent development audits: 288.

## What changed

Three separately switched common components were compared with the original control: A,
urgency/true-regret bounded service recovery; B, incremental time bounds and MP resource-label
reconstruction with exact useful charge targets; C, independently replayed first-control alternatives.
Original Completion/MCTS/ALNS/HGS/ACS, event triggers, canonical objective, physics, K_ref,
released-information boundary and five-second end-to-end budget are preserved.

## What the evidence supports

- MPC_COMPLETION / A_urgency: service 94.762% to 95.286%; complete 50.00% to 50.00%; wins/ties/losses 7/28/1; 100-customer gain +4; parent 95% service interval [+0.143, +0.952] pp.
- MPC_COMPLETION / B_resources: service 94.762% to 95.286%; complete 50.00% to 50.00%; wins/ties/losses 6/27/3; 100-customer gain +11; parent 95% service interval [+0.143, +0.952] pp.
- MPC_COMPLETION / C_first_action: service 94.762% to 95.667%; complete 50.00% to 50.00%; wins/ties/losses 11/22/3; 100-customer gain +12; parent 95% service interval [+0.190, +2.000] pp.
- MPC_ALNS / A_urgency: service 99.143% to 99.048%; complete 72.22% to 72.22%; wins/ties/losses 1/33/2; 100-customer gain -2; parent 95% service interval [-0.286, +0.000] pp.
- MPC_ALNS / B_resources: service 99.143% to 99.286%; complete 72.22% to 72.22%; wins/ties/losses 5/26/5; 100-customer gain +4; parent 95% service interval [-0.095, +0.381] pp.
- MPC_ALNS / C_first_action: service 99.143% to 99.143%; complete 72.22% to 75.00%; wins/ties/losses 1/34/1; 100-customer gain -1; parent 95% service interval [+0.000, +0.000] pp.

**No candidate passed the prespecified promotion checks.** All three stay disabled by default.
The original frozen primary study remains the strongest supported published system.
There is no enhanced final holdout or superiority claim. This is a completed negative development study.

## Diagnosis and reference coverage

The retrospective diagnosis evaluated 20 observable decision roots and 108 first-control alternatives.
Twenty-six alternatives were physically validated; none improved the canonical plan. Eighty-two
bounded reconstruction failures are not physical infeasibility proofs. This does not establish
which action would have improved eventual service, and unobserved future requests are never used.
Both formerly unresolved offline cases now have independently replayed full-service references:
r204_21_100 uses three EVs and r208_21_100 uses five. Physical witness coverage is 168/168.
These are separate physical upper bounds, never replacements for historical fleets.

## Publication limits

Historical primary results and original 270/450-run studies are immutable. This extension uses six
development parents, not 18 independent size variants. Bootstrap uncertainty is exploratory;
shared-machine timing is not isolated real-time certification. A valid negative result is useful
but does not establish a stronger routing method or guarantee publication acceptance.

## Reproduction

```powershell
python -m scripts.run_targeted_service --restore development
python -u -m scripts.run_targeted_service
python -m scripts.analyze_targeted_service --stage development
python -m scripts.investigate_targeted_references
python -m pytest -q
```

The runner validates source/data/config hashes and reuses exact saved raw bytes. A mismatched source
fails closed; check out the recorded execution commit before resuming or reproducing optimization.
Analysis replays every raw route independently. Paper tables are Markdown and figures PNG at 300 dpi.
