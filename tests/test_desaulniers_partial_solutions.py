"""Published partial-route orders are kept separate from frozen references."""

from evrp.external.replay import replay_routes
from evrp.instance import load_instance
from evrp.storage import BENCHMARK, PUBLISHED_SOLUTIONS
from scripts.audit_desaulniers_partial_solutions import parse


def test_sp_route_order_has_feasible_mp_charge_witness():
    name = "c201_21_100"
    instance = load_instance(BENCHMARK / f"{name}.txt")
    fleet, recharges, routes = parse(PUBLISHED_SOLUTIONS / "SP" / f"solution{name}")
    assert fleet == 4 and recharges == 3
    replay = replay_routes(instance, routes, fleet)
    assert replay.feasible and replay.complete and replay.served == 100
