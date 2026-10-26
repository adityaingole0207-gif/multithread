"""
Main Entrypoint for Multithreaded Task Execution Engine with Resource Monitor.

Modes:
- CLI Benchmark Mode: python main.py --cli
- Interactive Web Dashboard: python main.py [--port 5000]
"""

import sys
import argparse
from app.routes import create_app
from benchmarks.runner import BenchmarkSuite
from benchmarks.sync_demos import run_race_condition_demo, run_deadlock_demo


def print_banner():
    banner = r"""
================================================================================
  MULTITHREADED TASK EXECUTION ENGINE WITH RESOURCE MONITOR
  Operating Systems Mini Project - Multithreading & Synchronization
================================================================================
    """
    print(banner)


def format_table(results):
    headers = ["Configuration", "Workload", "Tasks", "Workers", "Wall Time(s)", "Speedup", "Throughput(t/s)", "Avg CPU%"]
    col_widths = [36, 10, 7, 18, 14, 9, 17, 10]

    header_row = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * col_widths[i] for i in range(len(headers)))

    print("\n" + separator)
    print(header_row)
    print(separator)

    for r in results:
        row_vals = [
            str(r["name"]),
            str(r["workload"]),
            str(r["tasks"]),
            str(r["workers"]),
            f"{r['wall_time']:.3f}",
            f"{r.get('speedup', 1.0):.2f}x",
            f"{r['throughput']:.1f}",
            f"{r['avg_cpu']:.1f}%",
        ]
        print(" | ".join(row_vals[i].ljust(col_widths[i]) for i in range(len(headers))))

    print(separator + "\n")


def run_cli_mode():
    print_banner()
    print("[*] Running in CLI Benchmark & Synchronization Mode...\n")

    # 1. Race Condition Demo
    print("-" * 80)
    print("1. RACE CONDITION & MUTUAL EXCLUSION (MUTEX) DEMO")
    print("-" * 80)
    print("Spawning 10 threads concurrently incrementing a shared counter (500 iterations each).\n")
    
    print("--> Test A: Unsynchronized (Race Condition - No Locks)")
    race_res = run_race_condition_demo(num_threads=10, increments_per_thread=500, use_lock=False)
    print(f"    Expected: {race_res['expected_value']} | Actual: {race_res['actual_value']} | Lost Updates: {race_res['lost_updates']}")
    print(f"    Result: {'FAILED (Race Condition Detected)' if race_res['lost_updates'] > 0 else 'SUCCESS'}")

    print("\n--> Test B: Synchronized (Mutex Protected Critical Section)")
    lock_res = run_race_condition_demo(num_threads=10, increments_per_thread=500, use_lock=True)
    print(f"    Expected: {lock_res['expected_value']} | Actual: {lock_res['actual_value']} | Lost Updates: {lock_res['lost_updates']}")
    print(f"    Result: {'SUCCESS (Mutual Exclusion Preserved)' if lock_res['success'] else 'FAILED'}")
    print(f"\n    OS Concept: {lock_res['explanation']}\n")

    # 2. Deadlock Avoidance Demo
    print("-" * 80)
    print("2. DEADLOCK REPRODUCTION & HIERARCHY-BASED AVOIDANCE DEMO")
    print("-" * 80)
    print("--> Test A: Circular Wait (Coffman Condition 4)")
    dl_res = run_deadlock_demo(avoid_deadlock=False)
    for log in dl_res["logs"]:
        print(f"    {log}")
    print(f"    Status: Deadlock detected = {dl_res['deadlocked']}")

    print("\n--> Test B: Deadlock Avoidance via Strict Lock Hierarchy (Lock A -> Lock B)")
    avoid_res = run_deadlock_demo(avoid_deadlock=True)
    for log in avoid_res["logs"]:
        print(f"    {log}")
    print(f"    Status: Completed successfully = {avoid_res['success']}")
    print(f"\n    OS Concept: {avoid_res['explanation']}\n")

    # 3. Workload Benchmark - I/O Bound
    print("-" * 80)
    print("3. BENCHMARK SUITE: I/O-BOUND WORKLOAD (12 Tasks)")
    print("-" * 80)
    print("Comparing Sequential vs Multithreaded vs Dynamic Scaling:")
    io_results = BenchmarkSuite.run_full_benchmark(workload_type="io", task_count=12)
    format_table(io_results)

    # 4. Workload Benchmark - CPU Bound & GIL Analysis
    print("-" * 80)
    print("4. BENCHMARK SUITE: CPU-BOUND WORKLOAD & GIL ANALYSIS (8 Tasks)")
    print("-" * 80)
    print("Comparing Multithreading (GIL-constrained) vs OS Multiprocessing:")
    cpu_results = BenchmarkSuite.run_full_benchmark(workload_type="cpu", task_count=8)
    format_table(cpu_results)

    print("-" * 80)
    print("THEORETICAL ANALYSIS & OS INSIGHTS:")
    print("-" * 80)
    print("""
- Amdahl's Law:
  Speedup S(N) = 1 / ((1 - P) + (P / N))
  Where P is the parallelizable portion.

- I/O-Bound Efficiency:
  When threads execute I/O (network/disk/sleep), they release the CPU and enter the BLOCKED
  state. The OS schedules another READY thread. Thus, multithreading delivers near-linear
  speedup for I/O workloads.

- Python GIL & Multiprocessing Contrast:
  In CPython, the Global Interpreter Lock prevents multiple native threads from executing
  Python bytecode concurrently on multiple physical CPU cores. Consequently, multithreading
  CPU-bound tasks yields limited speedup (and adds context-switch overhead). In contrast,
  OS Multiprocessing spawns separate processes with isolated memory spaces and distinct GILs,
  achieving true multi-core hardware parallelism.
    """)
    print("================================================================================")
    print("CLI Benchmark completed successfully.")


def run_web_mode(port: int = 5000, host: str = "127.0.0.1"):
    print_banner()
    print(f"[*] Starting Multithreaded Task Execution Engine Web Server...")
    print(f"[*] Dashboard URL: http://{host}:{port}")
    print(f"[*] Benchmarks URL: http://{host}:{port}/benchmark")
    print(f"[*] Real-time SSE Telemetry: http://{host}:{port}/api/metrics/stream\n")

    app = create_app()
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multithreaded Task Execution Engine with Resource Monitor")
    parser.add_argument("--cli", action="store_true", help="Run benchmark suite and synchronization demos in CLI mode")
    parser.add_argument("--port", type=int, default=5000, help="Web dashboard port (default: 5000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")

    args = parser.parse_args()

    if args.cli:
        run_cli_mode()
    else:
        run_web_mode(port=args.port, host=args.host)
