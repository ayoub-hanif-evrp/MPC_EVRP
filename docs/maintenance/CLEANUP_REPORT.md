# V3A branch cleanup report

This cleanup removed two unpromoted performance-engineering study trees and their dedicated launch/report tools from the active research branch. The original five-method plant, final CPU paper evidence (450 primary and 60 replication runs), historical protocol/source fingerprints, and Reliability V2 integrity inputs remain in place.

| Measure | Before | After |
| --- | ---: | ---: |
| Git-tracked files | 4,489 | 4,133, before adding this cleanup documentation and script |
| Git-tracked working-tree bytes | 533,681,630 | 518,237,207, before adding this cleanup documentation and script |
| Archived and removed tracked files | — | 356 |
| Reclaimed tracked working-tree bytes | — | 15,444,423 |

After adding the cleanup inventory and the separate V3A implementation, the branch contains **4,152 tracked files and 520,477,079 tracked working-tree bytes**. This final branch total includes the new SHA-256 manifest, code, tests, and pilot summary; it is therefore larger than the immediate post-deletion total above. Compared with the original branch, the final branch has 337 fewer tracked files and 13,204,551 fewer tracked working-tree bytes. Git history still contains the archive by design, so these are active-tree figures rather than a claim of repository-pack shrinkage.

Removed paths: `results/desaulniers/performance_engineering_v1/` (244 files), `results/desaulniers/fast_framework_v1/` (103 files), two matching YAML configs, and seven matching scripts. The complete exact path list and hashes are in [`cleanup_manifest.json`](cleanup_manifest.json). Ignored local files are excluded from these measurements and were not deleted. The old study results remain searchable via the manifest and the archived reports at the tag.

The remote tag `archive/pre-v3a-cleanup-2026-11-05` resolves to `af6f8cd4f21d07c2d02d4217f4dd75feefaec8a0`. Tag blob verification and a detached recovery check each passed for all 356 files and 15,444,423 bytes. See [the inventory](REPOSITORY_CLEANUP_INVENTORY.md) for restoration instructions. This tag was pushed before deletion, and no history was rewritten.

Two ignored temporary fast-framework directories remain locally unreadable to the ordinary workspace process. They were not tracked, and no deletion was attempted on them; they do not appear in clean clones. The 291 other ignored old-study files were likewise left as local material because their provenance was not checked for deletion.

The baseline suite passed with 526 tests and 4 skips before cleanup. The post-cleanup suite again passed with 526 tests and 4 skips in 81.93 seconds. The original Reliability V2 manifest verifier passed for all 377 retained files, and the V3A archive manifest verifier passed for all 356 archived files. Further historical results were retained because active audits or provenance relationships still depend on them. In particular, the Reliability V2 raw records cannot be pruned without changing its current retained-file verifier. This is an intentional limit on the cleanup, not an assertion that all historical results are active research inputs.
