// Multithreaded Task Execution Engine - Dashboard Client

let chartCpuMem = null;
let chartThroughputQueue = null;
let isEnginePaused = false;

// ---------------- CHART INITIALIZATION ----------------
function initCharts() {
  const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 400 },
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#64748b', maxTicksLimit: 8, font: { size: 10 } }
      },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#64748b', font: { size: 10 } }
      }
    },
    plugins: {
      legend: {
        labels: { color: '#94a3b8', font: { size: 11 } }
      }
    }
  };

  // 1. CPU & Memory Chart
  const ctx1 = document.getElementById('chart-cpu-mem').getContext('2d');
  chartCpuMem = new Chart(ctx1, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'CPU Utilization (%)',
          borderColor: '#06b6d4',
          backgroundColor: 'rgba(6, 182, 212, 0.1)',
          fill: true,
          tension: 0.3,
          data: [],
          yAxisID: 'y'
        },
        {
          label: 'Memory (MB)',
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99, 102, 241, 0.1)',
          fill: true,
          tension: 0.3,
          data: [],
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      ...chartDefaults,
      scales: {
        ...chartDefaults.scales,
        y1: {
          position: 'right',
          grid: { drawOnChartArea: false },
          ticks: { color: '#64748b', font: { size: 10 } }
        }
      }
    }
  });

  // 2. Throughput & Queue Length Chart
  const ctx2 = document.getElementById('chart-throughput-queue').getContext('2d');
  chartThroughputQueue = new Chart(ctx2, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Throughput (tasks/s)',
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          fill: true,
          tension: 0.3,
          data: []
        },
        {
          label: 'Ready Queue Length',
          borderColor: '#f59e0b',
          backgroundColor: 'rgba(245, 158, 11, 0.1)',
          fill: true,
          tension: 0.3,
          data: []
        }
      ]
    },
    options: chartDefaults
  });
}

// ---------------- SERVER-SENT EVENTS & POLLING FALLBACK ----------------
let errorCount = 0;
let pollingInterval = null;

function startPollingFallback() {
  if (pollingInterval) return;
  const statusEl = document.getElementById('sse-status');
  statusEl.textContent = 'Live Telemetry Active';
  statusEl.style.color = 'var(--accent-emerald)';

  pollingInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/metrics');
      if (res.ok) {
        const data = await res.json();
        updateDashboard(data);
      }
    } catch (e) {
      console.warn('Polling fetch error', e);
    }
  }, 1200);
}

function initSSE() {
  const statusEl = document.getElementById('sse-status');

  try {
    const evtSource = new EventSource('/api/metrics/stream');

    evtSource.onopen = () => {
      errorCount = 0;
      statusEl.textContent = 'Live SSE Connected';
      statusEl.style.color = 'var(--accent-emerald)';
    };

    evtSource.onerror = () => {
      errorCount++;
      if (errorCount > 2) {
        // Automatically switch to polling on serverless runtimes (e.g. Vercel)
        evtSource.close();
        startPollingFallback();
      } else {
        statusEl.textContent = 'SSE Reconnecting...';
        statusEl.style.color = 'var(--accent-amber)';
      }
    };

    evtSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        updateDashboard(data);
      } catch (e) {
        console.error('Failed to parse SSE payload', e);
      }
    };
  } catch (err) {
    startPollingFallback();
  }
}

// ---------------- DASHBOARD UI UPDATES ----------------
function updateDashboard(data) {
  // Top Metrics
  document.getElementById('val-cpu').textContent = `${data.cpu_percent}%`;
  document.getElementById('val-mem').textContent = `${data.memory_mb} MB`;
  document.getElementById('sub-mem').textContent = `${data.memory_percent}% of system RAM`;
  document.getElementById('val-workers').textContent = `${data.active_workers} / ${data.total_workers}`;
  document.getElementById('sub-workers').textContent = `${data.idle_workers} idle | ${data.os_threads} OS threads`;
  document.getElementById('val-queue').textContent = data.queue_length;
  document.getElementById('sub-policy').textContent = `Policy: ${data.policy}`;
  document.getElementById('val-throughput').textContent = `${data.tasks_per_second} t/s`;
  document.getElementById('sub-completed').textContent = `Completed: ${data.completed_count} | Failed: ${data.failed_count}`;
  document.getElementById('val-latency').textContent = `${data.avg_wait_time}s / ${data.avg_turnaround_time}s`;

  // Pause button state sync
  isEnginePaused = data.is_paused;
  const pauseBtn = document.getElementById('btn-pause');
  if (isEnginePaused) {
    pauseBtn.textContent = 'Resume';
    pauseBtn.className = 'btn-primary';
  } else {
    pauseBtn.textContent = 'Pause';
    pauseBtn.className = 'btn-warning';
  }

  // Update Charts
  if (data.history && chartCpuMem && chartThroughputQueue) {
    chartCpuMem.data.labels = data.history.timestamps;
    chartCpuMem.data.datasets[0].data = data.history.cpu;
    chartCpuMem.data.datasets[1].data = data.history.memory;
    chartCpuMem.update('none');

    chartThroughputQueue.data.labels = data.history.timestamps;
    chartThroughputQueue.data.datasets[0].data = data.history.throughput;
    chartThroughputQueue.data.datasets[1].data = data.history.queue;
    chartThroughputQueue.update('none');
  }

  // Workers List
  renderWorkers(data.workers || []);

  // Resource Pool Status
  if (data.resource_pool) {
    renderResourcePool(data.resource_pool);
  }

  // Event Log
  renderEvents(data.events || []);

  // Gantt Chart
  renderGantt(data.gantt || []);

  // Banking Accounts Ledger
  if (data.banking_accounts) {
    renderBankingAccounts(data.banking_accounts);
  }
}

function renderBankingAccounts(accounts) {
  const container = document.getElementById('banking-accounts-grid');
  if (!container) return;
  container.innerHTML = accounts.map(acc => `
    <div class="metric-card" style="padding:0.85rem; border-color:rgba(16,185,129,0.25);">
      <div class="metric-title">
        <span style="color:var(--accent-emerald); font-weight:700;">${acc.account_id}</span>
        <span style="font-size:0.7rem; color:var(--text-secondary);">${acc.holder_name}</span>
      </div>
      <div class="metric-value" style="font-size:1.3rem; color:var(--text-primary); margin:0.35rem 0;">
        $${acc.balance.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
      </div>
      <div class="metric-sub" style="display:flex; justify-content:space-between; font-size:0.7rem;">
        <span>Tx Count: ${acc.transaction_count}</span>
        <span style="color:var(--accent-cyan); font-weight:600;">Mutex Guarded</span>
      </div>
    </div>
  `).join('');
}

function renderWorkers(workers) {
  const container = document.getElementById('workers-list');
  container.innerHTML = workers.map(w => {
    const isBusy = w.is_busy;
    const taskInfo = w.current_task 
      ? `[${w.current_task.task_id}] ${w.current_task.name}` 
      : 'Waiting for task...';
    const badgeClass = isBusy ? 'badge-busy' : 'badge-idle';
    const statusText = isBusy ? 'BUSY' : 'IDLE';

    return `
      <div class="worker-pill ${isBusy ? 'busy' : ''}">
        <div class="worker-pill-top">
          <span>${w.name}</span>
          <span class="badge ${badgeClass}">${statusText}</span>
        </div>
        <div class="worker-task-desc" title="${taskInfo}">${taskInfo}</div>
      </div>
    `;
  }).join('');
}

function renderResourcePool(res) {
  document.getElementById('sem-available').textContent = `${res.available_count} / ${res.capacity}`;
  document.getElementById('sem-allocated').textContent = res.allocated_count;
  document.getElementById('sem-waiting').textContent = res.waiting_threads;

  const listEl = document.getElementById('sem-allocations-list');
  const slots = Object.entries(res.allocations || {});
  if (slots.length === 0) {
    listEl.innerHTML = '<span>All database connection permits idle and available.</span>';
  } else {
    listEl.innerHTML = slots.map(([slot, holder]) => `
      <div style="display:flex; justify-content:space-between; background:rgba(255,255,255,0.03); padding:0.2rem 0.4rem; border-radius:4px;">
        <span style="color:var(--text-secondary);">${slot}</span>
        <span style="color:var(--accent-cyan); font-weight:600;">Held by ${holder}</span>
      </div>
    `).join('');
  }
}

function renderEvents(events) {
  const container = document.getElementById('event-log');
  container.innerHTML = events.map(e => `
    <div class="log-entry">
      <span class="log-time">[${e.timestamp}]</span>
      <span class="log-cat cat-${e.category}">${e.category}</span>
      <span class="log-msg">${e.message}</span>
    </div>
  `).join('');
}

function renderGantt(ganttEntries) {
  const container = document.getElementById('gantt-container');
  if (!ganttEntries || ganttEntries.length === 0) {
    container.innerHTML = '<span style="color:var(--text-muted); font-size:0.75rem;">Timeline empty. Submit tasks to view worker execution windows.</span>';
    return;
  }

  // Calculate time bounds for normalization
  const minTime = Math.min(...ganttEntries.map(e => e.start));
  const maxTime = Math.max(...ganttEntries.map(e => e.end));
  const span = Math.max(0.1, maxTime - minTime);

  container.innerHTML = ganttEntries.slice(-15).map(e => {
    const leftPct = Math.max(0, Math.min(95, ((e.start - minTime) / span) * 100));
    const widthPct = Math.max(4, Math.min(100 - leftPct, (e.duration / span) * 100));

    return `
      <div class="gantt-row">
        <span class="gantt-label">${e.worker}</span>
        <div class="gantt-track">
          <div class="gantt-bar" style="left: ${leftPct}%; width: ${widthPct}%;" title="${e.name} (${e.duration}s)">
            ${e.name} (${e.duration}s)
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// ---------------- TASK TABLE ----------------
async function refreshTasks() {
  try {
    const res = await fetch('/api/tasks');
    const tasks = await res.json();
    const tbody = document.getElementById('task-table-body');

    if (tasks.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:var(--text-muted); padding:1.5rem;">No tasks submitted yet.</td></tr>';
      return;
    }

    tbody.innerHTML = tasks.slice(-30).reverse().map(t => {
      let stateBadge = 'badge-idle';
      if (t.state === 'RUNNING') stateBadge = 'badge-busy';
      else if (t.state === 'COMPLETED') stateBadge = 'badge-busy';
      else if (t.state === 'BLOCKED') stateBadge = 'badge-blocked';
      else if (t.state === 'FAILED' || t.state === 'CANCELLED') stateBadge = 'badge-idle';

      const canCancel = ['NEW', 'READY', 'RUNNING'].includes(t.state);

      return `
        <tr>
          <td><code style="color:var(--accent-cyan);">${t.task_id}</code></td>
          <td><strong>${t.name}</strong></td>
          <td><span style="font-size:0.75rem; color:var(--text-muted);">${t.task_type}</span></td>
          <td><span style="color:var(--accent-amber); font-weight:700;">${t.priority}</span></td>
          <td><span class="badge ${stateBadge}">${t.state}</span></td>
          <td>${t.assigned_worker || '-'}</td>
          <td>${t.wait_time}s</td>
          <td>${t.execution_time}s</td>
          <td>${t.turnaround_time}s</td>
          <td>
            ${canCancel ? `<button onclick="cancelTask('${t.task_id}')" class="btn-danger" style="padding:0.2rem 0.5rem; font-size:0.7rem;">Cancel</button>` : '-'}
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error refreshing tasks', err);
  }
}

async function cancelTask(taskId) {
  try {
    await fetch(`/api/tasks/${taskId}/cancel`, { method: 'POST' });
    refreshTasks();
  } catch (e) {
    console.error('Failed to cancel task', e);
  }
}

// ---------------- EVENT LISTENERS ----------------
function setupEventListeners() {
  // Task Submission
  document.getElementById('btn-submit').addEventListener('click', async () => {
    const taskType = document.getElementById('select-task-type').value;
    const count = parseInt(document.getElementById('select-batch-size').value, 10);
    const priority = parseInt(document.getElementById('select-priority').value, 10);

    await fetch('/api/tasks/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_type: taskType, count, priority })
    });
    refreshTasks();
  });

  // Pause / Resume
  document.getElementById('btn-pause').addEventListener('click', async () => {
    const endpoint = isEnginePaused ? '/api/control/resume' : '/api/control/pause';
    await fetch(endpoint, { method: 'POST' });
  });

  // Reset Engine
  document.getElementById('btn-reset').addEventListener('click', async () => {
    if (confirm('Reset ThreadPool and clear all recorded tasks?')) {
      await fetch('/api/control/reset', { method: 'POST' });
      refreshTasks();
    }
  });

  // Policy Switcher
  document.getElementById('select-policy').addEventListener('change', async (e) => {
    const policy = e.target.value;
    await fetch('/api/control/policy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ policy })
    });
  });

  // Worker Count Manual Sizing
  document.getElementById('btn-set-workers').addEventListener('click', async () => {
    const count = parseInt(document.getElementById('input-workers').value, 10);
    await fetch('/api/control/workers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count })
    });
  });

  // Dynamic Scaling Toggle
  document.getElementById('check-dynamic').addEventListener('change', async (e) => {
    const enabled = e.target.checked;
    await fetch('/api/control/workers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dynamic_scaling: enabled })
    });
  });

  // Refresh tasks button
  document.getElementById('btn-refresh-tasks').addEventListener('click', refreshTasks);

  // Reset Banking Ledger
  const resetLedgerBtn = document.getElementById('btn-reset-ledger');
  if (resetLedgerBtn) {
    resetLedgerBtn.addEventListener('click', async () => {
      await fetch('/api/banking/reset', { method: 'POST' });
    });
  }

  // Periodic task table update (every 2.5s)
  setInterval(refreshTasks, 2500);
}

// ---------------- BOOTSTRAP ----------------
window.addEventListener('DOMContentLoaded', () => {
  initCharts();
  initSSE();
  setupEventListeners();
  refreshTasks();
});
