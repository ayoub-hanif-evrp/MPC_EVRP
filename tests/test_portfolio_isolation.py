"""Campaign process isolation must make optimizer order irrelevant."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = """
import json, os, sys
from evrp.experiments import audit_result, simulation_config
from evrp.simulator import EventDrivenSimulator
from tests.test_simulator import synthetic
base = synthetic(release=5, fleet=2)
config = simulation_config(dict(algorithm=sys.argv[1], total_planning_time_limit=1.0,
                                fleet_mcts_iterations=4, fleet_mcts_depth=2,
                                fleet_mcts_branch_limit=4))
result = EventDrivenSimulator(base.instance, base.scenario, config).run()
audit_result(result, base.instance, base.scenario)
print(json.dumps(dict(pid=os.getpid(), served=result.metrics['customers_served'],
                      vehicles=result.metrics['vehicles_activated'],
                      distance=result.metrics['total_distance'],
                      actions=[(s.before.id, s.action.kind, s.action.destination)
                               for s in result.steps])))
"""


def test_fresh_process_results_are_order_invariant():
    def execute(order):
        return {method: json.loads(subprocess.check_output(
            [sys.executable, "-c", SCRIPT, method], cwd=ROOT, text=True))
                for method in order}

    forward = execute(("MPC_COMPLETION", "MPC_MCTS"))
    reverse = execute(("MPC_MCTS", "MPC_COMPLETION"))
    assert len({row["pid"] for row in (*forward.values(), *reverse.values())}) == 4
    for method in forward:
        assert {k: v for k, v in forward[method].items() if k != "pid"} == {
            k: v for k, v in reverse[method].items() if k != "pid"}
