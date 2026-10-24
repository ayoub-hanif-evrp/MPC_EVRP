# Pre-outcome structural eligibility amendment

No new closed-loop optimization was run before this amendment.
The first structural protocol attempted 12 unexposed parents at DoD .25/.75,
but only 28/96 cases were eligible and only six parents had any eligible case.
Its complete protocol is preserved as initial_structural_protocol.json; its
archived input files remain unchanged. It is not an execution preregistration
and has no associated online manifest or raw result.

Use a deterministic replacement rule before opening any online outcomes:
from the already audited 168-reference inventory, exclude historical online
parents and the six reserved parents, require all 25/50/100 variants to support
DoD .75, and take the first two lexicographic parents per family. This selects
c106/c107, c206/c207, r109/r110, r209/r210, rc106/rc107 and rc206/rc207, all
with suffix _21. No selection uses algorithm service, cost, runtime or success.

Keep the .25/.75 x seed0/1 grid, five engines, partial-size panel, mechanisms,
promotion thresholds, budget and physical/release generator unchanged.
This yields 12 independent development parents without changing existing
release schedules or historical fleets. Generalization is restricted to cases
eligible for this dynamicity grid, and this restriction must be reported.

The initial preflight captured starting HEAD while source was uncommitted.
Before the actual execution protocol, commit the scientific implementation,
then freeze with a clean-source guard. Preserve the initial artifact rather
than rewriting its source provenance. The new execution protocol records the
real implementation commit and exact source hashes before the first worker.
