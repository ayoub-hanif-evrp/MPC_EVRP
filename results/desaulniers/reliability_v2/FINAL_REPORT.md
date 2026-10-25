# Reliability study V2

Stopped at the user's request on 2026-10-25 for computation cost. No runner or worker is active. Preserve all 361 results; no restart without explicit authorization. See compute_review/RESULTS.md for the runtime diagnosis and budget-controlled alternatives.

## Evidence and limits

Historical final and robustness studies, and the completed targeted study, remain immutable.
New development: 12 independent parent cases; all at 100 customers plus one smaller size per parent.
The size panel is partial, not a full parent-size factorial. DoD and seed are fully crossed per file.
One new flexibility-guided exchange mechanism, a cache ablation, and a prospective Completion-only
V1 control comparison were frozen before new outcomes. No arbitrary waiting or future-demand inputs.
Two primary promotion contrasts use 97.5% parent bootstrap intervals; other engine effects are exploratory.
Development promotion is not final superiority. Shared-machine timing is not isolated certification.

See diagnosis/RESULTS.md and diagnosis/profile.json for measured bounds and profiling, not causal claims.

## Development

Runs: 361/1116; status: partial.

No completed new independent final result is claimed. Original ALNS remains the paper's primary system.

## Reproduce

```powershell
python -m pytest -q
python -u -m scripts.run_reliability_study
```

Use the recorded source commit. Valid raw files are byte-checked and reused; source drift fails closed.
Each invocation pauses at a scenario boundary after 12 hours. No earlier campaigns are rerun.
