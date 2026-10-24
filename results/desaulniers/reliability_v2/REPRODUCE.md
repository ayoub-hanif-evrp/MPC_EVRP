# Execute and reproduce Reliability V2

## Running study

Execution source commit: ed9f7cd54cfa596c02eace54437820b34138e64c.
The later supervisor/input checkpoint does not change the scientific source.
The actual frozen protocol is development/protocol.json, not the superseded
no-outcome structural preflight. All 96 cases passed eligibility, covering
12 independent parents and 24 selected benchmark files.

The live progress file is progress.json. run.log records every saved worker.
The hidden supervisor and its runner are recorded in execution_attempts/.
Do not launch another parent while that recorded runner is still active.

```powershell
Get-Content results/desaulniers/reliability_v2/progress.json
Get-Content results/desaulniers/reliability_v2/run.log -Tail 15
```

Each invocation pauses after 12 hours at a scenario boundary; it does not kill
an active unfavorable worker. A child timeout or other failure stops the campaign
with evidence rather than silently replacing the outcome. A 40-minute lack of
new records produces a monitor warning, not an automatic rerun or deletion.

After the current invocation has exited, resume exact saved runs with:

```powershell
python -u -m scripts.launch_reliability_study
```

The supervisor holds a temporary system-awake request, without keeping the
display awake or modifying permanent power settings. It writes progress and
append-only execution logs. A stale execution.lock requires checking its
recorded process before recovery; do not start competing parents.

## Validation and reporting

```powershell
python -m pytest -q
python -m scripts.analyze_reliability_study --stage development
```

Analysis refuses an incomplete manifest, duplicate or unpaired runs, altered
raw bytes, mismatched effective parameters, changed scenario/fleet/reference,
failed physical/information audits or decisions above five seconds. Every saved
raw trajectory is independently replayed before final aggregation. Source and
input mismatches fail closed. No original campaign is rerun for this audit.

The main runner automatically executes this analysis on completion. It opens
an untouched-parent holdout only after the preregistered gate passes. It then
automatically independently audits that complete holdout, renders PNG figures
at nominal300dpi and Markdown tables, and updates FINAL_REPORT.md. The relevant
standalone command, only once the gated holdout has actually completed, is:

```powershell
python -m scripts.analyze_reliability_study --stage holdout
```

No result from this still-running study is a new final superiority claim.
Original baselines and all historical results remain available unchanged.
