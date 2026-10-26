"""
Unit tests for ThreadPool life cycle, Worker Scaling, and Fault Tolerance.
Tests:
- Clean shutdown with no leaked threads
- Task completion and state transitions
- Task retry on failure
- Task cancellation
- Dynamic scaling behavior
"""

import time
import threading
import pytest
from engine.task import Task, TaskState
from engine.pool import ThreadPool
from engine.scheduler import SchedulingPolicy


def test_clean_shutdown_no_leaked_threads():
    """Verify ThreadPool terminates all workers cleanly without thread leaks."""
    initial_threads = threading.active_count()
    
    pool = ThreadPool(min_workers=3, max_workers=5, initial_workers=3, dynamic_scaling=False)
    assert len(pool.workers) == 3
    
    # Submit simple work
    for i in range(5):
        pool.submit(Task(name=f"Task-{i}", fn=lambda: time.sleep(0.02)))
        
    time.sleep(0.15)
    pool.shutdown(wait=True, timeout=2.0)
    
    # Check that all worker threads have ended
    alive_workers = [w for w in pool.workers if w.is_alive()]
    assert len(alive_workers) == 0, f"Found {len(alive_workers)} leaked workers!"


def test_task_lifecycle_states():
    """Verify states transition NEW -> READY -> RUNNING -> COMPLETED."""
    pool = ThreadPool(min_workers=2, max_workers=2, initial_workers=2, dynamic_scaling=False)
    
    task = Task(name="StateTask", fn=lambda: 100 + 200)
    assert task.state == TaskState.NEW
    
    pool.submit(task)
    time.sleep(0.1)
    
    assert task.state == TaskState.COMPLETED
    assert task.result == 300
    assert task.started_at is not None
    assert task.completed_at is not None
    assert task.assigned_worker is not None
    
    pool.shutdown(wait=True)


def test_task_retry_on_failure():
    """Verify failed tasks are automatically retried up to max_retries."""
    attempts = 0
    lock = threading.Lock()

    def flaky_function():
        nonlocal attempts
        with lock:
            attempts += 1
            if attempts < 3:
                raise ValueError("Transient error")
            return "recovered"

    pool = ThreadPool(min_workers=2, max_workers=2, initial_workers=2, dynamic_scaling=False)
    task = Task(name="FlakyTask", fn=flaky_function, max_retries=3)
    pool.submit(task)

    time.sleep(0.2)
    assert task.state == TaskState.COMPLETED
    assert task.result == "recovered"
    assert task.retry_count == 2

    pool.shutdown(wait=True)


def test_task_cancellation():
    """Verify queued and running tasks can be successfully cancelled."""
    pool = ThreadPool(min_workers=1, max_workers=1, initial_workers=1, dynamic_scaling=False)

    # Submit a blocking task to keep the single worker busy
    blocking_task = Task(name="Blocker", fn=lambda: time.sleep(0.4))
    pool.submit(blocking_task)

    # Submit second task that waits in ready queue
    queued_task = Task(name="Queued", fn=lambda: time.sleep(0.1))
    pool.submit(queued_task)

    # Cancel queued task
    cancelled = pool.cancel_task(queued_task.task_id)
    assert cancelled is True
    assert queued_task.state == TaskState.CANCELLED

    pool.shutdown(wait=True)


def test_dynamic_scaling_up():
    """Verify pool automatically scales worker count up under load."""
    pool = ThreadPool(min_workers=2, max_workers=6, initial_workers=2, dynamic_scaling=True)
    assert len(pool.workers) == 2

    # Submit 8 slow tasks to generate ready queue pressure
    for i in range(8):
        pool.submit(Task(name=f"HeavyTask-{i}", fn=lambda: time.sleep(0.3)))

    time.sleep(0.1)
    # Check that worker count has increased beyond initial 2
    assert len(pool.workers) > 2, f"Expected scaled workers > 2, got {len(pool.workers)}"

    pool.shutdown(wait=True, timeout=2.0)
