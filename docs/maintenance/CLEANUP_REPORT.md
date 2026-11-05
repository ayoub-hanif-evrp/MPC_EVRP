# V3A branch cleanup report

This cleanup removed two unpromoted performance-engineering study trees and their dedicated launch/report tools from the active research branch. The original five-method plant, final CPU paper evidence (450 primary and 60 replication runs), historical protocol/source fingerprints, and Reliability V2 integrity inputs remain in place.

| Measure | Before | After |
| --- | ---: | ---: |
| Git-tracked files | 4,489 | 4,133, before adding this cleanup documentation and script |
| Git-tracked working-tree bytes | 533,681,630 | 518,237,207, before adding this cleanup documentation and script |
| Archived and removed tracked files | — | 356 |
| Reclaimed tracked working-tree bytes | — | 15,444,423 |

Removed paths: `results/desaulniers/performance_engineering_v1/` (244 files), `results/desaulniers/fast_framework_v1/` (103 files), two matching YAML configs, and seven matching scripts. The complete exact path list and hashes are in [`cleanup_manifest.json`](cleanup_manifest.json). Ignored local files are excluded from these measurements and were not deleted. The old study results remain searchable via the manifest and the archived reports at the tag.

The remote tag `archive/pre-v3a-cleanup-2026-11-05` resolves to `af6f8cd4f21d07c2d02d4217f4dd75feefaec8a0`. Tag blob verification and a detached recovery check each passed for all 356 files and 15,444,423 bytes. See [the inventory](REPOSITORY_CLEANUP_INVENTORY.md) for restoration instructions. This tag was pushed before deletion, and no history was rewritten.

The baseline suite passed with 526 tests and 4 skips before cleanup. The post-cleanup suite again passed with 526 tests and 4 skips in 81.93 seconds. The original Reliability V2 manifest verifier passed for all 377 retained files, and the V3A archive manifest verifier passed for all 356 archived files. Further historical results were retained because active audits or provenance relationships still depend on them. In particular, the Reliability V2 raw records cannot be pruned without changing its current retained-file verifier. This is an intentional limit on the cleanup, not an assertion that all historical results are active research inputs.
