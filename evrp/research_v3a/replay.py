"""Independent event-log verifier for V3A fleet trajectories.

This module reads the recorded events and recomputes physics from the source
case. It does not call the simulator's state-transition methods.
"""

from __future__ import annotations

from .benchmark import Case
from .simulator import Outcome


def verify(case: Case, outcome: Outcome, *, fleet_size: int,
           releases: tuple[float, ...]) -> dict:
    if len(releases) != case.n_customers:
        raise ValueError("Release schedule length mismatch")
    eps = 1e-6
    states = [{"node": case.depot, "energy": case.battery_capacity,
               "load": case.load_capacity, "status": "idle", "arrival": 0.0,
               "destination": None, "charge_target": None}
              for _ in range(fleet_size)]
    announced: set[int] = set()
    accepted: set[int] = set()
    served: set[int] = set()
    queue: dict[int, list[tuple[float, int]]] = {s: [] for s in range(case.n_stations)}
    active: dict[tuple[int, int], tuple[int, float]] = {}
    last_time = -1.0
    for event in outcome.events:
        t, kind = float(event["time"]), event["kind"]
        if t + eps < last_time or t > case.max_time + eps:
            raise ValueError("Event order or horizon violation")
        last_time = t
        if kind == "release":
            i = event["customer"]
            if i in announced or abs(t - releases[i]) > eps:
                raise ValueError("Release provenance violation")
            announced.add(i)
            if event["accepted"]:
                accepted.add(i)
            continue
        vid = event.get("vehicle")
        if vid is not None and not 0 <= vid < fleet_size:
            raise ValueError("Unknown vehicle")
        v = states[vid] if vid is not None else None
        if kind == "depart":
            assert v is not None
            src, dst = event["origin"], event["destination"]
            if v["status"] not in ("idle", "queued") or v["node"] != src:
                raise ValueError("Interrupted action or wrong origin")
            if v["status"] == "queued":
                raise ValueError("Queue departure missing abandonment event")
            required = case.distances[src][dst] * case.consumption_rate
            if (abs(v["energy"] - event["energy_before"]) > eps or
                    abs(v["energy"] - required - event["energy_after"]) > eps or
                    v["energy"] + eps < required):
                raise ValueError("Travel energy violation")
            if event["action"] == "customer":
                i = event["customer"]
                if dst != i or i not in accepted or i in served or v["load"] + eps < case.demands[i]:
                    raise ValueError("Invalid customer assignment")
                start = max(t + case.times[src][dst], case.starts[i])
                if (start > case.ends[i] + eps or
                        start + case.service_times[i] + case.times[i][case.depot] > case.max_time + eps or
                        v["energy"] + eps < required + case.distances[i][case.depot] * case.consumption_rate):
                    raise ValueError("Window, return or energy infeasible")
            elif event["action"] == "station":
                if dst != case.station_node(event["station"]):
                    raise ValueError("Station index mismatch")
            elif event["action"] != "depot" or dst != case.depot:
                raise ValueError("Invalid action destination")
            v["energy"] -= required
            v["status"] = "travel"
            v["destination"] = dst
            v["arrival"] = t + case.times[src][dst]
        elif kind == "arrival":
            assert v is not None
            if (v["status"] != "travel" or v["destination"] != event["node"] or
                    abs(v["arrival"] - t) > eps):
                raise ValueError("Travel time or arrival violation")
            v["node"] = event["node"]
            v["status"] = "arrived"
            v["arrival"] = t
        elif kind == "queue_enter":
            assert v is not None
            s = event["station"]
            if v["status"] != "arrived" or v["node"] != case.station_node(s):
                raise ValueError("Queue station violation")
            queue[s].append((t, vid))
            v["status"] = "queued"
        elif kind == "queue_abandon":
            assert v is not None
            s = event["station"]
            if v["status"] != "queued" or not any(i == vid for _, i in queue[s]):
                raise ValueError("Invalid queue abandonment")
            queue[s] = [(a, i) for a, i in queue[s] if i != vid]
            v["status"] = "idle"
        elif kind == "charge_start":
            assert v is not None
            s, idx = event["station"], event["charger"]
            key = (s, idx)
            ch = next((x for x in case.station_chargers(s) if x.index == idx), None)
            if ch is None or key in active or v["status"] != "queued":
                raise ValueError("Charger allocation conflict")
            if not queue[s] or min(queue[s]) != (event["queue_arrival"], vid):
                raise ValueError("FCFS queue violation")
            duration = (event["target"] - v["energy"]) / ch.rate
            if (abs(duration - event["duration"]) > eps or duration <= 0 or
                    event["target"] > case.battery_capacity + eps or
                    not any(lo <= t + eps and t + duration <= hi + eps for lo, hi in ch.windows)):
                raise ValueError("Charge duration or availability violation")
            queue[s].remove((event["queue_arrival"], vid))
            active[key] = (vid, t + duration)
            v["status"] = "charging"
            v["charge_target"] = event["target"]
        elif kind == "charge_done":
            assert v is not None
            key = (event["station"], event["charger"])
            if key not in active or active[key][0] != vid or abs(active[key][1] - t) > eps:
                raise ValueError("Charge completion conflict")
            if (v["status"] != "charging" or
                    abs(v["charge_target"] - v["energy"] - event["gained"]) > eps or
                    abs(v["charge_target"] - event["energy"]) > eps):
                raise ValueError("Charge energy violation")
            v["energy"] = event["energy"]
            v["status"] = "idle"
            del active[key]
        elif kind == "service_done":
            assert v is not None
            i = event["customer"]
            if v["status"] != "arrived" or v["node"] != i or i in served:
                raise ValueError("Service sequence violation")
            start = max(v["arrival"], case.starts[i])
            if (start > case.ends[i] + eps or
                    abs(t - start - case.service_times[i]) > eps or
                    abs(v["load"] - case.demands[i] - event["load"]) > eps):
                raise ValueError("Service window or load violation")
            v["load"] -= case.demands[i]
            v["status"] = "idle"
            served.add(i)
        elif kind == "depot_reload":
            assert v is not None
            if v["status"] != "arrived" or v["node"] != case.depot:
                raise ValueError("Depot return violation")
            v["energy"] = case.battery_capacity
            v["load"] = case.load_capacity
            v["status"] = "idle"
        else:
            raise ValueError(f"Unknown trajectory event {kind}")
    if (len(announced) != outcome.announced or len(accepted) != outcome.accepted or
            len(served) != outcome.served):
        raise ValueError("Metric/event mismatch")
    if outcome.failure is None and (active or any(v["node"] != case.depot or v["status"] != "idle"
                                               for v in states)):
        raise ValueError("Fleet did not return to depot")
    return {"events_verified": len(outcome.events), "customers_verified": len(served),
            "chargers_active_at_end": len(active), "physical_violations": 0}
