# Results index

## Development pilot

`desaulniers/development_pilot_final_source/protocol.json` freezes the selected development
instances, fixed methods, five-second budget, controller, source, and dataset.
`manifest.json` indexes audited raw records. `SUMMARY.md` and PNG figures are
generated only after all 15 pilot runs complete. Local
`development_pilot/` is an ignored pre-cleanup checkpoint with a different
source fingerprint; the two directories must not be pooled.

## Development campaign

`desaulniers/development_campaign/` is the separately fingerprinted,
resumable six-family by three-size by three-DoD design. Its manifest is
complete at 270/270 audited method runs.

The old Schneider development, shadow, and final-study artifacts were removed
from the active tree and remain available in Git history.

`desaulniers/final_holdout/protocol.json` freezes the reserved 18-instance
final design before its first run.

The first final run stopped after 10 records on a strict replay-audit timing
defect. Its protocol, manifest, raw files, and failure evidence remain in
`desaulniers/final_holdout/`. The auditor-only correction uses a separately
fingerprinted continuation in `desaulniers/final_holdout_audit_erratum/`;
none of the original final records are silently reused or overwritten.
The corrected final manifest is complete at 270/270 audited method runs over
54 matched scenarios, with zero DoD exclusions. `SUMMARY.md` contains the
final tables and the two figures under `figures/` are PNG only.
