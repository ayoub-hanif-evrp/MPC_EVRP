"""Inventory the pre-V3A tree and verify a narrowly scoped archive cleanup.

This script never deletes files. It records exact tracked bytes and checks that
each proposed removal is recoverable from the named archival Git tag.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_TAG = "archive/pre-v3a-cleanup-2026-11-05"
ARCHIVED_DIRS = (
    "results/desaulniers/performance_engineering_v1/",
    "results/desaulniers/fast_framework_v1/",
)
ARCHIVED_FILES = frozenset({
    "configs/performance_engineering_v1.yaml",
    "configs/fast_framework_v1.yaml",
    "scripts/performance_engineering_worker.py",
    "scripts/run_performance_engineering.py",
    "scripts/report_performance_engineering.py",
    "scripts/fast_framework_worker.py",
    "scripts/run_fast_framework.py",
    "scripts/report_fast_framework.py",
    "scripts/run_fast_ablation.py",
})
MANIFEST = ROOT / "docs/maintenance/cleanup_manifest.json"


def git(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, input=data, check=True,
                          capture_output=True).stdout


def tracked_paths() -> list[str]:
    return sorted(path for path in
                  git("ls-files", "-z").decode("utf-8", "surrogateescape").split("\0") if path)


def classify(path: str) -> tuple[str, str]:
    if path in ARCHIVED_FILES or path.startswith(ARCHIVED_DIRS):
        return "ARCHIVE_REQUIRED", (
            "Unpromoted historical CPU/fast-framework engineering study; "
            "its exact source, configuration, raw records and negative outcomes "
            "must remain available in the verified archive."
        )
    if path.startswith("results/"):
        if path in {"results/README.md", "results/INDEX.md"}:
            return "ACTIVE_CORE", "Current results navigation."
        return "FROZEN_EVIDENCE", (
            "Retained at its original path: active paper, audit, reference, "
            "development or historical reproduction dependency."
        )
    if path.startswith("archive/"):
        return "FROZEN_EVIDENCE", "Retained historical source archive."
    if path.startswith("data/"):
        return "ACTIVE_CORE", "Authoritative benchmark input retained for reproduction."
    return "ACTIVE_CORE", "Current source, test, configuration or documentation dependency."


def build() -> dict:
    original = git("rev-parse", "HEAD").decode().strip()
    rows = []
    totals = Counter()
    for relative in tracked_paths():
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Unsupported tracked path type: {relative}")
        content = path.read_bytes()
        kind, reason = classify(relative)
        row = {
            "path": relative,
            "classification": kind,
            "bytes": len(content),
            "sha256": sha256(content).hexdigest(),
            "evidence": reason,
            "archive_location": (f"{ARCHIVE_TAG}:{relative}"
                                 if kind == "ARCHIVE_REQUIRED" else None),
            "expected_impact": ("Remove from active branch after remote archive/recovery verification"
                                if kind == "ARCHIVE_REQUIRED" else "Retain"),
        }
        rows.append(row)
        totals[kind] += 1
        totals[kind + "_bytes"] += row["bytes"]
    return {
        "schema": "v3a-cleanup-inventory-1",
        "pre_cleanup_commit": original,
        "archive_tag": ARCHIVE_TAG,
        "tracked_count": len(rows),
        "tracked_bytes": sum(row["bytes"] for row in rows),
        "totals": dict(sorted(totals.items())),
        "scope": "Every Git-tracked file in the pre-cleanup HEAD; ignored local files are reported separately.",
        "files": rows,
    }


def verify(manifest: dict, recovery_root: Path | None = None) -> dict:
    original = manifest["pre_cleanup_commit"]
    if git("rev-parse", ARCHIVE_TAG + "^{}").decode().strip() != original:
        raise ValueError("Archive tag does not resolve to the pre-cleanup commit")
    archived = [row for row in manifest["files"] if row["classification"] == "ARCHIVE_REQUIRED"]
    for row in archived:
        relative = row["path"]
        content = git("show", f"{ARCHIVE_TAG}:{relative}")
        if len(content) != row["bytes"] or sha256(content).hexdigest() != row["sha256"]:
            raise ValueError(f"Archive bytes differ from inventory: {relative}")
        current = ROOT / relative
        if current.exists() and sha256(current.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"Active bytes differ from inventory: {relative}")
        if recovery_root is not None:
            restored = recovery_root / relative
            if (not restored.is_file() or len(restored.read_bytes()) != row["bytes"] or
                    sha256(restored.read_bytes()).hexdigest() != row["sha256"]):
                raise ValueError(f"Detached recovery bytes differ: {relative}")
    result = {"verified_archived_files": len(archived),
              "verified_archived_bytes": sum(row["bytes"] for row in archived)}
    if recovery_root is not None:
        result["detached_recovery_verified_files"] = len(archived)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Create the pre-cleanup manifest")
    parser.add_argument("--verify", action="store_true", help="Verify archive and live bytes")
    parser.add_argument("--recovery-root", type=Path,
                        help="Also verify every proposed removal in a detached checkout")
    args = parser.parse_args()
    if args.write == args.verify:
        parser.error("Choose exactly one of --write or --verify")
    if args.write:
        manifest = build()
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with MANIFEST.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(json.dumps({key: manifest[key] for key in
                          ("pre_cleanup_commit", "tracked_count", "tracked_bytes", "totals")},
                         indent=2))
    else:
        print(json.dumps(verify(json.loads(MANIFEST.read_text(encoding="utf-8")),
                                args.recovery_root), indent=2))


if __name__ == "__main__":
    main()
