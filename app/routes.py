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
import random
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
from tasks.banking_tasks import (
    bank_ledger,
    bank_safe_transfer,
    bank_atm_withdrawal,
    bank_swift_wire_transfer,
    bank_fraud_ai_analysis,
    bank_corporate_payroll_quantum,
    run_banking_double_spend_race,
    run_banking_cross_transfer_deadlock,
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
                # Append resource pool & banking ledger status
                metrics["resource_pool"] = db_resource_pool.get_status()
                metrics["banking_accounts"] = bank_ledger.get_accounts_summary()
                metrics["swift_pool"] = bank_ledger.swift_gateway_pool.get_status()
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
        metrics["banking_accounts"] = bank_ledger.get_accounts_summary()
        metrics["swift_pool"] = bank_ledger.swift_gateway_pool.get_status()
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
            elif task_type == "bank_transfer":
                # P2P Transfer with deadlock-free lock ordering
                acc_keys = ["ACC_101", "ACC_102", "ACC_103", "ACC_104"]
                from_id = random.choice(acc_keys)
                to_id = random.choice([k for k in acc_keys if k != from_id])
                amt = round(random.uniform(50.0, 350.0), 2)
                task_name = f"TRANSFER_{from_id}->{to_id}_${amt}"
                fn = bank_safe_transfer
                args = (from_id, to_id, amt)
                est = 0.25
            elif task_type == "bank_atm":
                # ATM Withdrawal with Mutex
                acc_id = random.choice(["ACC_101", "ACC_102", "ACC_103", "ACC_104"])
                amt = round(random.uniform(50.0, 300.0), 2)
                task_name = f"ATM_WITHDRAW_{acc_id}_${amt}"
                fn = bank_atm_withdrawal
                args = (acc_id, amt)
                est = 0.2
            elif task_type == "bank_swift":
                # SWIFT Wire Transfer requiring Counting Semaphore permit
                amt = round(random.uniform(1000.0, 15000.0), 2)
                task_name = f"SWIFT_WIRE_${amt}"
                fn = bank_swift_wire_transfer
                args = (amt,)
                est = 0.45
            elif task_type == "bank_fraud":
                # CPU intensive AI Fraud Analysis
                acc_id = random.choice(["ACC_101", "ACC_102", "ACC_103", "ACC_104", "ACC_105"])
                task_name = f"FRAUD_AI_CHECK_{acc_id}"
                fn = bank_fraud_ai_analysis
                args = (acc_id,)
                est = 0.35
            elif task_type == "bank_payroll":
                # Corporate Payroll using Round Robin time quanta
                task_name = "PAYROLL_ENTERPRISE_BATCH"
                fn = bank_corporate_payroll_quantum
                args = ("ACC_105", 120)
                est = 0.5
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

    # ---------------- BANKING CORE API ENDPOINTS ----------------
    @app.route("/api/banking/accounts", methods=["GET"])
    def get_banking_accounts():
        return jsonify({
            "accounts": bank_ledger.get_accounts_summary(),
            "swift_gateway": bank_ledger.swift_gateway_pool.get_status(),
        })

    @app.route("/api/banking/reset", methods=["POST"])
    def reset_banking():
        bank_ledger.reset_balances()
        return jsonify({"status": "success", "message": "Ledger accounts reset to initial balances."})

    @app.route("/api/banking/sync/race", methods=["POST"])
    def api_banking_race():
        data = request.get_json() or {}
        use_mutex = bool(data.get("use_mutex", False))
        concurrent_atms = int(data.get("concurrent_atms", 10))
        amt = float(data.get("amount", 600.0))
        res = run_banking_double_spend_race(concurrent_withdrawals=concurrent_atms, amount_per_tx=amt, use_mutex=use_mutex)
        return jsonify(res)

    @app.route("/api/banking/sync/deadlock", methods=["POST"])
    def api_banking_deadlock():
        data = request.get_json() or {}
        avoid = bool(data.get("avoid_deadlock", False))
        res = run_banking_cross_transfer_deadlock(avoid_deadlock=avoid)
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
