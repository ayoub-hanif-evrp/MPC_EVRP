# Reliability V2 archival and active-tree pruning

Reliability V2 is a **stopped, partial** development study: 361 of 1,116
planned runs were saved. It is not a completed final experiment. This milestone
did not restart it or change scientific source, configuration, benchmark data,
or any other results campaign.

| Measure | Value |
| --- | ---: |
| Original tracked files | 689 |
| Original logical bytes | 144,737,237 (138.03 MiB) |
| Untracked files in the campaign | 0 |
| Files removed from the active worktree | 312 |
| Logical bytes removed from the active worktree | 13,653,695 (13.02 MiB) |
| Files retained at original paths | 377 |
| Retained logical bytes | 131,083,542 (125.01 MiB) |

The complete pre-pruning path, size, and SHA-256 inventory is
[`archive_manifests/reliability_v2_2026-10-29.json`](archive_manifests/reliability_v2_2026-10-29.json).
It records the original commit, development protocol and manifest identities,
all 689 tracked files, the empty untracked-file list, and every retained path.
Removed paths are exactly `tracked_files` minus `retained_relative_paths`.
The large removed groups were `development/inputs/` (155 files, 9,157,969
bytes), `diagnosis/roots/` (128 files, 3,851,485 bytes), and
`diagnosis/exchange_roots/` (20 files, 149,587 bytes); nine other files total
494,654 bytes. These files remain in the archival tag. Some are unique
historical evidence, not disposable caches; archival protection preceded
their removal.

## Archive verification

- Original commit: `3f1e9ff8e90843691b6d3347759dddb9815e00fa`.
- Annotated tag: `archive-reliability-v2-2026-10-29` (tag object
  `39bd527dc5ee863b88558b455b30b190f488c261`). It was pushed and
  verified before pruning; the original commit was not rewritten.
- GitHub's tag ref peeled to the exact original commit. A fresh shallow clone
  of that tag had the same root tree (`71d39178358e37924a61448f512d8e787ed1a0bf`)
  and all 689 Reliability V2 paths. Independently fetched stop-marker,
  protocol, and compressed-raw blobs matched the manifest's SHA-256 values.
- Before pruning, the development protocol identifier matched its partial
  manifest and every tracked file matched the manifest. After pruning,
  `python -m scripts.maintenance.manifest_reliability_v2 --verify-remaining`
  checks every retained hash and every expected removal.

To inspect or replay the complete historical snapshot without touching the
active tree, fetch the tag and create a separate detached worktree:

```powershell
git fetch origin tag archive-reliability-v2-2026-10-29
git worktree add --detach <separate-directory> archive-reliability-v2-2026-10-29
```

The old `REPRODUCE.md` and Reliability V2 analysis/runner need the archived
`development/inputs/` files. The study remains stopped; archival retrieval is
not authorization to restart it.

## Active dependencies

The current paper renderer reads `diagnosis/events.json` at its original path.
The active performance-engineering report verifies `STOP_REQUESTED.json`,
`development/manifest.json`, and all 361 `development/raw/` files byte-for-byte.
They therefore remain. `development/protocol.json` and the historical stop,
preregistration, amendment, run/supervisor records, compute review, diagnostic
summary, and linked profile remain for provenance and document links. The
retained paths are listed exactly in the hash manifest. No current final-paper
or performance-report command requires the archived inputs.

## Validation

The full suite passed before and after pruning: 473 passed, 4 skipped in each
run. All five baseline optimizer modules imported. Read-only physical and
information-boundary replays passed for the 450-run primary cohort and the
60-run independent CPU replication; 25 archived development pairs were
available. The 361 stopped-study raw hashes and the 128-miss paper diagnostic
input checked before and after. Existing GPU-archive and Git-transport checks
also passed. In isolated scratch output, all 13 final-paper Markdown tables
were byte-identical to the frozen package and all 12 PNG figures rendered at
300 dpi. No optimization campaign or Reliability V2 runner was executed.

This saves active worktree space only. The 144,737,237 original bytes remain
reachable through Git history and the tag; this is not repository-history
compaction. The large live diagnostic and raw files limit further safe
reduction without changing current reproduction commands.

The next candidate for a separate dependency audit is
`results/desaulniers/performance_engineering_v1/` (244 tracked files in the
original inventory). Its fast-framework references must be mapped before any
archival or removal decision.
