from dataclasses import replace

from evrp.coordinator import coordinate, forced_retained_choice
from evrp.model import Action
from evrp.mpc import MPCPlanningProblem
from tests.test_repair import customer, setup


def proposals():
    state, observation, config = setup((customer("A", 1), customer("B", 2), customer("C", 3)))
    candidates = {}
    for k, target in enumerate(("A", "B")):
        problem = MPCPlanningProblem(observation, replace(state, id=k), config)
        candidates[k] = (problem.proposal((Action("serve", target),)),
                         problem.proposal((Action("wait", wait_duration=1),)))
    return candidates


def test_forced_retained_choice_exactly_matches_all_three_coordination_objectives():
    candidates = proposals()
    kwargs = dict(available=frozenset({"A", "B", "C"}), background_intents=frozenset({"C"}))
    expected = coordinate(candidates, **kwargs)
    actual = forced_retained_choice(candidates, **kwargs)
    assert {k: p.actions for k, p in actual.items()} == {k: p.actions for k, p in expected.items()}
    assert forced_retained_choice({}, available=frozenset()) == {}


def test_forced_retained_choice_declines_real_combinatorial_or_ambiguous_choices():
    candidates = proposals()
    first, second = candidates[0][0], candidates[1][0]
    idle = candidates[0][1]
    available = frozenset({"A", "B"})
    assert forced_retained_choice({0: (first, second)}, available=available) is None
    assert forced_retained_choice({0: (first,), 1: (first,)}, available=available) is None
    assert forced_retained_choice({0: (idle, idle)}, available=available) is None
    assert forced_retained_choice({0: (first,)}, available=frozenset({"B"})) is None
    assert forced_retained_choice({0: (first,)}, available=available,
                                  background_intents=frozenset({"A"})) is None
