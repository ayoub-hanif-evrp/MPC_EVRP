# Pre-V3A cleanup inventory

The exact pre-cleanup inventory is [`cleanup_manifest.json`](cleanup_manifest.json). It records every one of the 4,489 Git-tracked paths at `af6f8cd4f21d07c2d02d4217f4dd75feefaec8a0`, their working-tree byte counts and SHA-256 digests, classification, reason, archive location, and intended impact. The tracked total was 533,681,630 bytes. This is a snapshot, not a claim that every untracked local artifact has been classified.

| Class | Files | Bytes | Treatment |
| --- | ---: | ---: | --- |
| ACTIVE_CORE | 1,051 | 31,273,844 | Retain source, tests, configurations, benchmark inputs, and current navigation. |
| FROZEN_EVIDENCE | 3,082 | 486,963,363 | Retain the paper evidence, historical raw records with live audit dependencies, and source archive. |
| ARCHIVE_REQUIRED | 356 | 15,444,423 | Remove from this branch after verified remote archival. |

The two archived groups are `results/desaulniers/performance_engineering_v1/` (244 tracked files) and `results/desaulniers/fast_framework_v1/` (103), plus their two configurations and seven dedicated orchestration/report scripts. They contain negative and technical engineering outcomes. Their exact source and raw data remain in the archival revision. No active final CPU paper runner or test imports those dedicated scripts. The frozen `evrp/` implementation remains intact.

The historical `reliability_v2/development/raw/` records are retained: `scripts/maintenance/manifest_reliability_v2.py --verify-remaining` explicitly expects them. The current final CPU paper, replication, audit, and source fingerprints are retained at their original paths. The broad `results/` tree also contains other historical studies, but their exact dependencies have not all been cleared; the manifest conservatively retains them.

Ignored local artifacts are outside the tracked byte counts. The existing results inventory found 1,796 removable local cache/scratch candidates (40,198,884 bytes) and 10,358 files requiring review. These are not treated as evidence that tracked files can be deleted. In particular, 291 ignored files under the old fast-framework directory were not staged for deletion.

## Archive and recovery

The annotated tag `archive/pre-v3a-cleanup-2026-11-05` was pushed to `origin`; its peeled commit is the pre-cleanup revision above. All 356 proposed files were checked against the tag with SHA-256, and all 356 were restored and checked byte for byte in a detached sparse worktree. For exact working-tree bytes on Windows, set `core.autocrlf false` before restoring and restore `.gitattributes` with the files.

```powershell
git fetch origin tag archive/pre-v3a-cleanup-2026-11-05
git worktree add --detach ..\MPC_EVRP_v3a_archive archive/pre-v3a-cleanup-2026-11-05
git -C ..\MPC_EVRP_v3a_archive config core.autocrlf false
python -m scripts.maintenance.v3a_cleanup_inventory --verify
```

The last command verifies tag blobs against the recorded pre-cleanup SHA-256 values; use `--recovery-root ..\MPC_EVRP_v3a_archive` as well after restoring with exact line-ending settings. The archive tag preserves historical source/configuration/protocol relationships without rewriting history. Historical studies should be audited in that detached revision, not by substituting current source files.
