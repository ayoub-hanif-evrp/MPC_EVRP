from dataclasses import replace

from scripts.report_targeted_losses import arrival_bound
from tests.test_repair import customer,setup


def test_arrival_bound_does_not_claim_energy_or_insertion_feasibility():
    state,observation,_=setup((customer("A",10,due=20),),battery=1)
    target=observation.customers[0]
    bound=arrival_bound({0:state},target,observation.infrastructure.parameters)
    assert bound["time_eligible_vehicles"]==1
    assert bound["earliest_service_start_lower_bound"]==10
    after=replace(state,time=15)
    bound=arrival_bound({0:after},target,observation.infrastructure.parameters)
    assert bound["time_eligible_vehicles"]==0
    assert bound["earliest_service_start_lower_bound"]==25


def test_arrival_bound_excludes_finished_and_already_served_origins():
    state,observation,_=setup((customer("A",1),))
    target=observation.customers[0]
    bound=arrival_bound({0:replace(state,finished=True),
                         1:replace(state,served_customers=("A",))},target,
                        observation.infrastructure.parameters)
    assert bound["time_eligible_vehicles"]==0
    assert bound["earliest_service_start_lower_bound"] is None
