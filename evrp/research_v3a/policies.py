"""Paired charge-planning approximations with identical customer ranking rules."""

from __future__ import annotations

from .simulator import Action, Observation, StationView


class GreedyChargePolicy:
    """Earliest-deadline greedy dispatch; only charger wait prediction differs.

    This is a controlled modeling comparator, not a port of historical ALNS.
    ``endogenous=False`` ignores other controlled EVs while planning charging;
    both versions execute in the same finite-capacity fleet plant.
    """

    def __init__(self, *, endogenous: bool):
        self.endogenous = endogenous

    def _charge_option(self, o: Observation, vehicle_id: int, station: StationView,
                       target_energy: float) -> tuple[float, float] | None:
        v = o.vehicles[vehicle_id]
        arrival = o.now + o.travel(v.node, station.node)
        remaining = v.energy - o.energy(v.node, station.node)
        if remaining < -1e-9 or target_energy <= remaining + 1e-9:
            return None
        options = []
        for idx, (busy, rate, windows) in enumerate(zip(station.busy_until, station.rates, station.windows)):
            duration = (target_energy - remaining) / rate
            estimate = arrival
            if self.endogenous:
                estimate = max(estimate, busy)
                # FCFS queued EVs need service before this arrival. We use a
                # conservative, observable average charge-time approximation.
                estimate += len(station.waiting) * min(duration, 60.0) / len(station.rates)
            for lo, hi in windows:
                start = max(estimate, lo)
                if start + duration <= min(hi, o.max_time) + 1e-9:
                    options.append((start + duration, target_energy))
                    break
        return min(options) if options else None

    def decide(self, o: Observation, vehicle_id: int) -> Action | None:
        v = o.vehicles[vehicle_id]
        if v.status == "queued":
            # Waiting is revisable, but this baseline does not abandon a queue.
            return None
        customers = sorted(o.customers, key=lambda x: (x.end, x.id))
        for customer in customers:
            if v.load + 1e-9 < customer.demand:
                continue
            arrival = max(o.now + o.travel(v.node, customer.id), customer.start)
            if (arrival > customer.end + 1e-9 or
                    arrival + customer.service + o.travel(customer.id, o.depot) > o.max_time + 1e-9):
                continue
            direct_energy = o.energy(v.node, customer.id) + o.energy(customer.id, o.depot)
            if v.energy + 1e-9 >= direct_energy:
                return Action("customer", customer.id)
            # Charge enough for a one-customer route and safe depot return.
            station_options = []
            for station in o.stations:
                needed = o.energy(station.node, customer.id) + o.energy(customer.id, o.depot)
                target = min(o.battery_capacity, needed + 1.0)
                if target + 1e-9 < needed:
                    continue
                option = self._charge_option(o, vehicle_id, station, target)
                if option is None:
                    continue
                charge_done, _ = option
                finish = max(charge_done + o.travel(station.node, customer.id), customer.start)
                if (finish > customer.end + 1e-9 or
                        finish + customer.service + o.travel(customer.id, o.depot) > o.max_time + 1e-9):
                    continue
                station_options.append((finish, charge_done, station.id, target))
            if station_options:
                _, _, station_id, target = min(station_options)
                return Action("station", station_id, target)
        if v.node != o.depot:
            # Depot restoration is identical for both models and does not
            # release a dispatched action early.
            if v.energy + 1e-9 >= o.energy(v.node, o.depot):
                return Action("depot", 0)
        return None
