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
     +-----------+-----------+-----------+
     |           |           |           |
 Completion    MCTS        ALNS         HGS
     +-----------+-----------+-----------+
                 |
       Exact validation and first action
```

MCTS is the principal tree-search method. ALNS and HGS are controlled
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
[`results/portfolio/`](results/portfolio/). No new final holdout has been run
or preregistered. A user review is required before that stage. The development
protocol and architecture are documented there.

## Repository Map

- `evrp/`: event-driven simulator, physics, route decoder, reference and
  scenario generation.
- `evrp/optimizers/`: common optimizer contract, `J_A/J_B` evaluator,
  completion, V1 MCTS, ALNS and HGS adapters.
- `evrp/external/`: independent external benchmarking integrations.
- `configs/portfolio_development.yaml`: the 66 already-inspected development
  scenarios and common five-second controller budget.
- `scripts/run_portfolio_campaign.py`: audited development-only runs; it has
  no final-holdout mode.
- `tests/`: physics, simulator, research protocol and optimizer regressions.
- [`results/INDEX.md`](results/INDEX.md): current versus historical outputs.

## Run

Python 3.11+ is required. From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m scripts.run_portfolio_campaign --case-limit 1
```

Omit `--case-limit` only when ready to run the full 66-scenario development
grid. The runner writes compressed raw records and SHA-256 provenance under
`results/portfolio/development/`. It does not use a new final holdout.

To reproduce the historical paper track, check out the V1 tag in a separate
worktree and follow [`results/paper/PAPER_PROTOCOL.md`](results/paper/PAPER_PROTOCOL.md).
Older development reports and one-off scripts remain preserved for provenance
but are not current performance claims.
