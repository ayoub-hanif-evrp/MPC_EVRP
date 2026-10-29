# Desaulniers research outputs

## Future active layout and retention

The current `desaulniers/` tree contains distinct frozen studies. A future
compact layout may use `baseline/` for new five-method runs, `proposed/` for a
future method, `ablations/` for component studies, `validation/` for physical
and integrity audits, and `paper/` for final figures and tables. These are
conceptual destinations; this milestone creates no empty directories or new
campaigns. Do not mix those future outputs with the historical studies below.

Keep each study's protocol, source/configuration hashes, seeds, raw manifest,
failure evidence, and independent audit together. Generated plots and logs
should be committed only when an identified study requires them as evidence.
Before using a new output path, review `.gitignore`: its broad results rule
needs an explicit exception for essential manifests and validation records.

`python -m scripts.maintenance.inventory_results` prints a deterministic JSON
inventory to stdout and does not write, move, or delete files. Its advisory
dispositions are `KEEP_ACTIVE`, `ARCHIVE`, `REMOVE_CANDIDATE`, and `REVIEW`.
`--output PATH` creates a JSON file only when that path does not yet exist.
Use `--summary` to print compact disposition and campaign totals.
Archive and removal candidates require the dependency and recovery checks in
the [retention plan](../docs/RESULTS_RETENTION_PLAN.md).

## Historical Desaulniers studies

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
The separate robustness-v3 study is complete at 450/450 audited runs over
90 matched scenarios and is reported in
[RESULTS.md](desaulniers/robustness_v3/RESULTS.md).

Each raw record is tied to its manifest by SHA-256. Do not mix records from
different source, controller, scenario, dataset, or charging-policy fingerprints.
The historical Schneider outputs are retained in Git history, not in the active
working tree.

Reference schedules and dynamic scenarios are cached under
`results/reference_schedules/` and `results/scenarios/`. Only use them with
the matching benchmark identity and generation protocol.
