# Final Optimizer Source Freeze

The authoritative development campaign uses one event-triggered MPC controller
with Completion, MCTS, ALNS, HGS, and ACS as its five configured variants. The
four optimization engines and shared scientific source are frozen for this
campaign. The campaign is incomplete; this checkpoint is verification, not a
performance claim.

| Item | Value |
| --- | --- |
| Tested Git commit | `c89fdeb7a0f107d6e39461360a8beb5660801e88` |
| Optimizer source fingerprint | `3c6ffdfb5ab86190ff6c45e7eaf063dcdb6c80508bf46c6849269342e718628b` |
| Common controller config SHA-256 | `a28ef410ebed72331815b49f954f907809637266d24e47043810dd96779a9817` |
| Development protocol SHA-256 | `e586fd8ce95453209fa8ad9ca2fb81eebdadbd32dfd5b78f14f64c48acfbd475` |
| JUnit XML SHA-256 | `1722b2eb9bf17bab85021b76bca7e968997485a22cd88d08c1276bf1905cd5f6` |
| Full-suite result | 357 tests, 0 failures, 0 errors, 0 skips |

Verification command (run with filesystem access sufficient for pytest's
temporary directory):

```powershell
python -m pytest -q --tb=short --basetemp=results/t20261016_committed --junitxml=results/verification/pytest.xml
```

The active development manifest and raw files must all use the source,
controller, and protocol fingerprints above. Any correctness change to shared
scientific source requires archiving and restarting that authoritative grid.
The prior 72-run source was retired after a false-positive constructor
insertion audit failure; its manifest and raw records remain historical under
`results/portfolio/development/historical_pre_audit_fix_manifest.json`.
