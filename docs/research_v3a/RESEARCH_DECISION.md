# V3A research decision

**Decision:** retain V3A as an isolated comparative modeling framework; do not claim a new optimization method or start a final holdout.

The plant and independent replay cover shared finite chargers, deterministic FCFS order, charger windows, partial charge energy, noninterruptible travel/active charging, revisable waiting and future actions, load/time windows and depot return. Exactly checkable toy cases show that contention can make individually feasible routes fleet-infeasible and can change a rational first charge dispatch. The prespecified eight-episode Dataset A pilot did not use public chargers at all, so it cannot support a closed-loop advantage claim. Its zero decision differences and zero queue exposure are a clear failure of the experimental exposure gate, not a win for either model.

The highest-value next task is to define and validate a physically justified depot charging-time/capacity assumption (the official data specifies cost but not time), then preregister a separate charger-exposed development pilot. Only if it generates actual shared-charger contention, preserves replay correctness and exposes repeatable first-action differences should a specialized optimization method be considered. Historical ALNS and other original solvers remain unchanged.
