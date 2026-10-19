"""Explicit scientific dependencies; bump when corresponding semantics change."""

OBJECTIVE_VERSION = "service-activation-distance-v2"
PLANNER_OBJECTIVE_VERSION = "risk-control-flex-service-v1"
SEARCH_POLICY_VERSION = "fleet-mcts-structural-rollout-v2"
REFERENCE_SOLVER_VERSION = "published-full-replay-or-pareto-repair-v3"
SCENARIO_GENERATOR_VERSION = "reference-preserving-exact-eligible-v3"
RESULT_SCHEMA_VERSION = 5


def fleet_objective(metrics: dict) -> tuple:
    return (metrics["customers_unserved"], metrics["vehicles_activated"], metrics["total_distance"])
