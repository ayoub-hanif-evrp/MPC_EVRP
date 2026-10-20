# Event-Triggered MPC for Dynamic EVRPTW

This project evaluates a common event-triggered MPC controller with five
interchangeable optimization modes: Completion, MCTS, ALNS, HGS, and ACS.
All modes use the same feasible constructor, plant physics, service-first
risk-aware lexicographic objective, fixed offline reference fleet `K_ref`,
released requests, and five-second optimization-decision limit. The old
Schneider campaigns are historical Git evidence, not results for the active
dataset.

## Active benchmark

The active static source is the [Desaulniers et al. (2016) EVRPTW bundle](https://doi.org/10.1287/opre.2016.1535)
under `data/opre.2016.1535-sm-data/`. There are 56 instances at each of 25,
50, and 100 customers, with C1, C2, R1, R2, RC1, and RC2 families. The
project uses the **multiple partial recharging (MP)** policy. Format-1 text
provides coordinates, demands, time windows, and vehicle parameters; format-2
`.inst` files provide rounded arc cost, travel time, and time-equivalent
energy. The loader validates every published arc before a run.

Static instance customers are made dynamic using the existing
reference-preserving release generator. Unreleased customers are hidden from
all online methods. A physically replayed full-service offline schedule
defines the same `K_ref` for every method on a scenario. Published `MF` or
`SF` full-charge solutions may supply that **offline feasible reference**
because full recharge is allowed under MP; where unavailable, the existing
reference solver is used. Published solution costs are never used as the MPC
objective or as an online comparison baseline.

The historical state-aware Portfolio is not deployed on this dataset:
its Schneider-trained selector is invalid here. It can be evaluated only
after a new Desaulniers development/shadow study and frozen retraining.
The dataset-neutral runtime adapter is retained, but no new selector has
been trained.

## Reproduce

Python 3.11+ is required. From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q tests/test_desaulniers_dataset.py
python -m scripts.run_desaulniers_pilot
python -m scripts.analyze_desaulniers_pilot
```

The pilot selects one previously unused C1 development instance at each
size, with DoD 0.25 and seed 0, and runs all five methods in separate
processes. It writes raw evidence, a hash manifest, a Markdown summary,
and a 300-dpi PNG under `results/desaulniers/development_pilot_final_source/`. It is
an **engineering pilot**, not a final study. The lexicographically last
instance of each family and size is reserved for a separately preregistered
future evaluation; no new final holdout has been opened.

An independent [development campaign configuration](configs/desaulniers_mp_development.yaml)
selects the first instance of each of the six families at each size, all
three target DoD levels, seed 0, and the same five methods. It is resumable
and records target-DoD ineligibility rather than silently changing the
denominator. Freeze its protocol without starting optimization using
`python -m scripts.run_desaulniers_campaign --scenario-limit 0`; the full
grid is launched with `python -m scripts.run_desaulniers_campaign` and,
once complete, audited with `python -m scripts.analyze_desaulniers_campaign`.
The analyzer refuses a partial manifest. This larger grid has **not** been
completed as part of the migration pilot. Some 50- and 100-customer cases
have no compatible published full-charge route; their fallback reference
construction remains an explicit runtime/feasibility limitation.

The separate [final holdout configuration](configs/desaulniers_mp_final.yaml)
uses the lexicographically last, previously reserved instance of each family
and size, the same three target DoD levels, seed 0, and all five fixed methods.
The resulting maximum is 270 method runs before explicitly recorded DoD
ineligibility. Its source- and dataset-bound protocol is frozen before any
holdout optimization. The runner refuses to open the holdout until the
development manifest is complete. Then run
`python -m scripts.run_desaulniers_final` and, after completion,
`python -m scripts.analyze_desaulniers_final`. An infeasible offline reference
is a campaign blocker, not a silently discarded final scenario. This is a
new Desaulniers evaluation, not a continuation of the historical Schneider
holdout.

For the field mapping, rounding validation, charging and fleet assumptions,
see [Desaulniers migration notes](docs/DESAULNIERS_MIGRATION.md).
