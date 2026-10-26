"""
Flask Application and REST / SSE API Routes.

OS Concepts Illustrated:
- Real-time Operating System Telemetry Streaming via Server-Sent Events (SSE).
- RESTful process/task control endpoints (Submit, Pause, Resume, Reset, Preemption).
- Interactive Concurrency Experimentation (Race Condition, Deadlock Avoidance, Semaphore DB Pool).
"""

import os
import time
import json
from flask import Flask, Response, jsonify, render_template, request
from engine.pool import ThreadPool
from engine.task import Task, TaskPriority, TaskState
from engine.scheduler import SchedulingPolicy
from engine.monitor import ResourceMonitor
from engine.resources import SharedResourcePool
from benchmarks.runner import BenchmarkSuite
from benchmarks.sync_demos import run_race_condition_demo, run_deadlock_demo
from tasks.task_types import (
    cpu_matrix_multiplication,
    cpu_prime_calculation,
    cpu_file_hashing,
    io_simulated_network,
    io_simulated_disk,
    mixed_word_count,
    mixed_image_processing,
    cooperative_quanta_task,
    database_query_task,
    faulty_task,
)

# Global engine instances managed by Flask
pool = ThreadPool(min_workers=4, max_workers=12, initial_workers=4, dynamic_scaling=True)
monitor = ResourceMonitor(pool)
db_resource_pool = SharedResourcePool(name="DB_Conn_Pool", capacity=3)
latest_benchmark_results = []


def create_app() -> Flask:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/benchmark")
    def benchmark_view():
        return render_template("benchmark.html")

    # ---------------- SSE METRICS STREAM ----------------
    @app.route("/api/metrics/stream")
    def metrics_stream():
        """Server-Sent Events endpoint streaming telemetry at 1 Hz."""
        def event_stream():
            while True:
                metrics = monitor.sample_metrics()
                # Append resource pool status
                metrics["resource_pool"] = db_resource_pool.get_status()
                yield f"data: {json.dumps(metrics)}\n\n"
                time.sleep(1.0)

        return Response(event_stream(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        })

    @app.route("/api/metrics")
    def get_metrics():
        metrics = monitor.sample_metrics()
        metrics["resource_pool"] = db_resource_pool.get_status()
        return jsonify(metrics)

    # ---------------- TASK SUBMISSION & MANAGEMENT ----------------
    @app.route("/api/tasks", methods=["GET"])
    def list_tasks():
        tasks = [t.to_dict() for t in pool.get_all_tasks()]
        return jsonify(tasks)

    @app.route("/api/tasks/submit", methods=["POST"])
    def submit_task():
        data = request.get_json() or {}
        task_type = data.get("task_type", "cpu_matrix")
        batch_size = int(data.get("count", 1))
        priority = int(data.get("priority", TaskPriority.NORMAL.value))
        retries = int(data.get("retries", 0))

        submitted_ids = []
        for i in range(batch_size):
            task_name = f"{task_type.upper()}_{i+1}"
            
            # Map task types to real executable callables
            if task_type == "cpu_matrix":
                fn = cpu_matrix_multiplication
                args = (60,)
                est = 0.4
            elif task_type == "cpu_prime":
                fn = cpu_prime_calculation
                args = (12000,)
                est = 0.35
            elif task_type == "cpu_hash":
                fn = cpu_file_hashing
                args = (400,)
                est = 0.25
            elif task_type == "io_network":
                fn = io_simulated_network
                args = (0.35,)
                est = 0.35
            elif task_type == "io_disk":
                fn = io_simulated_disk
                args = (0.3,)
                est = 0.3
            elif task_type == "mixed_word":
                fn = mixed_word_count
                args = (1500,)
                est = 0.3
            elif task_type == "mixed_image":
                fn = mixed_image_processing
                args = (45,)
                est = 0.35
            elif task_type == "round_robin_slice":
                fn = cooperative_quanta_task
                args = (4, 0.1)
                est = 0.4
            elif task_type == "semaphore_db":
                fn = database_query_task
                args = (db_resource_pool, 0.4)
                est = 0.4
            elif task_type == "faulty":
                fn = faulty_task
                args = (0.6,)
                est = 0.15
            else:
                fn = io_simulated_network
                args = (0.2,)
                est = 0.2

            task = Task(
                name=task_name,
                fn=fn,
                args=args,
                priority=priority,
                estimated_duration=est,
                max_retries=retries,
                task_type=task_type,
            )
            tid = pool.submit(task)
            submitted_ids.append(tid)

        return jsonify({
            "status": "success",
            "submitted_count": len(submitted_ids),
            "task_ids": submitted_ids,
        })

    @app.route("/api/tasks/<task_id>/cancel", methods=["POST"])
    def cancel_task(task_id: str):
        success = pool.cancel_task(task_id)
        return jsonify({"task_id": task_id, "cancelled": success})

    # ---------------- ENGINE CONTROLS ----------------
    @app.route("/api/control/pause", methods=["POST"])
    def pause_engine():
        pool.pause()
        return jsonify({"status": "paused", "is_paused": True})

    @app.route("/api/control/resume", methods=["POST"])
    def resume_engine():
        pool.resume()
        return jsonify({"status": "resumed", "is_paused": False})

    @app.route("/api/control/reset", methods=["POST"])
    def reset_engine():
        global pool, monitor
        pool.shutdown(wait=True, timeout=1.0)
        policy = pool.scheduler.policy
        pool = ThreadPool(min_workers=4, max_workers=12, initial_workers=4, policy=policy, dynamic_scaling=True)
        monitor = ResourceMonitor(pool)
        return jsonify({"status": "reset", "message": "Engine reset and cleared."})

    @app.route("/api/control/policy", methods=["POST"])
    def update_policy():
        data = request.get_json() or {}
        policy = data.get("policy", SchedulingPolicy.PRIORITY)
        pool.set_policy(policy)
        return jsonify({"status": "updated", "policy": policy})

    @app.route("/api/control/workers", methods=["POST"])
    def update_workers():
        data = request.get_json() or {}
        if "count" in data:
            count = int(data["count"])
            active = pool.set_worker_count(count)
            return jsonify({"status": "updated", "worker_count": active})
        if "dynamic_scaling" in data:
            pool.dynamic_scaling = bool(data["dynamic_scaling"])
            return jsonify({"status": "updated", "dynamic_scaling": pool.dynamic_scaling})
        return jsonify({"status": "noop"})

    # ---------------- SYNCHRONIZATION DEMOS ----------------
    @app.route("/api/sync/race", methods=["POST"])
    def api_race_condition():
        data = request.get_json() or {}
        use_lock = bool(data.get("use_lock", False))
        threads = int(data.get("threads", 10))
        increments = int(data.get("increments", 400))
        res = run_race_condition_demo(num_threads=threads, increments_per_thread=increments, use_lock=use_lock)
        return jsonify(res)

    @app.route("/api/sync/deadlock", methods=["POST"])
    def api_deadlock():
        data = request.get_json() or {}
        avoid = bool(data.get("avoid_deadlock", False))
        res = run_deadlock_demo(avoid_deadlock=avoid)
        return jsonify(res)

    # ---------------- BENCHMARK SUITE ----------------
    @app.route("/api/benchmarks/run", methods=["POST"])
    def api_run_benchmark():
        global latest_benchmark_results
        data = request.get_json() or {}
        workload = data.get("workload", "io")
        tasks = int(data.get("tasks", 12))
        latest_benchmark_results = BenchmarkSuite.run_full_benchmark(workload_type=workload, task_count=tasks)
        return jsonify({"status": "success", "results": latest_benchmark_results})

    @app.route("/api/benchmarks/export", methods=["GET"])
    def api_export_csv():
        global latest_benchmark_results
        if not latest_benchmark_results:
            latest_benchmark_results = BenchmarkSuite.run_full_benchmark(workload_type="io", task_count=10)
        csv_text = BenchmarkSuite.export_csv(latest_benchmark_results)
        return Response(csv_text, mimetype="text/csv", headers={
            "Content-Disposition": "attachment; filename=os_multithreading_benchmark.csv"
        })

    return app
