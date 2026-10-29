"""Remove only untracked pytest trees and Python caches under results/."""

import argparse
import json
import os
from pathlib import Path
import re
import stat

from .inventory_results import ROOT, tracked_results


def _linked(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _legacy_pytest_name(name: str) -> bool:
    return bool(re.fullmatch(r"t(?:[0-9][A-Za-z0-9_]*|_paper_reporting(?:_escalated)?)?", name))


def _results_root(repo_root: Path) -> Path:
    root = Path(repo_root).absolute()
    results = root / "results"
    if _linked(root) or _linked(results) or not results.is_dir():
        raise ValueError("results/ must be an ordinary directory inside the repository")
    return results


def _candidate(repo_root: Path, value: str | Path) -> Path:
    root = Path(repo_root).absolute()
    results = _results_root(root)
    raw = Path(value)
    path = raw if raw.is_absolute() else root / raw
    if ".." in path.parts or not path.is_relative_to(results):
        raise ValueError(f"Cleanup path is outside results/: {value}")
    relative = path.relative_to(results)
    if not ((len(relative.parts) == 1 and relative.name.startswith(".pytest_")) or
            (len(relative.parts) == 1 and _legacy_pytest_name(relative.name)) or
            (len(relative.parts) == 2 and relative.parts[0] == "verification" and
             relative.name.startswith("pytest_")) or
            (len(relative.parts) >= 2 and relative.name == "__pycache__")):
        raise ValueError(f"Cleanup path is not an approved cache location: {value}")
    current = results
    for part in relative.parts:
        current = current / part
        if _linked(current):
            raise ValueError(f"Linked cleanup path is forbidden: {current}")
    if not path.is_dir():
        raise ValueError(f"Cleanup candidate is not a directory: {path}")
    return path


def _discover(results: Path) -> list[Path]:
    found = []

    def fail(error: OSError) -> None:
        raise error

    for current, directories, _ in os.walk(results, followlinks=False, onerror=fail):
        parent = Path(current)
        for name in list(directories):
            path = parent / name
            if ((parent == results and (name.startswith(".pytest_") or _legacy_pytest_name(name))) or
                    (parent == results / "verification" and name.startswith("pytest_")) or
                    name == "__pycache__"):
                found.append(path)
                directories.remove(name)
            elif _linked(path):
                directories.remove(name)
    return sorted(found)


def _scan(repo_root: Path, value: str | Path, tracked: set[str]) -> dict:
    root = Path(repo_root).absolute()
    path = _candidate(root, value)
    if (path.parent == root / "results" / "verification" or
            (path.parent == root / "results" and _legacy_pytest_name(path.name))):
        allowed = lambda name: (name.startswith("test_") or
                                re.fullmatch(r"record[0-9]+", name) is not None or name == ".gitignore")
        if any(not allowed(child.name) for child in path.iterdir()):
            raise ValueError(f"Verification tree contains non-pytest contents: {path}")
    files = []
    directories = []

    def fail(error: OSError) -> None:
        raise error

    for current, names, filenames in os.walk(path, followlinks=False, onerror=fail):
        parent = Path(current)
        directories.append(parent.relative_to(path).as_posix())
        for name in names:
            child = parent / name
            if _linked(child):
                raise ValueError(f"Linked directory inside cleanup candidate: {child}")
        for name in filenames:
            child = parent / name
            if _linked(child):
                raise ValueError(f"Linked file inside cleanup candidate: {child}")
            info = child.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"Non-regular file inside cleanup candidate: {child}")
            if child.relative_to(root).as_posix() in tracked:
                raise ValueError(f"Git-tracked file inside cleanup candidate: {child}")
            files.append((child.relative_to(path).as_posix(), info.st_size, info.st_mtime_ns))
    files.sort()
    directories.sort(key=lambda name: (len(Path(name).parts), name), reverse=True)
    return {"path": path.relative_to(root).as_posix(), "files": len(files),
            "bytes": sum(size for _, size, _ in files),
            "_files": files, "_directories": directories}


def plan_cleanup(repo_root: Path = ROOT, requested: list[str | Path] | None = None,
                 tracked: set[str] | None = None) -> dict:
    root = Path(repo_root).absolute()
    results = _results_root(root)
    if tracked is None:
        tracked = tracked_results(root)
        if tracked is None:
            raise ValueError("Cannot verify Git-tracked results; cleanup refused")
        tracked = {f"results/{name}" for name in tracked}
    if requested is None:
        paths = _discover(results)
    else:
        paths = [_candidate(root, value) for value in requested]
    paths = sorted(set(paths))
    if any(parent in paths for path in paths for parent in path.parents):
        raise ValueError("Overlapping cleanup candidates are not allowed")
    candidates, rejected = [], []
    for path in paths:
        try:
            candidates.append(_scan(root, path, tracked))
        except (OSError, ValueError) as error:
            rejected.append({"path": path.relative_to(root).as_posix(), "reason": str(error)})
    return {"candidates": candidates, "rejected": rejected,
            "total_files": sum(row["files"] for row in candidates),
            "total_bytes": sum(row["bytes"] for row in candidates)}


def apply_cleanup(plan: dict, repo_root: Path = ROOT, tracked: set[str] | None = None) -> dict:
    root = Path(repo_root).absolute()
    results = _results_root(root)
    if tracked is None:
        tracked = tracked_results(root)
        if tracked is None:
            raise ValueError("Cannot verify Git-tracked results; cleanup refused")
        tracked = {f"results/{name}" for name in tracked}
    removed, errors = [], []
    for original in plan["candidates"]:
        path = root / original["path"]
        actual_files = actual_bytes = 0
        try:
            current = _scan(root, path, tracked)
            if (current["_files"] != original["_files"] or
                    current["_directories"] != original["_directories"]):
                raise ValueError("Candidate changed after dry-run; rescan before removal")
            for name, size, _ in current["_files"]:
                child = path / name
                check = child
                while check != results:
                    if _linked(check):
                        raise ValueError(f"Linked path appeared during cleanup: {check}")
                    check = check.parent
                child.unlink()
                actual_files += 1
                actual_bytes += size
            for name in current["_directories"]:
                directory = path if name == "." else path / name
                if _linked(directory):
                    raise ValueError(f"Linked path appeared during cleanup: {directory}")
                try:
                    directory.rmdir()
                except PermissionError:
                    # OneDrive can mark disposable pytest directories read-only.
                    if (os.name != "nt" or any(directory.iterdir()) or
                            not directory.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY):
                        raise
                    directory.chmod(stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
                    directory.rmdir()
            removed.append({"path": original["path"], "files": actual_files, "bytes": actual_bytes})
        except (OSError, ValueError) as error:
            errors.append({"path": original["path"], "files_removed": actual_files,
                           "bytes_removed": actual_bytes, "reason": str(error)})
    return {"removed": removed, "errors": errors,
            "total_files_removed": sum(row["files"] for row in removed) +
                                   sum(row["files_removed"] for row in errors),
            "total_bytes_removed": sum(row["bytes"] for row in removed) +
                                   sum(row["bytes_removed"] for row in errors)}


def main(argv: list[str] | None = None, repo_root: Path = ROOT) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete verified candidates; default is dry-run")
    parser.add_argument("--path", action="append", help="Approved candidate path; repeatable")
    args = parser.parse_args(argv)
    try:
        plan = plan_cleanup(repo_root, requested=args.path)
        public = {key: value for key, value in plan.items() if key != "candidates"}
        public["candidates"] = [{key: value for key, value in row.items() if not key.startswith("_")}
                                for row in plan["candidates"]]
        public["mode"] = "apply" if args.apply else "dry_run"
        if args.apply:
            public["outcome"] = apply_cleanup(plan, repo_root)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(public, indent=2, sort_keys=True))
    if args.apply and public["outcome"]["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
