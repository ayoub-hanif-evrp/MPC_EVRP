# Paper Benchmark Environment

- OS: Windows 11, build 26200, AMD64.
- Python: 3.12.10.
- RoutingBlocks subprocess: isolated CPython 3.11.15, routingblocks 0.2.1,
  pydantic 2.14.1, click 8.5.0. Its native Windows cp311 wheel is pinned in
  `external_versions.json`; this local runtime is not committed.
- CPU: Intel64 Family 6 Model 183 Stepping 1 (processor string reported by Python).
- Frozen controller source SHA-256: `4cdead8ab9956362ba9921c0818b7bcc9690487ab11ba001d087abebe43176b6`.
- Starting repository commit before this paper protocol: `e022cc8d2e962613381b576a946af75d3b9e2a9c`.
- Controller config SHA-256: `a28ef410ebed72331815b49f954f907809637266d24e47043810dd96779a9817`.
- Campaign config SHA-256: `9c0c7512c8e4002e554c03572af4766020869f85cee7c5604eaf4cd38ea87156`.
- Existing audited development package versions: numpy 2.5.3, scipy 1.18.1,
  pandas 3.0.6, matplotlib 3.11.2, PyYAML 6.0.3.
- External versions, licenses, install commands and blockers:
  `results/paper/external_versions.json`.
- Raw result hashes and actual frozen Git SHA: generated manifests under
  `results/paper/` after execution. Do not infer completed experiments from
  this protocol alone.

Core tests: `python -m pytest -q --basetemp=results/.pytest_paper_full2`.
The default `results/.pytest_work` is an inaccessible OneDrive reparse point
in this environment; no existing files there were modified.
