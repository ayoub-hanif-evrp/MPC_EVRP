from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from evrp.research_v3a.benchmark import Case, Charger, load
from evrp.research_v3a.policies import GreedyChargePolicy
from evrp.research_v3a.replay import verify
from evrp.research_v3a.simulator import (Action, CustomerView, FleetSimulator,
                                        Observation, StationView, VehicleView)


def toy(chargers: int = 1, *, closing: float = 30.0) -> Case:
    # Nodes: customer 0, customer 1, depot 2, station 3.
    distances = ((0., 2., 2., 1.), (2., 0., 2., 1.),
                 (2., 2., 0., 3.), (1., 1., 3., 0.))
    return Case("toy", 2, 1, 2., 10., 30., 1., 0.1,
                (1., 1.), (0., 0.), (0., 0.), (8., 8.),
                distances, distances,
                tuple(Charger(0, i, ((0., closing),), 1., 0.5)
                      for i in range(chargers)))


class ScriptedCharge:
    def decide(self, o, vid):
        v = o.vehicles[vid]
        if v.node == o.depot and o.now == 0:
            return Action("station", 0, 10.)
        if v.node == o.stations[0].node and v.status == "idle":
            for c in o.customers:
                if o.now + o.travel(v.node, c.id) <= c.end:
                    return Action("customer", c.id)
            return Action("depot", 0)
        if v.node != o.depot and v.status == "idle":
            return Action("depot", 0)
        return None


def test_one_vs_two_chargers_individual_vs_fleet_feasibility():
    results = []
    for capacity in (1, 2):
        case = toy(capacity)
        outcome = FleetSimulator(case, fleet_size=2, releases=(0., 0.)).run(
            ScriptedCharge(), name="scripted")
        assert outcome.failure is None
        assert verify(case, outcome, fleet_size=2, releases=(0., 0.))["physical_violations"] == 0
        results.append(outcome)
    assert results[0].served == 1
    assert results[1].served == 2
    starts = [e for e in results[0].events if e["kind"] == "charge_start"]
    assert [e["time"] for e in starts] == [3., 6.]
    assert results[0].charging_wait == 3.
    assert [e["time"] for e in results[1].events if e["kind"] == "charge_start"] == [3., 3.]


def test_charger_window_and_partial_charge():
    case = toy(closing=5.)
    outcome = FleetSimulator(case, fleet_size=2, releases=(0., 0.)).run(
        ScriptedCharge(), name="scripted")
    # A three-unit charge starting at time 3 cannot fit by closing at time 5.
    assert not any(e["kind"] == "charge_start" for e in outcome.events)
    assert outcome.served == 0
    assert outcome.failure is not None

    class Partial(ScriptedCharge):
        def decide(self, o, vid):
            action = super().decide(o, vid)
            if action and action.kind == "station":
                return Action("station", 0, 8.)
            return action

    open_case = toy()
    partial = FleetSimulator(open_case, fleet_size=2, releases=(0., 0.)).run(
        Partial(), name="partial")
    assert partial.failure is None
    assert partial.charging_wait == 1.
    assert [e["duration"] for e in partial.events if e["kind"] == "charge_start"] == [1., 1.]
    assert verify(open_case, partial, fleet_size=2, releases=(0., 0.))["physical_violations"] == 0


def test_queue_abandonment_and_immutable_travel_replay():
    class Abandon(ScriptedCharge):
        def decide(self, o, vid):
            if o.vehicles[vid].status == "queued":
                return Action("depot", 0)
            return super().decide(o, vid)

    case = toy()
    outcome = FleetSimulator(case, fleet_size=2, releases=(0., 0.)).run(
        Abandon(), name="abandon")
    assert outcome.failure is None
    assert sum(e["kind"] == "queue_abandon" for e in outcome.events) == 1
    assert verify(case, outcome, fleet_size=2, releases=(0., 0.))["physical_violations"] == 0
    altered = replace(outcome, events=[dict(e) for e in outcome.events])
    departure = next(e for e in altered.events if e["kind"] == "depart")
    extra = dict(departure)
    altered.events.insert(altered.events.index(departure) + 1, extra)
    with pytest.raises(ValueError, match="Interrupted"):
        verify(case, altered, fleet_size=2, releases=(0., 0.))


def test_impossible_late_release():
    case = toy()
    outcome = FleetSimulator(case, fleet_size=1, releases=(20., 20.)).run(
        GreedyChargePolicy(endogenous=True), name="late")
    assert outcome.announced == 2 and outcome.accepted == 0
    assert outcome.failure is None
    assert verify(case, outcome, fleet_size=1, releases=(20., 20.))["customers_verified"] == 0


def test_replayer_rejects_edited_energy_and_charger_conflict():
    case = toy(2)
    outcome = FleetSimulator(case, fleet_size=2, releases=(0., 0.)).run(
        ScriptedCharge(), name="scripted")
    altered = replace(outcome, events=[dict(e) for e in outcome.events])
    depart = next(e for e in altered.events if e["kind"] == "depart")
    depart["energy_after"] += 1
    with pytest.raises(ValueError, match="energy"):
        verify(case, altered, fleet_size=2, releases=(0., 0.))
    altered = replace(outcome, events=[dict(e) for e in outcome.events])
    starts = [e for e in altered.events if e["kind"] == "charge_start"]
    starts[1]["charger"] = starts[0]["charger"]
    with pytest.raises(ValueError, match="conflict"):
        verify(case, altered, fleet_size=2, releases=(0., 0.))


def test_hidden_future_does_not_change_current_action():
    base = toy()
    changed = replace(base, starts=(0., 20.), ends=(8., 25.),
                      distances=tuple(tuple(x + (100 if (i == 1 or j == 1) and i != j else 0)
                                            for j, x in enumerate(row)) for i, row in enumerate(base.distances)))
    policy = GreedyChargePolicy(endogenous=True)
    a = FleetSimulator(base, releases=(0., 20.)).observation()
    b = FleetSimulator(changed, releases=(0., 20.)).observation()
    assert policy.decide(a, 0) == policy.decide(b, 0)
    assert all(1 not in pair for pair in a.travel_times)
    assert all(1 not in pair for pair in b.travel_times)


def test_exact_observable_contention_changes_charge_dispatch():
    # Customer 0, depot 1, stations 2 and 3. EV 1 occupies station 2's only
    # charger until time 10. The other EV starts at the depot with energy 4.
    matrix = ((0., 4., 2., 1.), (8., 0., 1., 2.),
              (2., 1., 0., 2.), (1., 2., 2., 0.))
    pairs = {(i, j): matrix[i][j] for i in range(4) for j in range(4)}
    o = Observation(0., 1, 30., 10., 2., 1.,
                    (CustomerView(0, 1., 0., 0., 20.),),
                    (VehicleView(0, 1, 4., 2., "idle"),
                     VehicleView(1, 2, 8., 2., "charging")),
                    (StationView(0, 2, (10.,), (), (1.,), (((0., 30.),),)),
                     StationView(1, 3, (0.,), (), (1.,), (((0., 30.),),))),
                    pairs, pairs)
    independent = GreedyChargePolicy(endogenous=False).decide(o, 0)
    endogenous = GreedyChargePolicy(endogenous=True).decide(o, 0)
    assert independent == Action("station", 0, 7.)
    assert endogenous == Action("station", 1, 6.)
    # Explicit times: station 0 starts at 10, charges 4, reaches the customer
    # at 16; station 1 arrives at 2, charges 4, reaches it at 7.
    assert 10 + 4 + 2 == 16 and 2 + 4 + 1 == 7


def test_official_adapter_and_derived_fixture():
    path = Path("data/third_party_v3a/or-evrptw-cps-mrt-data/instances/c101_25_2.json")
    if not path.exists():
        pytest.skip("Ignored official Dataset A checkout is not installed")
    original, derived = load(path), load(path, one_charger=True)
    assert original.n_customers == derived.n_customers == 25
    assert original.n_stations == derived.n_stations == 6
    assert len(original.chargers) == 12 and len(derived.chargers) == 6
    assert original.times == derived.times and original.distances == derived.distances
    assert not original.derived and derived.derived
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["charger_costs"].pop()
    with pytest.raises(ValueError, match="Charger arrays"):
        from evrp.research_v3a.benchmark import from_dict
        from_dict(payload)
