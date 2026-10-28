// Multithreaded Task Execution Engine - Dashboard Client

let chartCpuMem = null;
let chartThroughputQueue = null;
let isEnginePaused = false;

// ---------------- CHART INITIALIZATION ----------------
function initCharts() {
  if (typeof Chart === 'undefined') {
    console.warn('Chart.js CDN is unavailable. Telemetry graphs disabled, core ledger active.');
    return;
  }

  try {
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
    const canvas1 = document.getElementById('chart-cpu-mem');
    if (canvas1) {
      const ctx1 = canvas1.getContext('2d');
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
    }

    // 2. Throughput & Queue Length Chart
    const canvas2 = document.getElementById('chart-throughput-queue');
    if (canvas2) {
      const ctx2 = canvas2.getContext('2d');
      chartThroughputQueue = new Chart(ctx2, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Throughput (TPS)',
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              fill: true,
              tension: 0.3,
              data: []
            },
            {
              label: 'Pending Settlement Backlog',
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
  } catch (err) {
    console.error('Failed to initialize charts', err);
  }
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

function safeSetText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// ---------------- DASHBOARD UI UPDATES ----------------
function updateDashboard(data) {
  if (!data) return;

  // Top Metrics (guarded with safeSetText)
  safeSetText('val-cpu', `${data.cpu_percent}%`);
  safeSetText('val-mem', `RAM: ${data.memory_mb} MB (${data.memory_percent}%)`);
  safeSetText('val-workers', `${data.active_workers} / ${data.total_workers}`);
  safeSetText('sub-workers', `${data.active_workers} busy | ${data.idle_workers} idle tellers`);
  safeSetText('val-queue', data.queue_length);
  safeSetText('sub-policy', `Dispatch: ${data.policy}`);
  safeSetText('val-throughput', `${data.tasks_per_second} TPS`);
  safeSetText('sub-completed', `Settled: ${data.completed_count} | Failed: ${data.failed_count}`);
  safeSetText('val-latency', `${data.avg_wait_time}s / ${data.avg_turnaround_time}s`);

  // Pause button state sync
  isEnginePaused = data.is_paused;
  const pauseBtn = document.getElementById('btn-pause');
  if (isEnginePaused) {
    pauseBtn.textContent = 'Resume Engine';
    pauseBtn.className = 'btn-primary';
  } else {
    pauseBtn.textContent = 'Freeze Engine';
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

  // Workers / Tellers List
  renderWorkers(data.workers || []);

  // SWIFT / Resource Pool Status
  if (data.resource_pool) {
    renderResourcePool(data.resource_pool);
  }

  // Event Log
  renderEvents(data.events || []);

  // Gantt Chart
  renderGantt(data.gantt || []);

  // Banking Accounts Ledger & Vault Reserve
  if (data.banking_accounts) {
    renderBankingAccounts(data.banking_accounts);
    const vaultTotal = data.banking_accounts.reduce((s, a) => s + (a.balance || 0), 0);
    const vaultEl = document.getElementById('val-total-vault');
    if (vaultEl) {
      vaultEl.textContent = '$' + vaultTotal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    }
  }
}

function renderBankingAccounts(accounts) {
  const container = document.getElementById('banking-accounts-grid');
  if (!container) return;
  container.innerHTML = accounts.map(acc => `
    <div class="account-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="color:var(--accent-emerald); font-weight:800; font-size:0.88rem;">${acc.account_id}</span>
        <span style="font-size:0.75rem; color:var(--text-secondary);">${acc.holder_name}</span>
      </div>
      <div style="font-size:1.45rem; font-weight:800; color:var(--text-primary); margin:0.4rem 0;">
        $${acc.balance.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.72rem; color:var(--text-muted); border-top:1px solid rgba(255,255,255,0.06); padding-top:0.35rem;">
        <span>Settled Tx: <strong style="color:var(--text-primary);">${acc.transaction_count}</strong></span>
        <span style="color:var(--accent-cyan); font-weight:600;">🔒 Mutex Guarded</span>
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
      : 'Waiting for financial transactions...';
    const badgeClass = isBusy ? 'badge-busy' : 'badge-idle';
    const statusText = isBusy ? 'BUSY (SETTLING)' : 'IDLE (READY)';

    return `
      <div class="worker-pill ${isBusy ? 'busy' : ''}">
        <div class="worker-pill-top">
          <span>Teller-${w.id}</span>
          <span class="badge ${badgeClass}">${statusText}</span>
        </div>
        <div class="worker-task-desc" title="${taskInfo}">${taskInfo}</div>
      </div>
    `;
  }).join('');
}

function renderResourcePool(res) {
  safeSetText('sem-available', `${res.available_count} / ${res.capacity}`);
  safeSetText('sem-allocated', res.allocated_count);
  safeSetText('sem-waiting', res.waiting_threads);

  const listEl = document.getElementById('sem-allocations-list');
  if (!listEl) return;
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

// ---------------- SNAPSHOT METRICS FETCHER ----------------
async function fetchMetricsOnce() {
  try {
    const res = await fetch('/api/metrics');
    if (res.ok) {
      const data = await res.json();
      updateDashboard(data);
    }
  } catch (err) {
    console.warn('Initial metrics fetch deferred to stream', err);
  }
}

// ---------------- EVENT LISTENERS ----------------
function setupEventListeners() {
  // Task / Transaction Submission with Immediate Visual Feedback
  const submitBtn = document.getElementById('btn-submit');
  if (submitBtn) {
    submitBtn.addEventListener('click', async () => {
      const origHtml = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span>⚡ Dispatching...</span>';

      try {
        const taskType = document.getElementById('select-task-type').value;
        const count = parseInt(document.getElementById('select-batch-size').value, 10) || 1;
        const priority = parseInt(document.getElementById('select-priority').value, 10) || 2;

        const res = await fetch('/api/tasks/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task_type: taskType, count, priority })
        });
        const data = await res.json();

        submitBtn.innerHTML = `<span>✓ Dispatched ${data.submitted_count} Tx!</span>`;
        setTimeout(() => {
          submitBtn.innerHTML = origHtml;
          submitBtn.disabled = false;
        }, 1200);

        // Instantly refresh task table & account balances without waiting for SSE
        refreshTasks();
        fetchMetricsOnce();
      } catch (err) {
        console.error('Dispatch error:', err);
        submitBtn.innerHTML = '<span>❌ Error</span>';
        setTimeout(() => {
          submitBtn.innerHTML = origHtml;
          submitBtn.disabled = false;
        }, 1500);
      }
    });
  }

  // Freeze / Resume Engine
  const pauseBtn = document.getElementById('btn-pause');
  if (pauseBtn) {
    pauseBtn.addEventListener('click', async () => {
      const endpoint = isEnginePaused ? '/api/control/resume' : '/api/control/pause';
      await fetch(endpoint, { method: 'POST' });
      fetchMetricsOnce();
    });
  }

  // Reset Engine
  const resetBtn = document.getElementById('btn-reset');
  if (resetBtn) {
    resetBtn.addEventListener('click', async () => {
      if (confirm('Reset ThreadPool and clear all recorded tasks?')) {
        await fetch('/api/control/reset', { method: 'POST' });
        refreshTasks();
        fetchMetricsOnce();
      }
    });
  }

  // Policy Switcher
  const policySelect = document.getElementById('select-policy');
  if (policySelect) {
    policySelect.addEventListener('change', async (e) => {
      const policy = e.target.value;
      await fetch('/api/control/policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ policy })
      });
      fetchMetricsOnce();
    });
  }

  // Worker Count Manual Sizing
  const setWorkersBtn = document.getElementById('btn-set-workers');
  if (setWorkersBtn) {
    setWorkersBtn.addEventListener('click', async () => {
      const count = parseInt(document.getElementById('input-workers').value, 10);
      await fetch('/api/control/workers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count })
      });
      fetchMetricsOnce();
    });
  }

  // Dynamic Scaling Toggle
  const dynamicCheck = document.getElementById('check-dynamic');
  if (dynamicCheck) {
    dynamicCheck.addEventListener('change', async (e) => {
      const enabled = e.target.checked;
      await fetch('/api/control/workers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dynamic_scaling: enabled })
      });
      fetchMetricsOnce();
    });
  }

  // Refresh tasks button
  const refreshTasksBtn = document.getElementById('btn-refresh-tasks');
  if (refreshTasksBtn) {
    refreshTasksBtn.addEventListener('click', () => {
      refreshTasks();
      fetchMetricsOnce();
    });
  }

  // Reset Banking Ledger
  const resetLedgerBtn = document.getElementById('btn-reset-ledger');
  if (resetLedgerBtn) {
    resetLedgerBtn.addEventListener('click', async () => {
      await fetch('/api/banking/reset', { method: 'POST' });
      fetchMetricsOnce();
    });
  }

  // Periodic task table update (every 2.5s)
  setInterval(refreshTasks, 2500);
}

// ---------------- BOOTSTRAP ----------------
window.addEventListener('DOMContentLoaded', () => {
  // 1. Hook user interaction first so buttons always work
  setupEventListeners();

  // 2. Load metrics & ledger immediately
  fetchMetricsOnce();

  // 3. Connect real-time streaming
  initSSE();

  // 4. Safely initialize charts
  initCharts();

  // 5. Populate task table
  refreshTasks();
});
