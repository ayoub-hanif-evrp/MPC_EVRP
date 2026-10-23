from evrp.reference import validate_reference
from scripts.extend_mp_reference_coverage import construct
from tests.test_simulator import synthetic


def test_separate_mp_reference_constructor_replays_full_service():
    instance = synthetic(release=5).instance
    reference = construct(instance)
    validate_reference(instance, reference)
    assert set(reference.predecessor_departures) == {c.id for c in instance.customers}
    assert reference.provenance == "separate_mp_first_feasible_insertion_v1"
    assert reference.fleet_size <= len(instance.customers)
    assert all(route.steps[-1].after.finished for route in reference.routes)
