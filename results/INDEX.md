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
resumable six-family by three-size by three-DoD design. Its protocol may be
frozen without execution; a partial manifest is not a completed study.

No Desaulniers final evaluation has been executed yet. The old Schneider
development, shadow, and final-study artifacts were removed from the active
tree and remain available in Git history.

`desaulniers/final_holdout/protocol.json` freezes the reserved 18-instance
final design before its first run. Its runner remains gated on completion of
the development campaign; a frozen protocol alone is not a final result.

The first final run stopped after 10 records on a strict replay-audit timing
defect. Its protocol, manifest, raw files, and failure evidence remain in
`desaulniers/final_holdout/`. The auditor-only correction uses a separately
fingerprinted continuation in `desaulniers/final_holdout_audit_erratum/`;
none of the original final records are silently reused or overwritten.
