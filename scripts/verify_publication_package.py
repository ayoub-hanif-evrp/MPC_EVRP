"""Verify generated paper hashes, figure resolution, links and frozen evidence."""

from hashlib import sha256
import re
import subprocess

from PIL import Image

from evrp.storage import ROOT, load_json
from scripts.render_publication_package import OUTPUT


FROZEN_PATHS = ("results/desaulniers/development_campaign",
                "results/desaulniers/final_holdout_audit_erratum",
                "results/desaulniers/robustness_v3", "evrp/instance.py", "evrp/model.py",
                "evrp/reference.py", "evrp/scenario.py", "evrp/observation.py")


def verify():
    inventory = load_json(OUTPUT / "artifact_inventory.json")
    expected = {row["path"] for row in inventory["artifacts"]}
    actual = {path.relative_to(OUTPUT).as_posix() for path in OUTPUT.rglob("*")
              if path.is_file() and path.name != "artifact_inventory.json"}
    if expected != actual or len(expected) != len(inventory["artifacts"]):
        raise ValueError("Paper inventory has missing, extra or duplicate artifacts")
    figures = tables = 0
    for row in inventory["artifacts"]:
        path = (OUTPUT / row["path"]).resolve()
        if not path.is_relative_to(OUTPUT.resolve()) or sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"Paper artifact identity mismatch: {path}")
        if path.suffix == ".png":
            with Image.open(path) as image:
                if (min(image.info.get("dpi", (0, 0))) < 299.5 or image.width != row["width"]
                        or image.height != row["height"]):
                    raise ValueError(f"Paper image resolution mismatch: {path}")
            figures += 1
        elif path.suffix == ".md":
            content = path.read_text(encoding="utf-8")
            tables += int(bool(re.search(r"^\|", content, re.M)))
            for link in re.findall(r"\]\(([^)]+)\)", content):
                if re.match(r"https?://|mailto:|#", link):
                    continue
                target = path.parent / link.split("#", 1)[0]
                if not target.is_file():
                    raise ValueError(f"Broken paper link in {path}: {link}")
        elif path.suffix != ".json":
            raise ValueError(f"Unexpected paper artifact type: {path}")
    changed = subprocess.run(["git", "diff", "--name-only", "bad3934", "--", *FROZEN_PATHS],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if changed:
        raise ValueError(f"Frozen evidence or physical engine was changed: {changed}")
    print(f"Verified {len(actual)} paper artifacts: {figures} PNG figures >=300 dpi, "
          f"{tables} Markdown files containing tables; links valid; historical evidence unchanged.")


if __name__ == "__main__":
    verify()
