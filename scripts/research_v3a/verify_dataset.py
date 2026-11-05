"""Verify pinned upstream Dataset A bytes and all official/derived imports."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess

from evrp.research_v3a.benchmark import load


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/third_party_v3a/or-evrptw-cps-mrt-data"
MANIFEST = ROOT / "docs/research_v3a/DATASET_A_MANIFEST.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    head = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    if head != manifest["commit"]:
        raise ValueError(f"Dataset A commit mismatch: {head}")
    files = sorted(SOURCE.glob("instances/*.json"))
    rows = manifest["files"]
    if len(files) != manifest["count"] or {"instances/" + f.name for f in files} != {r["path"] for r in rows}:
        raise ValueError("Dataset A inventory mismatch")
    for row in rows:
        path = SOURCE / row["path"]
        if path.stat().st_size != row["bytes"] or sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"Dataset A hash mismatch: {path}")
        original, derived = load(path), load(path, one_charger=True)
        if original.distances != derived.distances or original.times != derived.times:
            raise ValueError("Derived fixture altered travel matrices")
    print(f"Verified {len(rows)} pinned Dataset A files and {len(rows)} derived imports")


if __name__ == "__main__":
    main()
