# Event-Triggered MPC with Adaptive Combinatorial Optimization for Dynamic Electric Vehicle Routing with Time Windows

This repository studies dynamic EV routing with time windows under a fixed
reference fleet. MPC is the receding-horizon control framework: at an
observable event it constructs feasible fleet suffixes, optionally improves
them, validates the chosen routes against the physical EV model, executes only
the first control action, then observes again. Unreleased requests are never
visible to an optimizer.

```text
Measured fleet state and released requests
                 |
          Common MPC constructor
                 |
     +-----------+-----------+-----------+-----------+
     |           |           |           |           |
 Completion    MCTS        ALNS         HGS         ACS
     +-----------+-----------+-----------+-----------+
                 |
       Exact validation and first action
```

MCTS is the principal tree-search method. ALNS, HGS and ACS are controlled
alternatives inside the **same** controller, with the same event trigger,
constructor, released information, fixed `K_ref`, EV charging decoder,
lexicographic objective and total decision deadline. A state-aware portfolio
is a research hypothesis, not an established result: it will be developed
only if the development data show useful complementarity between optimizers.
RoutingBlocks remains an external **offline/static** benchmark, not MPC-ALNS.

## Evidence Status

The frozen V1 paper track is at Git tag `paper-v1-d5e3c28`. In its inspected
dynamic campaign, `FLEET_MPC_MCTS` served **5295/5400** customers versus
**5142/5400** for the completion-only controller. This is historical evidence
for V1, not evidence for ALNS, HGS or a portfolio. The complete record is in
[`results/paper/`](results/paper/); its provenance and interpretation are in
[`docs/V1_FROZEN_EVIDENCE.md`](docs/V1_FROZEN_EVIDENCE.md). The old holdout is
now development data; it is not unseen for future work.

The optimizer comparison is under development in
[`results/portfolio/`](results/portfolio/). A pre-final-MCTS isolated
six-family pilot contains 30 audited runs and a stopped extension contains
38, preserved as historical development evidence. The final-MCTS 330-run
development grid, common-state shadow experiment and new final holdout are
not complete. Historical pilot results must not be described as final
evidence. No new final holdout has been run or preregistered.

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
- `tests/`: physics, simulator, research protocol and optimizer regressions.
- [`results/INDEX.md`](results/INDEX.md): current versus historical outputs.

## Run

Python 3.11+ is required. From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q --basetemp=results/t
python -m scripts.run_portfolio_campaign --family-pilot
python -m scripts.analyze_portfolio_development --allow-incomplete
```

Omit `--family-pilot` to run the full 66-scenario development grid. Each
scenario-method simulation starts in a fresh Python interpreter and writes a
compressed raw record with audit and SHA-256 provenance under
`results/portfolio/development/`. The analyzer requires all 330 records
unless `--allow-incomplete` is explicit. It does not use a new final holdout.

To reproduce the historical paper track, check out the V1 tag in a separate
worktree and follow [`results/paper/PAPER_PROTOCOL.md`](results/paper/PAPER_PROTOCOL.md).
Older development reports and one-off scripts remain preserved for provenance
but are not current performance claims.
