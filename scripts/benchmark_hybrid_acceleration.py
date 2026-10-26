"""Read-only real-state geometry screening benchmark, including transfer costs."""

from dataclasses import asdict
from hashlib import sha256
from statistics import median
from time import perf_counter
import platform

import numpy as np

from evrp.fleet_mcts import _FleetProblem
from evrp.instance import distance, energy, travel_time
from evrp.storage import ROOT, load_json, save_json
from scripts.performance_engineering_worker import corpus, load_case

OUTPUT = ROOT / "results/desaulniers/hybrid_acceleration_v1"
PROTOCOL = ROOT / "results/desaulniers/performance_engineering_v1/protocol.json"


def _distance(raw, precision):
    return np.ceil(raw * precision - 1e-9) / precision if precision else raw


def numpy_kernel(values, distance_precision, energy_precision, speed, consumption):
    ab = np.hypot(values[:, 0] - values[:, 2], values[:, 1] - values[:, 3])
    bc = np.hypot(values[:, 2] - values[:, 4], values[:, 3] - values[:, 5])
    ac = np.hypot(values[:, 0] - values[:, 4], values[:, 1] - values[:, 5])
    db, dc, da = (_distance(x, distance_precision) for x in (ab, bc, ac))
    travel = db / speed
    e = np.ceil(ab * consumption * energy_precision - 1e-9) / energy_precision if energy_precision else ab * consumption
    return np.stack((db + dc - da, np.maximum(values[:, 6] + travel, values[:, 7]), e), axis=1)


def compiled_kernel(values, distance_precision, energy_precision, speed, consumption):
    from numba import njit
    from math import ceil, hypot

    @njit(cache=True, fastmath=False)
    def kernel(rows, dprec, eprec, velocity, rate):
        result = np.empty((len(rows), 3), dtype=np.float64)
        for i in range(len(rows)):
            row = rows[i]
            ab = hypot(row[0] - row[2], row[1] - row[3])
            bc = hypot(row[2] - row[4], row[3] - row[5])
            ac = hypot(row[0] - row[4], row[1] - row[5])
            db = ceil(ab * dprec - 1e-9) / dprec if dprec else ab
            dc = ceil(bc * dprec - 1e-9) / dprec if dprec else bc
            da = ceil(ac * dprec - 1e-9) / dprec if dprec else ac
            e = ceil(ab * rate * eprec - 1e-9) / eprec if eprec else ab * rate
            result[i, 0] = db + dc - da
            result[i, 1] = max(row[6] + db / velocity, row[7])
            result[i, 2] = e
        return result

    return kernel


def gpu_kernel(values, distance_precision, energy_precision, speed, consumption):
    import cupy as cp

    data = cp.asarray(values)
    ab = cp.hypot(data[:, 0] - data[:, 2], data[:, 1] - data[:, 3])
    bc = cp.hypot(data[:, 2] - data[:, 4], data[:, 3] - data[:, 5])
    ac = cp.hypot(data[:, 0] - data[:, 4], data[:, 1] - data[:, 5])
    dist = lambda x: cp.ceil(x * distance_precision - 1e-9) / distance_precision if distance_precision else x
    db, dc, da = dist(ab), dist(bc), dist(ac)
    e = cp.ceil(ab * consumption * energy_precision - 1e-9) / energy_precision if energy_precision else ab * consumption
    output = cp.stack((db + dc - da, cp.maximum(data[:, 6] + db / speed, data[:, 7]), e), axis=1)
    result = cp.asnumpy(output)
    cp.cuda.Stream.null.synchronize()
    return result


def python_objects(rows, distance_precision):
    from evrp.instance import Location

    prepared = []
    for row in rows:
        before = Location("before", "c", row[0], row[1], 0, 0, 100, 0, distance_precision)
        target = Location("target", "c", row[2], row[3], 0, 0, 100, 0, distance_precision)
        after = Location("after", "c", row[4], row[5], 0, 0, 100, 0, distance_precision)
        prepared.append((before, target, after, row[6], row[7]))
    return prepared


def python_kernel(prepared, speed, consumption, energy_precision):
    from evrp.instance import Parameters

    p = Parameters(100, 100, consumption, 1, speed, energy_precision)
    output = []
    for before, target, after, earliest, ready in prepared:
        output.append((distance(before, target) + distance(target, after) - distance(before, after),
                       max(earliest + travel_time(before, target, p), ready),
                       energy(before, target, p)))
    return np.asarray(output)


def candidates(protocol, index):
    instance, _ = load_case(protocol, index)
    origins, observation, _, sequences = corpus(protocol, index, instance)
    problem = _FleetProblem(origins, observation, protocol["simulation_config"], 3, 2)
    p = observation.infrastructure.parameters
    rows = []
    for k, sequence in sequences:
        target = next((c for c in observation.customer_by_id if c not in sequence), None)
        if target is None:
            continue
        profile = problem._screen_profile(k, sequence)
        customer = observation.customer_by_id[target]
        for position in range(len(sequence) + 1):
            before = origins[k].location if position == 0 else observation.customer_by_id[sequence[position - 1]]
            after = observation.infrastructure.depot if position == len(sequence) else observation.customer_by_id[sequence[position]]
            rows.append((before.x, before.y, customer.x, customer.y, after.x, after.y,
                         profile.earliest[position], customer.ready, customer.due))
    if not rows:
        raise ValueError("No real candidate rows in archived root")
    return rows, p, instance


def timed(call, repetitions):
    times = []
    for _ in range(repetitions):
        start = perf_counter()
        call()
        times.append(perf_counter() - start)
    return median(times)


def main():
    from evrp.experiments import simulation_config

    protocol = load_json(PROTOCOL)
    protocol["simulation_config"] = simulation_config(protocol["cases"][0]["base_options"]).mpc
    import numba
    try:
        import cupy as cp
        gpu_status = dict(available=True, version=cp.__version__, name=cp.cuda.runtime.getDeviceProperties(0)["name"].decode(),
                          runtime=cp.cuda.runtime.runtimeGetVersion())
    except Exception as exc:
        cp = None
        gpu_status = dict(available=False, error=repr(exc))
    results = []
    for index in (0, 1, 2):
        rows, p, instance = candidates(protocol, index)
        dprec, eprec = instance.infrastructure.depot.distance_precision, p.energy_precision
        cpu_compiled = compiled_kernel(None, dprec, eprec, p.speed, p.consumption)
        base = np.asarray(rows, dtype=np.float64)
        cpu_compiled(base, dprec, eprec, p.speed, p.consumption)
        if cp is not None:
            gpu_kernel(base[:1], dprec, eprec, p.speed, p.consumption)
        for count in (len(rows), 8, 32, 128, 512, 2048, 8192, 32768):
            selected = (rows * (count // len(rows) + 1))[:count]
            prepared = python_objects(selected, dprec)
            host = np.asarray(selected, dtype=np.float64)
            expected = python_kernel(prepared, p.speed, p.consumption, eprec)
            cpu = cpu_compiled(host, dprec, eprec, p.speed, p.consumption)
            numpy_result = numpy_kernel(host, dprec, eprec, p.speed, p.consumption)
            if not np.allclose(cpu, expected, rtol=0, atol=1e-10) or not np.allclose(numpy_result, expected, rtol=0, atol=1e-10):
                raise ValueError("Compiled/NumPy geometry discrepancy")
            if cp is not None:
                gpu = gpu_kernel(host, dprec, eprec, p.speed, p.consumption)
                if not np.allclose(gpu, expected, rtol=0, atol=1e-10):
                    raise ValueError("GPU geometry discrepancy")
            reps = 4 if count >= 8192 else 10 if count >= 512 else 30
            make = lambda: np.asarray(selected, dtype=np.float64)
            timings = dict(original_python=timed(lambda: python_kernel(prepared, p.speed, p.consumption, eprec), reps),
                           numpy=timed(lambda: numpy_kernel(make(), dprec, eprec, p.speed, p.consumption), reps),
                           compiled_cpu=timed(lambda: cpu_compiled(make(), dprec, eprec, p.speed, p.consumption), reps))
            if cp is not None:
                timings["gpu_full_transfer"] = timed(lambda: gpu_kernel(make(), dprec, eprec, p.speed, p.consumption), reps)
            results.append(dict(instance=instance.name, actual_root_batch=len(rows), batch_size=count,
                                seconds=timings, maximum_abs_error=float(np.max(np.abs(cpu - expected))),
                                tested_real_geometry=True))
    outcomes = dict(python=platform.python_version(), numpy=np.__version__, numba=numba.__version__,
                    gpu=gpu_status, source_sha256=sha256((ROOT / "scripts/benchmark_hybrid_acceleration.py").read_bytes()).hexdigest(),
                    results=results)
    save_json(OUTPUT / "kernel_benchmark.json", outcomes)
    for row in results:
        print(row["instance"], row["batch_size"], {k: round(v * 1e6, 1) for k, v in row["seconds"].items()}, flush=True)


if __name__ == "__main__":
    main()
