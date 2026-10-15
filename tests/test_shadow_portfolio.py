"""Observable state snapshots must round-trip without hidden demand."""

import json
from time import perf_counter

import pytest

from evrp.optimizers import OptimizationContext
from evrp.storage import identifier
from scripts.shadow_portfolio import (_context, _payload, _select, capture, run_shadow,
                                      summarize_shadow)
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


def test_shadow_capture_and_execution_refuse_unfinished_development():
    with pytest.raises(ValueError, match="development study must complete"):
        capture()
    with pytest.raises(ValueError, match="complete and source-frozen"):
        run_shadow()


def test_shadow_sbs_vbs_gate_and_conditional_pairwise_metrics():
    grouped = {}
    snapshots = {}
    for index in range(8):
        winner = "MPC_MCTS" if index < 4 else "MPC_ALNS"
        state_hash = f"state-{index}"
        snapshots[state_hash] = {"features": {"pending": index + 1}}
        runs = {}
        for method in ("MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"):
            unserved = 0 if method == winner else 1
            evs = 1 if method == winner else 2
            distance = 10 if method == winner else 20
            if index == 0 and method == "MPC_HGS":
                unserved, evs, distance = 0, 2, 20
            runs[method] = dict(objective=[unserved, 0.1 if method == winner else 0.2],
                                components=dict(activated_vehicles=evs, distance=distance),
                                wall_seconds=1.0 + index)
        grouped[state_hash] = runs
    summary = summarize_shadow(grouped, snapshots)
    assert summary["sbs"] == "MPC_MCTS"
    assert summary["vbs_minus_sbs_served"] == 4
    assert summary["portfolio_gate_passed"]
    assert summary["unique_service_wins"]["MPC_MCTS"] == 3
    assert summary["unique_service_wins"]["MPC_ALNS"] == 4
    assert summary["pairwise"]["MPC_MCTS"]["MPC_HGS"]["equal_service_states"] == 5
    assert summary["pairwise"]["MPC_MCTS"]["MPC_HGS"]["fewer_evs_at_equal_service"] == 1
    assert summary["pairwise"]["MPC_MCTS"]["MPC_HGS"]["lower_distance_at_equal_service_and_evs"] == 0
    assert summary["runtimes"]["MPC_MCTS"]["p95_seconds"] == 8.0
    assert len(summary["strongest_states"]["MPC_MCTS"]) == 4
