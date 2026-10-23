"""Compare original and LP-backed route insertion on seen development losses."""

import csv
from dataclasses import replace
from hashlib import sha256
from time import perf_counter

from evrp.audit import decode_result
from evrp.experiments import load_config, prepare
from evrp.model import Observation
from evrp.mpc import MPCConfig
from evrp.planning_budget import PlanningDeadlineExceeded, reset_deadline, set_deadline
from evrp.repair import build_route
from evrp.storage import ROOT, load_json, writable_path
from scripts.diagnose_mpc_enhancement import DEST, ready_states
from scripts import run_desaulniers_campaign as development


FIELDS = ("instance", "dod", "seed", "customer", "first_visible_decision",
          "ready_vehicles", "tested_sequences", "original_witness", "linear_only_witness",
          "status")


def _try_orders(options, state_by_id, observation, config, seconds):
    token = set_deadline(perf_counter() + seconds)
    tested = 0
    try:
        for vehicle_id, sequence in options:
            actions = build_route(state_by_id[vehicle_id], sequence, observation, config)
            tested += 1
            if actions is not None:
                return (vehicle_id, sequence), tested, False
    except PlanningDeadlineExceeded:
        return None, tested, True
    finally:
        reset_deadline(token)
    return None, tested, False


def probe():
    manifest = load_json(development.OUTPUT / "manifest.json")
    config = load_config(development.CONFIG)
    rows = []
    for record in manifest["records"]:
        if record["method"] != "MPC_ALNS":
            continue
        path = ROOT / record["raw"]
        if sha256(path.read_bytes()).hexdigest() != record["raw_sha256"]:
            raise ValueError(f"Corrupt frozen development trace: {path}")
        raw = load_json(path)
        result = decode_result(raw)
        if not result.unserved_customers:
            continue
        instance, _, scenario, _ = prepare(record["instance"],
                                           development.options(config, record["instance"],
                                                               record["dynamicity"], record["seed"],
                                                               record["method"]))
        if result.metadata["scenario_identifier"] != scenario.identifier:
            raise ValueError("Development scenario identity changed")
        mpc = raw["effective_config"]["mpc"]
        original = MPCConfig(**(mpc | {"charge_fractions": tuple(mpc["charge_fractions"])}))
        enhanced = replace(original, route_decoder_version="linear_charge_v1")
        customers = {customer.id: customer for customer in instance.customers}
        for customer_id in result.unserved_customers:
            visible = [decision for decision in result.decisions
                       if customer_id in decision["available"] and
                       decision["time"] <= customers[customer_id].due]
            first = visible[0] if visible else None
            ready = ready_states(instance, result, first) if first else {}
            base = dict(instance=record["instance"], dod=record["dynamicity"],
                        seed=record["seed"], customer=customer_id,
                        first_visible_decision=round(first["time"], 6) if first else "",
                        ready_vehicles=len(ready), tested_sequences=0,
                        original_witness="", linear_only_witness="")
            if not first or not ready:
                rows.append(base | {"status": "no_ready_vehicle_or_decision"})
                continue
            observation = Observation(first["time"], instance.infrastructure,
                                      tuple(c for c in instance.customers
                                            if c.id in first["available"]),
                                      tuple((c, int(k)) for c, k in
                                            first["committed_before"].items()))
            options = []
            already_selected = False
            long_route = False
            for vehicle_id in sorted(ready):
                sequence = tuple(action["destination"] for action in
                                 first["plans"][str(vehicle_id)]["actions"]
                                 if action["kind"] == "serve")
                if customer_id in sequence:
                    already_selected = True
                    continue
                if len(sequence) >= 8:
                    long_route = True
                    continue
                for position in range(len(sequence) + 1):
                    options.append((vehicle_id, sequence[:position] +
                                    (customer_id,) + sequence[position:]))
            if already_selected:
                rows.append(base | {"status": "already_selected_soft_plan"})
                continue
            if not options:
                rows.append(base | {"status": "route_too_long" if long_route else "no_candidates"})
                continue
            options.sort(key=lambda row: (len(row[1]), row[0], row[1]))
            original_found, tested_original, original_timeout = _try_orders(
                options, ready, observation, original, 4.0)
            if original_found:
                rows.append(base | {"tested_sequences": tested_original,
                                    "original_witness": f"{original_found[0]}:{'/'.join(original_found[1])}",
                                    "status": "original_insertion_witness"})
                continue
            if original_timeout:
                rows.append(base | {"tested_sequences": tested_original,
                                    "status": "original_probe_timeout"})
                continue
            linear_found, tested_linear, linear_timeout = _try_orders(
                options, ready, observation, enhanced, 4.0)
            status = ("linear_only_witness" if linear_found else
                      "linear_probe_timeout" if linear_timeout else
                      "no_witness_in_bounded_decoder")
            rows.append(base | {"tested_sequences": tested_original + tested_linear,
                                "linear_only_witness": (f"{linear_found[0]}:"
                                                        f"{'/'.join(linear_found[1])}"
                                                        if linear_found else ""),
                                "status": status})
        print(f"Probed {record['instance']} DoD={record['dynamicity']}", flush=True)
    rows.sort(key=lambda row: (row["instance"], row["dod"], row["customer"]))
    path = writable_path(DEST / "development_alns_insertion_probe.csv")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    from collections import Counter
    counts = Counter(row["status"] for row in rows)
    lines = ["# Charging-decoder insertion probe", "",
             "Development ALNS losses only. Each probe uses the first visible decision, "
             "measured ready states, observable customers, and the selected soft customer "
             "orders. Insertion is tested without changing the other route orders. Each "
             "decoder gets at most four seconds per lost customer; timeouts are inconclusive.", "",
             "| Result | Customers |", "| --- | ---: |"]
    lines.extend(f"| {status} | {count} |" for status, count in sorted(counts.items()))
    lines += ["", "A feasible insertion witness is not proof that the optimizer would "
             "choose or preserve that route. No witness under bounded search does not "
             "prove physical infeasibility. Full details are in the CSV.", ""]
    writable_path(DEST / "DECODER_PROBE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    probe()
