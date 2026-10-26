"""
Task Definitions and Lifecycle Management.

OS Concepts Illustrated:
- Process / Thread State Transition Model (New -> Ready -> Running -> Blocked -> Terminated)
- Process Control Block (PCB) represented here as the Task object holding metadata,
  context, priority, execution timers, and state.
- Starvation prevention via dynamic Priority Aging.
"""

import time
import uuid
import threading
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple


class TaskState(str, Enum):
    """Lifecycle states of a task, mirroring the standard OS process state lifecycle."""
    NEW = "NEW"                  # Created, awaiting admission to ready queue
    READY = "READY"              # In ready queue, eligible for CPU/worker dispatch
    RUNNING = "RUNNING"          # Actively executing on a worker thread
    BLOCKED = "BLOCKED"          # Waiting for I/O, lock, or semaphore resource
    COMPLETED = "COMPLETED"      # Execution finished successfully
    FAILED = "FAILED"            # Execution raised an unhandled exception
    CANCELLED = "CANCELLED"      # Aborted before or during execution


class TaskPriority(int, Enum):
    """Priority levels: higher value indicates higher scheduling preference."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class Task:
    """
    Encapsulates a unit of execution (analogous to an OS Process / Thread Control Block).
    
    Holds scheduling metadata, execution bounds, profiling metrics, and synchronization
    cancellation tokens.
    """

    def __init__(
        self,
        name: str,
        fn: Callable[..., Any],
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        priority: int = TaskPriority.NORMAL.value,
        estimated_duration: float = 0.5,
        max_retries: int = 0,
        timeout: Optional[float] = None,
        task_type: str = "GENERIC",
        task_id: Optional[str] = None,
    ):
        self.task_id = task_id or str(uuid.uuid4())[:8]
        self.name = name
        self.fn = fn
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.task_type = task_type
        
        # Priority Scheduling & Aging
        self.base_priority = int(priority)
        self.priority = int(priority)
        self.estimated_duration = float(estimated_duration)  # Used for SJF scheduling
        
        # Fault Tolerance
        self.max_retries = max_retries
        self.retry_count = 0
        self.timeout = timeout
        
        # Lifecycle & State
        self.state = TaskState.NEW
        self.assigned_worker: Optional[str] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.resource_held: Optional[str] = None

        # Timestamps for performance & turnaround profiling
        self.created_at = time.time()
        self.ready_at: Optional[float] = None
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        
        # Cooperative Preemption / Round Robin state
        self.cancellation_token = threading.Event()
        self.progress: float = 0.0
        self.quanta_remaining: int = 1
        self.is_sliced: bool = False

    @property
    def wait_time(self) -> float:
        """Time spent waiting in the READY queue before execution starts."""
        if self.started_at and self.ready_at:
            return max(0.0, self.started_at - self.ready_at)
        if self.ready_at:
            return max(0.0, time.time() - self.ready_at)
        return 0.0

    @property
    def execution_time(self) -> float:
        """Time spent in the RUNNING state."""
        if self.completed_at and self.started_at:
            return max(0.0, self.completed_at - self.started_at)
        if self.started_at:
            return max(0.0, time.time() - self.started_at)
        return 0.0

    @property
    def turnaround_time(self) -> float:
        """Total time from admission to ready queue until completion (Wait + Service)."""
        if self.completed_at and self.ready_at:
            return max(0.0, self.completed_at - self.ready_at)
        if self.ready_at:
            return max(0.0, time.time() - self.ready_at)
        return 0.0

    def calculate_aged_priority(self, aging_factor: float = 0.5) -> float:
        """
        Calculates dynamic effective priority using priority aging to avoid starvation.
        Effective Priority = Base Priority + (Wait Time in seconds * aging_factor)
        """
        effective = self.base_priority + (self.wait_time * aging_factor)
        self.priority = round(effective, 2)
        return self.priority

    def cancel(self) -> bool:
        """Signals task cancellation."""
        if self.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            return False
        self.cancellation_token.set()
        if self.state in (TaskState.NEW, TaskState.READY):
            self.state = TaskState.CANCELLED
            self.completed_at = time.time()
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serializes task status into JSON-friendly dictionary."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type,
            "priority": self.priority,
            "base_priority": self.base_priority,
            "estimated_duration": self.estimated_duration,
            "state": self.state.value,
            "assigned_worker": self.assigned_worker,
            "wait_time": round(self.wait_time, 3),
            "execution_time": round(self.execution_time, 3),
            "turnaround_time": round(self.turnaround_time, 3),
            "progress": round(self.progress, 2),
            "retries": self.retry_count,
            "max_retries": self.max_retries,
            "error": self.error,
            "resource_held": self.resource_held,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
