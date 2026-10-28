# Repository status and preservation policy

The selected publication configuration is the original five CPU MPC methods
on Desaulniers MP instances. The current workflow is the
[final CPU package](../results/desaulniers/final_cpu_paper_v1/FINAL_REPORT.md).
The [mission mapping](FINAL_MISSION_OBJECTIVES.md) distinguishes completed
research tasks from scientific gains that the experiments did not establish.

| Classification | Contents | Decision |
| --- | --- | --- |
| Active scientific framework | evrp/, five original optimizers, Desaulniers physics and common objective | Retain; five-second budget and frozen scientific source unchanged |
| Active publication workflows | Final CPU analyzers, renderer, independent auditors, input restoration | Maintain and test |
| Frozen reproduction dependencies | Historical launchers/configurations, optional research policies and regression tests | Retain to reproduce positive and negative evidence; not selected publication settings |
| Preserved evidence | Benchmark data, reference witnesses, protocols, manifests, raw records and failed attempts | Preserve exact bytes and historical identities |
| Archived obsolete GPU implementation | Four hybrid scripts, GPU configuration, 53 raw records and reports | Removed from active tree; recoverable at the verified remote archive tag |
| Regenerable | Derived reports, tables, figures and audit summaries | Rebuild from audited evidence |
| Ignored local artifacts | Virtual environments, test directories, caches and fresh-checkout directory | Not tracked or scientific evidence; no blanket deletion of user environments |

`scripts.audit_final_cpu_completion` produces a per-source-file classification
and explicit-path/module reference inventory in
`results/desaulniers/final_cpu_paper_v1/audit/repository_inventory.json`.
It also scans active Python source for CUDA/CuPy imports. A zero exact-token
reference count does not prove that a command-line entry point is dead.

Optional CPU screen, recovery, first-action and optimizer variants remain
execution-source dependencies of frozen development studies. They are retained
for reproducibility, including negative findings. The selected replication
runner forces all optional policies to `original`. Keeping the tested CPU
`compiled_screen.py` and `quality_policy.py` does not promote their results.
The stopped Reliability V2 campaign stays stopped.

## Exact reproduction and Git transport

The remote tag `archive/hybrid-gpu-negative-v1` resolves to
`cff13c21fa0947cbc988d80802a8a8b7301a74b7`. Its 53 raw hashes and the removed
source files are checked by the archive audit. See the
[CPU backend decision](CPU_BACKEND_DECISION.md).

Frozen CPU studies recorded exact executed bytes, including CRLF in some JSON
inputs and YAML configurations. `.gitattributes` now marks these artifacts
`-text`, preserving the bytes on LF and CRLF checkouts. Local frozen inputs and
expected hashes are not rewritten. Index/commit checks compare Git blobs with
executed bytes; a fresh detached checkout tests restoration and rendering.
This repairs the earlier LF-blob/CRLF-hash mismatch without weakening raw hashes.

Use the current [reproduction guide](../results/desaulniers/final_cpu_paper_v1/REPRODUCE.md).
Restore archived caches before historical audits. Old study-specific analyzers
require their recorded source revision; the current-tree entry point is
`scripts.audit_frozen_studies`.

## Evidence counts

The paper uses 450 historical primary results and 60 separately preregistered
replication results. Development comprises 120 ablation records and 15 extra
cache-coverage records. Four technical probe records are separate. Counts from
overlapping audit workflows must not be added as distinct experiments.

The general reference inventory reports 166 witnesses; a separate targeted
follow-up supplies the other two, giving combined 168/168 physical coverage
without changing historical fleets or release schedules. Final test, replay,
figure/table, budget and transport results are in
`final_cpu_paper_v1/audit/MISSION_COMPLETION.json`.
