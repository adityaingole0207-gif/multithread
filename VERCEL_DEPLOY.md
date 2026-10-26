# Vercel Deployment Guide

This project is configured and ready for 1-click deployment to **Vercel** using `@vercel/python` serverless WSGI.

---

## 1. What Has Been Configured for Vercel

1. **`api/index.py`**:
   The serverless entrypoint required by Vercel. It dynamically adds the project root to `sys.path` and exposes the WSGI `app` callable from `app.routes`.

2. **`vercel.json`**:
   Configured with `@vercel/python` builder and wildcard rewrites to route all web traffic and REST/SSE requests to `/api/index.py`.

3. **`.vercelignore`**:
   Excludes test caches, temporary files, local build directories, and scripts from being uploaded to the Vercel cloud bundle.

4. **Resilient Telemetry (SSE + Polling Fallback)**:
   On serverless platforms like Vercel, long-lived streaming connections (Server-Sent Events) are terminated by Vercel after 10–15 seconds due to serverless execution timeouts.  
   `static/js/app.js` automatically detects this and seamlessly falls back to real-time 1.2s polling (`/api/metrics`), ensuring the telemetry dashboard, Chart.js graphs, worker pills, and Gantt charts remain active with zero disconnections.

---

## 2. Deployment Methods

### Option A: Deploy via Vercel CLI (Fastest)

1. Open your terminal in this project folder (`c:\Users\ingol\Downloads\osproject`).
2. Run:
   ```bash
   npx vercel
   ```
   *(Or double-click `deploy_vercel.bat`)*
3. Follow the on-screen prompts:
   - **Log in**: Opens your browser to authenticate with Vercel (GitHub, GitLab, or Email).
   - **Set up and deploy?**: Type `y` and press `Enter`.
   - **Which scope?**: Select your personal Vercel account.
   - **Link to existing project?**: Type `n`.
   - **What's your project's name?**: Press `Enter` (or type `multithreaded-task-engine`).
   - **In which directory is your code located?**: Press `Enter` (`./`).
   - **Want to modify settings?**: Type `n`.
4. Vercel will upload the bundle, build the Python environment, and output your live public URL:
   ```
   Production: https://multithreaded-task-engine.vercel.app
   ```

---

### Option B: Deploy via GitHub (Recommended for Continuous Deployment)

1. Initialize git and commit your files (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Multithreaded Task Execution Engine - Vercel Ready"
   ```
2. Create a new repository on [GitHub](https://github.com/new).
3. Push your repository:
   ```bash
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git branch -M main
   git push -u origin main
   ```
4. Go to [vercel.com/new](https://vercel.com/new):
   - Select your newly pushed GitHub repository.
   - Leave the Framework Preset as **Other** (Vercel automatically detects `vercel.json` and `api/index.py`).
   - Click **Deploy**.
5. Your project will be live with automatic deployments on every `git push`!

---

## 3. Important Operating Systems Architectural Note

- **On a Local Server or VM / VPS (Render, Railway, Fly.io, AWS EC2)**:
  The Python process runs continuously. Worker threads stay alive in memory indefinitely, and dynamic scaling grows/shrinks real background OS threads across multiple minutes.
- **On Vercel Serverless**:
  Each request is served by an ephemeral serverless container. Tasks execute concurrently across native worker threads *during* the execution of each request lifecycle. Because of the smart telemetry fallback we built into `app.js`, all interactive dashboard controls, task submissions, synchronization demos (Race Condition & Deadlock Avoidance), and benchmark suite runs work seamlessly in the cloud.
