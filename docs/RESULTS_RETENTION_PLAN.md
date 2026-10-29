# Results retention and cleanup plan

This plan governs historical scientific evidence; no historical migration or
deletion has been executed. A separate cache-only cleanup was performed on
2026-10-29; see [the measured cleanup report](RESULTS_CLEANUP_2026-10-29.md).
The earlier read-only scan
on 2026-10-29 found 100,798 local files under `results/`: 3,696 Git-tracked
and 97,102 untracked. The inventory utility records every relative path,
size, type, Git status, nearest protocol/manifest metadata, disposition and
reason. Run `python -m scripts.maintenance.inventory_results --summary` for
current counts; run without `--summary` for the complete JSON file list.
Local counts will change as temporary tests and research runs create files.

| Disposition | Local files | Approx. MiB | Interpretation |
| --- | ---: | ---: | --- |
| KEEP_ACTIVE | 1,997 | 255.3 | Tracked current paper, validation, references and negative development evidence |
| ARCHIVE | 1,699 | 231.8 | Tracked historical evidence; no verified dedicated archive for these paths yet |
| REMOVE_CANDIDATE | 50,943 | 258.3 | Mostly ignored pytest trees and interrupted `.tmp` files; inspect before removal |
| REVIEW | 46,159 | 411.4 | Primarily untracked local research trees; provenance is not established |

## Tracked Desaulniers campaign inventory

The following 3,694 files are tracked under `results/desaulniers/`; the two
tracked root index files make 3,696. MiB values are working-tree sizes rounded
to two decimals. `A` means retain active; `H` means propose historical archive
only after the gates below pass.

| Directory under `results/desaulniers/` | Files | MiB | Plan and dependency |
| --- | ---: | ---: | --- |
| `final_cpu_paper_v1/` | 255 | 13.52 | A: replication raw, audit, paper tables and figures; current README/render links |
| `robustness_v3/` | 457 | 58.67 | A: 450-run primary raw, manifest, protocol; frozen audit and paper renderer |
| `reference_validation/` | 28 | 7.81 | A: benchmark feasibility and partial-solution witnesses |
| `final_cpu_development_v1/` | 309 | 24.85 | A: balanced ablation, CPU coverage, input hashes and failed attempt |
| `publication_development/` | 423 | 91.62 | A: frozen input restoration, historical/enhancement audits, diagnosis source |
| `targeted_service_v1/` | 412 | 45.55 | A: important negative development and reference evidence; reliability dependencies |
| `enhancement_development/` | 100 | 12.82 | A: enhancement audit and partial-reference witnesses |
| `two_worker_probe_v1/` | 11 | 0.43 | A: current CPU accounting and paper supplement |
| `development_campaign/` | 274 | 39.25 | H: historical 270-run study; frozen auditor and preflight read it |
| `final_holdout_audit_erratum/` | 275 | 35.36 | H: corrected 270-run final; frozen auditor and preflight read it |
| `reliability_v2/` | 689 | 138.03 | H: stopped 361-run study; diagnosis feeds current paper renderer |
| `performance_engineering_v1/` | 244 | 7.16 | H: previous CPU engineering evidence; fast-framework runner reads it |
| `fast_framework_v1/` | 103 | 7.47 | H: negative/technical follow-up and frozen opt-in evidence |
| `development_pilot_final_source/` | 19 | 1.87 | H: source-bound validated pilot and manifest |
| `final_holdout/` | 13 | 0.46 | H: stopped audit-defect evidence; final runner and verifier reference it |
| `paper_v2/` | 13 | 0.37 | H: historical derived figures/tables; publication-package renderer references it |
| `publication_package_v1/` | 53 | 1.49 | H: earlier consolidated report; documentation references it |
| `robustness_pilot_v2/` | 9 | 0.19 | H: engineering pilot; V2 launcher references it |
| `robustness_v2/` | 3 | 0.01 | H: rejected preflight/protocol; V3 runner references it |
| `service_diagnosis_v2/` | 3 | 0.11 | H: older customer-level diagnosis output |
| `validation/` | 1 | <0.01 | H: historical integrity report |

`H` is deliberately conditional. `scripts/audit_frozen_studies.py` reads the
historical development and corrected-final manifests and reconstructs their
source hashes from Git revisions. `scripts/render_final_cpu_paper.py` reads
`robustness_v3`, the current replication, `reliability_v2/diagnosis/events.json`,
and `publication_development/instrumented_v1/loss_transition_probes.csv`.
`scripts/audit_final_cpu_completion.py` also checks archived inputs, saved
tests, report hashes, and exact Git bytes. Moving any referenced path now would
break the current reproduction commands. Source and configuration hashes must
not be rewritten to make a moved campaign appear unchanged.

## Untracked and generated local files

Large untracked groups include `results/paper/` (about 155 MiB),
`results/final/` (112 MiB), `results/verification/` (22 MiB),
`results/reference_schedules/` (8.7 MiB), `results/scenarios/` (2.4 MiB),
and numerous `results/t*/` test or experiment trees. They are all `REVIEW`
unless a particular file is an obvious temporary candidate. The names alone
do not establish duplication or safe removal. In particular, reference and
scenario caches may be the only local copies of historical inputs. Many
`results/.pytest_*/` directories and interrupted `*.tmp` files are
`REMOVE_CANDIDATE`, but an interrupted file can still document a failure.
Untracked files cannot be recovered merely by naming a Git commit or tag.

## Exact proposed cleanup operations for a later milestone

1. Freeze the full file-level inventory and record SHA-256 for every file
   proposed for movement. Identify each study's protocol, source revision,
   configuration, seed list, raw manifest and failed-attempt records.
2. For the 13 `H` directories in the table, place an exact, immutable copy in
   a separately identified durable archive. Verify access and every copied
   hash from that location; document its address and source revision. The
   existing GPU archive tag covers different files and does not satisfy this.
3. Audit each `REVIEW` root separately. Compare hashes with tracked evidence
   and with the proposed archive; retain unique raw, reference and failure
   records. Do not infer duplicates from filenames or timestamps.
4. Update literal paths in the named runners, auditors, tests and documentation
   to read the archive or an explicit historical path. Replay independent
   audits and regenerate the current paper package from the authoritative raw.
5. Only after those checks and a later deletion approval, remove the verified
   original paths for `H` directories. Separately inspect and remove selected
   `results/.pytest_*/`, `results/**/__pycache__/`, and `results/**/*.tmp`
   candidates. No `REVIEW` path is on the deletion list.

Archiving all currently proposed `H` directories could shrink the active
tracked results tree by about 232 MiB. Confirmed disposable local test/temp
artifacts could release up to about 258 MiB more, but their safe subset is not
yet measured. These were conditional estimates, not achieved savings from the
original inventory milestone. The later cache-only cleanup is measured in the
linked report. The broad `.gitignore` rules already protect
many generated files, but new study manifests and validation evidence will
need explicit exceptions before new output paths are used.
