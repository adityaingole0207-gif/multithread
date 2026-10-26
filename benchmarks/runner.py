"""
Benchmark Execution Engine for Multithreading vs Sequential vs Dynamic vs Multiprocessing.

OS Concepts Illustrated:
- Speedup and Amdahl's Law: Theoretical vs actual speedup limits bounded by sequential fractions.
- Multithreading efficiency across I/O-bound vs CPU-bound workloads.
- The Python Global Interpreter Lock (GIL): Why CPU-bound threads contend for a single GIL
  while I/O-bound threads scale linearly, and how OS Processes (multiprocessing) bypass the GIL.
"""

import time
import csv
import io
import concurrent.futures
from typing import Any, Callable, Dict, List, Optional, Tuple
import psutil

from engine.task import Task
from engine.pool import ThreadPool
from engine.scheduler import SchedulingPolicy
from tasks.task_types import (
    cpu_matrix_multiplication,
    cpu_prime_calculation,
    io_simulated_network,
    mixed_word_count,
)


def _mp_matrix_worker(size: int) -> float:
    """Standalone worker for multiprocessing benchmark (bypasses GIL)."""
    import random
    random.seed(42)
    A = [[random.random() for _ in range(size)] for _ in range(size)]
    B = [[random.random() for _ in range(size)] for _ in range(size)]
    C = [[0.0 for _ in range(size)] for _ in range(size)]
    for i in range(size):
        for j in range(size):
            s = 0.0
            for k in range(size):
                s += A[i][k] * B[k][j]
            C[i][j] = s
    return sum(C[0])


class BenchmarkSuite:
    """
    Executes comparative benchmarks across multiple thread configurations
    and workload profiles.
    """

    @staticmethod
    def create_workload(workload_type: str, count: int) -> List[Tuple[Callable, tuple, dict, str, int]]:
        """Generates task blueprints (fn, args, kwargs, name, priority)."""
        tasks = []
        for i in range(count):
            if workload_type == "cpu":
                # CPU-bound matrix multiplication
                tasks.append((cpu_matrix_multiplication, (60,), {}, f"CPU_Matrix_{i+1}", 2))
            elif workload_type == "io":
                # I/O-bound simulated network request
                tasks.append((io_simulated_network, (0.1,), {}, f"IO_Net_{i+1}", 2))
            else:
                # Mixed workload
                if i % 2 == 0:
                    tasks.append((cpu_prime_calculation, (8000,), {}, f"CPU_Prime_{i+1}", 2))
                else:
                    tasks.append((mixed_word_count, (1200,), {}, f"Mixed_Word_{i+1}", 2))
        return tasks

    @classmethod
    def run_configuration(
        cls,
        name: str,
        workload_type: str,
        task_count: int,
        worker_count: int,
        dynamic: bool = False,
        min_workers: int = 2,
        max_workers: int = 8,
    ) -> Dict[str, Any]:
        """Runs a workload on our custom ThreadPool with specified config."""
        pool = ThreadPool(
            min_workers=min_workers if dynamic else worker_count,
            max_workers=max_workers if dynamic else worker_count,
            initial_workers=min_workers if dynamic else worker_count,
            dynamic_scaling=dynamic,
        )

        workload = cls.create_workload(workload_type, task_count)
        task_objs = []
        for fn, args, kwargs, tname, prio in workload:
            t = Task(name=tname, fn=fn, args=args, kwargs=kwargs, priority=prio)
            task_objs.append(t)

        proc = psutil.Process()
        cpu_readings = []

        start_time = time.time()
        for t in task_objs:
            pool.submit(t)

        # Await completion
        while True:
            time.sleep(0.05)
            try:
                cpu_readings.append(proc.cpu_percent(interval=None))
            except Exception:
                pass
            completed = sum(1 for t in task_objs if t.completed_at is not None)
            if completed >= task_count:
                break

        wall_time = max(0.001, time.time() - start_time)
        pool.shutdown(wait=True, timeout=2.0)

        avg_cpu = round(sum(cpu_readings) / max(1, len(cpu_readings)), 1)
        throughput = round(task_count / wall_time, 2)
        avg_wait = round(sum(t.wait_time for t in task_objs) / task_count, 3)
        avg_turnaround = round(sum(t.turnaround_time for t in task_objs) / task_count, 3)

        return {
            "name": name,
            "workload": workload_type,
            "tasks": task_count,
            "workers": f"Dynamic ({min_workers}-{max_workers})" if dynamic else str(worker_count),
            "wall_time": round(wall_time, 3),
            "throughput": throughput,
            "avg_wait": avg_wait,
            "avg_turnaround": avg_turnaround,
            "avg_cpu": avg_cpu,
        }

    @classmethod
    def run_multiprocessing_gil_demo(cls, task_count: int = 8, matrix_size: int = 60) -> Dict[str, Any]:
        """
        Runs CPU tasks using Python's ProcessPoolExecutor (multiprocessing).
        Demonstrates true parallel OS processes bypassing the Python GIL.
        """
        proc = psutil.Process()
        cpu_readings = []
        start_time = time.time()

        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(_mp_matrix_worker, matrix_size) for _ in range(task_count)]
            for f in concurrent.futures.as_completed(futures):
                try:
                    cpu_readings.append(proc.cpu_percent(interval=None))
                except Exception:
                    pass

        wall_time = max(0.001, time.time() - start_time)
        avg_cpu = round(sum(cpu_readings) / max(1, len(cpu_readings)), 1)
        throughput = round(task_count / wall_time, 2)

        return {
            "name": "OS Multiprocessing (4 Processes - GIL Bypassed)",
            "workload": "cpu",
            "tasks": task_count,
            "workers": "4 Processes",
            "wall_time": round(wall_time, 3),
            "throughput": throughput,
            "avg_wait": 0.0,
            "avg_turnaround": round(wall_time / task_count, 3),
            "avg_cpu": avg_cpu,
        }

    @classmethod
    def run_full_benchmark(cls, workload_type: str = "io", task_count: int = 12) -> List[Dict[str, Any]]:
        """
        Executes comparison across:
        1. 1 Thread (Sequential)
        2. 4 Threads (Fixed)
        3. 8 Threads (Fixed)
        4. Dynamic Scaling (2-8 Threads)
        5. Multiprocessing (if CPU workload)
        """
        results = []

        # 1. Sequential (1 thread)
        r1 = cls.run_configuration("1 Thread (Sequential)", workload_type, task_count, worker_count=1)
        r1["speedup"] = 1.0
        results.append(r1)
        base_time = r1["wall_time"]

        # 2. 4 Threads
        r4 = cls.run_configuration("4 Threads (Fixed Pool)", workload_type, task_count, worker_count=4)
        r4["speedup"] = round(base_time / max(0.001, r4["wall_time"]), 2)
        results.append(r4)

        # 3. 8 Threads
        r8 = cls.run_configuration("8 Threads (Fixed Pool)", workload_type, task_count, worker_count=8)
        r8["speedup"] = round(base_time / max(0.001, r8["wall_time"]), 2)
        results.append(r8)

        # 4. Dynamic Scaling
        rd = cls.run_configuration("Dynamic Scaling (2-8 Workers)", workload_type, task_count, worker_count=2, dynamic=True)
        rd["speedup"] = round(base_time / max(0.001, rd["wall_time"]), 2)
        results.append(rd)

        # 5. Multiprocessing for CPU contrast
        if workload_type == "cpu":
            rmp = cls.run_multiprocessing_gil_demo(task_count=task_count)
            rmp["speedup"] = round(base_time / max(0.001, rmp["wall_time"]), 2)
            results.append(rmp)

        return results

    @staticmethod
    def export_csv(results: List[Dict[str, Any]]) -> str:
        """Exports benchmark run metrics as a CSV formatted string."""
        output = io.StringIO()
        fieldnames = ["name", "workload", "tasks", "workers", "wall_time", "speedup", "throughput", "avg_wait", "avg_turnaround", "avg_cpu"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)
        return output.getvalue()
