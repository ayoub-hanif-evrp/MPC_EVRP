# Results index

## Historical Evidence

`paper/` is the frozen earlier paper track, not a new unseen holdout.
`portfolio/development/historical_pre_mcts_final_manifest.json` and
`portfolio/development/historical_nonisolated_manifest.json` preserve earlier
optimizer development. `portfolio/development/historical_pre_audit_fix_manifest.json`
preserves 72 audited records from the source retired after the
`c109_21`/0.25/2 ALNS audit failure. The failure record and diagnostic
reproduction are under `portfolio/development/failures/`. Other legacy
directories below remain for provenance.

## Development Study

`portfolio/development/manifest.json` is the authoritative final-source
66-scenario by five-method grid. Its raw records live under
`portfolio/development/raw/`; analysis belongs under
`portfolio/development/analysis/`. The grid is incomplete until 330 audited
records with one common source, controller and protocol fingerprint exist.

## Shadow Study

`portfolio/shadow/selection.json` must contain the complete, committed
observable-state selection before optimizer outcomes in `portfolio/shadow/raw/`
are generated. `portfolio/shadow/sbs_vbs_gate.json` is analysis-only until the
full shadow grid is audited.

## Final Study

`final_study/` is reserved for a new deterministic unused-instance
preregistration and its later audited holdout. No final results currently
exist; historical consumed instances are development evidence.

## Verification

`verification/pytest.xml` records the latest full suite. The matching source
and protocol fingerprints are documented in
[`docs/FINAL_SOURCE_FREEZE.md`](../docs/FINAL_SOURCE_FREEZE.md).

## Other Archives

| Directory | Classification | Meaning |
| --- | --- | --- |
| `paper/` | HISTORICAL_EVIDENCE | Immutable earlier paper raw evidence, manifests and tables |
| `portfolio/` | DEVELOPMENT_AND_SHADOW | Current optimizer study; no new final holdout yet |
| `verification/` | VALIDATION | Fresh test reports and protocol checks |
| `development/` | LEGACY_DEVELOPMENT | Earlier controller development |
| `final/` | LEGACY_DEVELOPMENT | Historical stopped/partial campaigns |
| `fleet_lns_development/` | LEGACY_DEVELOPMENT | Earlier LNS pilot |
| `fleet_lns_hybrid_static/` | LEGACY_DEVELOPMENT | Earlier hybrid static checks |
| `fleet_lns_review_validation/` | VALIDATION | Historical LNS review |
| `fleet_lns_static/` | LEGACY_DEVELOPMENT | Historical LNS static runs |
| `fleet_lns_validation/` | VALIDATION | Historical LNS validation |
| `fleet_mcts_risk_bounded_static/` | LEGACY_DEVELOPMENT | Earlier MCTS risk tests |
| `fleet_mcts_risk_dynamic_dev/` | LEGACY_DEVELOPMENT | Earlier dynamic risk tests |
| `fleet_mcts_risk_final_static/` | LEGACY_DEVELOPMENT | Earlier static risk tests |
| `fleet_mcts_risk_static/` | LEGACY_DEVELOPMENT | Earlier static risk tests |
| `fleet_mcts_risk_static_b695d12/` | LEGACY_DEVELOPMENT | Earlier source-specific static tests |
| `fleet_mcts_static/` | LEGACY_DEVELOPMENT | Earlier static MCTS runs |
| `fleet_mcts_upgrade_dev/` through `fleet_mcts_upgrade_dev6/` | LEGACY_DEVELOPMENT | Iterative MCTS pilots |
| `fleet_mcts_validation/` | VALIDATION | Earlier MCTS validation |
| `scenarios/` | REGENERABLE | Cached generated dynamic scenarios |
| `screening/` | LEGACY_DEVELOPMENT | Earlier screening studies |
| `smoke/` | VALIDATION | Small integration checks |
| `validate/` | VALIDATION | Historical validation runs |

The root `IMPLEMENTATION_REPORT.md` is a historical note; the root
`README.md` is the current project overview. No directory has been deleted
or moved. Historical manifests still refer to their original paths.
