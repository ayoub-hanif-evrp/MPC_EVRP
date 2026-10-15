"""Observable state snapshots must round-trip without hidden demand."""

import json
from time import perf_counter

from evrp.optimizers import OptimizationContext
from evrp.storage import identifier
from scripts.shadow_portfolio import _context, _payload, _select
from tests.test_repair import customer, setup


def test_snapshot_roundtrip_preserves_current_observation_and_root():
    state, observation, mpc = setup((customer("A", 1), customer("B", 2)))
    original = OptimizationContext(
        observation, {0: state}, {}, {}, frozenset(observation.customer_by_id),
        frozenset(), frozenset(), {0: ()}, 1, perf_counter() + 5, 19, mpc)
    payload = json.loads(json.dumps(_payload(original)))
    restored = _context(payload, 4.0)
    assert json.loads(json.dumps(_payload(restored))) == payload
    assert identifier(payload) == identifier(_payload(restored))
    assert restored.released_customers == frozenset({"A", "B"})
    assert restored.time_left() <= 4.0


def test_snapshot_selection_deduplicates_state_hashes():
    state, observation, mpc = setup((customer("A", 1),))
    context = OptimizationContext(
        observation, {0: state}, {}, {}, frozenset(observation.customer_by_id),
        frozenset(), frozenset(), {0: ()}, 1, perf_counter() + 5, 19, mpc)
    payload = _payload(context)
    row = dict(scenario_id="test", instance_sha256="test", epoch=0,
               state_hash=identifier(payload), available_seconds=4.0,
               features={}, payload=payload)
    assert len(_select([row, dict(row)])) == 1
