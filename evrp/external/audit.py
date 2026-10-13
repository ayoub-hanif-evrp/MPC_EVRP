"""Generate the static external data-equivalence report before solver execution."""

import argparse
import csv
import json
from pathlib import Path
import sys

from evrp.external.compatibility import pyevrp_matrix, routingblocks_matrix
from evrp.external.pyevrp_adapter import (audit_bundled_loader, build_pyevrp_model,
                                           verify_pyevrp_data)
from evrp.external.routingblocks_adapter import verify_routingblocks_instance
from evrp.instance import load_instance
from evrp.reference import ReferenceSchedule
from evrp.storage import BENCHMARK, ROOT, save_json, writable_path


STATIC = ("c101_21", "c201_21", "r101_21", "r201_21", "rc101_21", "rc201_21")


def reference_for(instance):
    matches = list((ROOT / "data/reference_schedules").glob(f"{instance.name}_*.json"))
    if len(matches) != 1:
        raise ValueError(f"Expected one frozen reference for {instance.name}; found {len(matches)}")
    return ReferenceSchedule.load(matches[0], instance)


def generate(examples_root: Path | None = None, pyevrp_source: Path | None = None,
             output: Path = Path("results/paper/external/equivalence_report.json")):
    if pyevrp_source is not None:
        sys.path.insert(0, str(pyevrp_source.resolve()))
    reports = []
    matrix = []
    for name in STATIC:
        path = BENCHMARK / f"{name}.txt"
        instance = load_instance(path)
        fleet_size = reference_for(instance).fleet_size
        report = {"instance": name, "instance_sha256": instance.sha256, "K_ref": fleet_size}
        if examples_root is not None:
            report["routingblocks"] = verify_routingblocks_instance(instance, path, examples_root, fleet_size)
        else:
            report["routingblocks"] = {"exact": False, "errors": ["official example source unavailable"]}
        try:
            model, customers, stations = build_pyevrp_model(instance, fleet_size)
            report["pyevrp_mapping"] = verify_pyevrp_data(instance, model.data(), customers, stations, fleet_size)
            report["pyevrp_loader"] = audit_bundled_loader(instance, path)
        except ImportError as error:
            report["pyevrp_mapping"] = {"exact_data_mapping": False, "errors": [str(error)]}
            report["pyevrp_loader"] = {"loader_equivalent": False, "error": str(error)}
        reports.append(report)
        for row in (*routingblocks_matrix(instance, fleet_size), *pyevrp_matrix(instance, fleet_size)):
            matrix.append({"instance": name, "solver": row.solver, "feature": row.feature,
                           "our_model": row.ours, "external_model": row.external,
                           "source_exact": row.exact,
                           "instance_equivalent": report["routingblocks"]["exact"] if row.solver == "RoutingBlocks"
                           else report["pyevrp_mapping"]["exact_data_mapping"],
                           "evidence": row.evidence})
    save_json(output, {"static_instances": reports})
    path = writable_path("results/paper/tables/table_compatibility.csv")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(matrix[0]))
        writer.writeheader()
        writer.writerows(matrix)
    return {"report": str(output), "table": str(path), "instances": len(reports)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routingblocks-examples", type=Path)
    parser.add_argument("--pyevrp-source", type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.routingblocks_examples, args.pyevrp_source), indent=2))


if __name__ == "__main__":
    main()
