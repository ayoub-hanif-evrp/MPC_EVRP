"""Render paired development evidence without treating it as a final holdout."""

from collections import defaultdict
from hashlib import sha256
from statistics import mean

from evrp.storage import ROOT, identifier, load_json, save_json, writable_path
from scripts.fast_framework_worker import OUTPUT
from scripts.run_fast_framework import source_hash, verify


def number(value, decimals=2):
    return f"{value:.{decimals}f}" if value is not None else "NA"


def main():
    protocol = load_json(OUTPUT / "protocol.json")
    manifest = load_json(OUTPUT / "manifest.json")
    if protocol["source_sha256"] != source_hash() or manifest["protocol_identifier"] != identifier(protocol):
        raise ValueError("Report source/protocol drift")
    jobs = {j["id"]: j for block in protocol["blocks"] for j in block["jobs"]}
    raw = {}
    for record in manifest["records"]:
        path = ROOT / record["raw"]
        if sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Raw hash drift")
        value = load_json(path)
        verify(value, protocol, jobs[record["id"]])
        raw[record["id"]] = value
    pairs = []
    for i, case in enumerate(protocol["cases"]):
        for method in protocol["config"]["methods"]:
            key = lambda variant: f"pilot_{i}_{method}_{variant}"
            if key("original") not in raw or key("enhanced") not in raw:
                continue
            a, b = raw[key("original")], raw[key("enhanced")]
            ma, mb = a["result"]["metrics"], b["result"]["metrics"]
            pairs.append(dict(case_index=i, case=case["case"], method=method,
                original_served=ma["customers_served"], enhanced_served=mb["customers_served"],
                original_complete=ma["complete_service"], enhanced_complete=mb["complete_service"],
                original_cpu=a["worker_cpu_seconds"], enhanced_cpu=b["worker_cpu_seconds"],
                original_wall=a["worker_wall_seconds"], enhanced_wall=b["worker_wall_seconds"],
                original_mean_latency=ma["mean_optimization_latency"],
                enhanced_mean_latency=mb["mean_optimization_latency"],
                original_max_latency=ma["max_optimization_latency"],
                enhanced_max_latency=mb["max_optimization_latency"],
                original_replans=ma["optimization_triggers"],
                enhanced_replans=mb["optimization_triggers"],
                original_vehicles=ma["vehicles_activated"], enhanced_vehicles=mb["vehicles_activated"],
                original_distance=ma["total_distance"], enhanced_distance=mb["total_distance"],
                original_charge=ma["total_charging_visits"], enhanced_charge=mb["total_charging_visits"],
                original_p95_latency=ma["p95_optimization_latency"],
                enhanced_p95_latency=mb["p95_optimization_latency"]))
    save_json(OUTPUT / "paired_summary.json", dict(source_commit=protocol["source_commit"],
              protocol_identifier=identifier(protocol), status=manifest["status"], pairs=pairs))
    grouped = defaultdict(list)
    for row in pairs:
        grouped[row["method"]].append(row)
    lines = ["# Fast, Service-Aware MPC: bounded development study", "",
             f"Status: **{manifest['status']}**. Completed workers: {len(raw)} of "
             f"{sum(len(b['jobs']) for b in protocol['blocks'])}. "
             f"Source commit: `{protocol['source_commit']}`. This is development evidence, not an independent final holdout.",
             "", "The original policy remains the publication default unless separately confirmed. "
             "Enhanced runs use the optional fast screen/cache, adaptive stopping, and urgent service guard. "
             "MCTS additionally uses the separately identified skip-blocked rollout correction. "
             "Completion remains no-search. All retain the same five-second maximum decision cap, fleet, "
             "physics, visibility, objective, and archived scenario inputs.", "",
             "## Matched five-method comparison", "",
             "| Method | Paired cases | Original served | Enhanced served | Original complete | Enhanced complete | Original CPU s | Enhanced CPU s | Service losses |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for method in protocol["config"]["methods"]:
        rows = grouped[method]
        if not rows:
            lines.append(f"| {method} | 0 | NA | NA | NA | NA | NA | NA | NA |")
            continue
        lines.append("| " + " | ".join((method, str(len(rows)),
            str(sum(r["original_served"] for r in rows)), str(sum(r["enhanced_served"] for r in rows)),
            str(sum(r["original_complete"] for r in rows)), str(sum(r["enhanced_complete"] for r in rows)),
            number(sum(r["original_cpu"] for r in rows)), number(sum(r["enhanced_cpu"] for r in rows)),
            str(sum(r["enhanced_served"] < r["original_served"] for r in rows)))) + " |")
    lines += ["", "Counts are over exactly matched completed pairs; CPU is fresh-worker process time. "
              "The five-case totals are not customer percentages across a representative population.", "",
              "## Every paired outcome", "",
              "| Case | Method | Served O -> E | Complete O -> E | CPU s O -> E | Mean latency s O -> E | Max latency s O -> E | Replans O -> E |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in pairs:
        lines.append(f"| {r['case'][0]} DoD={r['case'][1]} seed={r['case'][2]} | {r['method']} | "
                     f"{r['original_served']} -> {r['enhanced_served']} | "
                     f"{int(r['original_complete'])} -> {int(r['enhanced_complete'])} | "
                     f"{number(r['original_cpu'])} -> {number(r['enhanced_cpu'])} | "
                     f"{number(r['original_mean_latency'])} -> {number(r['enhanced_mean_latency'])} | "
                     f"{number(r['original_max_latency'])} -> {number(r['enhanced_max_latency'])} | "
                     f"{r['original_replans']} -> {r['enhanced_replans']} |")
    losses = [r for r in pairs if r["enhanced_served"] < r["original_served"]]
    lines += ["", "## Regressions and interpretation", ""]
    lines.append(f"Observed paired service regressions: {len(losses)}. " +
                 ("; ".join(f"{r['case'][0]} {r['method']} {r['original_served']}->{r['enhanced_served']}" for r in losses)
                  if losses else "None in completed pairs."))
    for method in protocol["config"]["methods"]:
        rows = grouped[method]
        if not rows:
            continue
        lost = any(r["enhanced_served"] < r["original_served"] for r in rows)
        gain = sum(r["enhanced_served"] - r["original_served"] for r in rows)
        cpu_ratio = sum(r["enhanced_cpu"] for r in rows) / max(1e-9, sum(r["original_cpu"] for r in rows))
        judgment = ("reject shared combined enhancement on these development cases" if lost else
                    "development candidate only; requires independent confirmation" if gain > 0 or cpu_ratio <= .9 else
                    "retain original; insufficient service or speed benefit")
        lines.append(f"- {method}: service delta {gain:+d}, CPU ratio {cpu_ratio:.2f}; {judgment}.")
    micro = [raw.get(f"micro_{i}_MPC_COMPLETION_enhanced", {}).get("fixed_work") for i in range(3)]
    lines += ["", "## Correctness and engineering observations", "",
              f"Fixed-work identical checksums on {sum(x is not None for x in micro)}/3 seen roots; "
              "each accepted route independently replayed through the unchanged physical transition.",
              "The optional fast screen removes calculations of two stored profile arrays that no "
              "screening caller consumes. Existing forward/backward time-window screening, capacity and "
              "safe-return checks, bounded charging labels, and exact transition reuse were already present; "
              "they were not redundantly reimplemented.",
              "The MCTS skip-blocked rollout fixes a confirmed zero-option early exit in a synthetic root. "
              "It is method-specific and therefore cannot be attributed to the shared framework.",
              "Prior HGS/ACS 100-customer divergences began in same-root, deadline-sensitive searches: "
              "HGS at decision 5 (same selected first actions but different future suffixes), ACS at "
              "decision 19 (different plan and first action). Their exact cause is not established by "
              "fixed-work equality; whole-scenario paired outcomes above are decisive.", ""]
    if any(r["case_index"] == 2 for r in pairs):
        lines += ["## 100-customer case", ""]
        for r in pairs:
            if r["case_index"] == 2:
                lines.append(f"- {r['method']}: {r['original_served']} -> {r['enhanced_served']} served; "
                             f"{number(r['original_cpu'])} -> {number(r['enhanced_cpu'])} CPU s.")
        lines.append("")
    lines += ["## Limits and next study", "",
              f"Independent additional development parents completed: "
              f"{len({r['case'][0].rsplit('_', 1)[0] for r in pairs if r['case_index'] >= 3})}. "
              "Even five structurally distinct development parents provide too little information "
              "for a stable confidence interval; no inferential CI or final-claim promotion is made. "
              "A new untouched confirmation study would have to be separately preregistered.",
              "For 30 paired scenarios across five methods and two variants (300 full workers), "
              "the conservative cost is 300 times the observed pilot mean worker wall time, "
              "with a 2x planning allowance; this is an estimate, not an authorized run.",
              "Conditional distance and fleet/charging outcomes are in `paired_summary.json`; "
              "distance is not compared as efficiency when customer sets differ.",
              "The original publication package and Reliability V2 stop marker were not touched. "
              "Timings are sequential fresh-process measurements on a shared machine.", ""]
    if pairs:
        expected = 300 * mean(r["original_wall"] + r["enhanced_wall"] for r in pairs) / 2
        lines[-5] = ("For 30 paired scenarios across five methods and two variants (300 full workers), "
                     f"the observed-mean cost is approximately {expected/3600:.2f} worker hours; "
                     f"a conservative 2x allowance is {2*expected/3600:.2f} hours. "
                     "This is an estimate, not an authorized run.")
    path = writable_path(OUTPUT / "FINAL_REPORT.md")
    path.write_text("\n".join(lines), encoding="utf-8")
    summary = ["# Fast framework v1", "",
               "The initial micro worker failed before any scenario simulation because the frozen "
               "protocol omitted the archived corpus-selection fields. Its log and 2.1-second "
               "budget charge remain in this directory; no result was overwritten.", "",
               "The corrected, separately frozen revision and full evidence are in "
               "[revision_1/FINAL_REPORT.md](revision_1/FINAL_REPORT.md).", "",
               *lines[2:]]
    writable_path(OUTPUT.parent / "FINAL_REPORT.md").write_text("\n".join(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
