"""Run the eight prespecified paired V3A development episodes once."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import gzip
import json
from pathlib import Path
from time import perf_counter

from evrp.research_v3a.benchmark import load
from evrp.research_v3a.policies import GreedyChargePolicy
from evrp.research_v3a.replay import verify
from evrp.research_v3a.simulator import FleetSimulator


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/third_party_v3a/or-evrptw-cps-mrt-data/instances"
RAW = ROOT / "results/research_v3a/pilot_v1/raw"
SUMMARY = ROOT / "docs/research_v3a/PILOT_RESULTS.json"
MAX_WALL = 4 * 3600.0


def sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def run() -> None:
    if SUMMARY.exists() or RAW.exists():
        raise FileExistsError("Pilot already exists; no silent retry or overwrite")
    manifest = json.loads((ROOT / "docs/research_v3a/DATASET_A_MANIFEST.json").read_text())
    lookup = {row["path"]: row["sha256"] for row in manifest["files"]}
    paths = [SOURCE / name for name in ("c101_25_2.json", "r101_25_2.json")]
    for path in paths:
        if sha(path) != lookup["instances/" + path.name]:
            raise ValueError(f"Source hash mismatch: {path}")
    modules = [ROOT / "evrp/research_v3a" / name for name in
               ("benchmark.py", "simulator.py", "policies.py", "replay.py")]
    source_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha(path) for path in modules}
    start = perf_counter()
    RAW.mkdir(parents=True, exist_ok=False)
    summary: dict = {"schema": "v3a-pilot-1", "dataset_commit": manifest["commit"],
                     "source_hashes": source_hashes,
                     "protocol": "docs/research_v3a/PILOT_PROTOCOL.md",
                     "case_order": [], "records": []}
    for path in paths:
        for one_charger in (False, True):
            for endogenous in (False, True):
                method = "endogenous" if endogenous else "independent"
                case = load(path, one_charger=one_charger)
                label = f"{case.name}_{method}"
                summary["case_order"].append(label)
                if perf_counter() - start >= MAX_WALL:
                    record = {"case": case.name, "policy": method, "failure": "four-hour cap",
                              "timed_out": True}
                    summary["records"].append(record)
                    continue
                releases = tuple(max(0., x - 120.) for x in case.starts)
                try:
                    outcome = FleetSimulator(case, fleet_size=4, releases=releases,
                                             decision_limit=5., episode_limit=min(600., MAX_WALL -
                                                                                  (perf_counter() - start))).run(
                        GreedyChargePolicy(endogenous=endogenous), name=method)
                    replay = verify(case, outcome, fleet_size=4, releases=releases)
                    payload = asdict(outcome)
                    raw_path = RAW / f"{label}.json.gz"
                    with gzip.open(raw_path, "wt", encoding="utf-8") as stream:
                        json.dump({"outcome": payload, "releases": releases,
                                   "replay": replay, "source_sha256": sha(path)}, stream)
                    latencies = sorted(outcome.decision_latencies)
                    record = {key: payload[key] for key in
                              ("case", "policy", "announced", "accepted", "served", "broken_accepted",
                               "rejected", "charging_wait", "resource_conflicts", "physical_violations",
                               "distance", "charging_cost", "wall_seconds", "cpu_seconds",
                               "timed_out", "failure")}
                    record.update({"source_sha256": sha(path), "replay": replay,
                                   "decision_count": len(latencies),
                                   "decision_median": latencies[len(latencies) // 2] if latencies else None,
                                   "decision_p95": latencies[min(len(latencies) - 1, int(len(latencies) * .95))]
                                   if latencies else None,
                                   "decision_max": latencies[-1] if latencies else None,
                                   "raw_path": str(raw_path.relative_to(ROOT)).replace("\\", "/"),
                                   "raw_sha256": sha(raw_path),
                                   "first_actions": [d for d in outcome.decisions if d["action"] is not None][:4]})
                except Exception as exc:
                    record = {"case": case.name, "policy": method,
                              "failure": f"{type(exc).__name__}: {exc}", "timed_out": False}
                summary["records"].append(record)
                summary["aggregate_wall_seconds"] = perf_counter() - start
                SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
                print(f"{label}: {record.get('served', '?')}/{record.get('announced', '?')} "
                      f"failure={record.get('failure')}", flush=True)


if __name__ == "__main__":
    run()
