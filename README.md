# AI Email Filter

Self-hosted Microsoft 365 email filtering stack combining a delta-based poller, local Llama 3.1 classifier, SQLite logging, and a FastAPI dashboard.

## 1. Architecture Overview

```
[Microsoft Graph delta] -> [poller @ services/poller.py] -> [URL Extraction] -> [LLM API (llm-api/api)]
         |                              |                            |
   state.json cache              SQLite quarantine.db           Ollama Llama 3.1
         |                              v                            |
         +--------> [Admin API + Dashboard /api/main.py + templates/quarantine.html]
```

Key components:

- **Poller container (CT100)** – Async loop invoking Microsoft Graph delta queries, extracting URLs from email bodies, classifying messages via LLM, and moving risky email into AI-Quarantine.
- **LLM container** – FastAPI wrapper around local Ollama Llama 3.1 8B for deterministic JSON threat scoring.
- **SQLite logging** – `data/quarantine.db` stores every decision, release status, timestamps, and user metadata.
- **Admin dashboard** – FastAPI + Jinja2 template served at `/admin/quarantine` with statistics, search, Basic Auth, and release workflow.
- **Systemd services** – `ai-email-poller.service` and `ai-email-api.service` keep poller and dashboard running on boot.

## 2. Repository Layout

| Path | Purpose |
| ---- | ------- |
| `api/` | FastAPI admin + JSON endpoints. Run via `uvicorn api.main:app --reload` for dev. |
| `services/` | Poller + Microsoft Graph helpers, DB access, URL extraction, state helpers. |
| `llm-api/` | FastAPI wrapper that forwards classification prompts to Ollama. |
| `templates/` | Jinja2 HTML for the dashboard. |
| `data/` | Contains `quarantine.db` (created on first run). |
| `state.json` | Delta links + cache per user, persisted between poller runs. |
| `ai-email-*.service.example` | Systemd unit templates for deployment. |
| `.env.example` | Reference environment configuration. Copy to `.env`. |
| `requirements.txt` | Python dependencies for both poller + admin API. |
| `scripts/setup.sh` | Helper to bootstrap virtualenv + install deps. |

## 3. Prerequisites

1. **Python** – 3.10+ recommended.
2. **pip / venv** – ability to create isolated environment.
3. **Microsoft Graph App Registration**
   - Client credential flow with permissions: `Mail.Read`, `Mail.ReadWrite`, `Mail.ReadWrite.All` (depending on scope), `User.Read.All` for `/users` discovery.
   - Record Tenant ID, Client ID, Secret.
4. **Ollama host** – Install Ollama, pull `llama3.1:8b`, and expose `http://127.0.0.1:11434` (default). LLM FastAPI wrapper runs on port `8081` by default.
5. **System packages** – `sqlite3`, `systemd` (for deployment target), `curl`/`wget` for testing.

## 4. Quick Start (Development)

```bash
# Clone repo
# git clone <repo-url> eye-of-sauron && cd eye-of-sauron

# Create .env from template
cp .env.example .env
# edit .env with tenant/client secrets, monitored users, LLM API URL, etc.
# TIP: Set ENABLE_TENANT_DISCOVERY=false to test with a single mailbox first!

# Bootstrap virtualenv & install deps
./scripts/setup.sh
source .venv/bin/activate  # or venv\Scripts\activate on Windows

# Initialize database (poller does this automatically, but you can force it)
python -c "from services.db import init_db; init_db()"

# Run poller (dev mode)
python -m services.poller

# In another terminal, run admin API
uvicorn api.main:app --reload --port 8000

# (Optional) Run LLM wrapper if not already deployed
uvicorn llm-api.api.main:app --host 0.0.0.0 --port 8081
```

Health check: `curl http://localhost:8000/health` should return `{ "status": "ok" }`. Dashboard: `http://localhost:8000/admin/quarantine`.

## 5. Environment Variables

See `.env.example` for documented values:

- `TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET`, `GRAPH_SCOPE`
- `MONITORED_USER` (legacy endpoints) and `MONITORED_USERS` fallback list
- `ENABLE_TENANT_DISCOVERY` ("true"/"false") to toggle between full tenant scanning and single-mailbox testing
- `ORG_DOMAIN`, `RISK_THRESHOLD`, `LLM_API_URL`, optional `QUARANTINE_FOLDER_ID`
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` for dashboard Basic Auth
- `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR) and `LOG_FORMAT` (`plain` or `json`) for stdout logging

Place `.env` at repo root so `load_dotenv()` in services can pick it up.

## 6. Dependency Management

- All Python deps captured in `requirements.txt`.
- `scripts/setup.sh` creates `.venv/` and installs requirements for both API + poller.
- For Windows, run the commands manually:
  ```powershell
  py -3 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```

## 7. Deployment (Proxmox LXC / Systemd)

This guide assumes two Ubuntu 22.04 LXC containers. Adjust IPs and paths as needed.

| Container | Role | Static IP |
|-----------|------|-----------|
| `ct-ai-filter` | Poller + Dashboard | 192.168.1.110 |
| `ct-llm` | Ollama + LLM API | 192.168.1.111 |

### A. Configure `ct-llm` (192.168.1.111)

1. **Install Ollama:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull llama3.1:8b
   ```

2. **Deploy LLM API Wrapper:**
   ```bash
   # Create directory
   mkdir -p /opt/llm-api
   cd /opt/llm-api
   
   # Copy the `llm-api/` folder from this repo to here (scp or git clone + mv)
   # Example if you cloned the repo to /tmp/eye-of-sauron:
   # cp -r /tmp/eye-of-sauron/llm-api/* /opt/llm-api/
   
   # Create venv & install
   python3 -m venv .venv
   source .venv/bin/activate
   pip install fastapi uvicorn httpx
   ```

3. **Create Systemd Service for LLM API:**
   Create `/etc/systemd/system/llm-api.service`:
   ```ini
   [Unit]
   Description=LLM API Wrapper
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/opt/llm-api
   ExecStart=/opt/llm-api/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8081
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

4. **Enable & Start:**
   ```bash
   systemctl daemon-reload
   systemctl enable --now llm-api
   ```

### B. Configure `ct-ai-filter` (192.168.1.110)

1. **Clone & Setup:**
   ```bash
   cd /opt
   git clone <your-repo-url> ai-email-filter
   cd ai-email-filter
   
   # Configure Env
   cp .env.example .env
   nano .env
   # Set: TENANT_ID, CLIENT_ID, SECRETS...
   # Set: LLM_API_URL=http://192.168.1.111:8081/classify
   # Set: ENABLE_TENANT_DISCOVERY=false (for initial testing)
   
   # Install
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

2. **Install Systemd Services:**
   ```bash
   # Copy example units
   cp ai-email-api.service.example /etc/systemd/system/ai-email-api.service
   cp ai-email-poller.service.example /etc/systemd/system/ai-email-poller.service
   
   # Edit them if your paths differ from defaults (/opt/ai-email-filter/.venv/...)
   nano /etc/systemd/system/ai-email-api.service
   nano /etc/systemd/system/ai-email-poller.service
   
   # Enable & Start
   systemctl daemon-reload
   systemctl enable --now ai-email-api ai-email-poller
   ```

3. **Verify:**
   ```bash
   journalctl -u ai-email-poller -f
   # Should see: "AI Email Poller started..."
   ```

## 8. Directory & Data Considerations

- `data/quarantine.db` – SQLite database; back up regularly. Safe to delete only if you accept losing history.
- `state.json` – Holds Graph delta tokens + cached folder IDs per user. Deleting forces full sync (longer first run).
- `templates/` – Update `quarantine.html` for UI tweaks.
- `llm-api/` – Deployed separately (optionally under its own systemd service). Ensure `LLM_API_URL` points to it.
- Logs – All services emit structured stdout logs via `services.logging_utils` (12-factor). Use `LOG_FORMAT=json` for ingestion into centralized pipelines; systemd/journald captures stdout automatically.

## 9. Troubleshooting

| Symptom | Action |
| ------- | ------ |
| Poller logs `403 Forbidden /users` | Ensure app registration has `User.Read.All` or set `ENABLE_TENANT_DISCOVERY=false` and use `MONITORED_USERS` fallback. |
| LLM timeout | Verify `LLM_API_URL`, Ollama availability, and network reachability between containers. |
| Dashboard empty | Confirm poller is running, `data/quarantine.db` exists, check `services.db` logs. |
| Emails not released | Ensure Graph app has `Mail.ReadWrite` and that `get_inbox_folder_id()` returns valid folder. |
| Stale delta state | Delete `state.json` (after stopping poller) to force re-sync. |
| `status=203/EXEC` in systemd | ExecStart points at missing interpreter (e.g., `/venv/` instead of `.venv/`). Update paths and `systemctl daemon-reload`. |
| `AADSTS90002` / tenant not found | `TENANT_ID` in `.env` is wrong. Copy the directory ID from Azure AD overview. |
| `AADSTS900023` / invalid_request | `TENANT_ID` or `CLIENT_ID` swapped or malformed. Re-check values. |
| Only polling one user? | Check if `ENABLE_TENANT_DISCOVERY=false` is set in `.env`. |

## 10. Validation Checklist

After deployment:
1. **API health** – `curl http://192.168.1.110:8000/health` returns `{"status":"ok"}`.
2. **LLM health** – `curl http://192.168.1.111:8081/docs` loads and `curl http://192.168.1.111:8081/classify -d '{...}'` returns JSON.
3. **Poller logs** – `journalctl -u ai-email-poller -f` shows user discovery and message processing without exceptions.
4. **End-to-end email** – Send a test mail to monitored mailbox; confirm entry in `/admin/quarantine` and log row in `data/quarantine.db`.
5. **Dashboard Check** – Visit `/admin/quarantine`, login with Basic Auth credentials, and verify the "Total Processed" stat increments.
6. **Release flow** – Click "Release" in dashboard and verify message moves back plus DB `released=1`.
7. **Failure simulation** – Stop `llm-api` service to ensure poller logs timeouts/fail-closed, then restart to confirm recovery.
7. **Reboot test** – Reboot both containers and confirm `ai-email-api`, `ai-email-poller`, and `llm-api` all come back (`systemctl status ...`).

## 11. Future Enhancements

- Full-body message retrieval and attachment inspection.
- URL reputation heuristics & enrichment.
- Dashboard authentication (Basic/Azure AD).
- Policy engine with per-user thresholds.

Track ideas or status in `NOTES.md`.
