# Reproduction and artifact provenance

Package-generation source commit: `6503ba965a8ca2b3d4f01f82650ffa2f176b651f`. Dependencies are in
`requirements.txt`; the validated regression suite contains 284 tests.
The evidence inventory binds copied artifacts to file SHA-256 digests.

```powershell
python -m pytest tests -q --basetemp results/.pytest_publication
python -m scripts.archive_frozen_inputs --restore
python -m scripts.audit_frozen_studies
python -m scripts.audit_enhancement_studies
python -m scripts.audit_reference_inventory
python -m scripts.analyze_planning_losses
python -m scripts.analyze_publication_pair --config configs/publication_stable_screen_v1.yaml
python -m scripts.analyze_runtime_validation
python -m scripts.render_publication_package
```

The historical-source auditor checks Git blobs at the exact executed source
revisions instead of requiring the current development tree to be identical.
On a fresh checkout the input-restoration command restores exact archived
references and scenarios first, without running a reference optimizer.
The old study-specific runners still enforce their own original fingerprints;
use the archived commits when reproducing their optimization, rather than
editing their protocols. Raw evidence remains in the original result paths.

New runner: `python -m scripts.run_publication_campaign --config <config>`.
Offline extension: `python -m scripts.extend_mp_reference_coverage`.
Both reuse validated saved artifacts, reject provenance drift, and preserve
failures. Do not rerun optimization to regenerate paper tables.
The optional planning-loss analyzer performs bounded diagnostic probes at
saved observable roots; it does not rerun the historical online campaigns.

All paper tables are Markdown and figures are PNG at 300 dpi or higher.
Internal JSON, CSV and XML are retained outside this paper directory.
