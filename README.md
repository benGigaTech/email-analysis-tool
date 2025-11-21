# AI Email Filter

Self-hosted Microsoft 365 email filtering stack combining a delta-based poller, local Llama 3.1 classifier, SQLite logging, and a FastAPI dashboard.

## 1. Architecture Overview

```
[Microsoft Graph delta] -> [poller @ services/poller.py] -> [LLM API (llm-api/api)]
         |                         |                           |
   state.json cache         SQLite quarantine.db        Ollama Llama 3.1
         |                         v                           |
         +--------> [Admin API + Dashboard /api/main.py + templates/quarantine.html]
```

Key components:

- **Poller container (CT100)** – Async loop invoking Microsoft Graph delta queries, classifying messages, and moving risky email into AI-Quarantine.
- **LLM container** – FastAPI wrapper around local Ollama Llama 3.1 8B for deterministic JSON threat scoring.
- **SQLite logging** – `data/quarantine.db` stores every decision, release status, timestamps, and user metadata.
- **Admin dashboard** – FastAPI + Jinja2 template served at `/admin/quarantine` with release workflow.
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
- `ORG_DOMAIN`, `RISK_THRESHOLD`, `LLM_API_URL`, optional `QUARANTINE_FOLDER_ID`
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

## 7. Deployment (Systemd)

1. Copy repo to `/opt/ai-email-filter` (match WorkingDirectory in unit files).
2. Create virtualenv inside `/opt/ai-email-filter/venv` and install requirements.
3. Copy `.env` and ensure `state.json` + `data/` are writable by service user.
4. Install service files:
   ```bash
   sudo cp ai-email-api.service.example /etc/systemd/system/ai-email-api.service
   sudo cp ai-email-poller.service.example /etc/systemd/system/ai-email-poller.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now ai-email-api.service ai-email-poller.service
   ```
5. Logs: `journalctl -u ai-email-api -f` and `journalctl -u ai-email-poller -f`.

## 8. Directory & Data Considerations

- `data/quarantine.db` – SQLite database; back up regularly. Safe to delete only if you accept losing history.
- `state.json` – Holds Graph delta tokens + cached folder IDs per user. Deleting forces full sync (longer first run).
- `templates/` – Update `quarantine.html` for UI tweaks.
- `llm-api/` – Deployed separately (optionally under its own systemd service). Ensure `LLM_API_URL` points to it.
- Logs – All services emit structured stdout logs via `services.logging_utils` (12-factor). Use `LOG_FORMAT=json` for ingestion into centralized pipelines; systemd/journald captures stdout automatically.

## 9. Troubleshooting

| Symptom | Action |
| ------- | ------ |
| Poller logs `403 Forbidden /users` | Ensure app registration has `User.Read.All` or set `MONITORED_USERS` fallback. |
| LLM timeout | Verify `LLM_API_URL`, Ollama availability, and network reachability between containers. |
| Dashboard empty | Confirm poller is running, `data/quarantine.db` exists, check `services.db` logs. |
| Emails not released | Ensure Graph app has `Mail.ReadWrite` and that `get_inbox_folder_id()` returns valid folder. |
| Stale delta state | Delete `state.json` (after stopping poller) to force re-sync. |

## 10. Future Enhancements

- Full-body message retrieval and attachment inspection.
- URL reputation heuristics & enrichment.
- Dashboard authentication (Basic/Azure AD).
- Policy engine with per-user thresholds.

Track ideas or status in `NOTES.md`.
