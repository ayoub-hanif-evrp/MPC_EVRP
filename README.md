# Event-Triggered Risk-Aware Fleet MPC-MCTS for Dynamic EVRPTW

**Current structural-rollout correction: STOPPED at the static gate.** The four
specified diagnostics served 100/100 statically on C101 and 99/100, 100/100,
99/100 on the three dynamic cases; all passed independent audits with
optimization calls below five seconds. In the subsequent six-instance static
gate, C101 served 100/100 but C201 served 94/100. The runner stopped before
the other four static cases. The 12-pair development grid, completion-only
ablation grid, and holdout were not run. See the
[current report](results/final/structural_rollout/FINAL_REPORT.md); no positive
final paper-performance claim is supported.

The terminal-completion correction and control-horizon campaign below are
historical development evidence, not results of the current method.

The prior frozen `6a1ab7e` Fleet MPC-MCTS campaign is **historical development
evidence**. It served 600/600 statically and 1005/1200 dynamically versus
Rolling-LNS's 782/1200 in 12 matched pairs, but failed its severe-collapse and
strict event-latency gates; its [report and raw archive](results/final/FINAL_REPORT.md)
remain preserved. An even earlier stopped four-pair campaign is documented in
the [risk-aware development record](docs/risk_aware_fleet_development.md).

The corrected method protects the next MPC control action with `R_CTRL`, then
the soft route suffix with `R_FLEX`. Fleet MCTS and Rolling-LNS share a bounded
screened regret constructor. MCTS tree nodes retain only structural fleet
actions; a direct completion rollout supplies terminal estimates, never a
hidden tree transition. Charging remains in the exact decoder. There is no
post-MCTS LNS. The [experiment protocol](docs/experiment_protocol.md) specifies
the stopped static gate and the conditional later stages.
The [incomplete execution record](results/final/control_horizon/INCOMPLETE_RUN.md)
documents the earlier every-completion execution attempt, not this corrected run.
Physical completions replay validated suffixes and dispatch their next action;
global optimization runs only initially, on release, invalid/missing
continuation, or after customer-service completion with uncovered released
work. A charge or wait completion with a valid suffix does not trigger global
optimization. Fleet MCTS and Rolling-LNS use the same trigger policy.
The current runner is `python -m scripts.final_structural_mcts_campaign` with
`diagnostic`, `static`, `development`, and `ablation` stages. Its development
gate remains blocked by the static result. The prior
[control-horizon report](results/final/FINAL_REPORT.md) remains an archive.

An additional fleet-wide LNS prototype and its six-instance, single-seed
development gate are documented in
[Fleet-LNS development](docs/fleet_lns_development.md). Rolling LNS passed its
six-instance static service prerequisite; the hybrid static check remains
incomplete and the dynamic comparison did not establish an MCTS-over-LNS
advantage. The holdout was not run. The method and study below describe the earlier
coordinator track, which remains available as an ablation.

This training-free research implementation asks whether persistent route coordination
between independently planned EVs improves dynamic EVRPTW performance over independent
MPC-MCTS and rolling-horizon regret insertion. Local Schneider benchmark files are
immutable. Historical V1/V2 outputs are preserved at Git commit `38d0d01`; they are
not evidence for the current method.

## Historical Coordinator Track

```text
Released requests and measured EV states
  -> preserve busy actions and use ready vehicles' old routes as soft incumbents
  -> finite-horizon MPC subproblems solved approximately by MCTS
  -> top-L feasible route candidates
  -> sequential MILP fleet coordination
  -> regret-2 repair of uncovered released requests
  -> one service-preserving fleet-compaction pass
  -> one final validation/reconciliation pass
  -> execute first actions, retain soft suffixes, replan after feedback
```

Every matched algorithm has exactly `K_ref` physical EVs (`fleet_mode:
fixed_reference`). Only the reference fleet size reaches online policies; reference
routes and unreleased requests do not. Unused depot EVs count as activated only
after departure. No vehicles are created beyond `K_ref`.

Only executing actions are hard commitments. A busy EV's future suffix is held
until that action completes; when ready, its old feasible suffix is a candidate
and its future customers return to the released planning pool. The finite
prediction horizon bounds new MCTS search; old incumbents may be longer.
Terminal WAIT/RETURN after the last service are not retained as commitments.
Temporary idleness must not force premature return: an active EV can wait while
latest-safe-return slack remains.

The fleet objective is lexicographic: minimize unserved customers, then activated
vehicles, then distance. Coordination selects customer-disjoint executable routes;
regret-2 repair follows coordination and precedes dispatch.

Final comparison algorithms are `RH_REGRET`, `INDEPENDENT_MPC_MCTS`, and
`COORDINATED_MPC_MCTS`. `GREEDY` remains for sanity checks. The frozen development
configuration uses 48 MCTS iterations, customer limit 16, top-L 5, and
parameter-free coverage-diverse proposals for both MPC-MCTS methods.

## Setup and CLI

Python 3.11+ is required. From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m evrp.cli --help
```

The implemented CLI is:

```powershell
python -m evrp.cli validate
python -m evrp.cli smoke
python -m evrp.cli run --instance c101C5
python -m evrp.cli screening
python -m evrp.cli development
python -m evrp.cli final --execute
python -m evrp.cli aggregate
python -m evrp.cli tables
python -m evrp.cli plot
python -m evrp.cli audit
```

Later studies require explicit execution and the applicable gates:

```powershell
python -m evrp.cli main --execute
python -m evrp.cli ablations --execute
python -m evrp.cli realtime --execute
```

Never launch the main study automatically. All generated research artifacts,
including scenarios, belong under repository-local `results/`. Output overrides
must not escape that directory.

## Development and Holdout

The previous 32-iteration screen failed. Its raw evidence and diagnosis remain
under `results/screening/` and `results/final/DIAGNOSIS.md`.

The new development study uses the same six 100-customer instances, DoD 0/0.5,
seeds 0, and the three final methods (36 runs). It writes a provenance-bound gate
to `results/development/GATE.md`. A failed gate blocks holdout execution.

After a development PASS, `final --execute` runs six different holdout instances
at DoD .25/.50/.75 and scenario seeds 0/1/2 (162 planned dynamic runs), plus
18 static sanity runs. Final outputs and `FINAL_REPORT.md` go under
`results/final/`. Target DoD conditions that cannot be realized are disclosed and
excluded from the dynamic comparison.

## Previous Screening Record

The earlier screen used `c101_21`, `c201_21`, `r101_21`, `r201_21`, `rc101_21`, and `rc201_21`,
at DoD `0.0/0.5`, scenario/algorithm seeds `0`, and 32 MCTS simulations. Use horizon
5, control horizon 1, top-L 3, partial charging, fixed `K_ref`, continuity, and
regret repair. Compare RH_REGRET, independent MPC-MCTS, and coordinated MPC-MCTS.
Stop and diagnose poor static service before launching further experiments.

Its Stage 2 was not run. See `results/screening/GATE.md` for its failed gate.

## Documentation

- [Methodology](docs/methodology.md): ownership, search, coordination, and repair.
- [Assumptions](docs/assumptions.md): physics, information, and limitations.
- [Experiment protocol](docs/experiment_protocol.md): study design and gates.
- [Reproducibility](docs/reproducibility.md): provenance, validation, and execution.
- [Fleet-LNS development](docs/fleet_lns_development.md): prototype, matched results, and holdout decision.
- [Output policy](results/README.md): generated artifacts and Git exclusions.

Generated evidence is intentionally ignored by Git; the CLI writes it locally.
