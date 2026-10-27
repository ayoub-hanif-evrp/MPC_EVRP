# Event-Triggered MPC for Dynamic EVRPTW

**Current publication result:** The CPU-only [final paper package](results/desaulniers/final_cpu_paper_v1/FINAL_REPORT.md)
contains the independently audited 450-run Desaulniers MP robustness study
and a separately preregistered 60-run replication of the five original
methods. The cohorts are reported separately. Opt-in service and speed
enhancements did not pass the development service-preservation gate, so no
enhanced method is claimed. See the [repository status](docs/REPOSITORY_STATUS.md)
for active versus preserved historical workflows.

The latest [balanced CPU development ablation](results/desaulniers/final_cpu_paper_v1/DEVELOPMENT_UPDATE.md)
completed 120/120 audited runs across six benchmark families and three customer
sizes. Its combined policy gained four paired customer-service counts but lost
one ACS count, so it was not promoted. A whole-worker timeout and the explicit
technical continuation are preserved with the raw evidence. The five-second
MPC decision budget and original independent results are unchanged.
The separate [two-worker CPU probe](results/desaulniers/two_worker_probe_v1/RESULTS.md)
observed 1.50x throughput on two small scenarios with unchanged service, but
does not replace the paper's sequential runtime measurements.

This project evaluates a common event-triggered MPC controller with five
interchangeable optimization modes: Completion, MCTS, ALNS, HGS, and ACS.
All modes use the same feasible constructor, plant physics, service-first
risk-aware lexicographic objective, fixed offline reference fleet `K_ref`,
released requests, and five-second optimization-decision limit. The old
Schneider campaigns are historical Git evidence, not results for the active
dataset.

The separate [enhancement development record](results/desaulniers/enhancement_development/STATUS.md)
reports audited loss diagnostics and controlled experiments. No enhanced
method has yet earned a new independent final evaluation; the original
paper results remain the primary findings.
The [publication development record](results/desaulniers/publication_development/STATUS.md)
adds observable candidate traces, controlled ablations, explicit runtime
corrections and separately audited MP reference coverage. See the consolidated
[publication package](results/desaulniers/publication_package_v1/RESULTS.md)
and [completion report](results/desaulniers/publication_package_v1/FINAL_REPORT.md).

The separate [targeted service study](results/desaulniers/targeted_service_v1/FINAL_REPORT.md)
completed all 288 independently audited development runs for three opt-in
constructor, resource-decoder and first-control candidates. No candidate
passed the predefined parent-clustered promotion checks, so all remain disabled
by default and no new final holdout was opened. The strongest resource-decoder
candidate increased matched ALNS service from 99.143% to 99.286%, but its
95% paired parent interval included zero (-0.095 to +0.381 percentage points).
The original primary results remain unchanged. Its separate
[offline investigation](results/desaulniers/targeted_service_v1/offline_resources/RESULTS.md)
closes the two remaining physical reference-witness cases, bringing combined
witness coverage to 168/168 without replacing historical reference fleets.
The [targeted reporting notes](results/desaulniers/targeted_service_v1/REPORTING_NOTES.md)
document the paired design and the gated MP-witness holdout policy. Complete or
resume that separate workflow with `python -u -m scripts.complete_targeted_study`;
do not run a second campaign parent while one is already active.

The separate [reliability V2 protocol](results/desaulniers/reliability_v2/PREREGISTRATION.md)
adds event-level loss evidence, opt-in two-EV exchanges, exact root-local replay
memoization and a prospective Completion-only control comparison. Its new
12-parent panel uses structural DoD eligibility only, with crossed seed/DoD
within each selected file; no historical result is replaced. See its
[status and report](results/desaulniers/reliability_v2/FINAL_REPORT.md).
This campaign is **stopped at the user's request after 361/1116 runs**.
The [compute-cost review](results/desaulniers/reliability_v2/compute_review/RESULTS.md)
explains the runtime and the next budget-controlled alternatives. The launcher
refuses to restart while `STOP_REQUESTED.json` exists; do not bypass that guard
with the direct runner. All saved evidence remains intact. No new improvement
or independent final result is claimed from this incomplete comparison.

The separate [performance-engineering report](results/desaulniers/performance_engineering_v1/FINAL_REPORT.md)
evaluates exact decision-local transition, route-prefix, charging-frontier and
objective reuse through the optional `proposal_cache_policy=incremental_v1`.
It compares all five engines on three previously seen 25/50/100-customer cases,
with separate profiling and allocation probes: all 75 workers, including 30
full simulations, completed in 35.2 charged minutes. The physical model, canonical
objective, search settings and five-second decision limit are unchanged.
Runtime gains are workload-dependent, not a general service improvement:
aggregate pilot CPU time fell about 16%, but the 100-customer HGS pair served
100 customers originally versus 98 incrementally, and ACS fell from 96 to 95.
**The original evaluator remains the default.** All 389 tests passed, 36 saved
trajectories passed independent replay, and maximum pilot latency was 4.807 s.
The staged runner enforces a persistent 7,200-second allowance, complete-pair
admission, per-worker watchdogs, hash-verified checkpoints and no silent retry.
It never resumes Reliability V2 or automatically starts a holdout. Execution
source and reproduction commands are recorded in the consolidated report.

The [fast-framework development report](results/desaulniers/fast_framework_v1/FINAL_REPORT.md)
evaluates an optional faster shared screen/cache, conservative adaptive search
stopping, an urgent service guard, and a separately labeled MCTS rollout fix.
All five methods were compared on three matched 25/50/100-customer development
cases under a cumulative two-hour execution allowance. The combined variant
reduced CPU but HGS served 99 instead of 100 on the 100-customer case; the
predeclared gate therefore skipped additional-parent confirmation. A controlled
[HGS/ACS component ablation](results/desaulniers/fast_framework_v1/ablation_1/REPORT.md)
also found service losses with fast evaluation alone. **All enhancements remain
opt-in; the original publication configuration and results are unchanged.**
The complete suite passes 393/393 tests when Windows filesystem and pipe
permissions allow the test runner to create its temporary resources.

The negative GPU/CPU engineering pilot is preserved at an independently verified
[archive tag](docs/CPU_BACKEND_DECISION.md). The active project uses CPU only.
Compiled insertion screening and the operational-quality policy remain opt-in:
both shortened some runs or routes but also had service regressions. **The
original configuration remains the publication default.** The stopped
Reliability V2 campaign and original publication results remain untouched.

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
python -m pytest tests -q --basetemp results/.pytest_reproduce
python -m scripts.archive_frozen_inputs --restore
python -m scripts.audit_frozen_studies
python -m scripts.audit_enhancement_studies
python -m scripts.audit_reference_inventory
python -m scripts.render_publication_package
```

These commands audit and render saved evidence; they do not rerun optimization.
The historical-source auditor verifies the exact archived Git blobs, so the
current development tree need not equal the frozen historical implementation.
Old study-specific verifiers and optimization runners must instead be used
with their original source commits; their drift guards remain intact.
The historical pilot, development, and
final campaigns are already complete and should not be launched merely to
reproduce the paper tables. The all-instance reference audit is
`python -m scripts.validate_desaulniers_coverage`; it can take substantially
longer because absent published references require isolated fallback search.

The pilot selected one previously unused C1 development instance at each
size, with DoD 0.25 and seed 0, and runs all five methods in separate
processes. It writes raw evidence, a hash manifest, a Markdown summary,
and a 300-dpi PNG under `results/desaulniers/development_pilot_final_source/`. It is
an **engineering pilot**, not a final study. The lexicographically last
instance of each family and size was reserved for a separately preregistered
final evaluation.

An independent [development campaign configuration](configs/desaulniers_mp_development.yaml)
selects the first instance of each of the six families at each size, all
three target DoD levels, seed 0, and the same five methods. It is resumable
and records target-DoD ineligibility rather than silently changing the
denominator. Freeze its protocol without starting optimization using
`python -m scripts.run_desaulniers_campaign --scenario-limit 0`; the full
grid is launched with `python -m scripts.run_desaulniers_campaign` and,
once complete, audited with `python -m scripts.analyze_desaulniers_campaign`.
The analyzer refuses a partial manifest. The full development grid is now
**complete: 270/270 audited runs**. Some 50- and 100-customer cases
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

An audit-only erratum was required after the first final protocol stopped at
10 runs: a floating-point wait could leave a vehicle's `before.time` a few
femtoseconds earlier than its actual dispatch event. Independent replay now
checks release legality at the recorded dispatch time and requires the vehicle
time to agree within the existing numerical tolerance. The original partial
holdout and failure evidence are preserved under `final_holdout/`; the
separately fingerprinted complete evaluation writes to
`final_holdout_audit_erratum/`. It is **complete: 270/270 audited final runs**
over 54 paired scenarios, with zero DoD exclusions. No optimizer, objective, controller, charging
policy, scenario, budget, or reserved instance was changed.

See the [final results](results/desaulniers/final_holdout_audit_erratum/SUMMARY.md)
and its 300-dpi PNG figures. On the final holdout, ALNS served 99.14% of
customers, HGS 98.89%, ACS 98.19%, MCTS 96.00%, and Completion 92.19%.
These are online service rates, not claims of static optimality.

The [new paper tables and 300-dpi PNG figures](results/desaulniers/paper_v2/RESULTS.md)
include instance-clustered paired intervals and conditional distance on
common complete-service scenarios. The [service-loss report](results/desaulniers/service_diagnosis_v2/REPORT.md)
documents observations from final traces without claiming causal proof.
The [270-record integrity report](results/desaulniers/validation/final_integrity.md)
replays every corrected final raw trace and checks file hashes and paired
identities. The [reference coverage audit](results/desaulniers/reference_validation/SUMMARY.md)
separately records published-route and fallback-reference status for all 168
instances; a search timeout is not proof of infeasibility.

The [v2 engineering pilot](results/desaulniers/robustness_pilot_v2/SUMMARY.md)
passed five independent audits. Its first six-instance draft was rejected
*before any robustness method run*: every selected instance was ineligible
at target DoD 0.75. The [eligibility-only preflight](results/desaulniers/robustness_v2/preflight_candidates.md)
preserves the reasons and selects the lexicographically first unused,
SF/MF-replayed eligible instance in each family-size slot, without looking
at optimizer outcomes. The actual [v3 multi-seed protocol](configs/desaulniers_mp_robustness_v3.yaml)
has six balanced instances, three eligible DoD levels, seeds 1-5, and is
**complete: 450/450 independently audited runs**. The separate
[robustness results](results/desaulniers/robustness_v3/RESULTS.md) report
90 matched scenarios, paired instance-clustered intervals, and 300-dpi PNG
figures. Its original analyzer is available at the archived source commit;
`python -m scripts.audit_frozen_studies` audits it from this branch. Do not pool these
new seeds or instances with the corrected final holdout; hardware and
runtime conditions are reported separately.

For the field mapping, rounding validation, charging and fleet assumptions,
see [Desaulniers migration notes](docs/DESAULNIERS_MIGRATION.md).
For protocol boundaries, audits, and exact reproduction commands, see
[validation and reproduction](docs/VALIDATION_AND_REPRODUCTION.md).
