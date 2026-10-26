"""
Standard Workload Task Types (CPU-Bound, I/O-Bound, and Mixed).

OS Concepts Illustrated:
- Workload characterization: CPU-bound tasks saturate execution cores; I/O-bound tasks
  yield control and spend time in BLOCKED/waiting state.
- Cooperative multitasking / Time-slicing support for Round Robin scheduling.
- Finite resource acquisition (Database connection simulation using Semaphores).
"""

import time
import math
import hashlib
import random
from typing import Any, Dict, List, Optional
from engine.task import Task


def cpu_prime_calculation(limit: int = 15000, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    CPU-bound task: computes prime numbers using trial division.
    Consumes CPU cycles; blocked by Python's Global Interpreter Lock (GIL) under pure threading.
    """
    primes = []
    count = 0
    for num in range(2, limit):
        if task_ref and task_ref.cancellation_token.is_set():
            return {"status": "cancelled", "primes_found": len(primes)}
            
        is_prime = True
        for i in range(2, int(math.isqrt(num)) + 1):
            if num % i == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(num)
        count += 1
        if task_ref and count % 2000 == 0:
            task_ref.progress = min(0.99, count / limit)

    if task_ref:
        task_ref.progress = 1.0
    return {"primes_found": len(primes), "highest_prime": primes[-1] if primes else 0}


def cpu_matrix_multiplication(size: int = 70, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    CPU-bound task: generates two random NxN matrices and calculates their dot product.
    O(N^3) time complexity.
    """
    random.seed(42)
    A = [[random.random() for _ in range(size)] for _ in range(size)]
    B = [[random.random() for _ in range(size)] for _ in range(size)]
    C = [[0.0 for _ in range(size)] for _ in range(size)]

    total_rows = size
    for i in range(size):
        if task_ref and task_ref.cancellation_token.is_set():
            return {"status": "cancelled"}
        for j in range(size):
            s = 0.0
            for k in range(size):
                s += A[i][k] * B[k][j]
            C[i][j] = s
        if task_ref:
            task_ref.progress = min(0.99, (i + 1) / total_rows)

    if task_ref:
        task_ref.progress = 1.0
    return {"matrix_size": f"{size}x{size}", "checksum": round(sum(C[0]), 4)}


def cpu_file_hashing(size_kb: int = 500, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    CPU-bound task: generates synthetic binary data and computes SHA-256 hashes repeatedly.
    """
    chunk = b"OS_MULTITHREADING_BENCHMARK_PAYLOAD_" * 32  # 1 KB
    hasher = hashlib.sha256()
    for i in range(size_kb):
        if task_ref and task_ref.cancellation_token.is_set():
            return {"status": "cancelled"}
        hasher.update(chunk)
        if task_ref and i % 50 == 0:
            task_ref.progress = min(0.99, (i + 1) / size_kb)

    if task_ref:
        task_ref.progress = 1.0
    return {"digest": hasher.hexdigest(), "size_kb": size_kb}


def io_simulated_network(duration: float = 0.4, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    I/O-bound task: simulates network latency / socket calls where thread yields CPU.
    OS Concept: Thread transitions to BLOCKED state, freeing core for other threads.
    """
    interval = 0.05
    steps = int(max(1, duration / interval))
    for step in range(steps):
        if task_ref and task_ref.cancellation_token.is_set():
            return {"status": "cancelled"}
        time.sleep(interval)
        if task_ref:
            task_ref.progress = min(0.99, (step + 1) / steps)

    if task_ref:
        task_ref.progress = 1.0
    return {"simulated_network_latency": duration, "bytes_received": 4096}


def io_simulated_disk(duration: float = 0.3, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    I/O-bound task: simulates disk seek time and non-volatile storage access.
    """
    interval = 0.05
    steps = int(max(1, duration / interval))
    for step in range(steps):
        if task_ref and task_ref.cancellation_token.is_set():
            return {"status": "cancelled"}
        time.sleep(interval)
        if task_ref:
            task_ref.progress = min(0.99, (step + 1) / steps)

    if task_ref:
        task_ref.progress = 1.0
    return {"simulated_disk_io_seconds": duration, "sectors_read": 128}


def mixed_word_count(num_lines: int = 1500, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    Mixed CPU & I/O task: simulates streaming log lines and computing frequency table.
    """
    vocabulary = ["thread", "process", "mutex", "semaphore", "deadlock", "starvation",
                  "quantum", "scheduling", "kernel", "interrupt", "context_switch"]
    
    # 1. I/O simulation delay
    time.sleep(0.05)
    
    # 2. CPU text parsing
    counts: Dict[str, int] = {}
    for i in range(num_lines):
        if task_ref and task_ref.cancellation_token.is_set():
            return {"status": "cancelled"}
        word = vocabulary[i % len(vocabulary)]
        counts[word] = counts.get(word, 0) + 1
        if task_ref and i % 200 == 0:
            task_ref.progress = min(0.99, (i + 1) / num_lines)

    if task_ref:
        task_ref.progress = 1.0
    return {"total_lines": num_lines, "top_word": "thread", "occurrences": counts["thread"]}


def mixed_image_processing(dim: int = 50, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    Mixed task: creates a synthetic 2D grid of pixels and applies a 3x3 convolution blur filter.
    """
    pixels = [[(x * y) % 256 for x in range(dim)] for y in range(dim)]
    blurred = [[0 for _ in range(dim)] for _ in range(dim)]
    
    for y in range(1, dim - 1):
        if task_ref and task_ref.cancellation_token.is_set():
            return {"status": "cancelled"}
        for x in range(1, dim - 1):
            s = (
                pixels[y - 1][x - 1] + pixels[y - 1][x] + pixels[y - 1][x + 1] +
                pixels[y][x - 1]     + pixels[y][x]     + pixels[y][x + 1] +
                pixels[y + 1][x - 1] + pixels[y + 1][x] + pixels[y + 1][x + 1]
            )
            blurred[y][x] = s // 9
        if task_ref:
            task_ref.progress = min(0.99, y / (dim - 2))

    if task_ref:
        task_ref.progress = 1.0
    return {"dimensions": f"{dim}x{dim}", "avg_pixel": sum(blurred[1]) // len(blurred[1])}


def cooperative_quanta_task(slices: int = 4, quantum_time: float = 0.1, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    Time-sliced task designed for Round Robin demonstration.
    Executes in distinct quanta. In cooperative round robin, if remaining slices > 1,
    the task decrements its quanta and can yield.
    """
    if task_ref and not hasattr(task_ref, "completed_slices"):
        task_ref.completed_slices = 0
        task_ref.total_slices = slices

    # Execute one slice
    time.sleep(quantum_time)
    if task_ref:
        task_ref.completed_slices += 1
        task_ref.progress = min(1.0, task_ref.completed_slices / task_ref.total_slices)
        is_finished = task_ref.completed_slices >= task_ref.total_slices
        return {"finished": is_finished, "completed_slice": task_ref.completed_slices, "of": task_ref.total_slices}
    
    return {"finished": True}


def database_query_task(resource_pool, duration: float = 0.3, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    Task demonstrating Semaphore guarded access:
    Must acquire a connection permit, perform work, and release permit.
    """
    if task_ref:
        task_ref.state = task_ref.state.__class__.BLOCKED
        
    permit = resource_pool.acquire(requester_id=task_ref.task_id if task_ref else "Worker", timeout=4.0)
    if not permit:
        raise TimeoutError("Could not acquire DB connection permit from semaphore pool (Resource exhaustion)")

    try:
        if task_ref:
            task_ref.resource_held = permit
            task_ref.state = task_ref.state.__class__.RUNNING
            
        time.sleep(duration)
        if task_ref:
            task_ref.progress = 1.0
        return {"acquired_resource": permit, "status": "query_completed"}
    finally:
        resource_pool.release(permit)
        if task_ref:
            task_ref.resource_held = None


def faulty_task(fail_rate: float = 0.7, task_ref: Optional[Task] = None) -> Dict[str, Any]:
    """
    Task that randomly raises an exception to demonstrate fault tolerance & retry mechanics.
    """
    time.sleep(0.1)
    if random.random() < fail_rate:
        raise RuntimeError(f"Simulated hardware/network fault in Task {task_ref.task_id if task_ref else 'unknown'}")
    if task_ref:
        task_ref.progress = 1.0
    return {"status": "recovered_successfully"}
