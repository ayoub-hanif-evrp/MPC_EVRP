"""Published partial-route orders are kept separate from frozen references."""

from evrp.external.replay import replay_routes
from evrp.instance import load_instance
from evrp.storage import BENCHMARK, PUBLISHED_SOLUTIONS
from scripts.audit_desaulniers_partial_solutions import parse
from scripts.construct_partial_reference_witnesses import make_schedule


def test_sp_route_order_has_feasible_mp_charge_witness():
    name = "c201_21_100"
    instance = load_instance(BENCHMARK / f"{name}.txt")
    fleet, recharges, routes = parse(PUBLISHED_SOLUTIONS / "SP" / f"solution{name}")
    assert fleet == 4 and recharges == 3
    replay = replay_routes(instance, routes, fleet)
    assert replay.feasible and replay.complete and replay.served == 100


def test_timed_out_partial_order_materializes_full_reference_without_changing_policy():
    name = "c202_21_100"
    instance = load_instance(BENCHMARK / f"{name}.txt")
    fleet, _, routes = parse(PUBLISHED_SOLUTIONS / "SP" / f"solution{name}")
    schedule = make_schedule(instance, routes, fleet, "SP")
    assert schedule.fleet_size == fleet == 4
    assert len(schedule.predecessor_departures) == len(instance.customers) == 100
    assert schedule.provenance == "separate_SP_partial_LP_MP_witness"
