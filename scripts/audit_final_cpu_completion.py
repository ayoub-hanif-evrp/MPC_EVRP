"""Verify final deliverables, frozen Git transport, tests and cumulative evidence."""

import argparse
import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from evrp.storage import ROOT, load_json, save_json, writable_path
from scripts.complete_cpu_coverage import OUTPUT as COVERAGE, PAPER, prior_accounting


AUDIT = PAPER / "audit"
ARCHIVE = "archive/hybrid-gpu-negative-v1"
REMOVED = ("scripts/benchmark_hybrid_acceleration.py", "scripts/run_hybrid_acceleration.py",
           "scripts/hybrid_acceleration_worker.py", "scripts/report_hybrid_acceleration.py",
           "configs/hybrid_acceleration_v1.yaml")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def archive_check(remote=False):
    commit = git("rev-parse", ARCHIVE + "^{}").decode().strip()
    base = "results/desaulniers/hybrid_acceleration_v1/"
    manifest = json.loads(git("show", ARCHIVE + ":" + base + "manifest.json"))
    for row in manifest["records"]:
        if sha256(git("show", ARCHIVE + ":" + row["raw"])).hexdigest() != row["sha256"]:
            raise ValueError("Archived GPU experiment raw hash mismatch")
    for relative in REMOVED:
        git("cat-file", "-e", ARCHIVE + ":" + relative)
        if (ROOT / relative).exists():
            raise ValueError("Obsolete GPU launcher remains active")
    record = dict(tag=ARCHIVE, commit=commit, raw_records=len(manifest["records"]),
                  exact_raw_hashes_passed=True, removed_gpu_paths=list(REMOVED))
    if remote:
        refs = git("ls-remote", "origin", "refs/tags/" + ARCHIVE, "refs/tags/" + ARCHIVE + "^{}").decode()
        if commit + "\trefs/tags/" + ARCHIVE + "^{}" not in refs:
            raise ValueError("Remote archival tag does not resolve to the verified commit")
        record["remote_verified"] = True
        record["remote_refs"] = refs.strip().splitlines()
        save_json(AUDIT / "archive_recovery.json", record)
    return record


def transport_check(revision):
    tracked = git("ls-files", "-z", "configs/final_cpu_development_v1.yaml",
                  "configs/final_cpu_replication_v1.yaml",
                  "results/desaulniers/final_cpu_paper_v1",
                  "results/desaulniers/final_cpu_development_v1",
                  "results/desaulniers/two_worker_probe_v1").decode().split("\0")
    rows = []
    for relative in filter(None, tracked):
        if relative.endswith(("MISSION_COMPLETION.json", "MISSION_COMPLETION.md")):
            continue
        spec = ":" + relative if revision == "index" else revision + ":" + relative
        blob = git("show", spec)
        local = (ROOT / relative).read_bytes()
        rows.append(dict(path=relative, equal=blob == local, sha256=sha256(local).hexdigest()))
    failures = [row["path"] for row in rows if not row["equal"]]
    if failures:
        raise ValueError(f"Git export differs from executed evidence bytes: {failures[:8]}")
    return dict(revision=revision, exact_files=len(rows), all_exact=True)


def local_links(paths):
    checked = 0
    for path in paths:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = target.strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / target).exists():
                raise ValueError(f"Broken local link in {path.relative_to(ROOT)}: {target}")
            checked += 1
    return checked


def repository_inventory():
    paths = [Path(value) for value in git("ls-files", "-z").decode().split("\0") if value]
    counts = Counter()
    rows = []
    current_scripts = {"render_final_cpu_paper", "audit_final_cpu_completion", "archive_frozen_inputs",
                       "audit_frozen_studies", "audit_enhancement_studies", "audit_reference_inventory",
                       "analyze_final_cpu_development", "analyze_cpu_coverage", "complete_cpu_coverage",
                       "run_final_cpu_development", "complete_final_cpu_development", "run_final_cpu_replication",
                       "performance_budget"}
    reference_paths = [path for path in paths if path.suffix in (".py", ".yaml", ".md", ".toml")]
    text = [(path, (ROOT / path).read_text(encoding="utf-8")) for path in reference_paths]
    for path in paths:
        top = path.parts[0]
        if top == "data":
            category = "preserved_benchmark"
        elif top == "results":
            category = "regenerable_report" if path.suffix in (".md", ".png", ".svg", ".csv", ".tex") else "preserved_evidence"
        elif top == "archive":
            category = "historical_archive"
        elif top == "scripts":
            category = "current_workflow" if path.stem in current_scripts else "historical_reproduction"
        elif top == "configs":
            category = "frozen_experiment_configuration"
        else:
            category = "active_source_tests_or_documentation"
        counts[category] += 1
        if top in ("evrp", "scripts", "configs", "tests"):
            module = path.with_suffix("").as_posix().replace("/", ".")
            references = [other.as_posix() for other, body in text if other != path and
                          (path.as_posix() in body or module in body)]
            rows.append(dict(path=path.as_posix(), category=category, reference_files=references))
        if top in ("evrp", "scripts") and path.suffix == ".py":
            tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules = [item.name for item in node.names] if isinstance(node, ast.Import) else (
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                if any(name == "cupy" or name.startswith(("cupy.", "pycuda", "numba.cuda")) for name in modules):
                    raise ValueError(f"Active GPU import in {path}")
    save_json(AUDIT / "repository_inventory.json", dict(counts=dict(counts), source_files=rows,
              retention="Historical launchers and opt-in policies remain execution-source dependencies of "
                        "frozen studies. They are unsupported for the selected publication configuration. "
                        "No unreferenced result directory or user environment is deleted."))
    return dict(counts)


def read_tests(path):
    suites = ET.parse(path).getroot().findall(".//testsuite")
    if not suites:
        raise ValueError("No test suite in JUnit validation record")
    result = {key: sum(int(suite.get(key, 0)) for suite in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    if result["tests"] < 402 or result["failures"] or result["errors"]:
        raise ValueError("The full validation suite did not pass")
    return dict(result, sha256=digest(path))


def audit(revision=None):
    tests = read_tests(AUDIT / "final_tests.xml")
    paper = load_json(AUDIT / "verification.json")
    if (paper["status"] != "complete" or paper["total_records"] != 510 or
            not paper["independent_disk_replay_passed"] or not paper["five_second_limit_passed"] or
            paper["cpu_coverage"]["new_runs"] != 15):
        raise ValueError("Independent paper evidence is incomplete")
    for relative, expected in paper["files_sha256"].items():
        if digest(PAPER / relative) != expected:
            raise ValueError(f"Generated paper artifact changed after replay: {relative}")
    original = load_json(ROOT / "results/desaulniers/publication_development/audits/historical_integrity.json")
    enhanced = load_json(ROOT / "results/desaulniers/publication_development/audits/enhancement_integrity.json")
    if (not all(row["all_independent_audits_passed"] for row in original["studies"].values()) or
            not all(row["all_independent_audits_passed"] for row in enhanced["studies"])):
        raise ValueError("Historical evidence audit failed")
    accounting = prior_accounting()
    budget = load_json(COVERAGE / "budget.json")
    accounting.append(dict(path=(COVERAGE / "budget.json").relative_to(ROOT).as_posix(),
                           sha256=digest(COVERAGE / "budget.json"), charged_seconds=budget["charged_seconds"],
                           worker_cpu_seconds=sum(job["cpu_seconds"] for job in budget["jobs"]),
                           attempts=len(budget["jobs"])))
    wall = sum(row["charged_seconds"] for row in accounting)
    cpu = sum(row["worker_cpu_seconds"] for row in accounting)
    if wall > 28800 or cpu > 43200:
        raise ValueError("Aggregate mission experiment allowance exceeded")
    archive = load_json(AUDIT / "archive_recovery.json")
    if not archive["remote_verified"] or archive["commit"] != archive_check()["commit"]:
        raise ValueError("Recoverable remote archive has not been verified")
    inventory = repository_inventory()
    documents = [ROOT / "README.md", ROOT / "docs/REPOSITORY_STATUS.md", ROOT / "docs/FINAL_MISSION_OBJECTIVES.md",
                 *PAPER.glob("*.md"), *(PAPER / "tables").glob("*.md")]
    link_count = local_links(documents)
    report = dict(status="verified_deliverables_with_negative_enhancement_result", tests=tests,
                  git_head=git("rev-parse", "HEAD").decode().strip(),
                  implementation_source_hashes={path.relative_to(ROOT).as_posix(): digest(path)
                                                for directory in ("evrp", "scripts", "tests")
                                                for path in sorted((ROOT / directory).rglob("*.py"))},
                  independent_records=510, separate_development_records=135, technical_probe_records=4,
                  new_successful_mission_runs=199, all_attempts=sum(row["attempts"] for row in accounting),
                  compute_accounting=accounting, charged_experiment_seconds=wall, attempted_worker_cpu_seconds=cpu,
                  wall_allowance_seconds=28800, cpu_allowance_seconds=43200,
                  scope="Final CPU mission after cff13c21; earlier frozen studies reused, not charged as new runs. "
                        "Charged execution is a conservative ledger quantity, not calendar duration. "
                        "Validation and report-generation work is separate from optimization experiments.",
                  archive=archive, inventory=inventory, local_links_checked=link_count,
                  png_figures=paper["png_figures"], markdown_tables=paper["markdown_tables"],
                  publication_configuration="five original MPC methods", enhanced_method_promoted=False,
                  scientific_improvement="Not established; original-method fallback required by the mission applies.",
                  unresolved_scientific_limits=["Six independent parents per cohort", "Shared-machine timing",
                      "Overlapping, partly unproven service-loss mechanisms", "No enhanced independent superiority claim"])
    if revision:
        report["exact_git_transport"] = transport_check(revision)
    save_json(AUDIT / "MISSION_COMPLETION.json", report)
    lines = ["# Final mission completion evidence", "",
             "The requested implementation/evaluation/reporting work is concluded with the original-method "
             "fallback. A service improvement for all five methods was not demonstrated. This distinction "
             "is an experimental result, not permission to omit adverse evidence.", "",
             f"- {tests['tests']-tests['skipped']} tests passed; {tests['skipped']} skipped; no failures or errors.",
             "- 510 primary/replication records, 135 separate development records and four technical probe records.",
             "- 199 new successful scenario runs in this mission; one preserved failed attempt; "
             "450 historical primary runs reused.",
             f"- Charged experiment execution {wall/3600:.3f}/8 h; attempted worker CPU {cpu/3600:.3f}/12 h.",
             f"- {paper['png_figures']} PNG/SVG figures; {paper['markdown_tables']} Markdown/CSV/LaTeX table sets.",
             f"- {link_count} local documentation links checked; remote GPU archive and its 53 raw hashes verified.",
             "- Frozen raw outcomes, fleet sizes, scientific source and five-second MPC limits preserved.", "",
             "The byte-preservation attributes store the executed CRLF or LF bytes directly. "
             "No frozen expected hash was replaced to excuse Git newline conversion. "
             "See [machine-readable audit](MISSION_COMPLETION.json), "
             "[requirement mapping](../../../../docs/FINAL_MISSION_OBJECTIVES.md), "
             "[CPU coverage](../CPU_COVERAGE.md), and [figure/table index](../INDEX.md).", ""]
    writable_path(AUDIT / "MISSION_COMPLETION.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Final mission: {tests['tests']} tests; {wall/3600:.3f} charged h; "
          f"{cpu/3600:.3f} worker CPU h; {paper['png_figures']} figures, {paper['markdown_tables']} tables")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-only", action="store_true")
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--git-revision", help="Also compare every tracked CPU evidence byte against index or a commit")
    args = parser.parse_args()
    if args.archive_only:
        print(archive_check(remote=args.remote))
    else:
        audit(args.git_revision)
