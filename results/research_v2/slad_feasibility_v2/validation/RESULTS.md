# SLAD service-loss transition diagnosis V2

Retrospective, loss-selected development transitions. V1 outputs are unchanged.
Only recorded observations enter candidate construction. Busy actions are
immutable; their recorded after-states are the origins for adjustable suffixes.
Earlier plans are observations, not recovery witnesses.

Decision: **INCONCLUSIVE**. Full hashes, actions, per-vehicle physical replay,
candidate failures, and safe-return evidence are in `report.json`.

| Case | Prior -> loss time | Prior owner | Candidates | Valid | Added-coverage witnesses | Equal swaps |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| C1 / C18 | 387.780 -> 388.353 | 3 | 3 | 1 | 0 | 1 |

## C1 / C18

Prior target owner: EV 3; later validated target owner: None. Lost from plan: C18. Newly planned: C28.
The later constructor still planned C18: True. The loss is a constructor-to-validated-plan selection change.
New busy actions replayed: 4. Later search status: WITNESS_FOUND; timed out: False.
- direct_insertion: BOUNDED_SEARCH_FAILURE (not a physical infeasibility proof).
- direct_insertion: BOUNDED_SEARCH_FAILURE (not a physical infeasibility proof).
- retained_prior_suffix: physical; added ['C18'], dropped ['C28'], service delta 0; busy suffixes changed [3]; ready firsts changed [].
| R1 / C65 | 38.382 -> 38.736 | 2 | 3 | 1 | 0 | 1 |

## R1 / C65

Prior target owner: EV 2; later validated target owner: None. Lost from plan: C65. Newly planned: C11.
The later constructor still planned C65: True. The loss is a constructor-to-validated-plan selection change.
New busy actions replayed: 0. Later search status: WITNESS_FOUND; timed out: False.
- retained_prior_suffix: physical; added ['C65'], dropped ['C11'], service delta 0; busy suffixes changed [2]; ready firsts changed [].
- v1_ready_exchange: BOUNDED_SEARCH_FAILURE (not a physical infeasibility proof).
- v1_ready_exchange: BOUNDED_SEARCH_FAILURE (not a physical infeasibility proof).

## Negative control

Root 219bffea81a97e08: C61 is already unreachable under the
optimistic direct-travel necessary condition. No rescue candidate was
generated. Passing an optimistic bound would not itself validate an EV route.

## Interpretation

A valid future-suffix change is not automatically a better dispatch policy.
Equal-service swaps are not additional coverage. No candidate proves that
the preceding decision caused a later service loss. This bounded result
does not establish a closed-loop service-rate improvement.
