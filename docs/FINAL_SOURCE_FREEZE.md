# Final Optimizer Source Freeze

The authoritative development campaign uses one event-triggered MPC controller
with Completion, MCTS, ALNS, HGS, and ACS as its five configured variants. The
four optimization engines and shared scientific source are frozen for this
campaign. The campaign is incomplete; this checkpoint is verification, not a
performance claim.

| Item | Value |
| --- | --- |
| Tested Git commit | `b1ccbb8da81fb87c25c12907df5507cd1bb8eaf2` |
| Optimizer source fingerprint | `be83aa76bb897303733319c9ba69a4534f08137faf3a53b4c07ad3f20e4d6662` |
| Common controller config SHA-256 | `a28ef410ebed72331815b49f954f907809637266d24e47043810dd96779a9817` |
| Development protocol SHA-256 | `e586fd8ce95453209fa8ad9ca2fb81eebdadbd32dfd5b78f14f64c48acfbd475` |
| JUnit XML SHA-256 | `c2e0233352ed1f283e0f4316c5acb69f6a097da063b8d10d5d39507d23dc6712` |
| Full-suite result | 355 tests, 0 failures, 0 errors, 0 skips |

Verification command (run with filesystem access sufficient for pytest's
temporary directory):

```powershell
python -m pytest -q --tb=short --basetemp=results/t20261015_committed --junitxml=results/verification/pytest.xml
```

The active development manifest and raw files must all use the source,
controller, and protocol fingerprints above. Any correctness change to shared
scientific source requires archiving and restarting that authoritative grid.
