# Event-Triggered MPC for Dynamic EVRPTW

A common event-triggered MPC controller with Completion, MCTS, ALNS, HGS and
ACS, evaluated on Desaulniers (2016) multiple-partial-charging instances.
All methods share the physical constraints, fixed reference fleet, released
requests, risk-aware lexicographic objective and five-second planning budget.
CPU is the active backend.

## Current paper results

The [final package](results/desaulniers/final_cpu_paper_v1/FINAL_REPORT.md)
contains 450 primary runs and a separate 60-run preregistered replication.
See [every figure and table](results/desaulniers/final_cpu_paper_v1/INDEX.md)
and [the statistics](results/desaulniers/final_cpu_paper_v1/STATISTICAL_ANALYSIS.md).
All five original methods remain the publication configuration.

| Method | Primary service | Fully served scenarios |
| --- | ---: | ---: |
| Completion | 87.35% | 40/90 |
| MCTS | 92.84% | 45/90 |
| ALNS | 98.95% | 63/90 |
| HGS | 97.47% | 58/90 |
| ACS | 95.98% | 49/90 |

These descriptive rankings do not establish superiority across all instances.
There are six independent parents per cohort; repeated DoD/seeds are clustered.
Efficiency comparisons use identical served sets or common complete scenarios.

The [120-run ablation](results/desaulniers/final_cpu_paper_v1/DEVELOPMENT_UPDATE.md)
tested recovery, first-action protection, route quality, caching and their
combination. Combined service gained three net customers with one ACS loss.
The stricter implemented promotion screen is explicitly disclosed as post hoc.
The [CPU supplement](results/desaulniers/final_cpu_paper_v1/CPU_COVERAGE.md)
adds 15 frozen runs, completing 30 original/cache pairs across all six families.
Service counts and complete-service outcomes matched in this panel. Recorded
CPU savings were about 9-37%, with distance trade-offs and earlier regressions.
These are exploratory shared-machine results, not an enhanced holdout.

## Reproduce saved evidence

Use Python 3.11+ from the repository root:

```powershell
python -m pip install -r requirements.txt
python -m scripts.archive_frozen_inputs --restore
python -m scripts.audit_frozen_studies
python -m scripts.audit_enhancement_studies
python -m scripts.audit_reference_inventory
python -m pytest -q --basetemp results/.pytest_cpu_reproduce --junitxml results/desaulniers/final_cpu_paper_v1/audit/final_tests.xml
python -m scripts.render_final_cpu_paper
python -m scripts.audit_final_cpu_completion
```

These commands replay saved evidence and regenerate 300-dpi PNG/SVG figures
and Markdown/CSV/LaTeX tables. No optimization campaign or PDF export is needed.
Plotted coordinates are checked against numerical tables. Frozen CPU-study
bytes are preserved in Git on Windows and LF checkouts. See the
[reproduction guide](results/desaulniers/final_cpu_paper_v1/REPRODUCE.md).

Final validation and cumulative compute accounting are in
`results/desaulniers/final_cpu_paper_v1/audit/MISSION_COMPLETION.json`.
The [objective mapping](docs/FINAL_MISSION_OBJECTIVES.md) distinguishes completed
research work from the unachieved claim of a reliably improved routing policy.

## Dataset and preserved research

The unchanged benchmark is under `data/opre.2016.1535-sm-data/`: 56 instances
at each of 25/50/100 customers across six families. Format-1 parameters and
format-2 arcs are cross-validated. The dynamic generator preserves a feasible
full-service offline reference with the same fleet. That reference has advance
information; unreleased requests remain hidden from online methods.

See [migration details](docs/DESAULNIERS_MIGRATION.md),
[loss diagnosis](results/desaulniers/final_cpu_paper_v1/audit/SERVICE_LOSS_DIAGNOSIS.md),
[limitations](results/desaulniers/final_cpu_paper_v1/LIMITATIONS.md), and the
[repository inventory](docs/REPOSITORY_STATUS.md).

Historical primary, robustness, targeted-service, performance-engineering and
fast-framework evidence is preserved. The [GPU archive](docs/CPU_BACKEND_DECISION.md)
contains exact source and 53 raw records on a verified remote tag. The
[Reliability V2 campaign](results/desaulniers/reliability_v2/FINAL_REPORT.md)
remains stopped at the user's request. Old launchers require their frozen source
revisions; do not restart campaigns merely to regenerate reports.
