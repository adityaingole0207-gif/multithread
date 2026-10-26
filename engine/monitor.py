"""
Telemetry, Performance Profiling, and Resource Monitor.

OS Concepts Illustrated:
- System Telemetry & Performance Counters (CPU core load, Memory footprints, OS Thread count).
- Execution metrics: Wait time, Turnaround time, Response time, Throughput (tasks/sec).
- Worker Thread Utilization & Scheduling Gantt Timeline.
- Circular Event Logging.
"""

import time
import os
import collections
import threading
from typing import Any, Deque, Dict, List, Optional
import psutil
from engine.pool import ThreadPool
from engine.task import Task, TaskState


class EventLog:
    def __init__(self, category: str, message: str):
        self.timestamp = time.strftime("%H:%M:%S")
        self.category = category
        self.message = message

    def to_dict(self) -> Dict[str, str]:
        return {
            "timestamp": self.timestamp,
            "category": self.category,
            "message": self.message,
        }


class GanttEntry:
    def __init__(self, task_id: str, name: str, worker: str, start: float, end: float, state: str):
        self.task_id = task_id
        self.name = name
        self.worker = worker
        self.start = start
        self.end = end
        self.duration = max(0.001, end - start)
        self.state = state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "worker": self.worker,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "state": self.state,
        }


class ResourceMonitor:
    """
    Monitors OS system statistics and ThreadPool operational metrics.
    """

    def __init__(self, pool: ThreadPool, history_len: int = 60, max_events: int = 200, max_gantt: int = 150):
        self.pool = pool
        self.process = psutil.Process(os.getpid())
        self._lock = threading.Lock()

        # Telemetry history buffers
        self.history_len = history_len
        self.history_timestamps: Deque[str] = collections.deque(maxlen=history_len)
        self.history_cpu: Deque[float] = collections.deque(maxlen=history_len)
        self.history_memory: Deque[float] = collections.deque(maxlen=history_len)
        self.history_throughput: Deque[float] = collections.deque(maxlen=history_len)
        self.history_queue_len: Deque[int] = collections.deque(maxlen=history_len)

        # Event log and Gantt records
        self.events: Deque[EventLog] = collections.deque(maxlen=max_events)
        self.gantt_records: Deque[GanttEntry] = collections.deque(maxlen=max_gantt)

        # Throughput computation counters
        self._last_completed_count = 0
        self._last_sample_time = time.time()

        # Wire logging callback into pool
        self.pool.event_callbacks.append(self.record_event)

        # Baseline CPU reading
        try:
            self.process.cpu_percent(interval=None)
        except Exception:
            pass

    def record_event(self, category: str, message: str) -> None:
        """Records a new system or task lifecycle event."""
        with self._lock:
            self.events.append(EventLog(category, message))

    def record_task_completion(self, task: Task) -> None:
        """Appends finished task to the Gantt chart timeline."""
        if not task.assigned_worker or not task.started_at:
            return
        end_time = task.completed_at or time.time()
        with self._lock:
            self.gantt_records.append(
                GanttEntry(
                    task_id=task.task_id,
                    name=task.name,
                    worker=task.assigned_worker,
                    start=task.started_at,
                    end=end_time,
                    state=task.state.value,
                )
            )

    def sample_metrics(self) -> Dict[str, Any]:
        """
        Samples hardware and software metrics and updates historical telemetry.
        """
        now = time.time()
        time_str = time.strftime("%H:%M:%S")

        # Hardware & Process metrics
        try:
            cpu_pct = round(self.process.cpu_percent(interval=None), 1)
            mem_info = self.process.memory_info()
            mem_mb = round(mem_info.rss / (1024 * 1024), 1)
            mem_pct = round(self.process.memory_percent(), 1)
            os_threads = self.process.num_threads()
        except Exception:
            cpu_pct = 0.0
            mem_mb = 0.0
            mem_pct = 0.0
            os_threads = threading.active_count()

        # Engine metrics
        workers_info = self.pool.get_workers_info()
        total_workers = len(workers_info)
        active_workers = sum(1 for w in workers_info if w["is_busy"])
        idle_workers = total_workers - active_workers
        queue_len = self.pool.scheduler.size()
        worker_utilization = round((active_workers / total_workers * 100), 1) if total_workers > 0 else 0.0

        all_tasks = self.pool.get_all_tasks()
        completed_tasks = [t for t in all_tasks if t.state == TaskState.COMPLETED]
        failed_tasks = [t for t in all_tasks if t.state == TaskState.FAILED]
        cancelled_tasks = [t for t in all_tasks if t.state == TaskState.CANCELLED]

        # Sync finished tasks with Gantt timeline
        with self._lock:
            recorded_ids = {g.task_id for g in self.gantt_records}
            for t in completed_tasks + failed_tasks + cancelled_tasks:
                if t.task_id not in recorded_ids and t.started_at:
                    self.gantt_records.append(
                        GanttEntry(
                            task_id=t.task_id,
                            name=t.name,
                            worker=t.assigned_worker or "Unknown",
                            start=t.started_at,
                            end=t.completed_at or now,
                            state=t.state.value,
                        )
                    )

        # Average wait and turnaround
        if completed_tasks:
            avg_wait = round(sum(t.wait_time for t in completed_tasks) / len(completed_tasks), 3)
            avg_turnaround = round(sum(t.turnaround_time for t in completed_tasks) / len(completed_tasks), 3)
        else:
            avg_wait = 0.0
            avg_turnaround = 0.0

        # Throughput (tasks/sec) over delta
        delta_t = max(0.001, now - self._last_sample_time)
        delta_done = len(completed_tasks) - self._last_completed_count
        throughput = round(max(0.0, delta_done / delta_t), 2)
        self._last_sample_time = now
        self._last_completed_count = len(completed_tasks)

        # Update historical series
        with self._lock:
            self.history_timestamps.append(time_str)
            self.history_cpu.append(cpu_pct)
            self.history_memory.append(mem_mb)
            self.history_throughput.append(throughput)
            self.history_queue_len.append(queue_len)

            events_snap = [e.to_dict() for e in list(self.events)[-30:]]
            gantt_snap = [g.to_dict() for g in list(self.gantt_records)[-40:]]

        return {
            "timestamp": time_str,
            "cpu_percent": cpu_pct,
            "memory_mb": mem_mb,
            "memory_percent": mem_pct,
            "os_threads": os_threads,
            "active_workers": active_workers,
            "idle_workers": idle_workers,
            "total_workers": total_workers,
            "worker_utilization": worker_utilization,
            "queue_length": queue_len,
            "tasks_per_second": throughput,
            "total_tasks": len(all_tasks),
            "completed_count": len(completed_tasks),
            "failed_count": len(failed_tasks),
            "cancelled_count": len(cancelled_tasks),
            "avg_wait_time": avg_wait,
            "avg_turnaround_time": avg_turnaround,
            "policy": self.pool.scheduler.policy,
            "is_paused": not self.pool.pause_event.is_set(),
            "history": {
                "timestamps": list(self.history_timestamps),
                "cpu": list(self.history_cpu),
                "memory": list(self.history_memory),
                "throughput": list(self.history_throughput),
                "queue": list(self.history_queue_len),
            },
            "events": events_snap,
            "gantt": gantt_snap,
            "workers": workers_info,
        }
