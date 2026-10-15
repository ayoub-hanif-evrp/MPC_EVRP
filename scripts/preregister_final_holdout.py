"""Select untouched 100-customer holdout instances only after development gates."""

import argparse
from hashlib import sha256
from pathlib import Path
import re
import subprocess

from evrp.experiments import load_config
from evrp.storage import ROOT, load_json, save_json
from scripts.run_portfolio_campaign import CONFIG_PATH, OUTPUT as DEVELOPMENT, source_hash
from scripts.shadow_portfolio import OUTPUT as SHADOW


BENCHMARK = ROOT / "data" / "evrptw_instances"
OUTPUT = ROOT / "results" / "final_study" / "PRE_REGISTERED_PROTOCOL.md"
JSON_OUTPUT = OUTPUT.with_suffix(".json")
RUNNER = Path(__file__).with_name("run_final_holdout.py")
RULE = "MPC_EVRPTW_SHA256_UNUSED_21_V1"
NAME = re.compile(r"\b(?:rc|c|r)[12]\d{2}_21\b", re.IGNORECASE)
FAMILIES = ("C1", "C2", "R1", "R2", "RC1", "RC2")
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".csv", ".py", ".txt"}


def family(name):
    match = re.fullmatch(r"(rc|c|r)([12])\d{2}_21", name, re.IGNORECASE)
    if not match:
        raise ValueError(f"Not a Schneider 100-customer _21 instance: {name}")
    return (match.group(1) + match.group(2)).upper()


def used_instances():
    used = set()
    for top in ("configs", "docs", "scripts", "tests", "results"):
        for path in (ROOT / top).rglob("*"):
            if not path.is_file():
                continue
            parts = path.relative_to(ROOT).parts
            if ("upstream" in parts or "downloads" in parts or "venv" in parts or
                    "__pycache__" in parts or path.is_relative_to(OUTPUT.parent)):
                continue
            used.update(match.group(0).lower() for match in NAME.finditer(path.name))
            if path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size < 8_000_000:
                try:
                    used.update(match.group(0).lower() for match in NAME.finditer(
                        path.read_text(encoding="utf-8")))
                except (UnicodeError, PermissionError):
                    continue
    return used


def choose_unused(used):
    candidates = {}
    for path in BENCHMARK.glob("*_21.txt"):
        name = path.stem.lower()
        if name in used:
            continue
        group = family(name)
        digest = sha256(path.read_bytes()).hexdigest()
        rank = sha256(f"{RULE}|{group}|{name}|{digest}".encode("ascii")).hexdigest()
        candidates.setdefault(group, []).append((rank, name, digest))
    if any(not candidates.get(group) for group in FAMILIES):
        raise ValueError("No demonstrably unused _21 instance for every family")
    return {group: min(candidates[group]) for group in FAMILIES}, candidates


def preregister():
    study = load_config(CONFIG_PATH)
    development = load_json(DEVELOPMENT / "manifest.json")
    analysis = load_json(DEVELOPMENT / "analysis" / "paired_analysis.json")
    if (development["status"] != "development_complete" or
            len(development["records"]) != 330 or
            analysis["status"] != "complete_development" or
            analysis["scenarios"] != 66):
        raise ValueError("The full audited development comparison is not complete")
    if any(row["source_sha256"] != source_hash() for row in development["records"]):
        raise ValueError("Optimizer source changed since development")
    shadow = load_json(SHADOW / "sbs_vbs_gate.json")
    selection_path = SHADOW / "selection.json"
    selection = load_json(selection_path)
    shadow_manifest = load_json(SHADOW / "manifest.json")
    if (shadow["snapshots"] < 66 * 4 or
            shadow_manifest["status"] != "shadow_complete" or
            shadow_manifest["selection_sha256"] != sha256(selection_path.read_bytes()).hexdigest() or
            selection["status"] != "frozen_selection" or
            selection["source_sha256"] != source_hash()):
        raise ValueError("Common-state shadow experiment is not complete and source-frozen")
    if shadow["portfolio_gate_passed"]:
        raise ValueError("Portfolio gate passed: freeze and validate the selector first")
    methods = tuple(study["methods"])
    if len(methods) != 5:
        raise ValueError("Expected the frozen five-method study")
    used = used_instances()
    selected, candidates = choose_unused(used)
    controller = ROOT / study["base_controller"]
    runner_hash = sha256(RUNNER.read_bytes()).hexdigest()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     text=True).strip()
    protocol = dict(status="preregistered_final_holdout", selection_rule=RULE,
                    development_commit=commit, source_sha256=source_hash(),
                    controller_config=study["base_controller"],
                    controller_sha256=sha256(controller.read_bytes()).hexdigest(),
                    development_protocol_sha256=sha256(CONFIG_PATH.read_bytes()).hexdigest(),
                    holdout_runner_sha256=runner_hash,
                    shadow_selection_sha256=sha256(selection_path.read_bytes()).hexdigest(),
                    shadow_gate_sha256=sha256((SHADOW / "sbs_vbs_gate.json").read_bytes()).hexdigest(),
                    methods=list(methods), dynamicity=[0.25, 0.5, 0.75], seeds=[0, 1, 2],
                    selected={group: dict(instance=selected[group][1],
                                          benchmark_sha256=selected[group][2])
                              for group in FAMILIES},
                    statistical_protocol=dict(primary="paired customers served and complete-service rate",
                                              secondary="EVs at equal service; distance at equal service and EVs",
                                              bootstrap_draws=5000, bootstrap_seed=0,
                                              confidence_level=0.95))
    lines = ["# Pre-Registered Final Holdout", "",
             "This protocol must be committed before any final-holdout result is opened.",
             "No tuning after the first final result is opened.", "",
             f"Selection rule: `{RULE}`. For each family, take the candidate with the",
             "lexicographically smallest SHA-256 of",
             "`RULE|FAMILY|instance_stem|benchmark_file_sha256`.", "",
             f"Frozen development commit: `{commit}`  ",
             f"Optimizer source fingerprint: `{source_hash()}`  ",
             f"Controller config: `{study['base_controller']}`  ",
             f"Controller SHA-256: `{sha256(controller.read_bytes()).hexdigest()}`  ",
             f"Development protocol SHA-256: `{sha256(CONFIG_PATH.read_bytes()).hexdigest()}`",
             f"Holdout runner SHA-256: `{runner_hash}`  ",
             f"Shadow selection SHA-256: `{protocol['shadow_selection_sha256']}`  ",
             f"Shadow gate SHA-256: `{protocol['shadow_gate_sha256']}`",
             "", "Previously referenced/used _21 instances are excluded:",
             ", ".join(f"`{name}`" for name in sorted(used)), "",
             "| Family | Selected unused instance | Source SHA-256 | Eligible pool |",
             "| --- | --- | --- | ---: |"]
    for group in FAMILIES:
        _, name, digest = selected[group]
        lines.append(f"| {group} | `{name}` | `{digest}` | {len(candidates[group])} |")
    lines += ["", "Dynamicity targets: `{0.25, 0.50, 0.75}`. Scenario seeds: `{0, 1, 2}`.",
              "The grid has 54 scenarios per method and 270 isolated simulations.",
              "Methods: " + ", ".join(f"`{name}`" for name in methods) + ".", "",
              "Every simulation starts in a fresh interpreter, runs one method/scenario,",
              "passes independent physical and information-boundary audit, and records",
              "compressed raw evidence. Primary ranking is customers served, then",
              "complete-service rate, EV count only at equal service, and distance only",
              "at equal service and EV count. VBS is analysis-only and is not deployed.", ""]
    if OUTPUT.exists() or JSON_OUTPUT.exists():
        raise FileExistsError("Holdout protocol already exists; never overwrite it")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    save_json(JSON_OUTPUT, protocol)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    return selected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(preregister())
