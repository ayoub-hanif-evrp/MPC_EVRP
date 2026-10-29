# Generated-results cleanup, 2026-10-29

This report is the earlier cache-only snapshot. The later, separate
[Reliability V2 archival milestone](RELIABILITY_V2_ARCHIVE_2026-10-29.md)
verified a remote annotated tag and proposed 312 tracked-file deletions;
its measured reduction is not included in the table below.

This cleanup removed disposable local test artifacts only. The before/after
table is a consistent PowerShell `Get-ChildItem -Recurse -File` snapshot of
logical byte lengths, taken before this report was written. It excludes
`.git/` for the project total and does not measure allocated disk blocks.
PowerShell omits some OneDrive reparse subtrees under `results/paper/`: the
independent Python inventory after cleanup counted 14,015 results files and
803,060,168 bytes, rather than the table's smaller PowerShell-visible subset.
Tests ran between measurements, so net deltas are not identical to the sum of
per-pass removal logs. Documentation added after the snapshot also changes
the current worktree count slightly.

| Scope | Before files | After files | Before bytes | After bytes | Net bytes reduced |
| --- | ---: | ---: | ---: | ---: | ---: |
| `results/` | 97,432 | 10,758 | 1,161,540,497 | 744,337,331 | 417,203,166 |
| Project excluding `.git/` | 104,335 | 17,694 | 2,948,904,848 | 2,532,268,982 | 416,635,866 |

`python -m scripts.maintenance.clean_generated_results` is a read-only dry
run. `--apply` deletes only untracked, link-free candidates after rescanning
them. It reports actual per-directory removals in JSON and refuses changed
candidates. The final dry run found zero candidates and zero rejections.

Actual removal passes covered 80 root `results/.pytest_*` trees, 130 nested
`__pycache__` trees, four `results/verification/pytest_*` fixture trees, and
25 legacy `results/t*` pytest fixture trees. Full test runs recreated
`results/.pytest_work`; it was removed after each run. The first cache
pass removed 50,519 files (267,277,183 bytes), the verification pass 6,872
files (22,933,416 bytes), and the legacy-fixture pass 28,983 files
(116,051,321 bytes). An intermediate retry removed five small files and
remaining read-only OneDrive directories; the two later test-cache passes each
removed 378 files (10,443,796 and 10,443,789 bytes). Directory-removal
permission errors from the
first pass were resolved by a tested read-only-attribute retry. No approved
cache candidate remains.

The retained `results/desaulniers/` campaigns, including `final_cpu_paper_v1`,
`robustness_v3`, `reference_validation`, development and negative-result
evidence, and frozen inputs, were not edited. Untracked `results/final/`
contains 39 JSON run records; `results/paper/` contains raw/protocol and
external-package artifacts. The two `results/verification/*.xml` reports were
retained. These trees were not deleted based on naming or apparent age.

The 51 local `results/reference_schedules/` files include 50 exact SHA-256
matches with tracked frozen/reference copies, leaving one unmatched. Of 344
local `results/scenarios/` files, 198 match tracked frozen inputs exactly,
leaving 146 unmatched. Live scripts read these caches, so whole-directory
deletion would risk both unique inputs and reproduction paths. Two legacy
test-fixture trees (`results/t2/` and `results/t3/`) had 646 files with matching
relative paths and SHA-256 hashes; deletion was based on their complete
pytest fixture layout and absence of tracked files/references, not that sample
alone. `results/.p1/`, `results/paper/test_tmp_2/`, and other untracked raw or
temporary-looking files remain pending provenance review.

Historical tracked archival candidates remain those in
[RESULTS_RETENTION_PLAN.md](RESULTS_RETENTION_PLAN.md): `development_campaign`,
`final_holdout`, `final_holdout_audit_erratum`, `reliability_v2`,
`performance_engineering_v1`, `fast_framework_v1`, `paper_v2`,
`publication_package_v1`, and the smaller pilot/validation directories.
Before moving them, verify a durable remote archive and exact hashes, then
update frozen auditors, paper renderers, runners, and documentation that read
their current paths. No historical evidence was archived or removed here.

Outside `results/`, ignored `.pytest_cache/` and `__pycache__/` directories are
generated cleanup candidates for a separately scoped pass. `.venv-accel/`
needs environment-rebuild verification first. Historical scripts, configs,
`archive/v1/` source, and benchmark data are not deletion candidates merely
because they are old. The five baseline optimizers still import. The full
suite passed before cleanup (455 passed, 2 skipped) and after the final code
change (473 passed, 4 skipped); no tracked benchmark or Desaulniers result file
was modified or deleted. No research campaign was run.
