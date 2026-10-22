# Desaulniers research outputs

The active benchmark is Desaulniers et al. (2016), using multiple partial
recharges. `desaulniers/development_pilot_final_source/` contains source- and
dataset-bound pilot records, an independent physical audit, a manifest, and
analysis outputs. `desaulniers/development_pilot/` is an earlier migration
checkpoint with a different source hash and must not be pooled with it.
These development pilots are not a final holdout or a claim of superiority.

`desaulniers/development_campaign/` is complete at 270/270 audited runs.
The original `desaulniers/final_holdout/` stopped after ten records and is
preserved as audit-failure evidence. The separately fingerprinted corrected
`desaulniers/final_holdout_audit_erratum/` is complete at 270/270 audited
runs. New integrity, coverage, service-loss, paper, pilot, and robustness
outputs are indexed in [INDEX.md](INDEX.md). Never pool these campaigns.

Each raw record is tied to its manifest by SHA-256. Do not mix records from
different source, controller, scenario, dataset, or charging-policy fingerprints.
The historical Schneider outputs are retained in Git history, not in the active
working tree.

Reference schedules and dynamic scenarios are cached under
`results/reference_schedules/` and `results/scenarios/`. Only use them with
the matching benchmark identity and generation protocol.
