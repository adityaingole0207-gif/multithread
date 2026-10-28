"""
Task Scheduling Policies.

OS Concepts Illustrated:
- CPU Scheduling Algorithms:
  1. First-Come, First-Served (FCFS) [Non-preemptive]
  2. Priority Scheduling with Dynamic Aging (Prevents Starvation)
  3. Shortest Job First (SJF) [Optimal average wait time, risk of starvation]
  4. Round Robin (RR) with Time Quanta (Fairness and responsiveness via cooperative preemption)
"""

import time
import heapq
import threading
from typing import List, Optional, Tuple
from engine.task import Task, TaskState


class SchedulingPolicy:
    FCFS = "FCFS"
    PRIORITY = "PRIORITY"
    SJF = "SJF"
    ROUND_ROBIN = "ROUND_ROBIN"


class Scheduler:
    """
    Thread-safe Task Scheduler managing the READY queue with pluggable scheduling policies.
    Guarded by a Condition variable to coordinate Producer (task submitter) and
    Consumer (worker threads).
    """

    def __init__(self, policy: str = SchedulingPolicy.PRIORITY, aging_interval: float = 2.0, aging_factor: float = 1.0, time_quantum: float = 0.2):
        self._lock = threading.RLock()
        self._not_empty = threading.Condition(self._lock)
        self.policy = policy
        self.aging_interval = aging_interval
        self.aging_factor = aging_factor
        self.time_quantum = time_quantum
        
        # Internal storage
        self._tasks: List[Task] = []
        self._sequence: int = 0  # Tie-breaker for stable sorting in priority queues
        self._last_aging_time = time.time()

    def set_policy(self, policy: str) -> None:
        """Dynamically switch scheduling policy at runtime."""
        with self._lock:
            self.policy = policy
            self._reorder_locked()

    def add_task(self, task: Task) -> None:
        """
        Submits a task into the READY queue.
        Notifies waiting worker threads via Condition variable.
        """
        with self._lock:
            task.state = TaskState.READY
            task.ready_at = time.time()
            self._tasks.append(task)
            self._sequence += 1
            self._reorder_locked()
            self._not_empty.notify()

    def get_task(self, timeout: Optional[float] = None) -> Optional[Task]:
        """
        Pulls the next eligible task according to the active scheduling policy.
        Blocks on the Condition variable if queue is empty.
        """
        with self._lock:
            deadline = time.time() + timeout if timeout else None
            
            while not self._tasks:
                if timeout is not None:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        return None
                    self._not_empty.wait(timeout=remaining)
                else:
                    self._not_empty.wait()

            # Apply priority aging periodically to avoid starvation for Priority/SJF
            now = time.time()
            if now - self._last_aging_time >= self.aging_interval:
                self._apply_aging_locked()
                self._last_aging_time = now

            # Pop the first task in the prioritized/ordered list
            task = self._tasks.pop(0)
            return task

    def requeue_task(self, task: Task) -> None:
        """Re-adds a yielded or pre-empted task back into the ready queue (Round Robin)."""
        with self._lock:
            task.state = TaskState.READY
            self._tasks.append(task)
            if self.policy != SchedulingPolicy.ROUND_ROBIN:
                self._reorder_locked()
            self._not_empty.notify()

    def remove_task(self, task_id: str) -> Optional[Task]:
        """Removes a task from the ready queue (e.g. on cancellation)."""
        with self._lock:
            for i, task in enumerate(self._tasks):
                if task.task_id == task_id:
                    removed = self._tasks.pop(i)
                    return removed
            return None

    def get_ready_tasks(self) -> List[Task]:
        """Returns a snapshot of currently queued tasks."""
        with self._lock:
            return list(self._tasks)

    def size(self) -> int:
        """Returns the number of ready tasks."""
        with self._lock:
            return len(self._tasks)

    def notify_all(self) -> None:
        """Wakes up all waiting threads (used during shutdown)."""
        with self._lock:
            self._not_empty.notify_all()

    def _apply_aging_locked(self) -> None:
        """
        OS Concept: Starvation Prevention via Aging.
        Increases the priority of older waiting tasks proportionally to their wait time.
        """
        for task in self._tasks:
            task.calculate_aged_priority(aging_factor=self.aging_factor)
        self._reorder_locked()

    def _reorder_locked(self) -> None:
        """Re-sorts the queue in place based on the active policy."""
        if not self._tasks:
            return

        if self.policy == SchedulingPolicy.FCFS:
            # First-Come First-Served: sorted by ready_at timestamp
            self._tasks.sort(key=lambda t: t.ready_at or 0.0)

        elif self.policy == SchedulingPolicy.PRIORITY:
            # Highest priority first (higher value = higher priority), tie-break on arrival
            self._tasks.sort(key=lambda t: (-t.priority, t.ready_at or 0.0))

        elif self.policy == SchedulingPolicy.SJF:
            # Shortest Job First: estimated burst duration ascending
            self._tasks.sort(key=lambda t: (t.estimated_duration, t.ready_at or 0.0))

        elif self.policy == SchedulingPolicy.ROUND_ROBIN:
            # In pure Round Robin, new tasks append to the tail; order remains FIFO
            pass
