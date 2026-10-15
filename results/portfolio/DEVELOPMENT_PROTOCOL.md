# Optimizer development protocol

The 12 historical development scenarios and 54 inspected historical holdout
scenarios form 66 **development** scenarios. `configs/portfolio_development.yaml`
enumerates them. All comparisons use the same existing paper controller
configuration, five-second total decision limit, reference fleet, scenario
seed and common constructor. A run can select a method subset for pilot work,
but a paired comparison must complete all four methods on the same scenario.

Run `python -m scripts.run_portfolio_campaign --case-limit 1` for a bounded
pilot, or omit the limit for the entire development grid. Raw records are
compressed JSON under `results/portfolio/development/raw/`, with SHA-256
digests in the manifest. Source and protocol hashes are recorded per row.
Incomplete pilots are not treated as comparative evidence. No new final
holdout may run before complementarity review and explicit user approval.
