"""Inspect first-epoch insertion reachability without changing the optimizer."""

import argparse
from collections import Counter

from evrp.experiments import prepare, simulation_config
from evrp.fleet_mcts import _FleetProblem
from evrp.model import Action
from evrp.observation import get_agent_observation, initial_global_state
from evrp.repair import build_route
from evrp.storage import load_json


def inspect(path):
    record = load_json(path)
    instance, _, scenario, _ = prepare(record["identity"]["instance"],
                                       record["requested_config"])
    state = initial_global_state(instance, scenario)
    state.reveal()
    observation = get_agent_observation(state, instance)
    origins = state.vehicles
    config = simulation_config(record["requested_config"]).mpc
    decision = record["decisions"][0]
    routes = {}
    for key, proposal in decision["plans"].items():
        actions = tuple(Action(**action) for action in proposal["actions"])
        if any(action.kind == "serve" for action in actions):
            routes[int(key)] = actions
    problem = _FleetProblem(origins, observation, config, 3, 2)
    plan = problem.initial(routes)
    for customer in sorted(problem.pending - {c for seq in plan.sequences for c in seq}):
        options = problem.screened_options(plan.sequences, customer)
        exact = []
        for _, _, k, pos, _ in options:
            index = problem.ids.index(k)
            sequence = plan.sequences[index]
            proposed = sequence[:pos] + (customer,) + sequence[pos:]
            exact.append((k, pos, problem._decode(k, proposed) is not None))
        reasons = Counter()
        for index, k in enumerate(problem.ids):
            sequence = plan.sequences[index]
            for pos in range(len(sequence) + 1):
                _, _, reason = problem._screen_gap_detail(k, sequence, customer, pos)
                reasons[reason] += 1
        print(customer, "screened=", len(options), "exact=", exact,
              "failures=", dict(reasons))
    print("constructor", decision["constructor_service"],
          "final_root", decision["best_service_after_search"],
          "mcts", {key: decision["fleet_mcts"].get(key) for key in (
              "iterations", "ejection_chains_generated", "ejection_chains_feasible",
              "ejection_chains_selected")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record")
    inspect(parser.parse_args().record)
