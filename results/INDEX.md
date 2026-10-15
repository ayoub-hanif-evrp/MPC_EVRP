# Results index

Only `results/paper/`, `results/portfolio/`, and `results/verification/` are
current entry points. Other directories are preserved for provenance; they
must not be confused with the current optimizer comparison.

| Directory | Classification | Meaning |
| --- | --- | --- |
| `paper/` | CURRENT_PAPER | Immutable V1 raw evidence, manifests and tables |
| `portfolio/` | CURRENT_PORTFOLIO | New optimizer development; no final holdout yet |
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
`README.md` is the current project overview.
No directory has been deleted or moved. V1 manifests still refer to their
original paths.
