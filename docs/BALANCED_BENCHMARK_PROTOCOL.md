# Balanced independent MPC-ALNS versus MPC-HGS preflight

## Decision

**BLOCKED: insufficient untouched eligible parent groups.** No evaluation parents are selected, no confirmatory protocol is frozen, and no optimizer executions are authorized by this preflight. The requested design remains 18 parents, 54 files/scenarios, and 108 paired optimizer jobs. It is not replaced with a smaller or previously examined cohort.

The read-only utility is [design_balanced_benchmark.py](../scripts/experiments/design_balanced_benchmark.py). Its explicitly saved [machine-readable exposure inventory](../results/research_v2/balanced_evaluation_v1/validation/exposure_inventory_final.json) contains all 56 parents, 168 variant identities, source hashes, references, exclusion reasons, exposure roles/examples, and historical timing samples. It is an audit snapshot, not a preregistered execution protocol. An earlier local preview snapshot is preserved separately. The earlier [research decision](RESEARCH_DIRECTION_DECISION.md) remains applicable.

## Inventory and exposure rules

The actual format-1 directory contains 169 text files: 168 benchmark instances and `Readme.txt`. Parsing confirms 56 distinct parents, each with 25-, 50-, and 100-customer variants. Group by the part before `_21_`, retaining the family digit: `c105_21_25`, `c105_21_50`, and `c105_21_100` are one parent, `c105`. A parser checks the customer count and paired format-2 arcs; filenames alone are insufficient.

The complete parent inventory is:

| Family | Parents |
| --- | --- |
| C1 | c101, c102, c103, c104, c105, c106, c107, c108, c109 |
| C2 | c201, c202, c203, c204, c205, c206, c207, c208 |
| R1 | r101, r102, r103, r104, r105, r106, r107, r108, r109, r110, r111, r112 |
| R2 | r201, r202, r203, r204, r205, r206, r207, r208, r209, r210, r211 |
| RC1 | rc101, rc102, rc103, rc104, rc105, rc106, rc107, rc108 |
| RC2 | rc201, rc202, rc203, rc204, rc205, rc206, rc207, rc208 |

Prior outcome exposure at any size excludes the entire parent. Raw result metadata, completed manifest records, explicit historical-exposure declarations, and diagnostic roots are evidence. Unresolved mentions are excluded conservatively. Protocol/config listings alone are `planned_only`; benchmark/reference/scenario replay alone is `reference_only`. In particular, the unexecuted portion of the stopped Reliability V2 protocol is not silently counted as completed optimization.

The search covers tracked and available local untracked evidence under results/docs/configs/archive, the [Reliability V2 archive inventory](archive_manifests/reliability_v2_2026-10-29.json), and named raw-result paths in all available local Git refs. It inspected 3,799 local evidence files and retained 3,128 relevant source-byte fingerprints with zero scan errors. Identified pytest scratch and third-party vendor trees are excluded and listed. External or unavailable experiments cannot be ruled out; `no_outcome_evidence_found` is conditional on this search, never an absolute guarantee.

Related studies include:

| Role | Parent groups and evidence |
| --- | --- |
| Primary 450-run study | c105, c205, r105, r205, rc105, rc205; `robustness_v3/manifest.json` |
| Independent CPU replication | c102, c202, r102, r202, rc102, rc202; `final_cpu_paper_v1/protocol.json`, manifest and raw metadata |
| Development, selection and targeted ALNS | c101, c201, r101, r201, rc101, rc201 across size variants; development, stable-ALNS, targeted-service and CPU-development evidence; c103 also has an executed engineering pilot |
| Historical final studies | c109, c208, r112, r211, rc108, rc208; corrected final manifests and preserved earlier failures |
| Stopped Reliability V2 | Saved outcomes include c106, c107, c206 and c207. Other preregistered parents remain planned-only unless another source establishes exposure. The 361/1116 study is not resumed. |
| SLAD V1/V2 | c101 and r101; retrospective selection by missed-service outcomes is development exposure |
| Legacy related-parent optimization | Archived `_21` raw-result paths cover all 56 parent identifiers. These are disclosed separately from exact Desaulniers variant exposure and conservatively exclude the related parent from a genuinely untouched claim. |

For example, Git commit `51a2559d1ec0a862031cb9972e5f8c3b8e45cd9a` contains `results/paper/raw/c104_21_GREEDY_a0411823dad3de7ef699.json.gz` (SHA-256 `f6e49928b59c1d5c8184acd2aebe322c59c5c04a5990735dc46f22683718758c`). Its metadata records an executed 100-customer GREEDY result. All 53 customer coordinates encountered in that saved trace match current `c104_21_100`; the instance hashes differ. This establishes related problem exposure, not identical historical physics. Raw-path evidence for every parent is indexed separately in the machine inventory, with a fingerprint of the complete Git-history raw-path list.

## Eligibility and deterministic selection

Use three lexicographically first eligible, unexposed parents within each of C1/C2/R1/R2/RC1/RC2, then all three sizes. All six families must qualify before any parent is selected. Reference replay uses the existing [168-reference inventory](../results/desaulniers/targeted_service_v1/reference_inventory.json): verify benchmark SHA, reference source bytes and canonical ID, full service, all physical constraints, depot return, and fixed fleet size. Use saved reference artifacts or direct replay of published MF/SF routes. Never invoke `prepare()` or `solve_reference()` to populate a cache or construct a new reference during preflight.

| Family | Available parents | Direct outcome exposure | Legacy-related exposure only | Full three-size reference panel eligible at target DoD 0.75 | Untouched eligible parents |
| --- | ---: | ---: | ---: | ---: | ---: |
| C1 | 9 | 7 | 2 | 6 | 0 |
| C2 | 8 | 6 | 2 | 5 | 0 |
| R1 | 12 | 4 | 8 | 6 | 0 |
| R2 | 11 | 4 | 7 | 5 | 0 |
| RC1 | 8 | 4 | 4 | 5 | 0 |
| RC2 | 8 | 4 | 4 | 5 | 0 |

All 168 files have full-service physical witnesses, but some reference-derived release bounds cannot support the requested dynamic count. Missing, stale, corrupt, or incompatible references receive explicit exclusions; expensive construction is forbidden. Reference checking has a 120-second admission cap. **Exact selected parent list: `[]`; selected file/scenario list: `[]`; matched-job list: `[]`.** Inventing 108 selected jobs while the cohort is blocked would misrepresent the design. The utility creates the full job list only if all scientific gates pass.

## Frozen settings and information boundary

Prespecify scenario seed **7301**, target DoD **0.75**, algorithm seed **0** from the paper controller, and the original exact-count scenario generator. Its half-up rounding gives realized DoD 19/25, 38/50, or 75/100; this discretization is preserved. The panel concerns this high-dynamicity regime only.

For a valid cohort, generate each scenario once in memory from its verified reference. Store the benchmark and arc SHA-256, reference-source SHA-256, canonical reference ID, K_ref, release schedule, and canonical scenario SHA-256/ID in the protocol. The SHA of a scenario denotes canonical JSON content, not an invented saved file. Replay verifies reference dispatches occur after release.

The paired configs come from `configs/paper_controller.yaml` with the existing paper execution overrides: summary traces, diagnostics off, original constructor/initialization/coordination/dispatch/first-action/cache/computation/recovery policies, original route decoder and ALNS/HGS parameters, partial charging, one-action MPC control horizon, and **five seconds total planning time**. Only `algorithm` differs between paired configs. The simulator retains its event triggers, fixed fleet, noninterruptible dispatched actions, busy post-action planning origins, physical charging model and safe-return checks. Observations continue to reveal customers only at release; the offline reference and future release schedule are not online optimizer features.

No evaluation parent may train a selector or tune an operator. The other three original methods remain available. Alternate ALNS/HGS execution order deterministically across paired blocks; run one worker at a time with numerical-library thread counts fixed to one. Shared-machine load must be documented; it cannot become an isolated timing claim.

## Compute admission

The provisional preview defaults are **12 wall-hours, 12 worker-CPU hours, and 1 GiB storage**, configurable before freezing. These are planning limits, not permission to execute. Historical original-method samples come only from SHA-checked raw records labelled isolated in the primary and CPU-replication manifests: 34 wall observations and four measured worker-CPU observations per size/method. Missing primary CPU measurements are not fabricated from wall time.

Per worker, set the spending cap to `ceil(max(60, 2*max_observed_wall + 60, 2*max_measured_CPU + 60))`; do not clip high predictions to make admission pass. This is an empirical conservative forecast and a hard spending cap, not a mathematical guarantee of completion.

| Customers | ALNS cap (s) | HGS cap (s) |
| --- | ---: | ---: |
| 25 | 192 | 207 |
| 50 | 591 | 676 |
| 100 | 425 | 876 |

For a hypothetical eligible 18-parent panel: ALNS worker allowance is **21,744 s (6.04 h)**; HGS is **31,662 s (8.80 h)**. Add 600 s setup, 900 s validation, and 2 s supervisor reserve for each of 108 jobs: **55,122 s (15.31 h)** sequential wall/CPU admission allowance. This exceeds both default limits. The scientific status remains BLOCKED; if the cohort were valid, these defaults would return OVER BUDGET. No automatic budget extension or sample reduction is allowed.

Estimated storage is **57,073,996 bytes (54.43 MiB)**, using twice the historical maximum compressed raw size per stratum, 64 KiB log reserve per job, and 16 MiB for inputs and inventory. This is a forecast; the future runner must enforce its storage limit as well as wall/CPU limits.

The next execution milestone must implement resumable, append-only paired blocks and persistent failure records. Admit both legs plus reserves before starting a pair. Enforce each worker cap on the greater of elapsed and measured child CPU time. On timeout, kill only the owned worker, preserve logs/failure evidence and any completed leg, and pause for review; no silent retry, dropped hard case, or replacement parent. Do not claim a complete comparison until every required pair passes audit.

## Prespecified analysis

For size s in {25,50,100}, let d[p,s] = served_ALNS[p,s]/s - served_HGS[p,s]/s. Define d[p] = (d[p,25] + d[p,50] + d[p,100])/3 and the primary estimand Delta = mean of d[p] over the 18 parents. Report proportions and percentage points. This weights parents and their three sizes equally; it differs from pooled customer-weighted service.

Use 20,000 percentile bootstrap draws, seed **7302**: independently resample three complete parent groups with replacement within each of the six fixed families, carrying all three sizes together, and recompute Delta. Report a descriptive 95% interval. Three parents per family give limited resampling support; inherited benchmark structure also limits generalization. This is not a power guarantee. Size variants, release seeds, and decision epochs are never independent parent observations.

Apply the same aggregation to complete-service indicators and report its paired difference and interval. Also report pooled customer-weighted service, counts of fully served scenarios, family/size descriptions, the 100-customer subset, scenario-level and parent-level wins/ties/losses, p50/p95/p99/max decision latency, and all physical/information audits. Compare distance and operating measures only when both methods served the identical customer set on the same scenario. Subgroups are exploratory; do not test thousands of decisions as independent instances.

An ALNS-superiority statement requires positive Delta with a 95% lower bound above zero, a complete-service 95% lower bound at least zero, all required paired outcomes, and no physical/information/five-second compliance failure. This strict complete-service gate is chosen before new results. Always report effects and uncertainty if the rule fails; an interval containing zero is not evidence of equivalence.

## Commands and next decision

```powershell
# Read-only preview; exit code 2 means the design is not admitted.
python -m scripts.experiments.design_balanced_benchmark --summary
python -m scripts.experiments.design_balanced_benchmark --wall-hours 12 --cpu-hours 12 --storage-gib 1

# Explicitly save the exposure audit once; refuses to overwrite it.
python -m scripts.experiments.design_balanced_benchmark --write-inventory exposure_inventory_final.json

# Allowed only after a complete valid cohort and budget exist. Currently refuses.
python -m scripts.experiments.design_balanced_benchmark --freeze

# Read-only verification of a future frozen READY protocol; none exists now.
python -m scripts.experiments.design_balanced_benchmark --verify results/research_v2/balanced_evaluation_v1/validation/protocol.json

python -m pytest -q tests/test_balanced_benchmark_design.py
```

The frozen protocol would include exact scientific source fingerprints and reject subsequent source, exposure, dataset, reference, release-schedule, configuration or budget drift. Creation is exclusive and versioned by `balanced_evaluation_v1`; it cannot overwrite an existing protocol. A later corrected design needs a separately named study, before any outcomes are opened.

Validation: the final full suite passed **507 tests, with 4 skipped**. The new fixture tests cover grouping, outcome-independent selection, prior exposure versus reference-only evidence, pairing, original settings, compute refusal, missing/corrupt references, preview writes, freeze refusal, non-overwriting creation, and verification drift. All 3,128 saved source hashes and current utility fingerprints were checked after the final preview. A real freeze request against the saved BLOCKED report was refused and no `protocol.json` was created. No benchmark optimization jobs were executed.

The next step is a scientific design decision, not launching 108 jobs: either obtain a benchmark cohort with genuinely new parent geometry and suitable audited references, or preregister a clearly labelled **exploratory comparison on exposed parents** with explicit limits on independence. The latter may be informative but cannot be sold as an untouched confirmation. Merely reducing this panel or changing DoD/seeds does not erase exposure. Only after a defensible cohort and budget are approved should a separate prompt implement the paired supervisor. No optimizer, simulator, historical result or frozen launcher is changed by this milestone.
