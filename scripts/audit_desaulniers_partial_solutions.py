"""Replay SP/MP published route orders separately from frozen MF/SF references."""

import csv
import re

from evrp.external.replay import replay_routes
from evrp.instance import discover_instances, load_instance
from evrp.storage import PUBLISHED_SOLUTIONS, ROOT, writable_path


OUTPUT = ROOT / "results/desaulniers/reference_validation"
FIELDS = ("instance", "variant", "published_vehicles", "published_recharges",
          "route_order_replay_feasible", "complete", "served", "vehicles",
          "distance", "reason")


def parse(path):
    content = path.read_text(encoding="utf-8")
    match_vehicles = re.search(r"^NoVehicles\s*=\s*(\d+);$", content, re.M)
    match_recharges = re.search(r"^NoRecharges\s*=\s*(\d+);$", content, re.M)
    blocks = re.findall(r"Route\s+(\d+)\s+Cost\s+\d+\s*\{([^}]*)\}", content, re.S)
    if (not match_vehicles or not match_recharges or
            len(blocks) != int(match_vehicles.group(1))):
        raise ValueError("Published route/recharge metadata is incomplete")
    routes = []
    recharges = 0
    for index, (number, body) in enumerate(blocks):
        visits = re.findall(r"_([A-Za-z0-9]+)([ond]);", body)
        if (int(number) != index or not visits or visits[0] != ("D0", "o") or
                visits[-1] != ("D0", "d") or
                any(suffix != "n" for _, suffix in visits[1:-1])):
            raise ValueError("Published route endpoints or visit suffixes are invalid")
        route = [node for node, _ in visits]
        recharges += sum(node.startswith("S") for node in route)
        routes.append(route)
    if recharges != int(match_recharges.group(1)):
        raise ValueError("Published station-visit count mismatch")
    return int(match_vehicles.group(1)), recharges, routes


def audit():
    rows = []
    for path in discover_instances():
        name = path.stem
        if any((PUBLISHED_SOLUTIONS / variant / f"solution{name}").exists()
               for variant in ("MF", "SF")):
            continue
        instance = load_instance(path)
        for variant in ("SP", "MP"):
            source = PUBLISHED_SOLUTIONS / variant / f"solution{name}"
            if not source.is_file():
                continue
            row = dict.fromkeys(FIELDS, "")
            row.update(instance=name, variant=variant)
            try:
                fleet, visits, routes = parse(source)
                row.update(published_vehicles=fleet, published_recharges=visits)
                result = replay_routes(instance, routes, fleet)
                row.update(route_order_replay_feasible=result.feasible,
                           complete=result.complete, served=result.served,
                           vehicles=result.vehicles, distance=result.distance,
                           reason=result.reason)
            except Exception as error:
                row["reason"] = f"{type(error).__name__}: {error}"
            rows.append(row)
            print(f"{name} {variant}: feasible={row['route_order_replay_feasible']}", flush=True)
    path = writable_path(OUTPUT / "partial_published_audit.csv")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    witnessed = sum(r["route_order_replay_feasible"] is True and r["complete"] is True
                    for r in rows)
    lines = ["# Published SP/MP route-order audit", "",
             "This is a separate read-only diagnostic for instances lacking SF/MF "
             "full-charge references. The published SP/MP files give node orders but "
             "not a charging-amount trace. A continuous-charge LP witness is sought, "
             "then every action is replayed through the common MP transition engine. "
             "A successful witness shows feasibility of that order under our model; "
             "it does not reproduce the paper's charging choices or replace the frozen "
             "`K_ref` construction used in final or robustness studies.", "",
             f"Published partial-route files inspected: {len(rows)}; complete MP "
             f"route-order witnesses: {witnessed}. All failures and details are in "
             "`partial_published_audit.csv`.", ""]
    writable_path(OUTPUT / "PARTIAL_SOLUTIONS.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return rows


if __name__ == "__main__":
    audit()
