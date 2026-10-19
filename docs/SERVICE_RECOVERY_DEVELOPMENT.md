# Service-Recovery Development Branch

Status: design only. No new optimizer or controller result is claimed here.
The completed final holdout remains the frozen primary study on `main`.

## Evidence motivating this branch

The read-only [service-gap postmortem](../results/final_study/postmortem/ONLINE_SERVICE_GAP.md)
verified all 54 full-service clairvoyant references and audited all 324 final
traces. MPC + ALNS missed 36 customers. Of those, 34 had at least one recorded
decision state at which a ready vehicle could serve the customer directly and
retain a safe return, and 18 appeared in a selected route at least once.
This is not proof that a different action would improve final service:
single-action feasibility ignores the opportunity cost to other customers.
The final scenarios are now seen and are not development or selection cases.

## Two candidate mechanisms

1. **Observable fleet-flexibility control:** test an event-triggered replanning
   rule based only on current vehicle states, visible requests, retained routes,
   and their computed time-window/battery slack. Charge extra computation to the
   same five-second decision budget. Do not access hidden releases or customer
   attributes.
2. **Targeted ALNS recovery:** when a visible unplanned customer has a feasible
   direct action or insertion candidate, test bounded cross-route ejection and
   repair under the same exact decoder. The four-customer destroy cap is a
   candidate for adaptive expansion, not an assumed cause of lost service.

Do not combine these mechanisms until each is evaluated separately. Keep the
plant physics, charging, exact route decoder, K_ref, observations, objective,
and five-second per-decision limit identical to the frozen baselines.

## Development evaluation

Use only the existing 66 development scenarios. Start with the 12 original
development scenarios (six old-development instances, DoD 0.5, seeds 0 and 1)
as an engineering pilot; then, if a variant is feasible and reproducible,
run the complete 66-scenario grid. Pair by exact scenario identifier and
rerun MPC + ALNS and MPC + Completion in the same execution conditions as the
candidate. Preserve all raw runs, failures, source/config hashes, and latency
measurements. Do not use the final 54 scenarios for candidate selection,
parameter tuning, or debugging outcomes.

Primary development outcomes are paired customers served and complete-service
rate. Secondary outcomes are conditional activated-EV and distance differences
(only among equal-service pairs), mean/p95/max decision latency, total worker
time, and independent audit violations. Compare every candidate with both
baselines and report all paired wins, ties, losses, and instance-clustered
uncertainty. Reject a variant that breaches the five-second budget, introduces
an audit violation, or lacks a meaningful repeatable service improvement.

This branch is not a new final protocol. If development warrants a candidate,
freeze its source and settings, select genuinely unused benchmark instances,
and preregister a separate evaluation before opening those instances. Rerun
the fixed baselines in that new evaluation. Report any result as a new MPC
control-policy version, never as a correction to the frozen final study.
