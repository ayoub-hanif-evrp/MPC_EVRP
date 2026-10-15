# Optimizer development protocol

The 12 historical development scenarios and 54 inspected historical holdout
scenarios form 66 **development** scenarios. `configs/portfolio_development.yaml`
enumerates them. All comparisons use the same existing paper controller
configuration, five-second total decision limit, reference fleet, scenario
seed and common constructor. A run can select a method subset for pilot work,
but a paired comparison must complete all five methods on the same scenario.
Every method/scenario executes in a fresh Python interpreter, with no
cross-method mutable cache. Each worker independently audits and saves its
compressed raw result before exiting.

Run `python -m scripts.run_portfolio_campaign --case-limit 1` for a bounded
pilot, or use `--family-pilot` for one DoD 0.5, seed-0 case from each of the
six C1/C2/R1/R2/RC1/RC2 families. Omit both flags only for the entire
development grid. Raw records are
compressed JSON under `results/portfolio/development/raw/`, with SHA-256
digests in the manifest. Source and protocol hashes are recorded per row.
Incomplete pilots are development diagnostics, not final comparative
evidence. No new final holdout may run before method freeze, shadow analysis,
the portfolio gate and a committed preregistration.

Current status: the isolated six-family pilot has 30 audited pre-final-MCTS
records, with a stopped 38-run extension archived separately. The
authoritative 330-run grid must start from the final MCTS source; see
`README.md` for the historical pilot table.
The earlier non-isolated 24-run pilot remains historical only in
`SIX_FAMILY_PILOT.md` and `development/historical_nonisolated_manifest.json`.
