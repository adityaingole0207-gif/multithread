"""
Concurrency Synchronization Primitives and Resource Control.

OS Concepts Illustrated:
- Counting Semaphore: Limiting concurrent access to finite shared resources (e.g., DB connections).
- Mutual Exclusion (Mutex / Lock): Protecting critical sections against race conditions and lost updates.
- Deadlock: Demonstrating Coffman's 4 conditions (Mutual exclusion, Hold & wait, No preemption, Circular wait).
- Deadlock Avoidance / Prevention: Resource Ordering Protocol (Lock Hierarchy) breaking the Circular Wait condition.
"""

import time
import threading
from typing import Any, Dict, List, Optional, Tuple


class SharedResourcePool:
    """
    Manages a finite pool of shared resources (e.g., Database connections)
    using a Counting Semaphore to enforce admission limits.
    """

    def __init__(self, name: str = "DB_Connection_Pool", capacity: int = 3):
        self.name = name
        self.capacity = capacity
        self._semaphore = threading.Semaphore(capacity)
        self._lock = threading.Lock()
        
        # Resource slot tracking
        self._available_slots: List[str] = [f"{name}_Slot_{i+1}" for i in range(capacity)]
        self._allocated: Dict[str, str] = {}  # slot -> worker_or_task_id
        self._wait_count = 0

    def acquire(self, requester_id: str, timeout: Optional[float] = 5.0) -> Optional[str]:
        """
        Acquires a resource permit. Blocks if capacity is exhausted.
        OS Concept: Counting Semaphore P() / wait() operation.
        """
        with self._lock:
            self._wait_count += 1
            
        acquired = self._semaphore.acquire(timeout=timeout)
        
        with self._lock:
            self._wait_count -= 1
            if not acquired:
                return None
            slot = self._available_slots.pop(0)
            self._allocated[slot] = requester_id
            return slot

    def release(self, slot: str) -> bool:
        """
        Returns a resource permit back to the pool.
        OS Concept: Counting Semaphore V() / signal() operation.
        """
        with self._lock:
            if slot not in self._allocated:
                return False
            del self._allocated[slot]
            self._available_slots.append(slot)
            
        self._semaphore.release()
        return True

    def get_status(self) -> Dict[str, Any]:
        """Telemetry snapshot of the resource pool."""
        with self._lock:
            active_allocations = dict(self._allocated)
            available = list(self._available_slots)
            waiting = self._wait_count
        return {
            "name": self.name,
            "capacity": self.capacity,
            "available_count": len(available),
            "allocated_count": len(active_allocations),
            "waiting_threads": waiting,
            "allocations": active_allocations,
        }


class SharedCounter:
    """
    Demonstrates race conditions (lost updates) vs mutex protection.
    OS Concept: Critical Section and Mutual Exclusion (Mutex).
    """

    def __init__(self):
        self.value = 0
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self.value = 0

    def increment_unsafe(self) -> None:
        """
        Intentionally unsafe read-modify-write without synchronization.
        Causes lost updates when invoked concurrently by multiple threads due to context switches.
        """
        temp = self.value
        # Introduce a micro-delay to maximize probability of preemptive context switch
        time.sleep(0.0001)
        self.value = temp + 1

    def increment_safe(self) -> None:
        """
        Thread-safe critical section protected by a Mutex (Lock).
        Guarantees atomicity: no lost updates.
        """
        with self._lock:
            temp = self.value
            time.sleep(0.0001)
            self.value = temp + 1


class DeadlockDemo:
    """
    Demonstrates:
    1. Deadlock via Circular Wait (Dining Philosophers / AB-BA lock inversion).
    2. Deadlock Prevention via Global Lock Ordering (Resource Hierarchy).
    """

    def __init__(self):
        self.lock_a = threading.Lock()
        self.lock_b = threading.Lock()
        self.log_messages: List[str] = []
        self._log_lock = threading.Lock()

    def log(self, msg: str) -> None:
        with self._log_lock:
            self.log_messages.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def run_circular_wait_threads(self, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Simulates deadlock:
        Thread 1 acquires Lock A, then tries to acquire Lock B.
        Thread 2 acquires Lock B, then tries to acquire Lock A.
        Both hold one resource and wait indefinitely for the other (Deadlock).
        """
        self.log_messages.clear()
        state = {"thread1_done": False, "thread2_done": False, "deadlocked": False}

        def worker_1():
            self.log("Worker 1: Requesting Lock A...")
            self.lock_a.acquire()
            self.log("Worker 1: Acquired Lock A. Holding and sleeping...")
            time.sleep(0.2)
            self.log("Worker 1: Requesting Lock B (Wait for Worker 2)...")
            # Try acquire with timeout to avoid permanent hanging in the test demo
            acquired = self.lock_b.acquire(timeout=timeout)
            if acquired:
                self.log("Worker 1: Acquired Lock B!")
                self.lock_b.release()
                state["thread1_done"] = True
            else:
                self.log("Worker 1: DEADLOCK DETECTED (Timed out waiting for Lock B)!")
            self.lock_a.release()

        def worker_2():
            self.log("Worker 2: Requesting Lock B...")
            self.lock_b.acquire()
            self.log("Worker 2: Acquired Lock B. Holding and sleeping...")
            time.sleep(0.2)
            self.log("Worker 2: Requesting Lock A (Wait for Worker 1)...")
            acquired = self.lock_a.acquire(timeout=timeout)
            if acquired:
                self.log("Worker 2: Acquired Lock A!")
                self.lock_a.release()
                state["thread2_done"] = True
            else:
                self.log("Worker 2: DEADLOCK DETECTED (Timed out waiting for Lock A)!")
            self.lock_b.release()

        t1 = threading.Thread(target=worker_1, name="DeadlockDemo-T1")
        t2 = threading.Thread(target=worker_2, name="DeadlockDemo-T2")
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        state["deadlocked"] = not (state["thread1_done"] and state["thread2_done"])
        return {
            "deadlocked": state["deadlocked"],
            "logs": list(self.log_messages),
            "explanation": (
                "Deadlock occurred because of Circular Wait (Coffman Condition 4): "
                "Thread 1 holds Lock A waiting for Lock B, while Thread 2 holds Lock B waiting for Lock A."
            ),
        }

    def run_ordered_locks_threads(self) -> Dict[str, Any]:
        """
        Deadlock Avoidance via Resource Ordering:
        Both threads must acquire resources in a strict monotonic order: Lock A THEN Lock B.
        Circular wait is mathematically impossible.
        """
        self.log_messages.clear()
        state = {"thread1_done": False, "thread2_done": False}

        def worker_ordered(worker_id: int):
            self.log(f"Worker {worker_id}: Requesting Lock A (Hierarchy Rule 1)...")
            with self.lock_a:
                self.log(f"Worker {worker_id}: Acquired Lock A. Requesting Lock B (Hierarchy Rule 2)...")
                with self.lock_b:
                    self.log(f"Worker {worker_id}: Acquired Lock B. Executing critical section safe from deadlock!")
                    time.sleep(0.1)
                self.log(f"Worker {worker_id}: Released Lock B.")
            self.log(f"Worker {worker_id}: Released Lock A. Completed successfully!")
            state[f"thread{worker_id}_done"] = True

        t1 = threading.Thread(target=worker_ordered, args=(1,), name="AvoidDemo-T1")
        t2 = threading.Thread(target=worker_ordered, args=(2,), name="AvoidDemo-T2")
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        return {
            "deadlocked": False,
            "success": state["thread1_done"] and state["thread2_done"],
            "logs": list(self.log_messages),
            "explanation": (
                "Deadlock was avoided by enforcing Lock Hierarchy (Lock A -> Lock B). "
                "Since both threads request locks in identical order, circular dependency cannot form."
            ),
        }
