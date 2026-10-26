"""
Synchronization Demos: Race Condition & Deadlock Avoidance.

OS Concepts Illustrated:
1. Race Condition / Lost Updates:
   - Multiple threads concurrently reading and writing a shared memory variable without locks.
   - Fixed version: Critical section protected by a Mutex (Lock).
2. Deadlock (Coffman Conditions) vs Resource Hierarchy:
   - AB-BA lock inversion creating circular wait.
   - Fixed version: Lock hierarchy / total ordering protocol eliminating circular wait.
"""

import time
import threading
from typing import Any, Dict
from engine.resources import SharedCounter, DeadlockDemo


def run_race_condition_demo(num_threads: int = 10, increments_per_thread: int = 500, use_lock: bool = False) -> Dict[str, Any]:
    """
    Spawns multiple threads incrementing a shared counter.
    - If use_lock is False: Race conditions lead to lost updates (final value < expected).
    - If use_lock is True: Mutex guarantees mutual exclusion and final value == expected.
    """
    counter = SharedCounter()
    expected_value = num_threads * increments_per_thread

    def worker():
        for _ in range(increments_per_thread):
            if use_lock:
                counter.increment_safe()
            else:
                counter.increment_unsafe()

    threads = []
    start = time.time()
    for i in range(num_threads):
        t = threading.Thread(target=worker, name=f"CounterWorker-{i+1}")
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = time.time() - start
    final_value = counter.value
    lost_updates = expected_value - final_value

    return {
        "mode": "Locked (Mutex Protected)" if use_lock else "Unsynchronized (Race Condition)",
        "threads": num_threads,
        "increments_per_thread": increments_per_thread,
        "expected_value": expected_value,
        "actual_value": final_value,
        "lost_updates": lost_updates,
        "duration_seconds": round(duration, 3),
        "success": final_value == expected_value,
        "explanation": (
            "With Mutex Lock enabled, mutual exclusion is enforced across the critical section, "
            "preventing lost updates. Without locks, concurrent read-modify-write interleaved context switches "
            "overwrite counter increments."
        ),
    }


def run_deadlock_demo(avoid_deadlock: bool = False) -> Dict[str, Any]:
    """
    Demonstrates deadlock via circular wait vs avoidance via resource ordering.
    """
    demo = DeadlockDemo()
    if avoid_deadlock:
        res = demo.run_ordered_locks_threads()
        return {
            "mode": "Deadlock Avoided (Global Lock Ordering)",
            "deadlocked": False,
            "success": res["success"],
            "logs": res["logs"],
            "explanation": res["explanation"],
        }
    else:
        res = demo.run_circular_wait_threads(timeout=1.5)
        return {
            "mode": "Deadlock Incurred (Circular Wait)",
            "deadlocked": res["deadlocked"],
            "success": not res["deadlocked"],
            "logs": res["logs"],
            "explanation": res["explanation"],
        }
