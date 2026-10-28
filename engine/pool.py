"""
Custom Multithreaded Thread Pool with Dynamic Scaling.

OS Concepts Illustrated:
- Thread Pool Architecture: Eliminates thread creation/destruction overhead by reusing
  worker threads across multiple short-lived jobs.
- Producer-Consumer Pattern: Tasks submitted to a bounded priority ready queue;
  worker threads consume tasks concurrently.
- Thread Synchronization: Uses Thread, Lock, Condition, and Event primitives.
- Dynamic Resource Provisioning: Autoscaling worker count based on queue backlog and load.
- Fault Tolerance & Lifecycle: Timeouts, retries, cooperative cancellation, and graceful teardown.
"""

import time
import inspect
import threading
from typing import Any, Callable, Dict, List, Optional, Set
from engine.task import Task, TaskState
from engine.scheduler import Scheduler, SchedulingPolicy


class WorkerThread(threading.Thread):
    """
    Dedicated OS-level worker thread that continuously pulls tasks from the scheduler.
    """

    def __init__(self, worker_id: int, pool: "ThreadPool"):
        super().__init__(name=f"Worker-{worker_id}")
        self.worker_id = worker_id
        self.pool = pool
        self.current_task: Optional[Task] = None
        self.is_busy = False
        self.is_running = True
        self.last_busy_time = time.time()
        self.daemon = True  # Avoid blocking interpreter exit if abnormal termination

    def run(self) -> None:
        """Main worker execution loop."""
        while self.is_running and not self.pool.is_shutdown:
            # 1. Pause support: block if the pool is paused
            self.pool.pause_event.wait()

            # 2. Dynamic scaling down: terminate if idle and worker count exceeds minimum
            if self.pool.dynamic_scaling and len(self.pool.workers) > self.pool.min_workers:
                idle_duration = time.time() - self.last_busy_time
                if idle_duration > self.pool.idle_timeout and self.pool.scheduler.size() == 0:
                    with self.pool._lock:
                        if len(self.pool.workers) > self.pool.min_workers:
                            self.pool._unregister_worker_locked(self)
                            self.is_running = False
                            self.pool.log_event("SCALING", f"{self.name} scaled down (idle for {idle_duration:.1f}s)")
                            break

            # 3. Pull next task from the scheduler (blocks on condition variable)
            task = self.pool.scheduler.get_task(timeout=0.5)
            if not task:
                continue

            # 4. Check for pre-execution cancellation
            if task.cancellation_token.is_set():
                task.state = TaskState.CANCELLED
                task.completed_at = time.time()
                self.pool.on_task_finished(task)
                continue

            # 5. Execute task
            self.is_busy = True
            self.current_task = task
            task.assigned_worker = self.name
            task.state = TaskState.RUNNING
            task.started_at = time.time()
            self.pool.log_event("TASK_START", f"{self.name} started task [{task.task_id}] '{task.name}'")

            try:
                # Pass task_ref if accepted by the task function
                sig = inspect.signature(task.fn)
                kwargs = dict(task.kwargs)
                if "task_ref" in sig.parameters:
                    kwargs["task_ref"] = task

                result = task.fn(*task.args, **kwargs)

                # Check if this is a cooperative Round Robin sliced quantum
                if isinstance(result, dict) and result.get("finished") is False:
                    # Task yielded remaining quantum; requeue for Round Robin fairness
                    self.pool.log_event("TASK_YIELD", f"Task [{task.task_id}] yielded time quantum, requeueing.")
                    self.pool.scheduler.requeue_task(task)
                elif task.cancellation_token.is_set():
                    task.state = TaskState.CANCELLED
                    task.completed_at = time.time()
                    self.pool.log_event("TASK_CANCEL", f"Task [{task.task_id}] was cancelled during execution.")
                    self.pool.on_task_finished(task)
                else:
                    task.result = result
                    task.state = TaskState.COMPLETED
                    task.completed_at = time.time()
                    self.pool.log_event("TASK_DONE", f"{self.name} completed [{task.task_id}] in {task.execution_time:.3f}s")
                    self.pool.on_task_finished(task)

            except Exception as ex:
                # Fault Tolerance & Retries
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    self.pool.log_event("TASK_RETRY", f"Task [{task.task_id}] failed ({ex}), retry {task.retry_count}/{task.max_retries}")
                    self.pool.scheduler.requeue_task(task)
                else:
                    task.state = TaskState.FAILED
                    task.error = str(ex)
                    task.completed_at = time.time()
                    self.pool.log_event("TASK_FAIL", f"Task [{task.task_id}] failed: {ex}")
                    self.pool.on_task_finished(task)

            finally:
                self.is_busy = False
                self.current_task = None
                self.last_busy_time = time.time()


class ThreadPool:
    """
    Multithreaded Task Execution Engine managing real OS worker threads.
    """

    def __init__(
        self,
        min_workers: int = 4,
        max_workers: int = 12,
        initial_workers: int = 4,
        policy: str = SchedulingPolicy.PRIORITY,
        dynamic_scaling: bool = True,
        idle_timeout: float = 3.0,
    ):
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.dynamic_scaling = dynamic_scaling
        self.idle_timeout = idle_timeout
        self.is_shutdown = False

        self._lock = threading.RLock()
        self.pause_event = threading.Event()
        self.pause_event.set()  # Initially unpaused

        self.scheduler = Scheduler(policy=policy)
        self.workers: List[WorkerThread] = []
        self._worker_counter = 0

        # Registry of all tasks submitted to the engine
        self._all_tasks: Dict[str, Task] = {}
        self._completed_tasks: List[Task] = []
        self.event_callbacks: List[Callable[[str, str], None]] = []

        # Boot initial workers
        with self._lock:
            for _ in range(initial_workers):
                self._spawn_worker_locked()

        # Autoscaler daemon thread
        self._scaler_thread = threading.Thread(target=self._autoscaler_loop, name="ThreadPool-Autoscaler", daemon=True)
        self._scaler_thread.start()

    def _spawn_worker_locked(self) -> WorkerThread:
        """Spawns and starts a new worker thread within the pool."""
        self._worker_counter += 1
        worker = WorkerThread(self._worker_counter, self)
        self.workers.append(worker)
        worker.start()
        return worker

    def unregister_worker(self, worker: WorkerThread) -> None:
        """Removes a worker thread from active pool."""
        with self._lock:
            self._unregister_worker_locked(worker)

    def _unregister_worker_locked(self, worker: WorkerThread) -> None:
        """Removes a worker thread from active pool (caller holds self._lock)."""
        if worker in self.workers:
            self.workers.remove(worker)

    def submit(self, task: Task) -> str:
        """
        Submits a task into the thread pool.
        OS Concept: Producer thread enqueueing into Ready Queue.
        """
        if self.is_shutdown:
            raise RuntimeError("Cannot submit task to a terminated ThreadPool.")

        with self._lock:
            self._all_tasks[task.task_id] = task

        self.scheduler.add_task(task)
        self.log_event("TASK_SUBMIT", f"Task [{task.task_id}] '{task.name}' submitted (Priority: {task.priority})")

        # Dynamic Scale Up: if queue is backing up and headroom exists, spawn worker immediately
        if self.dynamic_scaling:
            with self._lock:
                busy_count = sum(1 for w in self.workers if w.is_busy)
                queue_len = self.scheduler.size()
                if (busy_count >= len(self.workers) or queue_len >= len(self.workers)) and len(self.workers) < self.max_workers:
                    worker = self._spawn_worker_locked()
                    self.log_event("SCALING", f"Autoscaled UP: spawned {worker.name} (Active: {len(self.workers)})")

        return task.task_id

    def cancel_task(self, task_id: str) -> bool:
        """Cancels a pending or running task."""
        with self._lock:
            task = self._all_tasks.get(task_id)
        if not task:
            return False

        # Attempt to remove from scheduler ready queue
        removed = self.scheduler.remove_task(task_id)
        if removed:
            removed.state = TaskState.CANCELLED
            removed.completed_at = time.time()
            self.on_task_finished(removed)
            self.log_event("TASK_CANCEL", f"Task [{task_id}] cancelled before execution.")
            return True

        # If already executing, signal cancellation token
        cancelled = task.cancel()
        if cancelled:
            self.log_event("TASK_CANCEL", f"Cancellation token flagged for running Task [{task_id}].")
        return cancelled

    def pause(self) -> None:
        """Pauses worker dispatch."""
        self.pause_event.clear()
        self.log_event("CONTROL", "ThreadPool paused.")

    def resume(self) -> None:
        """Resumes worker dispatch."""
        self.pause_event.set()
        self.log_event("CONTROL", "ThreadPool resumed.")

    def set_worker_count(self, count: int) -> int:
        """Manually adjusts the active worker count."""
        target = max(1, min(count, self.max_workers))
        with self._lock:
            current = len(self.workers)
            if target > current:
                for _ in range(target - current):
                    self._spawn_worker_locked()
                self.log_event("CONTROL", f"Worker count scaled up manually to {target}.")
            elif target < current:
                # Mark excess workers to stop
                excess = current - target
                for w in self.workers[-excess:]:
                    w.is_running = False
                self.scheduler.notify_all()
                self.log_event("CONTROL", f"Worker count set to scale down to {target}.")
        return target

    def set_policy(self, policy: str) -> None:
        """Updates the active scheduling policy."""
        self.scheduler.set_policy(policy)
        self.log_event("CONTROL", f"Scheduling policy switched to {policy}.")

    def on_task_finished(self, task: Task) -> None:
        """Invoked when a task reaches a terminal state."""
        with self._lock:
            self._completed_tasks.append(task)

    def log_event(self, category: str, message: str) -> None:
        """Dispatches an event log message to all listeners."""
        for cb in self.event_callbacks:
            try:
                cb(category, message)
            except Exception:
                pass

    def _autoscaler_loop(self) -> None:
        """Periodic background evaluation for scaling worker pool."""
        while not self.is_shutdown:
            time.sleep(1.0)
            if not self.dynamic_scaling or not self.pause_event.is_set():
                continue

            with self._lock:
                queue_len = self.scheduler.size()
                busy_count = sum(1 for w in self.workers if w.is_busy)
                total_workers = len(self.workers)

                # Scale UP condition: backlog present and all current workers busy
                if queue_len > 1 and busy_count == total_workers and total_workers < self.max_workers:
                    worker = self._spawn_worker_locked()
                    self.log_event("SCALING", f"Backlog detected ({queue_len} ready). Autoscaled UP to {len(self.workers)} workers.")

    def shutdown(self, wait: bool = True, timeout: float = 5.0) -> None:
        """
        Gracefully terminates the thread pool.
        OS Concept: Orderly Process / Thread Termination.
        """
        self.is_shutdown = True
        self.pause_event.set()  # Unblock any paused workers
        
        # Stop all workers
        with self._lock:
            for w in self.workers:
                w.is_running = False

        self.scheduler.notify_all()

        if wait:
            deadline = time.time() + timeout
            for w in list(self.workers):
                remaining = max(0.1, deadline - time.time())
                w.join(timeout=remaining)
            
            with self._lock:
                self.workers = [w for w in self.workers if w.is_alive()]

        self.log_event("CONTROL", f"ThreadPool shutdown completed. Residual active threads: {len(self.workers)}")

    def get_workers_info(self) -> List[Dict[str, Any]]:
        """Returns status snapshot of each worker thread."""
        with self._lock:
            info = []
            for w in self.workers:
                info.append({
                    "id": w.worker_id,
                    "name": w.name,
                    "is_busy": w.is_busy,
                    "is_alive": w.is_alive(),
                    "current_task": w.current_task.to_dict() if w.current_task else None,
                })
            return info

    def get_all_tasks(self) -> List[Task]:
        """Returns all registered tasks."""
        with self._lock:
            return list(self._all_tasks.values())
