# Incremental refactoring roadmap

The first milestone established documentation and a read-only results inventory.
No operational module has moved. The target is a small set of clear boundaries,
not an immediate package tree of empty directories.

| Order | Narrow change | Completion check |
| --- | --- | --- |
| 1. Configuration and output paths | Add a read-only path/configuration preview for new runs; migrate a nonfrozen launcher later. | Preview resolves root-relative YAML and isolated output paths without writes; all five methods still import. Writer and resume behavior remain future work. |
| 2. Physics and benchmark loading | Clarify parsing separately from physical transitions; preserve loader imports. | Published-arc and charge/return tests, identical reference and scenario hashes, independent replay. |
| 3. MPC decision control | Extract one pure event-trigger or dispatch-decision helper from `simulator.py`. | Identical trigger trace, first actions, fallback and five-second latency on fixed seeds. |
| 4. Route/charging decoder | Give `repair.py` and both decoders a small shared interface. | Route/action parity and feasible MP charging, including deadline cases. |
| 5. Optimizer contract | Make shared fleet dependencies explicit while preserving all five adapters. | Each baseline runs through its public name and returns replayable routes. |
| 6. Proposed-method space | Define a distinct SLAD hypothesis; add a separate opt-in MPC-ALNS variant only after overlap review. | Observable-only data, physical counterfactual witnesses, original ALNS unchanged, decision within five seconds. |
| 7. Experiment/report pipeline | Give new studies one runner, auditor and renderer contract; keep historical revisions. | Frozen protocols and raw hashes remain valid; reports regenerate from audited raw data. |

Each step should have a small source change, targeted tests, and a full
regression run when a shared contract changes. Historical outputs stay in
place until the [retention plan](RESULTS_RETENTION_PLAN.md) has file-level
references, an accessible authoritative copy, and verified hashes. The first
implementation task after the first milestone was order 1.

## Milestone 2: path preview

`scripts/experiments/paths.py` reserves `results/research_v2/<study_id>/` and
its five output areas for future studies. `python -m scripts.experiments.inspect_study`
prints a read-only JSON preview with setting provenance. It does not create
directories, run a study, provide an artifact writer, or migrate historical
launchers. Future writers must retain benchmark protection and use exclusive
creation; path preflight alone cannot prevent a concurrent overwrite.

## Milestone 1 validation (2026-10-29)

- The new inventory tests passed, including a byte-and-modification-time check
  showing that a scan did not change or remove fixture evidence.
- The complete existing suite passed: 421 tests in 64.40 seconds. A first
  focused test attempt could not access its Windows sandbox temporary
  directory; the focused tests and full run passed with normal filesystem
  access.
- Import and construction checks passed for `MPC_COMPLETION`, `MPC_MCTS`,
  `MPC_ALNS`, `MPC_HGS`, and `MPC_ACS`.
- The inventory scanned the local `results/` tree with normal Windows access,
  distinguished Git-tracked from untracked files, and made no changes to it.
- The changed files are planning documents, the results guide, the inventory
  utility, and its tests. Benchmark data, physical model, scenario generation,
  objective, optimizer implementations, frozen protocols and raw results were
  not edited. No optimization study, file migration, deletion, commit or push
  was performed.
