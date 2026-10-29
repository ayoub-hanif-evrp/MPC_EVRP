"""Read-only, deterministic inventory of research results."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path, PurePosixPath
import subprocess


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"

KEEP_ACTIVE = {
    "final_cpu_paper_v1", "robustness_v3", "reference_validation",
    "final_cpu_development_v1", "publication_development",
    "targeted_service_v1", "enhancement_development", "two_worker_probe_v1",
}
ARCHIVE = {
    "development_campaign", "development_pilot_final_source", "final_holdout",
    "final_holdout_audit_erratum", "paper_v2", "robustness_pilot_v2",
    "robustness_v2", "service_diagnosis_v2", "reliability_v2",
    "performance_engineering_v1", "fast_framework_v1",
    "publication_package_v1", "validation",
}
METADATA_FIELDS = (
    "study", "status", "source_commit", "source_sha256", "dataset_sha256",
    "config_sha256", "protocol_identifier", "planned_runs", "completed_runs",
    "seed", "seeds", "methods", "dynamicities",
)


def classify(relative: PurePosixPath, tracked: bool | None = None) -> tuple[str, str]:
    parts = relative.parts
    if (relative.name.endswith(".tmp") or "__pycache__" in parts or
            any(part.startswith(".pytest_") for part in parts)):
        return "REMOVE_CANDIDATE", "Temporary or test-generated file; check for unique failure evidence."
    if len(parts) == 1 and relative.name in {"README.md", "INDEX.md"}:
        return "KEEP_ACTIVE", "Results navigation and preservation guidance."
    if len(parts) >= 2 and parts[0] == "desaulniers":
        campaign = parts[1]
        if tracked is False and campaign in KEEP_ACTIVE | ARCHIVE:
            return "REVIEW", "Untracked local artifact; provenance and durable recovery are unverified."
        if campaign in KEEP_ACTIVE:
            return "KEEP_ACTIVE", "Current paper, audit, reference, or negative-development dependency."
        if campaign in ARCHIVE:
            return "ARCHIVE", "Historical evidence; movement requires verified durable copy and reference updates."
    return "REVIEW", "No verified disposition for this path."


def tracked_results(repo_root: Path) -> set[str] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "-z", "--", "results"],
            cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if result.returncode:
        return None
    return {path.removeprefix("results/") for path in
            result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
            if path.startswith("results/")}


def _files(root: Path) -> list[Path]:
    found = []
    def fail(error: OSError) -> None:
        raise error

    for current, directories, names in os.walk(root, followlinks=False, onerror=fail):
        parent = Path(current)
        linked = [name for name in directories if (parent / name).is_symlink()]
        directories[:] = sorted(name for name in directories if name not in linked)
        found.extend(parent / name for name in names + linked)
    return sorted(found, key=lambda path: path.relative_to(root).as_posix())


def _document(path: Path) -> dict:
    if path.stat().st_size > 2_000_000:
        return {"metadata_error": "Metadata file exceeds 2 MB inspection limit."}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as error:
        return {"metadata_error": type(error).__name__}
    if not isinstance(data, dict):
        return {"metadata_error": "Expected a JSON object."}
    return {field: data[field] for field in METADATA_FIELDS
            if field in data and isinstance(data[field], (str, int, float, list))}


def inventory_results(root: Path = RESULTS, tracked: set[str] | None = None) -> dict:
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"Results directory does not exist: {root}")
    files = _files(root)
    experiment_metadata = {}
    for path in files:
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if (path.name not in {"protocol.json", "manifest.json"} or path.is_symlink() or
                classify(relative)[0] == "REMOVE_CANDIDATE"):
            continue
        directory = path.parent.relative_to(root).as_posix()
        experiment_metadata.setdefault(directory, {})[path.name.removesuffix(".json")] = _document(path)
    entries = []
    totals = Counter()
    campaigns = {}
    for path in files:
        relative = PurePosixPath(path.relative_to(root).as_posix())
        git_tracked = None if tracked is None else relative.as_posix() in tracked
        disposition, explanation = classify(relative, git_tracked)
        if path.is_symlink():
            disposition, explanation = "REVIEW", "Symbolic link; target and provenance require inspection."
        campaign = relative.parts[1] if len(relative.parts) > 1 and relative.parts[0] == "desaulniers" else relative.parts[0]
        experiment = None
        for parent in (path.parent, *path.parent.parents):
            if parent == root.parent:
                break
            key = parent.relative_to(root).as_posix()
            if key in experiment_metadata:
                experiment = key
                break
        entry = {
            "path": relative.as_posix(), "campaign": campaign,
            "bytes": path.lstat().st_size,
            "file_type": "symlink" if path.is_symlink() else
                         "".join(path.suffixes).lstrip(".") or "no_extension",
            "git_tracked": git_tracked,
            "experiment": experiment,
            "disposition": disposition, "reason": explanation,
        }
        entries.append(entry)
        totals[disposition] += entry["bytes"]
        group = campaigns.setdefault(campaign, {"files": 0, "bytes": 0,
                                                 "tracked_files": 0, "dispositions": {}})
        group["files"] += 1
        group["bytes"] += entry["bytes"]
        group["tracked_files"] += int(git_tracked is True)
        group["dispositions"][disposition] = group["dispositions"].get(disposition, 0) + 1
    return {
        "root": root.as_posix(),
        "files": entries,
        "experiments": dict(sorted(experiment_metadata.items())),
        "campaigns": dict(sorted(campaigns.items())),
        "summary": {name: {"files": sum(row["disposition"] == name for row in entries),
                            "bytes": totals[name]}
                    for name in ("KEEP_ACTIVE", "ARCHIVE", "REMOVE_CANDIDATE", "REVIEW")},
        "policy": "Classification is advisory; no file is removed or moved.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Create a new JSON file; default: stdout only")
    parser.add_argument("--summary", action="store_true", help="Print only disposition and campaign totals")
    args = parser.parse_args()
    payload = inventory_results(RESULTS, tracked_results(ROOT))
    if args.summary:
        payload = {key: payload[key] for key in ("summary", "campaigns", "policy")}
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)


if __name__ == "__main__":
    main()
