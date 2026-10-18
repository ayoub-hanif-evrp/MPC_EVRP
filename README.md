# Event-Triggered MPC with Combinatorial Optimizers for Dynamic Electric Vehicle Routing with Time Windows

This repository studies dynamic EV routing with time windows under a fixed
reference fleet. MPC is the receding-horizon control framework: at an
observable event it constructs feasible fleet suffixes, optionally improves
them, validates the chosen routes against the physical EV model, executes only
the first control action, then observes again. Unreleased requests are never
visible to an optimizer.

```text
Event trigger: measured fleet state and released requests
                 |
         Event-Triggered MPC
                 |
          Common constructor
                 |
     +-----------+-----------+-----------+-----------+
     |           |           |           |           |
 Completion    MCTS        ALNS         HGS         ACS
     +-----------+-----------+-----------+-----------+
                 |
       Exact EV validation and first control
```

MCTS is the principal tree-search method. ALNS, HGS and ACS are controlled
alternatives inside the **same** controller, with the same event trigger,
constructor, released information, fixed `K_ref`, EV charging decoder,
lexicographic objective and total decision deadline. A state-aware portfolio
is a research hypothesis, not an established result: it will be developed
only if the development data show useful complementarity between optimizers.
RoutingBlocks remains an external **offline/static** benchmark, not MPC-ALNS.

## Evidence Status

The historical paper track is at Git tag `paper-v1-d5e3c28`. In its inspected
dynamic campaign, `FLEET_MPC_MCTS` served **5295/5400** customers versus
**5142/5400** for the completion-only controller. This is historical evidence
for the earlier MCTS configuration, not evidence for ALNS, HGS or a portfolio. The complete record is in
[`results/paper/`](results/paper/); its provenance and interpretation are in
[`docs/V1_FROZEN_EVIDENCE.md`](docs/V1_FROZEN_EVIDENCE.md). The old holdout is
now development data; it is not unseen for future work.

The optimizer comparison is under development in
[`results/portfolio/`](results/portfolio/). Earlier pilots and a stopped
72-run grid are preserved as historical development evidence. A correctness
fix to the independent audit changed the source fingerprint, so the
authoritative 330-run development grid restarted from zero. The common-state
shadow experiment and new final holdout are not complete. Historical results
must not be described as final evidence. No new final holdout has been run or
preregistered.

## Repository Map

- `evrp/`: event-driven simulator, physics, route decoder, reference and
  scenario generation.
- `evrp/optimizers/`: common optimizer contract, `J_A/J_B` evaluator,
  Completion, MCTS, ALNS, HGS and ACS adapters.
- `evrp/external/`: independent external benchmarking integrations.
- `configs/portfolio_development.yaml`: the 66 already-inspected development
  scenarios and common five-second controller budget.
- `scripts/run_portfolio_campaign.py`: independently audited, fresh-process
  development runs; it has no final-holdout mode.
- `scripts/analyze_portfolio_development.py`: paired development analysis,
  confidence intervals and PNG figures.
- `scripts/shadow_portfolio.py`: observable-state snapshot capture and
  independent common-state optimizer comparison. VBS is analysis only.
- `scripts/preregister_final_holdout.py`: deterministic unused-instance
  selection after the development and shadow gates.
- `scripts/run_final_holdout.py` and `scripts/analyze_final_holdout.py`:
  committed-protocol final runs and paired audited analysis.
- `tests/`: physics, simulator, research protocol and optimizer regressions.
- [`results/INDEX.md`](results/INDEX.md): historical, development, shadow,
  final-study and verification outputs.
- [`docs/FINAL_SOURCE_FREEZE.md`](docs/FINAL_SOURCE_FREEZE.md): tested source
  and protocol fingerprints for the authoritative campaign.

## Run

Python 3.11+ is required. From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q --basetemp=results/t
python -m scripts.run_portfolio_campaign
python -m scripts.analyze_portfolio_development
```

The development command runs the full 66-scenario grid sequentially. Each
scenario-method simulation starts in a fresh Python interpreter and writes a
compressed raw record with audit and SHA-256 provenance under
`results/portfolio/development/`. The analyzer requires all 330 records
unless `--allow-incomplete` is explicit. It does not use a new final holdout.

After the complete development grid, the guarded sequence is:

```powershell
python -m scripts.analyze_portfolio_development
python -m scripts.shadow_portfolio capture
# Commit results/portfolio/shadow/selection.json before optimizer outcomes.
python -m scripts.shadow_portfolio run
python -m scripts.shadow_portfolio analyze
```

If the common-state gate passes, fit the predeclared observable-state selector
and commit its model, grouped-CV record, and decision before preregistration:

```powershell
python -m scripts.portfolio_selector
# Commit results/portfolio/selector/ before final preregistration.
```

The selector is deployed only if held-out-scenario and held-out-instance
planned service both exceed the frozen SBS. The current 396-state study passed
that rule; the portfolio is therefore a sixth **MPC variant**, not a separate
controller. If the gate fails or the selector fails grouped validation, the
holdout keeps the five frozen variants. In either case, run:

```powershell
python -m scripts.preregister_final_holdout
# Commit both PRE_REGISTERED_PROTOCOL files before the first final run.
python -m scripts.run_final_holdout
python -m scripts.analyze_final_holdout
python -m scripts.render_final_paper
```

The renderer rechecks the complete audited final holdout and frozen shadow
study before writing `results/final_study/paper/RESULTS.md`, nine 300-dpi PNG
figures, and ten Markdown tables. Development plots remain diagnostic and are
not used as final paper evidence.

No new final holdout has been opened. The final grid has 324 isolated runs when
the frozen portfolio is included, or 270 otherwise.

To reproduce the historical paper track, check out the V1 tag in a separate
worktree and follow [`results/paper/PAPER_PROTOCOL.md`](results/paper/PAPER_PROTOCOL.md).
Older development reports and one-off scripts remain preserved for provenance
but are not current performance claims.
