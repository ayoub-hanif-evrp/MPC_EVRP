# Control-Horizon Campaign: Incomplete Technical Run

## Frozen provenance

- Git source commit: `51308b7e888baceda9b73946decd08c978c828b8`
- EVRP source SHA-256: `8068c8c5d5dc5ccdfe728857eba0892ddb236814994448deeffcc46de7d00e57`
- `configs/final_control_horizon.yaml` SHA-256: `6a728091f5f25429778371d04cd470642514c64d1046be5e9572ab87e029a57e`
- Full pre-freeze suite: 293 passed (`results/verification/pytest.xml`)
- Schneider small-case reference validations: 4/4 passed (`reference_validation/reference_validation.csv`)

## Execution

`python -m scripts.final_control_horizon_campaign static` started the first
static Fleet MPC-MCTS case, `c101_21`, at approximately 2026-10-12 19:16:40 UTC.
At 20:46:50 UTC it still had not returned a record or printed a completed-case
line. The Python process was CPU-active and had approximately 1.9 GB private
memory. It was interrupted through the execution session to avoid unbounded
resource consumption. The process exited with code 1, and there is no raw JSON
for this attempt. A separate, unrelated `evaluate.py` process was observed on
the machine; it was not interrupted or attributed to this experiment.

No successful static cases, dynamic pairs, or holdout conditions from this
corrected frozen source were completed. The 600/600 static prerequisite is
unverified. The development PASS gate cannot be evaluated and the holdout was
not inspected or run. The historical `6a1ab7e` campaign remains separate and
must not be presented as evidence for this corrected objective.

No objective, seed, fleet size, deadline, or algorithm parameter was changed
after the freeze. The result is **incomplete**, not a service-performance win
or loss. Any new campaign would need an explicit new protocol and source freeze;
the current attempt cannot support a final-paper performance claim.
