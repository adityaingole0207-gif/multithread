"""
Integration and End-to-End API Route Tests using Flask Test Client.
Tests:
- GET / (HTML Dashboard)
- GET /benchmark (HTML Benchmark page)
- GET /api/metrics (JSON metrics snapshot)
- POST /api/tasks/submit (Task dispatch)
- POST /api/control/pause and /resume
- POST /api/control/policy (Policy switching)
- POST /api/sync/race (Locked vs Unlocked Counter)
- POST /api/sync/deadlock (Deadlock Avoidance)
- POST /api/benchmarks/run (Benchmark execution)
- GET /api/benchmarks/export (CSV export)
"""

import json
import pytest
from app.routes import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_html_pages_render(client):
    r1 = client.get("/")
    assert r1.status_code == 200
    assert b"Multithreaded Task Execution Engine" in r1.data

    r2 = client.get("/benchmark")
    assert r2.status_code == 200
    assert b"Multithreading Performance & Speedup Benchmark" in r2.data


def test_metrics_api(client):
    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.get_json()
    assert "cpu_percent" in data
    assert "total_workers" in data
    assert "resource_pool" in data
    assert data["resource_pool"]["capacity"] == 3


def test_task_submission_and_lifecycle(client):
    res = client.post(
        "/api/tasks/submit",
        data=json.dumps({"task_type": "io_network", "count": 2, "priority": 3}),
        content_type="application/json",
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["submitted_count"] == 2
    assert len(data["task_ids"]) == 2


def test_control_endpoints(client):
    # Pause
    r_pause = client.post("/api/control/pause")
    assert r_pause.status_code == 200
    assert r_pause.get_json()["is_paused"] is True

    # Resume
    r_resume = client.post("/api/control/resume")
    assert r_resume.status_code == 200
    assert r_resume.get_json()["is_paused"] is False

    # Policy Switch
    r_policy = client.post(
        "/api/control/policy",
        data=json.dumps({"policy": "FCFS"}),
        content_type="application/json",
    )
    assert r_policy.status_code == 200
    assert r_policy.get_json()["policy"] == "FCFS"


def test_race_condition_api(client):
    res = client.post(
        "/api/sync/race",
        data=json.dumps({"use_lock": True, "threads": 4, "increments": 100}),
        content_type="application/json",
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["lost_updates"] == 0


def test_deadlock_avoidance_api(client):
    res = client.post(
        "/api/sync/deadlock",
        data=json.dumps({"avoid_deadlock": True}),
        content_type="application/json",
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["deadlocked"] is False
    assert data["success"] is True


def test_benchmark_api_and_csv_export(client):
    res = client.post(
        "/api/benchmarks/run",
        data=json.dumps({"workload": "io", "tasks": 4}),
        content_type="application/json",
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert len(data["results"]) >= 4

    csv_res = client.get("/api/benchmarks/export")
    assert csv_res.status_code == 200
    assert csv_res.mimetype == "text/csv"
    assert b"name,workload,tasks" in csv_res.data
