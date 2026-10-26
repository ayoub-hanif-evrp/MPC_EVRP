"""Optional conservative time-window prefilter for batched insertion gaps."""

from functools import lru_cache
from math import hypot


@lru_cache(maxsize=1)
def _kernel():
    try:
        import numpy as np
        from numba import njit
    except ImportError:
        return None

    @njit(cache=True, fastmath=False)
    def screen(rows, speed, due, service):
        accepted = np.ones(len(rows), dtype=np.bool_)
        for i in range(len(rows)):
            r = rows[i]
            # The benchmark's upward rounding can undershoot raw Euclidean
            # distance by at most its tiny tolerance; use an even looser bound.
            to_customer = max(0.0, hypot(r[0] - r[2], r[1] - r[3]) - 1e-7) / speed
            to_next = max(0.0, hypot(r[2] - r[4], r[3] - r[5]) - 1e-7) / speed
            start = max(r[6] + to_customer, r[8])
            if start > due + 1e-7 or start + service + to_next > r[7] + 1e-7:
                accepted[i] = False
        return accepted

    return screen


def available():
    return _kernel() is not None


def prepare():
    kernel = _kernel()
    if kernel is None:
        return False
    import numpy as np

    kernel(np.zeros((1, 9), dtype=np.float64), 1.0, 1.0, 0.0)
    return True


def optimistic_time_mask(problem, vehicle, sequence, customer_id):
    """False means provably late under a strictly optimistic travel bound."""
    kernel = _kernel()
    if kernel is None:
        return None
    import numpy as np

    profile = problem._screen_profile(vehicle, sequence)
    obs = problem.observation
    target = obs.customer_by_id[customer_id]
    rows = []
    for position in range(len(sequence) + 1):
        before = problem.origins[vehicle].location if position == 0 else obs.customer_by_id[sequence[position - 1]]
        after = obs.infrastructure.depot if position == len(sequence) else obs.customer_by_id[sequence[position]]
        latest = after.due if position == len(sequence) else profile.latest[position]
        rows.append((before.x, before.y, target.x, target.y, after.x, after.y,
                     profile.earliest[position], latest, target.ready))
    values = np.asarray(rows, dtype=np.float64)
    return kernel(values, obs.infrastructure.parameters.speed, target.due, target.service)
