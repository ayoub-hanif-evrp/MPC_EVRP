# Fresh-checkout verification

Verified on 2026-10-29 from committed revision `cd53d47`, using a detached
worktree created with `git -c core.autocrlf=false worktree add --detach`.
This tested committed bytes without relying on the original working-tree
newline conversions or its untracked frozen-input caches.

| Command | Observed outcome |
| --- | --- |
| `python -m scripts.complete_cpu_coverage --freeze` | Existing protocol and scientific hashes matched; 15 jobs and the original 4200-second cap retained; no experiment launched |
| `python -m scripts.archive_frozen_inputs --restore` | 248 cached inputs restored, zero reused; 42 reference and 198 scenario objects accounted for |
| `python -m scripts.audit_final_cpu_completion --git-revision HEAD` | Completion audit passed, including exact committed CPU evidence bytes |
| `python -m pytest -q --basetemp results/.pytest_cpu_checkout` | 419 passed in 81.37 seconds, with no skips or failures |
| `python -m scripts.render_final_cpu_paper` | 510/510 records independently replayed; 15 PNG/SVG figures and 17 Markdown table sets regenerated |

No optimization campaign was rerun. Restoration, tests, replay and rendering
are validation work, not additional scientific experiments. The checkout
contains the same scientific implementation as the final delivery; subsequent
documentation records this verification without changing frozen inputs,
methods or outcomes. This check establishes reproducibility on this machine,
not portability to every platform or isolated-machine runtime performance.
