"""
Unit tests for Synchronization Primitives and Concurrency Control.
Tests:
- No lost updates with Mutex
- Detection of lost updates without Mutex
- Semaphore capacity limits never exceeded
- Deadlock reproduction & Deadlock avoidance via Lock Hierarchy
"""

import threading
import time
import pytest
from engine.resources import SharedCounter, SharedResourcePool, DeadlockDemo
from benchmarks.sync_demos import run_race_condition_demo, run_deadlock_demo


def test_mutex_prevents_lost_updates():
    """Verify that Lock/Mutex prevents lost updates under concurrent access."""
    res_safe = run_race_condition_demo(num_threads=8, increments_per_thread=250, use_lock=True)
    assert res_safe["success"] is True
    assert res_safe["lost_updates"] == 0
    assert res_safe["actual_value"] == res_safe["expected_value"]


def test_unsynchronized_counter_loses_updates():
    """Verify that unsynchronized concurrent increments cause race conditions / lost updates."""
    res_unsafe = run_race_condition_demo(num_threads=10, increments_per_thread=300, use_lock=False)
    # Due to concurrent race conditions, lost updates should be > 0
    assert res_unsafe["lost_updates"] > 0
    assert res_unsafe["actual_value"] < res_unsafe["expected_value"]


def test_semaphore_capacity_limit_never_exceeded():
    """Verify that a Counting Semaphore strictly bounds concurrent access to its capacity."""
    capacity = 3
    pool = SharedResourcePool(name="TestPool", capacity=capacity)
    
    current_concurrency = 0
    max_observed_concurrency = 0
    lock = threading.Lock()
    errors = []

    def worker(worker_id: int):
        nonlocal current_concurrency, max_observed_concurrency
        slot = pool.acquire(requester_id=f"Worker-{worker_id}", timeout=2.0)
        if not slot:
            errors.append("Timeout acquiring slot")
            return

        with lock:
            current_concurrency += 1
            if current_concurrency > max_observed_concurrency:
                max_observed_concurrency = current_concurrency

        # Hold permit briefly
        time.sleep(0.05)

        with lock:
            current_concurrency -= 1

        pool.release(slot)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert max_observed_concurrency <= capacity, f"Observed {max_observed_concurrency} > {capacity}"
    status = pool.get_status()
    assert status["available_count"] == capacity
    assert status["allocated_count"] == 0


def test_deadlock_circular_wait_detected():
    """Verify that circular wait produces deadlock/timeout."""
    res = run_deadlock_demo(avoid_deadlock=False)
    assert res["deadlocked"] is True


def test_deadlock_avoidance_succeeds():
    """Verify that strict lock hierarchy ordering completes without deadlock."""
    res = run_deadlock_demo(avoid_deadlock=True)
    assert res["deadlocked"] is False
    assert res["success"] is True
