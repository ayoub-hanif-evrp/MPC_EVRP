# Validation notes

- The first focused determinism test also compared elapsed improvement timestamps. It failed because wall-clock measurements differ between identical seeded searches; routes, objectives and search counters matched. The corrected assertion compares deterministic routes/objectives/counters and excludes only elapsed improvement times. Physical assertions were not relaxed.
- The complete pre-pilot suite passed 524 tests with 4 skipped. Its original JUnit bytes remain bound to the frozen protocol.
- All 510 historical raw records passed independent physical/information replay and remained byte-identical after the pilot.
- All ten original-method pilot executions completed, passed their worker audits, and passed a second replay from saved files. No outcome was rerun or replaced.
- The initial report routine assumed a fallback-count field absent from the original five-method schema. The analysis-only KeyError is saved in analysis_failure.json. A separate analyzer reports missing counters as unavailable and has two regression tests; it did not change the executed source or outcomes.
- The final full suite, including analysis regressions, passed 526 tests with 4 skipped. tests_analysis.xml is separate from the preserved pre-pilot tests.xml.
