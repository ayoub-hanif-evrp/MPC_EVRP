"""Fixed-fleet event-driven MPC with optional fleet-level neighborhood search."""

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from time import perf_counter
from collections import Counter, deque

import numpy as np

from .agent import EVAgent, agent_seed
from .baselines import greedy_plan, independent_selection
from .continuity import (assert_unique_routes, with_soft_incumbent, reserved_customers,
                         route_observation, service_prefix, service_tail)
from .coordinator import coordinate
from .instance import Instance
from .model import Action, EPS, Observation, Transition, transition
from .mpc import MPCConfig, MPCPlanningProblem, PlanningResult
from .observation import get_agent_observation, initial_global_state
from .planning_budget import PlanningDeadlineExceeded, remaining_time, reset_deadline, set_deadline
from .scenario import DynamicScenario
from .storage import identifier, save_json

ROLLING_LNS_ALGORITHMS = {"ROLLING_LNS", "ROLLING_ALNS"}
HYBRID_LNS_ALGORITHMS = {"MPC_MCTS_LNS", "MPC_MCTS_ALNS"}
FLEET_LNS_ALGORITHMS = ROLLING_LNS_ALGORITHMS | HYBRID_LNS_ALGORITHMS
OPTIMIZER_ALGORITHMS = {"MPC_COMPLETION", "MPC_MCTS_V1", "MPC_ALNS", "MPC_HGS"}
COMMON_CONSTRUCTOR_ALGORITHMS = {"FLEET_MPC_MCTS", "FLEET_MPC_COMPLETION_ONLY", "ROLLING_LNS"} | OPTIMIZER_ALGORITHMS
ALGORITHMS = {"GREEDY", "RH_REGRET", "MPC_MCTS_H1", "INDEPENDENT_MPC_MCTS",
              "COORDINATED_MPC_MCTS"} | COMMON_CONSTRUCTOR_ALGORITHMS | FLEET_LNS_ALGORITHMS


@dataclass(frozen=True)
class SimulationConfig:
    algorithm: str = "COORDINATED_MPC_MCTS"
    experiment_seed: int = 0
    parallel_agents: bool = False
    workers: int = 2
    max_events: int = 100000
    mpc: MPCConfig = field(default_factory=MPCConfig)
    trace_level: str = "full"
    symmetry_reuse: bool = False
    fleet_mode: str = "fixed_reference"
    diagnostics: bool = False
    route_continuity: bool = True
    regret_repair: bool = True
    lns_iterations: int = 100
    lns_time_limit: float = 3.0
    lns_destroy_fraction: float = 0.1
    total_planning_time_limit: float | None = None
    fleet_mcts_iterations: int = 256
    fleet_mcts_depth: int = 4
    fleet_mcts_branch_limit: int = 12
    candidate_position_limit: int = 3
    rollout_regret_k: int = 2
    engineering_watchdog_seconds: float | None = None

    def __post_init__(self):
        if self.algorithm not in ALGORITHMS or self.workers < 1 or self.max_events < 1:
            raise ValueError("Invalid simulation configuration")
        if self.trace_level not in {"none", "summary", "full"}:
            raise ValueError("Unknown trace level")
        if self.fleet_mode != "fixed_reference":
            raise ValueError("Only the fixed K_ref fleet is supported")
        if self.route_continuity and self.trace_level == "none":
            raise ValueError("Route continuity requires at least a summary trace")
        if self.algorithm == "RH_REGRET" and not (self.route_continuity and self.regret_repair):
            raise ValueError("RH_REGRET requires persistent routes and regret repair")
        if self.algorithm in FLEET_LNS_ALGORITHMS and not (self.route_continuity and self.regret_repair):
            raise ValueError("Fleet LNS requires persistent routes and regret repair")
        if self.lns_iterations < 1 or self.lns_time_limit <= 0 or not 0 < self.lns_destroy_fraction <= 1:
            raise ValueError("Invalid fleet LNS budget")
        if self.total_planning_time_limit is not None and self.total_planning_time_limit <= 0:
            raise ValueError("Invalid total planning deadline")
        if self.engineering_watchdog_seconds is not None and self.engineering_watchdog_seconds <= 0:
            raise ValueError("Invalid engineering watchdog")
        if (min(self.fleet_mcts_iterations, self.fleet_mcts_depth, self.fleet_mcts_branch_limit,
                self.candidate_position_limit) < 1 or self.rollout_regret_k not in {2, 3}):
            raise ValueError("Invalid fleet MCTS configuration")
        if self.algorithm in COMMON_CONSTRUCTOR_ALGORITHMS and not (self.route_continuity and self.regret_repair):
            raise ValueError("Common fleet constructor requires persistent routes and regret repair")


@dataclass(frozen=True)
class SimulationEvent:
    time: float
    kind: str
    vehicle_id: int | None = None
    customer_id: str | None = None
    action: Action | None = None


@dataclass
class ExperimentResult:
    metadata: dict
    effective_config: dict
    metrics: dict
    events: list[SimulationEvent]
    steps: list[Transition]
    decisions: list[dict]
    searches: list[dict]
    unserved_customers: list[str]
    diagnostics: dict = field(default_factory=dict)

    def save(self, path):
        save_json(path, self)

    def logical_dict(self):
        result = asdict(self)
        result["searches"] = [{k: v for k, v in s.items() if k not in
                              {"elapsed", "deadline_exceeded", "deadline_overrun_seconds"}} for s in result["searches"]]
        result["metrics"] = {k: v for k, v in result["metrics"].items()
                             if "planning_time" not in k and "overrun" not in k
                             and k not in {"complete_instance_wall_clock_seconds",
                                           "mean_optimization_latency", "p95_optimization_latency",
                                           "max_optimization_latency"}
                             and k not in {"repair_seconds", "fleet_mcts_service_seconds",
                                           "fleet_mcts_full_seconds", "final_validation_seconds_total",
                                           "final_validation_seconds_p95"}}
        for decision in result["decisions"]:
            decision.pop("final_validation_seconds", None)
            decision.pop("constructor_seconds", None)
            decision.pop("mcts_seconds", None)
            if decision.get("fleet_mcts"):
                for field in ("elapsed", "service_seconds", "full_seconds"):
                    decision["fleet_mcts"].pop(field, None)
        result["effective_config"].pop("parallel_agents", None)
        result["effective_config"].pop("workers", None)
        return result


def _plan_job(agent, state, observation, seed, algorithm):
    if algorithm == "GREEDY":
        return greedy_plan(state, observation, agent.controller.config)
    return agent.plan(state, observation, seed)


def unused_symmetry_key(state, observation, config):
    if state.departed or state.finished or state.location.kind != "d" or state.current_committed_action is not None:
        return None
    return replace(state, id=0), observation, config


def rebind_plan(result, vehicle_id):
    def rebind(p):
        end = replace(p.predicted_end_state, id=vehicle_id) if p.predicted_end_state else None
        return replace(p, vehicle_id=vehicle_id, predicted_end_state=end)
    return PlanningResult(tuple(rebind(p) for p in result.proposals), rebind(result.fallback),
                          replace(result.statistics, iterations=0, nodes_expanded=0, elapsed=0),
                          tuple(rebind(p) for p in result.evaluated_proposals))


def idle_proposal(vehicle, observation, config):
    # With a fixed fleet, no known work is not evidence that a route should end.
    # Sleep until the latest safe escape, interruptibly on observable events.
    problem = MPCPlanningProblem(observation, vehicle, replace(config, max_idle_wait=0))
    return problem.proposal((problem.fallback(problem.initial),))


def optimization_root_hash(observation, origins, committed, tails):
    return identifier(dict(time=observation.time,
                           released=sorted(observation.customer_by_id),
                           origins={str(k): asdict(v) for k, v in sorted(origins.items())},
                           committed=sorted(committed.items()),
                           sequences={str(k): [a.destination for a in actions if a.kind == "serve"]
                                      for k, actions in sorted(tails.items())}))


class EventDrivenSimulator:
    def __init__(self, instance: Instance, scenario: DynamicScenario,
                 config: SimulationConfig = SimulationConfig()):
        self.instance, self.scenario, self.config = instance, scenario, config
        if config.algorithm == "MPC_MCTS_H1":
            self.config = replace(config, mpc=replace(config.mpc, prediction_horizon=1))
        self.state = initial_global_state(instance, scenario)
        self.agents = {k: EVAgent(k, self.config.mpc) for k in self.state.vehicles}

    def run(self):
        from .repair import compact_unused_routes, regret_repair, route_proposal
        from .fleet_lns import fleet_score, improve_fleet
        from .fleet_mcts import construct_fleet_root, solve_fleet_mcts
        from .optimizers import OptimizationContext, create_optimizer
        from .diagnostics import ServiceDiagnostics
        state, instance, config = self.state, self.instance, self.config
        events, steps, decisions, searches, timings = [], [], [], [], []
        tails, coverages, local_times = {}, [], []
        epochs = replans = conflicts = resolved = waits = simulations = expanded = reused = 0
        new_activations = inserted_requests = compacted_vehicles = 0
        repair_seconds = lns_seconds = 0.
        constructor_seconds_total = 0.0
        constructor_service_gain_total = 0
        lns_iterations = lns_improvements = 0
        fleet_mcts_iterations = fleet_mcts_expanded = fleet_mcts_improvements = deadline_events = 0
        fleet_service_seconds = fleet_full_seconds = 0.0
        final_validation_times = []
        deadline_fallbacks = 0
        run_started = perf_counter()
        simulation_events = optimization_triggers = mcts_calls = 0
        optimization_latencies = []
        trigger_counts = Counter()
        recent_triggers = deque(maxlen=20)
        seen_states = set()
        previous_root_hash = None
        previous_root_routes = None
        event_triggered = config.algorithm in COMMON_CONSTRUCTOR_ALGORITHMS
        diagnostic = ServiceDiagnostics(instance, self.scenario) if config.diagnostics else None
        pool = ProcessPoolExecutor(max_workers=config.workers) if config.parallel_agents else None
        try:
            for loop_count in range(config.max_events):
                if (config.engineering_watchdog_seconds is not None and
                        perf_counter() - run_started > config.engineering_watchdog_seconds):
                    raise RuntimeError(
                        f"Engineering watchdog: time={state.time} loops={loop_count} "
                        f"epochs={epochs} triggers={optimization_triggers} "
                        f"served={len(state.served_customers)} committed={len(state.committed_customers)} "
                        f"busy={len(state.busy)} idle={len(state.vehicles)-len(state.busy)} "
                        f"mcts_calls={mcts_calls} last_triggers={list(recent_triggers)}")
                global_hash = identifier(dict(time=state.time, vehicles={str(k): asdict(v)
                                                for k, v in sorted(state.vehicles.items())},
                                              hidden=sorted(state.hidden_customers),
                                              available=sorted(state.available_customers),
                                              committed=sorted(state.committed_customers.items()),
                                              served=sorted(state.served_customers),
                                              busy={str(k): asdict(v) for k, v in sorted(state.busy.items())},
                                              idle=sorted(state.idle_until.items())))
                if global_hash in seen_states:
                    raise RuntimeError(f"Repeated global state at time={state.time} loop={loop_count}")
                seen_states.add(global_hash)
                simulation_events += 1
                revealed = state.reveal()
                events.extend(SimulationEvent(state.time, "release", customer_id=c) for c in revealed)
                service_completed = False
                for k in sorted(k for k, s in state.busy.items() if s.after.time <= state.time):
                    step = state.busy.pop(k)
                    state.vehicles[k] = step.after
                    steps.append(step)
                    if step.served:
                        service_completed = True
                        assert state.committed_customers.pop(step.served) == k
                        assert step.served not in state.served_customers
                        state.served_customers.add(step.served)
                    events.append(SimulationEvent(state.time, "complete", k, step.served, step.action))
                state.check_partition(instance)
                ready = [k for k, v in sorted(state.vehicles.items()) if k not in state.busy and not v.finished]
                for k in ready:
                    vehicle = state.vehicles[k]
                    if vehicle.time < state.time:
                        step = transition(vehicle, Action("wait", wait_duration=state.time-vehicle.time),
                                          Observation(vehicle.time, instance.infrastructure, ()))
                        state.vehicles[k] = step.after
                        steps.append(step)
                if not ready and not state.busy:
                    break
                skip_optimization = False
                trigger_reason = None
                root_hash = None
                if event_triggered and (ready or revealed):
                    observation = get_agent_observation(state, instance)
                    origins = {k: state.busy[k].after if k in state.busy else v
                               for k, v in state.vehicles.items()
                               if not (state.busy[k].after if k in state.busy else v).finished}
                    assert_unique_routes(tails)
                    invalid = [k for k, actions in tails.items() if actions and
                               route_proposal(origins[k], actions, observation, config.mpc) is None]
                    reasons = []
                    if epochs == 0:
                        reasons.append("initial")
                    if revealed:
                        reasons.append("release")
                    if invalid:
                        reasons.append("suffix_infeasible")
                        for k in invalid:
                            tails.pop(k)
                    uncovered = (set(observation.customer_by_id) -
                                 reserved_customers(tails) - state.served_customers)
                    if service_completed and uncovered:
                        reasons.append("service_completion_uncovered")
                    if any(k not in tails and state.vehicles[k].location.kind != "d"
                           for k in ready):
                        reasons.append("no_continuation")
                    root_hash = optimization_root_hash(observation, origins,
                                                       state.committed_customers, tails)
                    if reasons:
                        trigger_reason = ",".join(reasons)
                        optimization_triggers += 1
                        trigger_counts.update(reasons)
                        recent_triggers.append(trigger_reason)
                    else:
                        # Every retained suffix is replayed from the measured state.
                        validated_tails = {k: route_proposal(origins[k], actions, observation, config.mpc)
                                           for k, actions in tails.items() if actions}
                        if any(p is None for p in validated_tails.values()):
                            raise RuntimeError("Validated continuation changed within one event")
                        selected = {k: validated_tails.get(k) or
                                    idle_proposal(state.vehicles[k], observation, config.mpc)
                                    for k in ready}
                        frozen = {k: actions for k, actions in tails.items() if k not in ready and actions}
                        owned = reserved_customers(tails)
                        background = reserved_customers(frozen)
                        coverage = set().union(*(set(p.unique_predicted_customer_set)
                                                 for p in selected.values()))
                        decisions.append(dict(epoch=epochs, time=state.time,
                                              optimization_trigger_reason=None,
                                              optimization_root_hash=root_hash, mcts_called=False,
                                              available=[c.id for c in observation.customers],
                                              committed_before=dict(observation.committed_customers),
                                              candidate_intents=sorted(owned),
                                              background_intents=sorted(background),
                                              unique_intention_coverage=sorted(coverage),
                                              route_insertions=[], route_compactions=[],
                                              fleet_lns=None, fleet_mcts=None,
                                              route_owners_after_repair={a.destination: k for k, actions in tails.items()
                                                                         for a in actions if a.kind == "serve"},
                                              customers_available=len(observation.customers),
                                              coverage_before_coordination=len(owned),
                                              coverage_after_coordination=len(owned),
                                              uncovered_before_repair=len(set(observation.customer_by_id)-owned),
                                              repair_insertions=0, coverage_after_repair=len(owned),
                                              vehicles_before_repair=sum(origins[k].departed or bool(tails.get(k))
                                                                         for k in origins),
                                              vehicles_after_compaction=sum(origins[k].departed or bool(tails.get(k))
                                                                             for k in origins),
                                              distance_before_repair=sum(p.total_predicted_distance
                                                                         for p in validated_tails.values()),
                                              distance_after_repair=sum(p.total_predicted_distance
                                                                        for p in validated_tails.values()),
                                              selected_firsts=[p.first.destination for p in selected.values()
                                                               if p.first.kind == "serve"],
                                              plans={str(k): asdict(p) for k, p in selected.items()}))
                        coverages.append(len(coverage))
                        tails = dict(frozen)
                        for k, p in selected.items():
                            step = transition(state.vehicles[k], p.first, observation)
                            tails[k] = service_tail(p)
                            events.append(SimulationEvent(state.time, "dispatch", k, step.served, p.first))
                            if p.first.kind == "wait":
                                state.idle_until[k] = step.after.time
                                waits += 1
                            else:
                                state.idle_until.pop(k, None)
                                state.busy[k] = step
                                state.vehicles[k] = replace(state.vehicles[k], status="busy",
                                                            current_committed_action=p.first)
                                if step.served:
                                    assert step.served in state.available_customers
                                    state.available_customers.pop(step.served)
                                    state.committed_customers[step.served] = k
                        assert_unique_routes(tails)
                        epochs += 1
                        state.check_partition(instance)
                        skip_optimization = True
                if (ready or revealed) and not skip_optimization:
                    observation = get_agent_observation(state, instance)
                    started = perf_counter()
                    deadline_token = (set_deadline(started + config.total_planning_time_limit -
                                                   min(0.25 if event_triggered else 0.15,
                                                       config.total_planning_time_limit * 0.1))
                                      if config.total_planning_time_limit is not None else None)
                    origins = {k: state.busy[k].after if k in state.busy else v
                               for k, v in state.vehicles.items()
                               if not (state.busy[k].after if k in state.busy else v).finished}
                    if config.route_continuity:
                        assert_unique_routes(tails)
                    frozen = {k: a for k, a in tails.items() if k not in ready and a}
                    for k, actions in frozen.items():
                        if route_proposal(origins[k], actions, observation, config.mpc) is None:
                            raise RuntimeError("Busy route became infeasible")
                    background = reserved_customers(frozen)
                    jobs = [(self.agents[k], state.vehicles[k], route_observation(observation, frozen, k),
                             agent_seed(config.experiment_seed, self.scenario.scenario_seed, epochs, k),
                             config.algorithm) for k in ready]
                    results, cache = [], {}
                    for job in jobs:
                        agent, vehicle, obs, seed, algorithm = job
                        if algorithm in {"RH_REGRET"} | COMMON_CONSTRUCTOR_ALGORITHMS:
                            result = PlanningResult((), idle_proposal(vehicle, obs, config.mpc))
                        else:
                            key = unused_symmetry_key(vehicle, obs, config.mpc) if config.symmetry_reuse else None
                            if key is not None and key in cache:
                                result = rebind_plan(cache[key], vehicle.id)
                                reused += 1
                            else:
                                result = pool.submit(_plan_job, *job).result() if pool else _plan_job(*job)
                                if key is not None:
                                    cache[key] = result
                        results.append(result)
                    plans = {k: with_soft_incumbent(r, state.vehicles[k], job[2], config.mpc,
                                                    tails.get(k, ()) if config.route_continuity else ())
                             for k, r, job in zip(ready, results, jobs)}
                    candidate_coverage = background | set().union(*(set(p.unique_predicted_customer_set)
                                         for r in plans.values() for p in r.candidates))
                    firsts = [p.proposals[0].first.destination for p in plans.values()
                              if p.proposals and p.proposals[0].first.kind == "serve"]
                    duplicates = len(firsts)-len(set(firsts))
                    conflicts += duplicates
                    if config.algorithm in {"GREEDY", "RH_REGRET", "INDEPENDENT_MPC_MCTS",
                                            "FLEET_MPC_MCTS", "FLEET_MPC_COMPLETION_ONLY"} | ROLLING_LNS_ALGORITHMS:
                        selected, count = independent_selection(plans, exclusive_routes=True)
                        resolved += count
                    else:
                        selected = coordinate({k: r.candidates for k, r in plans.items()},
                                              frozenset(state.committed_customers),
                                              available=frozenset(c.id for c in observation.customers),
                                              background_intents=background, exclusive_routes=True)
                        resolved += duplicates
                    routes = dict(frozen)
                    routes.update({k: service_prefix(p.actions) for k, p in selected.items()})
                    fallback_routes = dict(routes)
                    fallback_validated = {k: route_proposal(origins[k], a, observation, config.mpc)
                                          for k, a in routes.items() if a}
                    if any(p is None for p in fallback_validated.values()):
                        raise RuntimeError("Selected incumbent is not replay-feasible")
                    coordinated_coverage = reserved_customers(routes)
                    retained_service = len(coordinated_coverage)
                    constructor_service = retained_service
                    constructor_seconds = 0.0
                    vehicles_before_repair = sum(origins[k].departed or bool(routes.get(k)) for k in origins)
                    distance_before_repair = sum(p.total_predicted_distance
                                                 for p in fallback_validated.values())
                    insertions = []
                    compactions = []
                    constructor_record = None
                    lns_record = None
                    fleet_mcts_record = None
                    optimizer_result = None
                    if config.regret_repair:
                        repair_start = perf_counter()
                        eligible = origins if config.route_continuity else {k: origins[k] for k in ready}
                        try:
                            repair_token = None
                            if (config.algorithm in COMMON_CONSTRUCTOR_ALGORITHMS
                                    and config.total_planning_time_limit is not None):
                                repair_token = set_deadline(started +
                                                            0.4 * config.total_planning_time_limit)
                            try:
                                if config.algorithm in COMMON_CONSTRUCTOR_ALGORITHMS:
                                    constructor_record = construct_fleet_root(
                                        eligible, routes, observation, config.mpc)
                                    routes, insertions = (constructor_record.routes,
                                                          constructor_record.insertions)
                                else:
                                    routes, insertions = regret_repair(
                                        eligible, routes, observation, config.mpc,
                                        position_limit=5 if config.algorithm in FLEET_LNS_ALGORITHMS else None)
                            finally:
                                if repair_token is not None:
                                    reset_deadline(repair_token)
                            if config.algorithm not in FLEET_LNS_ALGORITHMS | COMMON_CONSTRUCTOR_ALGORITHMS:
                                routes, compactions = compact_unused_routes(eligible, routes, observation, config.mpc)
                        except PlanningDeadlineExceeded:
                            deadline_events += 1
                        repair_seconds += perf_counter()-repair_start
                        if config.algorithm in COMMON_CONSTRUCTOR_ALGORITHMS:
                            constructor_seconds = perf_counter()-repair_start
                            constructor_service = len(reserved_customers(routes))
                            constructor_seconds_total += constructor_seconds
                            constructor_service_gain_total += max(0, constructor_service-retained_service)
                            fallback_routes = dict(routes)
                            fallback_validated = {k: route_proposal(origins[k], a, observation, config.mpc)
                                                  for k, a in routes.items() if a}
                            if any(p is None for p in fallback_validated.values()):
                                raise RuntimeError("Common constructor returned an infeasible route")
                        inserted_requests += len(insertions)
                        compacted_vehicles += len(compactions)
                    if config.algorithm in FLEET_LNS_ALGORITHMS:
                        try:
                            if config.algorithm in HYBRID_LNS_ALGORITHMS:
                                rh_routes, _ = regret_repair(origins, frozen, observation, config.mpc, position_limit=5)
                                if fleet_score(origins, rh_routes, observation, config.mpc) < fleet_score(
                                        origins, routes, observation, config.mpc):
                                    routes = rh_routes
                            available_time = min(config.lns_time_limit, remaining_time())
                            if available_time > 0:
                                lns_record = improve_fleet(
                                    origins, routes, observation, config.mpc,
                                    seed=agent_seed(config.experiment_seed, self.scenario.scenario_seed, epochs, -1),
                                    iterations=config.lns_iterations, time_limit=available_time,
                                    destroy_fraction=config.lns_destroy_fraction)
                                routes = lns_record.routes
                                lns_seconds += lns_record.elapsed
                                lns_iterations += lns_record.iterations
                                lns_improvements += lns_record.improvements
                            released = set(observation.customer_by_id) - observation.committed_ids
                            if released <= reserved_customers(routes) | state.served_customers:
                                routes, compactions = compact_unused_routes(origins, routes, observation, config.mpc)
                                compacted_vehicles += len(compactions)
                        except PlanningDeadlineExceeded:
                            deadline_events += 1
                    if config.algorithm == "FLEET_MPC_MCTS":
                        try:
                            if root_hash == previous_root_hash and previous_root_routes is not None:
                                routes = dict(previous_root_routes)
                            else:
                                mcts_calls += 1
                                fleet_mcts_record = solve_fleet_mcts(
                                    origins, routes, observation, config.mpc,
                                    seed=agent_seed(config.experiment_seed, self.scenario.scenario_seed, epochs, -1),
                                    iterations=config.fleet_mcts_iterations, depth=config.fleet_mcts_depth,
                                    branch_limit=config.fleet_mcts_branch_limit,
                                    position_limit=config.candidate_position_limit,
                                    regret_k=config.rollout_regret_k)
                                routes = fleet_mcts_record.routes
                                fleet_mcts_iterations += fleet_mcts_record.iterations
                                fleet_mcts_expanded += fleet_mcts_record.nodes_expanded
                                fleet_mcts_improvements += fleet_mcts_record.tree_improvements
                                fleet_service_seconds += fleet_mcts_record.service_seconds
                                fleet_full_seconds += fleet_mcts_record.full_seconds
                                deadline_events += int(fleet_mcts_record.deadline_reached)
                        except PlanningDeadlineExceeded:
                            deadline_events += 1
                    if config.algorithm in OPTIMIZER_ALGORITHMS:
                        try:
                            context = OptimizationContext(
                                observation=observation, origins=origins,
                                busy_actions={k: step.action for k, step in state.busy.items()},
                                soft_suffixes=tails,
                                released_customers=frozenset(observation.customer_by_id),
                                committed_customers=frozenset(state.committed_customers),
                                served_customers=frozenset(state.served_customers),
                                constructor_routes=routes, k_ref=self.scenario.fleet_size,
                                deadline=(started + config.total_planning_time_limit -
                                          min(0.25 if event_triggered else 0.15,
                                              config.total_planning_time_limit * 0.1)
                                          if config.total_planning_time_limit is not None else None),
                                seed=agent_seed(config.experiment_seed, self.scenario.scenario_seed, epochs, -1),
                                mpc=config.mpc)
                            optimizer_result = create_optimizer(config.algorithm, config).optimize(context)
                            routes = dict(optimizer_result.routes)
                            deadline_events += int(optimizer_result.deadline_reached)
                        except PlanningDeadlineExceeded:
                            deadline_events += 1
                    # Reconcile all future suffixes before dispatching any physical action.
                    assert_unique_routes(routes)
                    validation_started = perf_counter()
                    deadline_fallback = False
                    replay_reserved = (config.algorithm in COMMON_CONSTRUCTOR_ALGORITHMS
                                       and remaining_time() <= 0.02)
                    try:
                        if replay_reserved:
                            raise PlanningDeadlineExceeded
                        validated = {k: route_proposal(origins[k], a, observation, config.mpc)
                                     for k, a in routes.items() if a}
                    except PlanningDeadlineExceeded:
                        if fleet_mcts_record is not None:
                            routes = fleet_mcts_record.routes
                            validated = fleet_mcts_record.validated
                        elif optimizer_result is not None:
                            routes = dict(optimizer_result.routes)
                            validated = dict(optimizer_result.validated)
                        elif lns_record is not None:
                            routes = lns_record.routes
                            validated = lns_record.validated
                        else:
                            routes, validated = fallback_routes, fallback_validated
                        if set(validated) != {k for k, a in routes.items() if a} or any(
                                validated[k].actions != routes[k] for k in validated):
                            raise RuntimeError("Fleet fallback does not match validated incumbent")
                        deadline_events += 1
                        deadline_fallbacks += 1
                        deadline_fallback = True
                    final_validation_seconds = perf_counter() - validation_started
                    final_validation_times.append(final_validation_seconds)
                    timings.append(perf_counter()-started)
                    if event_triggered:
                        optimization_latencies.append(timings[-1])
                    if deadline_token is not None:
                        reset_deadline(deadline_token)
                        deadline_token = None
                    if any(p is None for p in validated.values()):
                        raise RuntimeError("Repair failed final route reconciliation")
                    if event_triggered:
                        previous_root_hash = root_hash
                        previous_root_routes = dict(routes)
                    final_coverage = reserved_customers(routes)
                    distance_after_repair = sum(p.total_predicted_distance for p in validated.values())
                    vehicles_after_compaction = sum(origins[k].departed or bool(routes.get(k)) for k in origins)
                    selected = {k: validated.get(k) or idle_proposal(state.vehicles[k], observation, config.mpc)
                                for k in ready}
                    tails = {k: a for k, a in routes.items() if k not in ready and a} if config.route_continuity else {}
                    measured = list(zip(ready, results))
                    if diagnostic:
                        diagnostic.observe(state, observation, plans, selected, measured, 0, config)
                    coverage = set().union(*(set(p.unique_predicted_customer_set) for p in selected.values()))
                    coverages.append(len(coverage))
                    new_activations += sum(p.new_activation for p in selected.values())
                    replans += len(results) if config.algorithm != "RH_REGRET" and config.algorithm not in ROLLING_LNS_ALGORITHMS else 0
                    background = reserved_customers(tails)
                    candidate_intents = sorted(set().union(*(set(p.unique_predicted_customer_set)
                                               for r in plans.values() for p in r.candidates)))
                    decision = dict(epoch=epochs, time=state.time, available=[c.id for c in observation.customers],
                                    optimization_trigger_reason=trigger_reason,
                                    optimization_root_hash=root_hash,
                                    mcts_called=fleet_mcts_record is not None,
                                    retained_service=retained_service,
                                    constructor_service=constructor_service,
                                    best_service_after_search=len(final_coverage),
                                    constructor_seconds=constructor_seconds,
                                    constructor_screened_insertions=(constructor_record.screened_insertions
                                                                     if constructor_record else 0),
                                    constructor_exact_decoder_calls=(constructor_record.exact_decoder_calls
                                                                     if constructor_record else 0),
                                    constructor_zero_option_customers=(constructor_record.zero_option_customers
                                                                       if constructor_record else 0),
                                    constructor_cache_hit_rate=(constructor_record.cache_hits /
                                                                max(1, constructor_record.cache_lookups)
                                                                if constructor_record else 0.0),
                                    constructor_candidate=(constructor_record.candidate
                                                           if constructor_record else None),
                                    mcts_seconds=fleet_mcts_record.elapsed if fleet_mcts_record else 0.0,
                                    committed_before=dict(observation.committed_customers),
                                    candidate_intents=candidate_intents, background_intents=sorted(background),
                                    unique_intention_coverage=sorted(coverage), route_insertions=insertions,
                                    route_compactions=compactions,
                                    fleet_lns=(dict(initial_score=lns_record.initial_score,
                                                    best_score=lns_record.best_score,
                                                    iterations=lns_record.iterations,
                                                    improvements=lns_record.improvements,
                                                    elapsed=lns_record.elapsed) if lns_record else None),
                                    fleet_mcts=(dict(initial_score=fleet_mcts_record.initial_score,
                                                     seed_score=fleet_mcts_record.seed_score,
                                                     best_score=fleet_mcts_record.best_score,
                                                     best_components=fleet_mcts_record.best_components,
                                                     criticality=fleet_mcts_record.criticality,
                                                     iterations=fleet_mcts_record.iterations,
                                                     nodes_expanded=fleet_mcts_record.nodes_expanded,
                                                     tree_improvements=fleet_mcts_record.tree_improvements,
                                                     service_seconds=fleet_mcts_record.service_seconds,
                                                     full_seconds=fleet_mcts_record.full_seconds,
                                                     elapsed=fleet_mcts_record.elapsed,
                                                     deadline_reached=fleet_mcts_record.deadline_reached)
                                                | dict(root_uncovered=fleet_mcts_record.root_uncovered,
                                                       completed_root_uncovered=fleet_mcts_record.completed_root_uncovered,
                                                       final_uncovered=fleet_mcts_record.final_uncovered,
                                                       service_gain_over_root=fleet_mcts_record.service_gain_over_root,
                                                       rollout_count=fleet_mcts_record.rollout_count,
                                                       rollout_customers_completed=fleet_mcts_record.rollout_customers_completed,
                                                       maximum_rollout_residual=fleet_mcts_record.maximum_rollout_residual,
                                                       screened_customer_count=fleet_mcts_record.screened_customer_count,
                                                       screened_vehicle_evaluations=fleet_mcts_record.screened_vehicle_evaluations,
                                                       screened_insertions=fleet_mcts_record.screened_insertions,
                                                       exact_decoded_options=fleet_mcts_record.exact_decoded_options,
                                                       service_improvements=fleet_mcts_record.service_improvements,
                                                       objective_only_improvements=fleet_mcts_record.objective_only_improvements,
                                                       screen_cache_hits=fleet_mcts_record.screen_cache_hits,
                                                       screen_cache_lookups=fleet_mcts_record.screen_cache_lookups,
                                                       screen_to_decode_ratio=(fleet_mcts_record.screened_insertions /
                                                                               max(1, fleet_mcts_record.exact_decoded_options)),
                                                       cache_hit_rate=(fleet_mcts_record.screen_cache_hits /
                                                                       max(1, fleet_mcts_record.screen_cache_lookups)),
                                                       ejection_chains_generated=fleet_mcts_record.ejection_chains_generated,
                                                       ejection_chains_feasible=fleet_mcts_record.ejection_chains_feasible,
                                                       ejection_chains_selected=fleet_mcts_record.ejection_chains_selected)
                                                if fleet_mcts_record else None),
                                    optimizer=(dict(name=config.algorithm,
                                                    objective=optimizer_result.objective,
                                                    components=dict(optimizer_result.components),
                                                    runtime=optimizer_result.runtime,
                                                    status=optimizer_result.status,
                                                    deadline_reached=optimizer_result.deadline_reached)
                                               if optimizer_result else None),
                                    route_owners_after_repair={a.destination: k for k, actions in routes.items()
                                                               for a in actions if a.kind == "serve"},
                                    customers_available=len(observation.customers),
                                    coverage_before_coordination=len(candidate_coverage),
                                    coverage_after_coordination=len(coordinated_coverage),
                                    uncovered_before_repair=len(set(c.id for c in observation.customers) - coordinated_coverage),
                                    repair_insertions=len(insertions), coverage_after_repair=len(final_coverage),
                                    vehicles_before_repair=vehicles_before_repair,
                                    vehicles_after_compaction=vehicles_after_compaction,
                                    distance_before_repair=distance_before_repair,
                                    distance_after_repair=distance_after_repair,
                                    selected_firsts=[p.first.destination for p in selected.values() if p.first.kind == "serve"],
                                    plans={str(k): asdict(p) for k, p in selected.items()} if config.trace_level != "none" else {})
                    if config.algorithm == "FLEET_MPC_MCTS":
                        decision["final_validation_seconds"] = final_validation_seconds
                        decision["deadline_fallback"] = deadline_fallback
                    if config.trace_level == "full":
                        decision["candidates"] = {str(k): [asdict(p) for p in r.candidates] for k, r in plans.items()}
                    decisions.append(decision)
                    for k, r in measured:
                        simulations += r.statistics.iterations
                        expanded += r.statistics.nodes_expanded
                        if config.algorithm not in {"GREEDY", "RH_REGRET", "FLEET_MPC_MCTS"} | ROLLING_LNS_ALGORITHMS:
                            local_times.append(r.statistics.elapsed)
                        if config.trace_level != "none":
                            details = asdict(r.statistics)
                            if config.trace_level == "summary":
                                details.pop("root_actions", None)
                            searches.append(dict(epoch=epochs, vehicle_id=k, **details))
                    for k, p in selected.items():
                        step = transition(state.vehicles[k], p.first, observation)
                        if config.route_continuity:
                            tails[k] = service_tail(p)
                        events.append(SimulationEvent(state.time, "dispatch", k, step.served, p.first))
                        if p.first.kind == "wait":
                            state.idle_until[k] = step.after.time
                            waits += 1
                        else:
                            state.idle_until.pop(k, None)
                            state.busy[k] = step
                            state.vehicles[k] = replace(state.vehicles[k], status="busy", current_committed_action=p.first)
                            if step.served:
                                assert step.served in state.available_customers
                                state.available_customers.pop(step.served)
                                state.committed_customers[step.served] = k
                    assert_unique_routes(tails)
                    epochs += 1
                    state.check_partition(instance)
                future = [t for _, t in state.hidden_customers.values() if t > state.time]
                future.extend(s.after.time for s in state.busy.values())
                future.extend(t for k, t in state.idle_until.items() if not state.vehicles[k].finished)
                if not future:
                    break
                next_time = min(future)
                if next_time < state.time or next_time > instance.infrastructure.depot.due+EPS:
                    raise RuntimeError("Invalid next event time")
                state.time = next_time
            else:
                raise RuntimeError("Simulation event guard exceeded")
        finally:
            set_deadline(None)
            if pool:
                pool.shutdown(wait=True, cancel_futures=True)
        events.append(SimulationEvent(state.time, "end"))
        served, total = len(state.served_customers), len(instance.customers)
        distance = sum(s.distance for s in steps)
        returned = all(v.finished and v.location.kind == "d" for v in state.vehicles.values())
        metrics = dict(feasible=served == total and returned, customers_served=served,
                       complete_service=served == total, customers_unserved=total-served,
                       service_ratio=served/total if total else 1., total_distance=distance,
                       distance_per_served_customer=distance/served if served else None,
                       vehicles_activated=sum(v.departed for v in state.vehicles.values()),
                       total_charging_visits=sum(s.action.kind == "charge" for s in steps),
                       total_energy_charged=sum(s.energy_charged for s in steps),
                       total_charging_time=sum(s.charging_time for s in steps),
                       total_waiting_time=sum(s.waiting_time for s in steps), final_return_feasibility=returned,
                       time_window_violations=sum(s.action.kind == "serve" and s.service_start > s.after.location.due+EPS for s in steps),
                       battery_violations=sum(s.after.battery < -EPS or s.after.battery > instance.infrastructure.parameters.battery+EPS for s in steps),
                       capacity_violations=sum(s.after.load < -EPS for s in steps), decision_epochs=epochs,
                       duplicate_customer_proposal_conflicts=conflicts, conflicts_resolved=resolved,
                       wait_selected=waits, agent_replans=replans,
                       mean_unique_intention_coverage=float(np.mean(coverages)) if coverages else 0.,
                       vehicle_activations_caused_by_coordinator=new_activations if config.algorithm in {"COORDINATED_MPC_MCTS", "MPC_MCTS_H1"} else 0,
                       duplicate_service_violations=0, hidden_information_violations=0,
                       symmetry_reused_replans=reused, mcts_iterations=simulations, nodes_expanded=expanded,
                       route_insertions=inserted_requests, route_compactions=compacted_vehicles,
                       repair_seconds=repair_seconds, lns_seconds=lns_seconds,
                       constructor_seconds_total=constructor_seconds_total,
                       constructor_service_gain_total=constructor_service_gain_total,
                       lns_iterations=lns_iterations, lns_improvements=lns_improvements,
                       fleet_mcts_iterations=fleet_mcts_iterations,
                       fleet_mcts_nodes_expanded=fleet_mcts_expanded,
                       fleet_mcts_tree_improvements=fleet_mcts_improvements,
                       simulation_events=simulation_events,
                       optimization_triggers=optimization_triggers,
                       optimization_trigger_counts=dict(trigger_counts),
                       mcts_calls=mcts_calls,
                       mcts_calls_per_simulation_event=mcts_calls / simulation_events if simulation_events else 0.0,
                       complete_instance_wall_clock_seconds=perf_counter()-run_started,
                       mean_optimization_latency=(float(np.mean(optimization_latencies))
                                                  if optimization_latencies else 0.0),
                       p95_optimization_latency=(float(np.percentile(optimization_latencies, 95))
                                                 if optimization_latencies else 0.0),
                       max_optimization_latency=(max(optimization_latencies)
                                                 if optimization_latencies else 0.0),
                       total_deadline_events=deadline_events,
                       total_deadline_overrun_rate=(float(np.mean(np.array(timings) > config.total_planning_time_limit))
                                                   if timings and config.total_planning_time_limit is not None else None),
                       deadline_overrun_rate=float(np.mean(np.array(local_times) > config.mpc.time_limit))
                       if local_times and config.mpc.budget_mode == "wall_clock" else None)
        if config.algorithm == "FLEET_MPC_MCTS":
            metrics.update(fleet_mcts_service_seconds=fleet_service_seconds,
                           fleet_mcts_full_seconds=fleet_full_seconds,
                           final_validation_seconds_total=sum(final_validation_times),
                           final_validation_seconds_p95=(float(np.percentile(final_validation_times, 95))
                                                         if final_validation_times else 0.0),
                           deadline_fallback_count=deadline_fallbacks)
        for name, fn in [("mean", np.mean), ("median", np.median), ("p95", lambda x: np.percentile(x, 95)), ("maximum", np.max), ("total", np.sum)]:
            metrics[f"{name}_planning_time"] = float(fn(timings)) if timings else 0.
        import re
        metadata = dict(instance=instance.name, instance_sha256=instance.sha256,
                        instance_family=re.match(r"([a-z]+[12])", instance.name).group(1).upper(),
                        number_of_customers=total, number_of_stations=len(instance.infrastructure.stations),
                        K=self.scenario.fleet_size, K_ref=self.scenario.fleet_size, K_max=self.scenario.fleet_size,
                        fleet_mode=config.fleet_mode, DoD_target=self.scenario.target_DoD,
                        DoD_realized=self.scenario.realized_DoD, scenario_seed=self.scenario.scenario_seed,
                        scenario_identifier=self.scenario.identifier, algorithm_seed=config.experiment_seed,
                        algorithm=config.algorithm, reference_schedule_identifier=self.scenario.reference_schedule_identifier)
        return ExperimentResult(metadata, asdict(config), metrics, events, steps, decisions, searches,
                                sorted(c.id for c in instance.customers if c.id not in state.served_customers),
                                diagnostic.finish(state) if diagnostic else {})
