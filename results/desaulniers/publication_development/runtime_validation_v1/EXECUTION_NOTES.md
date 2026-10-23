# Shared-machine execution notes

The predeclared runtime validation uses one campaign worker at a time, not a
machine-exclusive benchmark. At the user's request, an unrelated CPU-heavy
Python evaluation was left running. No unrelated process was stopped.

The read-only historical evidence auditor was started while this campaign
had 26/30 completed records. Its independent trace replay also used CPU.
Runtime measurements therefore include uncontrolled background contention
and must remain descriptive. They do not establish general hardware speedup,
service superiority or noninferiority.

Original and guarded runs retain the same mathematical objective, plant,
scenario, fixed fleet and five-second end-to-end decision budget. Each raw
record and protocol is preserved unchanged. The exact forced-choice proof,
route-agreement microbenchmark and synthetic initialization regression tests
are separate evidence for the narrow implementation corrections.
