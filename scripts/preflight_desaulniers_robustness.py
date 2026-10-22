"""Find unused, MP-replayed, DoD-eligible instances without optimizer outcomes."""

from collections import defaultdict

from evrp.instance import discover_instances, load_instance
from evrp.reference import ReferenceConfig, published_full_reference
from evrp.storage import ROOT, load_json, writable_path
from scripts.run_desaulniers_pilot import family_of


PAIR_SIZE = {"C1": 100, "C2": 50, "R1": 100, "R2": 50, "RC1": 25, "RC2": 25}
OUTPUT = ROOT / "results/desaulniers/robustness_v2/preflight_candidates.md"


def preflight():
    development = load_json(ROOT / "results/desaulniers/development_campaign/protocol.json")
    final = load_json(ROOT / "results/desaulniers/final_holdout_audit_erratum/protocol.json")
    used = {r["instance"] for r in development["selected"] + final["selected"]}
    rows = []
    for family, size in PAIR_SIZE.items():
        for path in discover_instances(size):
            if family_of(path.stem) != family or path.stem in used:
                continue
            instance = load_instance(path)
            try:
                reference = published_full_reference(instance, ReferenceConfig())
                if reference is None:
                    rows.append((family, size, path.stem, "none", "not tested", "no SF/MF route"))
                    continue
                bound_count = sum(min(c.ready, reference.predecessor_departures[c.id]) > 0
                                  for c in instance.customers)
                required = int(.75 * size + .5)
                rows.append((family, size, path.stem, bound_count, required,
                             "eligible" if bound_count >= required else "ineligible"))
            except Exception as error:
                rows.append((family, size, path.stem, "none", "not tested",
                             f"replay failed: {type(error).__name__}: {error}"))
            print(f"preflight {path.stem}: {rows[-1][-1]}", flush=True)
    lines = ["# Prospective robustness candidate eligibility", "",
             "Checked only unused instance identity, published SF/MF physical replay, and "
             "reference-derived eligibility for target DoD 0.75. No optimizer results "
             "were inspected. The original robustness-v2 protocol remains preserved "
             "because all of its selected instances were ineligible at DoD 0.75.", "",
             "| Family | Size | Instance | Eligible requests | Required at DoD 0.75 | Status |",
             "| --- | ---: | --- | ---: | ---: | --- |"]
    lines.extend(f"| {family} | {size} | {name} | {count} | {required} | {status} |"
                 for family, size, name, count, required, status in rows)
    selected = {}
    for family, size in PAIR_SIZE.items():
        eligible = [name for fam, n, name, _, _, status in rows
                    if fam == family and n == size and status == "eligible"]
        selected[family] = eligible[0] if eligible else None
    lines.extend(["", "Lexicographically first eligible unused candidate per family-size "
                  "slot, without optimizer outcomes:", "",
                  *[f"- {family} ({PAIR_SIZE[family]}): {selected[family] or 'none'}"
                    for family in PAIR_SIZE], ""])
    writable_path(OUTPUT).write_text("\n".join(lines), encoding="utf-8")
    return selected


if __name__ == "__main__":
    print(preflight())
