"""
Unit tests for CPU Scheduling Policies.
Tests:
- FCFS ordering
- Priority ordering
- Starvation prevention via Dynamic Priority Aging
- SJF ordering
- Round Robin requeueing
"""

import time
import pytest
from engine.task import Task, TaskState, TaskPriority
from engine.scheduler import Scheduler, SchedulingPolicy


def dummy_fn():
    return 42


def test_fcfs_scheduling():
    """Verify tasks are served First-Come, First-Served."""
    scheduler = Scheduler(policy=SchedulingPolicy.FCFS)
    
    t1 = Task(name="T1", fn=dummy_fn)
    time.sleep(0.01)
    t2 = Task(name="T2", fn=dummy_fn)
    time.sleep(0.01)
    t3 = Task(name="T3", fn=dummy_fn)

    scheduler.add_task(t1)
    scheduler.add_task(t2)
    scheduler.add_task(t3)

    assert scheduler.get_task().name == "T1"
    assert scheduler.get_task().name == "T2"
    assert scheduler.get_task().name == "T3"


def test_priority_scheduling():
    """Verify tasks are served in order of priority (higher first)."""
    scheduler = Scheduler(policy=SchedulingPolicy.PRIORITY)

    t_low = Task(name="Low", fn=dummy_fn, priority=TaskPriority.LOW.value)
    t_high = Task(name="High", fn=dummy_fn, priority=TaskPriority.HIGH.value)
    t_crit = Task(name="Critical", fn=dummy_fn, priority=TaskPriority.CRITICAL.value)

    scheduler.add_task(t_low)
    scheduler.add_task(t_high)
    scheduler.add_task(t_crit)

    assert scheduler.get_task().name == "Critical"
    assert scheduler.get_task().name == "High"
    assert scheduler.get_task().name == "Low"


def test_priority_aging_prevents_starvation():
    """Verify that older tasks gain priority over time through dynamic aging."""
    scheduler = Scheduler(policy=SchedulingPolicy.PRIORITY, aging_interval=0.05, aging_factor=50.0)

    # Low priority task arrives early
    t_old_low = Task(name="OldLow", fn=dummy_fn, priority=1)
    scheduler.add_task(t_old_low)
    
    # Wait so wait_time > 0.08s => aged priority increases by > 4 => total > 5 > 2
    time.sleep(0.08)
    t_new_med = Task(name="NewMed", fn=dummy_fn, priority=2)
    scheduler.add_task(t_new_med)

    first = scheduler.get_task()
    assert first.name == "OldLow", f"Expected aged task to jump ahead, got {first.name}"


def test_sjf_scheduling():
    """Verify Shortest Job First schedules shortest estimated duration first."""
    scheduler = Scheduler(policy=SchedulingPolicy.SJF)

    t_long = Task(name="LongJob", fn=dummy_fn, estimated_duration=5.0)
    t_short = Task(name="ShortJob", fn=dummy_fn, estimated_duration=0.2)
    t_mid = Task(name="MidJob", fn=dummy_fn, estimated_duration=1.5)

    scheduler.add_task(t_long)
    scheduler.add_task(t_short)
    scheduler.add_task(t_mid)

    assert scheduler.get_task().name == "ShortJob"
    assert scheduler.get_task().name == "MidJob"
    assert scheduler.get_task().name == "LongJob"


def test_round_robin_requeue():
    """Verify Round Robin policy correctly requeues yielded tasks to back of queue."""
    scheduler = Scheduler(policy=SchedulingPolicy.ROUND_ROBIN)

    t1 = Task(name="T1", fn=dummy_fn)
    t2 = Task(name="T2", fn=dummy_fn)

    scheduler.add_task(t1)
    scheduler.add_task(t2)

    popped = scheduler.get_task()
    assert popped.name == "T1"
    
    # Requeue T1 to back
    scheduler.requeue_task(popped)
    
    assert scheduler.get_task().name == "T2"
    assert scheduler.get_task().name == "T1"
