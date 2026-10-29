"""Inventory the original Reliability V2 tree before archival pruning."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from evrp.storage import ROOT


PREFIX = Path("results/desaulniers/reliability_v2")
DEFAULT_OUTPUT = ROOT / "docs/archive_manifests/reliability_v2_2026-10-29.json"


def tracked_paths():
    raw = subprocess.run(
        ["git", "ls-files", "-z", "--", PREFIX.as_posix()],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout
    return sorted(Path(p.decode("utf-8")) for p in raw.split(b"\0") if p)


def digest(path):
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tracked = tracked_paths()
    all_files = sorted(p for p in (ROOT / PREFIX).rglob("*") if p.is_file())
    if any(p.is_symlink() for p in all_files):
        raise ValueError("Symlink found in archival source")
    tracked_set = {ROOT / p for p in tracked}
    missing = sorted(str(p) for p in tracked_set - set(all_files))
    if missing:
        raise ValueError(f"Missing tracked files: {missing}")
    rows = [dict(path=p.as_posix(), size=(ROOT / p).stat().st_size,
                 sha256=digest(ROOT / p)) for p in tracked]
    extra = [dict(path=p.relative_to(ROOT).as_posix(), size=p.stat().st_size,
                  sha256=digest(p)) for p in all_files if p not in tracked_set]
    protocol = json.loads((ROOT / PREFIX / "development/protocol.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / PREFIX / "development/manifest.json").read_text(encoding="utf-8"))
    retained = [
        "STOP_REQUESTED.json",
        "FINAL_REPORT.md",
        "REPRODUCE.md",
        "PREREGISTRATION.md",
        "progress.json",
        "run.log",
        "supervisor.log",
        "supervisor_error.log",
        "compute_review/RESULTS.md",
        "diagnosis/RESULTS.md",
        "diagnosis/profile.json",
        "preflight/AMENDMENT.md",
        "development/protocol.json",
        "development/manifest.json",
        "diagnosis/events.json",
        *[p.relative_to(PREFIX).as_posix() for p in tracked
          if p.is_relative_to(PREFIX / "development/raw")],
        *[p.relative_to(PREFIX).as_posix() for p in tracked
          if p.is_relative_to(PREFIX / "execution_attempts")],
    ]
    retained = sorted(set(retained))
    if not set(retained) <= {p.relative_to(PREFIX).as_posix() for p in tracked}:
        raise ValueError("Retained path is not tracked")
    return dict(
        original_commit=head,
        tracked_count=len(rows),
        tracked_bytes=sum(row["size"] for row in rows),
        tracked_files=rows,
        untracked_files=extra,
        development_protocol=dict(
            sha256=digest(ROOT / PREFIX / "development/protocol.json"),
            identifier=manifest["protocol_identifier"],
            source_commit=protocol["source_commit"],
            source_sha256=protocol["source_sha256"],
        ),
        development_manifest=dict(
            sha256=digest(ROOT / PREFIX / "development/manifest.json"),
            status=manifest["status"],
            completed_runs=manifest["completed_runs"],
            planned_runs=manifest["planned_runs"],
        ),
        retained_relative_paths=retained,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--verify-remaining", action="store_true")
    args = parser.parse_args()
    if args.verify_remaining:
        saved = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        kept = set(saved["retained_relative_paths"])
        for row in saved["tracked_files"]:
            path = ROOT / row["path"]
            relative = Path(row["path"]).relative_to(PREFIX).as_posix()
            if relative in kept:
                if not path.is_file() or path.stat().st_size != row["size"] or digest(path) != row["sha256"]:
                    raise ValueError(f"Retained file changed: {path}")
            elif path.exists():
                raise ValueError(f"Pruned file still present: {path}")
        print(f"Verified {len(kept)} retained files against original SHA-256 manifest")
        return
    current = inventory()
    if args.verify:
        saved = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        if current != saved:
            raise ValueError("Current Reliability V2 files differ from archived manifest")
    else:
        DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        if DEFAULT_OUTPUT.exists():
            raise FileExistsError(DEFAULT_OUTPUT)
        DEFAULT_OUTPUT.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    print(f"Reliability V2: {current['tracked_count']} tracked, "
          f"{current['tracked_bytes']} bytes, {len(current['untracked_files'])} untracked")


if __name__ == "__main__":
    main()
