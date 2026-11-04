# V3 research decision: stop at the novelty gate

**Decision date:** 2026-11-04. **Decision:** The planned *Commitment- and Charging-Resource-Aware Anticipatory MPC* is not yet a defensible new algorithmic contribution. Stop before downloading datasets, changing the plant, creating V3 optimizers, or running a pilot. This executes the early-stop condition in the agreed plan; it is not evidence that such a method cannot work.

## Baseline audit before any V3 behavior change

- Branch: `research/v3-commitment-charging`, created from clean `main` at `7a6a72263b37b083a2887cc2c6b3b36c0ffb1bcd`.
- Environment: Windows 11 build 26200; Python 3.12.10; pytest 9.1.1; NumPy 2.5.3; SciPy 1.18.1; pandas 3.0.6; matplotlib 3.11.2; PyYAML 6.0.3.
- Full baseline command: `python -m pytest -q --tb=short`; **526 passed, 4 skipped in 68.13 s**, exit 0, when run with filesystem access. Two sandboxed attempts failed primarily because pytest could not clear/access its temporary directory; those permission errors are not counted as code failures.
- The frozen final CPU study reports 450 primary and 60 replication method runs. Its verification inventory records a primary source digest `bb593ad57e9b0196ad3712d8c9d873addb5ed156c32ea7857e21471a1fe3f140`, primary protocol digest `a1a59dd9b88d7b2348deb7e23a22b4b64519e3ebd11761d6788b7cfa729578ad`, and primary manifest digest `2703b27d078fb253f63d552ad5a5fd5bb4cad8a97d37edddf41b29e3650c70c1` ([verification](../../results/desaulniers/final_cpu_paper_v1/audit/verification.json)). These are historical execution fingerprints, not V3 results.

Pre-change SHA-256 source bytes, recorded with PowerShell `Get-FileHash -Algorithm SHA256`:

| File | SHA-256 |
| --- | --- |
| `evrp/simulator.py` | `5779ffc7093fe1803b959a8320d5282380d7823e54c442a6bcf06fed470d00da` |
| `evrp/scenario.py` | `1d9c1e1772aed2bfcd488968fdbe600ecd6dc1ba215c9329d40acf9ad600a96a` |
| `evrp/observation.py` | `d4638557084258d44d55129361e6064899fcc7bad482d1f00b539adc07582cee` |
| `evrp/mpc.py` | `66614afd55a3ecb633b769fb8cea2d49c34201db77966c305fc50f47f1650269` |
| `evrp/fleet_mcts.py` | `3ebf5c809bd458d125a5085ffa8587130e2bd97b04e0af2f2fa7b0b1dba0f019` |
| `evrp/optimizers/objective.py` | `eac0aa1c54dd3a3f67763450811c699779bcb6578bb55ba36cb5f8abb89d91c8` |
| `evrp/optimizers/alns.py` | `07589f5ddf749da43f4ef5d7cf9c3c9a8f5388ea9fa2b56e6e452141a11c694e` |
| `evrp/repair.py` | `2ea9db8b3bbd95901337f0c8dcb259d77dc8e2f43b65ce86207ed01bb5a63e75` |
| `evrp/resource_decoder.py` | `6a76536a232ea5f2059b25d44e4ce4ff0ea17422695157e0f01919daafd90e63` |

## What the current repository already provides

The [architecture](../ARCHITECTURE.md) and [reviewer audit](../REVIEWER_READINESS_AUDIT.md) establish a common event-triggered controller with custom Completion, MCTS, ALNS, HGS and ACS adapters. The optimizer sees released customers; its old release generator preserves an offline feasible reference. Dispatched travel/service/charge actions are noninterruptible, while later route suffixes remain revisable. Existing ALNS has six destroy and four repair policies, a bounded five-second search context and physical route replay. `targeted_recovery.py` already screens alternatives to ready vehicles' first actions and checks observable-state commitment opportunities. The prior [research decision](../RESEARCH_DIRECTION_DECISION.md) rejected another equal-service guard after the stable ALNS and SLAD V2 negative findings.

The plant has no general endogenous finite-charger queue, and `committed_customers` denotes dispatched service rather than business-level request acceptance. These are real modeling limitations. Implementing them would create a more faithful **new problem environment** but would not automatically create a new optimization method.

## Candidate mechanisms and gate judgment

| Candidate | Closest verified overlap | Decision |
| --- | --- | --- |
| Paired stochastic rollout over ALNS first actions with shared-charger simulation and a commitment feasibility screen (the agreed V3 concept) | [Jiang et al.](https://doi.org/10.1287/trsc.2025.0476) use stochastic EV lookahead; [Lam et al.](https://doi.org/10.1016/j.cor.2022.105870) schedule finite chargers; [Soeffker et al.](https://doi.org/10.1007/s00291-024-00747-1) protect fixed requests and value fleet flexibility; the [2026 queue-ALNS study](https://www.mdpi.com/2071-1050/18/15/7580) combines ALNS and endogenous charger scheduling. | **Reject as an algorithmic novelty claim.** The proposed selection is a conjunction of known tests/estimators. No new operator, bound, structural rule or causal failure mode has been specified. |
| Queue-capacity continuation certificate for accepted work | Static charger scheduling and online fixed-request feasibility are separately established by Lam and Soeffker. A heuristic replay witness is not a stochastic guarantee. | **Reject for now.** A certificate with a new formal guarantee or provably smaller search would need a precise theorem and assumptions; none are in the plan. |
| Learned or fluid charger congestion value in the MPC score | [Kahlert et al.](https://arxiv.org/abs/2605.26970), [Ma et al.](https://arxiv.org/abs/2412.09978) and [Widmann & Sawodny](https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/itr2.70180) already forecast and coordinate charging congestion. | **Reject.** It adds model and calibration complexity without a distinct research mechanism or supporting repository diagnostic. |

The literature matrix records exact scope and verification limits. No reviewed source was verified to solve the *exact* proposed conjunction, but this absence is neither proof of priority nor enough to justify method novelty. The current plan contains no narrow falsifiable contribution beyond assembling established ingredients. The correct action under its novelty gate is to stop.

## Data and experiment status at stop

No dataset was downloaded, transformed or hashed; no V3 scenario, algorithm, simulation, pilot, holdout or result exists. Therefore no service, timing or confidence-interval claim is made. No `DATA_PROVENANCE`, formulation, algorithm, protocol, correctness or reproduction document is emitted as if implementation had occurred. The original five-method evidence is untouched.

Metadata inspection identified [Dataset A](https://github.com/lmores/or-evrptw-cps-mrt-data) as GPL-3.0 and its public repository as describing 224 JSON instances. Its README permits one- or two-charger names, while the inspected current file inventory showed only `_2.json` names; the agreed one-charger test would have to be visibly **derived** if a later project proceeds. [Dataset B](https://zenodo.org/records/18529191) describes Geo-AC-v1.1 but offers a `v1.0`-named 527.7 MB archive with MD5 `7cc5ddd617dff8792b167f45ab7e4ed3`; the fetched Rights/License field is blank. No license, archive-version or extraction assertion is made without further verification. Dataset C was not accessed or downloaded after the failed novelty gate.

## Revised research question and next action

The narrower scientifically defensible question is: **How much online service and promise reliability are lost when a dynamic EV fleet planner substitutes independent mean charger waits for the endogenous interactions of its own vehicles, under identical information and a common decision budget?** This is a comparative modeling/benchmark question, not a claim of a new optimizer. Its proposed treatment would be a separate, preregistered study with independent geometry, exact small-instance queue checks, and the same acceptance rule across policies.

**Single next action:** write a short problem-definition and prior-art comparison for that revised question, identifying a measurable gap relative to the 2026 queue-ALNS and dynamic electric dial-a-ride studies. Only if that review supports a useful contribution should a new task authorize data adapters and the simulator. No pilot is currently justified.
