"""Focused checks for the read-only supplementary final-trace analysis."""

from dataclasses import asdict

import pytest

from evrp.instance import Location
from evrp.model import VehicleState
from scripts.diagnose_final_service_loss import (clustered_interval, markdown_table,
                                                 validate_inputs, vehicle_from_raw)


def test_markdown_table():
    assert markdown_table(["A", "B"], [(1, 2)]) == "| A | B |\n| --- | --- |\n| 1 | 2 |"


def test_vehicle_round_trip():
    location = Location("D0", "d", 0, 0, 0, 0, 100, 0)
    vehicle = VehicleState(0, location, 0, 100, 100, route_history=("D0",))
    raw = asdict(vehicle)
    raw["route_history"] = list(raw["route_history"])
    raw["served_customers"] = list(raw["served_customers"])
    assert vehicle_from_raw(raw) == vehicle


def test_clustered_interval_rejects_incomplete_pairing():
    with pytest.raises(ValueError, match="pairing"):
        clustered_interval([dict(instance="x", scenario_id="a", method="MPC_ALNS",
                                 customers_served=100)], "MPC_ALNS", "MPC_COMPLETION")


def test_frozen_study_is_complete_and_reference_feasible():
    manifest, instances, scenarios = validate_inputs()
    assert len(manifest["records"]) == 324
    assert len(instances) == 6
    assert len(scenarios) >= 54
