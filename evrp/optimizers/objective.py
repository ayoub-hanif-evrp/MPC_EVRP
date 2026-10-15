"""Canonical lexicographic fleet objective shared by MPC optimizers."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from ..model import Action, VehicleState


@dataclass(frozen=True)
class FleetObjectiveEvaluator:
    """Evaluate the V1 J_A/J_B hierarchy with V1 route-risk measurements.

    The risk and insertion-option callbacks belong to the decision-epoch
    problem so every optimizer uses the same measured state and decoder.
    """

    ids: tuple[int, ...]
    origins: Mapping[int, VehicleState]
    pending: frozenset[str]
    distance_scale: float
    initial_owners: Mapping[str, int]
    route_metrics: Callable[[int, tuple[Action, ...]], Mapping[str, float]]
    control_metrics: Callable[[int, tuple[Action, ...]], Mapping[str, float]]
    criticality: Callable[[tuple[tuple[str, ...], ...]], Sequence[tuple]]

    @staticmethod
    def _unit(value: float) -> float:
        return max(0.0, min(1.0, value))

    def evaluate(self, sequences: Sequence[tuple[str, ...]],
                 actions: Sequence[tuple[Action, ...]],
                 costs: Sequence[float]) -> tuple[tuple[float, ...], dict[str, float]]:
        owned = {c for sequence in sequences for c in sequence}
        uncovered = self.pending - owned
        vehicles = sum(self.origins[k].departed or bool(actions[index])
                       for index, k in enumerate(self.ids))
        risks = [self.route_metrics(k, actions[index]) for index, k in enumerate(self.ids)
                 if actions[index]]
        mean = lambda field: sum(r[field] for r in risks) / len(risks) if risks else 0.0
        tw = mean("tw")
        battery = mean("battery")
        capacity = mean("capacity")
        active_time_risks = [self.route_metrics(k, actions[index])["time_risk"]
                             for index, k in enumerate(self.ids)
                             if self.origins[k].departed or actions[index]]
        time_risk = (sum(active_time_risks) / len(active_time_risks)
                     if active_time_risks else 0.0)
        flexibility_risk = (tw + battery + capacity + time_risk) / 4
        control_risk = sum(self.control_metrics(k, actions[index])["total"]
                           for index, k in enumerate(self.ids)) / max(1, len(self.ids))
        route_distance = sum(costs)
        normalized_distance = self._unit(route_distance / max(1.0, self.distance_scale * 2))
        durations = [r["duration"] for r in risks]
        balance = max(durations) - min(durations) if len(durations) > 1 else 0.0
        moved = sum(self.initial_owners.get(c, k) != k for index, k in enumerate(self.ids)
                    for c in sequences[index])
        instability = moved / max(1, len(owned))
        if uncovered:
            critical = self.criticality(tuple(sequences))
            zero = sum(count == 0 for _, count, _, _, _ in critical)
            one = sum(count == 1 for _, count, _, _, _ in critical)
            components = dict(unserved_customers=len(uncovered), screened_zero_option_customers=zero,
                              screened_one_option_customers=one, time_window_risk=tw,
                              battery_risk=battery, capacity_risk=capacity, time_reserve_risk=time_risk,
                              flexibility_risk=flexibility_risk, control_risk=control_risk,
                              normalized_distance=normalized_distance,
                              activated_vehicles=vehicles, distance=route_distance,
                              route_instability=instability)
            score = (len(uncovered), zero, one, control_risk, tw, battery,
                     capacity, normalized_distance)
        else:
            operational = sum((normalized_distance, mean("duration"), mean("charge"),
                               mean("wait"), tw, battery, balance)) / 7
            components = dict(unserved_customers=0, screened_zero_option_customers=0,
                              screened_one_option_customers=0, time_window_risk=tw,
                              battery_risk=battery, capacity_risk=capacity,
                              time_reserve_risk=time_risk, flexibility_risk=flexibility_risk,
                              control_risk=control_risk,
                              normalized_distance=normalized_distance,
                              normalized_route_duration=mean("duration"),
                              normalized_charging_time=mean("charge"),
                              normalized_waiting_time=mean("wait"),
                              route_balance_risk=balance, operational_cost=operational,
                              activated_vehicles=vehicles, distance=route_distance,
                              route_instability=instability)
            score = (0, control_risk, flexibility_risk, vehicles, operational,
                     route_distance, instability)
        return score, components
