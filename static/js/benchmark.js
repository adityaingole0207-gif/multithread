// OS Benchmarks and Synchronization Demos Client

let chartBenchTime = null;
let chartBenchSpeedup = null;

function initBenchmarkCharts() {
  const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#94a3b8', font: { size: 10 } }
      },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#94a3b8', font: { size: 10 } }
      }
    },
    plugins: {
      legend: { display: false }
    }
  };

  // Wall time chart
  const ctxTime = document.getElementById('chart-bench-time').getContext('2d');
  chartBenchTime = new Chart(ctxTime, {
    type: 'bar',
    data: {
      labels: [],
      datasets: [{
        label: 'Wall Time (seconds)',
        backgroundColor: ['#64748b', '#6366f1', '#06b6d4', '#10b981', '#a855f7'],
        borderRadius: 6,
        data: []
      }]
    },
    options: chartDefaults
  });

  // Speedup chart
  const ctxSpeedup = document.getElementById('chart-bench-speedup').getContext('2d');
  chartBenchSpeedup = new Chart(ctxSpeedup, {
    type: 'bar',
    data: {
      labels: [],
      datasets: [{
        label: 'Speedup Factor',
        backgroundColor: ['#64748b', '#6366f1', '#06b6d4', '#10b981', '#a855f7'],
        borderRadius: 6,
        data: []
      }]
    },
    options: chartDefaults
  });
}

function setupBenchmarkHandlers() {
  // Execute Benchmark
  document.getElementById('btn-run-benchmark').addEventListener('click', async () => {
    const workload = document.getElementById('bench-workload').value;
    const tasks = parseInt(document.getElementById('bench-tasks').value, 10);
    const spinner = document.getElementById('bench-spinner');
    const runBtn = document.getElementById('btn-run-benchmark');

    spinner.style.display = 'inline';
    runBtn.disabled = true;

    try {
      const res = await fetch('/api/benchmarks/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workload, tasks })
      });
      const data = await res.json();
      renderBenchmarkResults(data.results || []);
    } catch (err) {
      console.error('Benchmark execution failed', err);
      alert('Benchmark execution failed. Check server console.');
    } finally {
      spinner.style.display = 'none';
      runBtn.disabled = false;
    }
  });

  // Race Condition Test
  document.getElementById('btn-run-race').addEventListener('click', async () => {
    const useLock = document.getElementById('check-use-lock').checked;
    const btn = document.getElementById('btn-run-race');
    btn.disabled = true;
    btn.textContent = 'Running...';

    try {
      const res = await fetch('/api/sync/race', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_lock: useLock, threads: 10, increments: 400 })
      });
      const data = await res.json();

      document.getElementById('race-mode').textContent = data.mode;
      document.getElementById('race-expected').textContent = data.expected_value.toLocaleString();
      document.getElementById('race-actual').textContent = data.actual_value.toLocaleString();
      
      const lostEl = document.getElementById('race-lost');
      lostEl.textContent = data.lost_updates.toLocaleString();
      lostEl.style.color = data.lost_updates > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)';

      document.getElementById('race-duration').textContent = `${data.duration_seconds}s`;
      document.getElementById('race-explanation').textContent = data.explanation;
    } catch (e) {
      console.error('Failed to run race test', e);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Run Race Test';
    }
  });

  // Deadlock Avoidance Test
  document.getElementById('btn-run-deadlock').addEventListener('click', async () => {
    const avoid = document.getElementById('check-avoid-deadlock').checked;
    const btn = document.getElementById('btn-run-deadlock');
    btn.disabled = true;
    btn.textContent = 'Executing...';

    try {
      const res = await fetch('/api/sync/deadlock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ avoid_deadlock: avoid })
      });
      const data = await res.json();

      const statusEl = document.getElementById('dl-status');
      if (data.deadlocked) {
        statusEl.textContent = 'DEADLOCK ENCOUNTERED (Timed out waiting for inverse locks)';
        statusEl.style.color = 'var(--accent-rose)';
      } else {
        statusEl.textContent = 'SUCCESS: Both threads completed without deadlock!';
        statusEl.style.color = 'var(--accent-emerald)';
      }

      const logsEl = document.getElementById('dl-logs');
      logsEl.innerHTML = (data.logs || []).map(l => `<span>${l}</span>`).join('');
      document.getElementById('dl-explanation').textContent = data.explanation;
    } catch (e) {
      console.error('Failed to run deadlock test', e);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Run Deadlock Test';
    }
  });
}

function renderBenchmarkResults(results) {
  const tbody = document.getElementById('bench-table-body');
  if (!results || results.length === 0) return;

  tbody.innerHTML = results.map(r => `
    <tr>
      <td><strong>${r.name}</strong></td>
      <td><span style="font-size:0.75rem; color:var(--text-muted);">${r.workload}</span></td>
      <td>${r.tasks}</td>
      <td><code style="color:var(--accent-cyan);">${r.workers}</code></td>
      <td><strong>${r.wall_time}s</strong></td>
      <td><span style="color:var(--accent-emerald); font-weight:700;">${r.speedup ? r.speedup + 'x' : '1.00x'}</span></td>
      <td>${r.throughput} t/s</td>
      <td>${r.avg_turnaround}s</td>
      <td>${r.avg_cpu}%</td>
    </tr>
  `).join('');

  // Update Charts
  const labels = results.map(r => r.name);
  const times = results.map(r => r.wall_time);
  const speedups = results.map(r => r.speedup || 1.0);

  chartBenchTime.data.labels = labels;
  chartBenchTime.data.datasets[0].data = times;
  chartBenchTime.update();

  chartBenchSpeedup.data.labels = labels;
  chartBenchSpeedup.data.datasets[0].data = speedups;
  chartBenchSpeedup.update();
}

window.addEventListener('DOMContentLoaded', () => {
  initBenchmarkCharts();
  setupBenchmarkHandlers();
});
