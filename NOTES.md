# 🚀 **AI Email Filter – Project Notes (Complete Summary)**

### _(Up to the point where we left off — ready for continuation in a new chat)_

## 📅 Latest Progress (Nov 24, 2025)

- **Parallel Processing**: Refactored `services/poller.py` to use `asyncio.gather` with a semaphore (`MAX_CONCURRENT_MSGS=5`). This solved the "slow processing" issue while respecting LLM resource limits.
- **Dashboard UI Fixes**:
  - Differentiated "Quarantined" (moved) vs "Allowed" (safe, not moved) vs "Released".
  - Disabled "Release" button for emails that were never quarantined.
- **Security & Stats (Phase 1)**:
  - Added **Statistics Widget** to dashboard (Total, Quarantined, Released, Allowed).
  - Implemented **HTTP Basic Authentication** for `/admin` routes.
  - Updated `.env.example` with `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
- **Deployment Documentation**:
  - Added comprehensive `Section 7` in README for Proxmox LXC deployment.
  - Documented `ct-llm` (Ollama) and `ct-ai-filter` (Poller) setup explicitly.
  - Fixed `systemd` path issues (pointing to `.venv` correctly).
- **Configuration**: Added `ENABLE_TENANT_DISCOVERY` to toggle between full tenant scan and single-mailbox testing.

## 🏗️ **Architecture Overview**

We deployed a **self-hosted AI-powered email filtering system** integrated with Microsoft 365 using:

- **Proxmox container (CT100)** – Poller + API + Dashboard
- **Separate LLM container** – Local Llama 3.1 8B running via Ollama
- **Microsoft Graph API** – For polling messages and moving emails
- **SQLite** – Local logging of AI decisions
- **FastAPI + Jinja2** – Web dashboard
- **Systemd services** – For poller and dashboard

The system works by:

1. Polling the mailbox with **Graph delta queries** (Parallelized)
2. Sending new emails to a local Llama classifier
3. Scoring each email (safe/spam/phishing/malicious)
4. Moving suspicious ones to **AI-Quarantine**
5. Storing a log entry for each email in SQLite
6. Providing an admin dashboard for reviewing and releasing emails

---

# ✅ **What We Built So Far**

---

## **1. Polling Layer (CT100)**

### ✔ Microsoft Graph integration

Includes:
- `get_delta_messages()` – uses `/delta` queries
- `move_message(message_id, folder_id)`
- `get_inbox_folder_id()`

### ✔ Parallelized Polling

- Uses `asyncio.Semaphore(5)` to process messages concurrently.
- Handles errors per-message to prevent crash loops.

### ✔ Delta-based polling using a `state.json`

Ensures:
- Only new/changed emails are processed
- No re-processing of old mails

### ✔ Working poller loop (asyncio + systemd)

The poller:
- Runs every 60 seconds
- Gets new mail
- Classifies each with Llama (in parallel)
- Moves risky ones to quarantine
- Logs each event to SQLite
- Runs permanently under systemd

Poller entrypoint:
`python -m services.poller`

---

## **2. LLM Classification Layer (LLM Container)**

### ✔ Ollama running Llama 3.1 8B (local)

With full REST access via:
`http://127.0.0.1:11434/api/generate`

### ✔ FastAPI wrapper API (`/classify`)

Runs separately on port **8081** via systemd or manually.

### ✔ Improved prompt

Classifier now returns strict JSON:
`{   "risk_score": 0-100,   "classification": "safe" | "spam" | "phishing" | "malicious",   "reasons": [...] }`

### ✔ URL-aware classification

Email body preview is scanned for URLs and passed into the model:
`urls: [...]`

---

## **3. URL Extraction Layer**

### ✔ Added `services/url_analysis.py`

Basic URL regex extraction + normalization.

---

## **4. Logging Layer**

### ✔ SQLite DB (`data/quarantine.db`)

Table: `quarantine_events`

Fields include:
- message_id
- sender
- subject
- received_datetime
- risk_score
- classification
- reasons
- moved (bool)
- released (bool)
- timestamps

### ✔ Added DB helpers

- `init_db()`
- `log_quarantine_event()`
- `list_quarantine_events()`
- `get_event_by_id()`
- `mark_released(event_id)`

---

## **5. Quarantine + Release Flow**

### ✔ AI-Quarantine folder

Created via Graph API and folder ID stored in `.env` as:
`QUARANTINE_FOLDER_ID=xxxx`

### ✔ Poller uses risk threshold (>= 60)

If high risk:
- Move to AI-Quarantine
- Log entry created

### ✔ Release flow

Admin clicks "Release" → message moves back to Inbox.

---

## **6. Admin Dashboard**

### ✔ Web dashboard at:

`http://<CT100-IP>:8000/admin/quarantine`

### ✔ Features:

- See all processed emails
- Risk badges
- Classification (Safe/Spam/Phishing)
- Status (Allowed/Quarantined/Released)
- URLs (as reasons)
- Release button (disabled if allowed)
- Refresh button

### ✔ Systemd-managed API service

`ai-email-api.service`
Runs uvicorn:
`uvicorn api.main:app --host 0.0.0.0 --port 8000`

### ✔ Clean HTML template (`quarantine.html`)

Styled, clickable, reliable.

---

## **7. Full End-to-End Flow (Now Working)**

**Inbound email → Graph delta → local classification → quarantine → dashboard → release**

Everything from raw email ingestion through human review is functioning reliably in production testing.

---

# 📌 **Where We Stopped (exact handoff point)**

We ended after:
- **Successfully validating the parallel poller** in a live environment.
- **Fixing dashboard UI bugs** where safe emails were labeled "Quarantined".
- **Updating README** with precise deployment steps for Proxmox.

We are **ready to continue** with:

## ⭐ Proposed Next Steps (Pick any when restarting)

### **1. Search & Filter (Dashboard)**
Add a text box to filter rows by Subject or Sender.

### **2. Full-body email analysis**
Fetch full email MIME/HTML content (not just bodyPreview) for better LLM accuracy.

### **3. URL reputation heuristics layer**
Add suspicious TLD detection, IP-based URL detection, etc.

### **4. Attachment awareness**
Detect dangerous file extensions or names.

---

# 📘 **Summary For Use in New Conversation**

If you paste the following block into a new conversation, I will automatically understand exactly where to continue:

---

## 📌 **Paste This in a New Chat to Resume**

**We have a production-ready AI email filter running on Proxmox (LXC) with:**

- **Parallel Polling**: `services/poller.py` processes 5 emails concurrently via `asyncio.Semaphore`.
- **Local LLM**: Llama 3.1 8B running on a separate container via Ollama.
- **Dashboard**: FastAPI + Jinja2 admin panel with **Statistics**, **Basic Auth**, and correct status labels.
- **Deployment**: Fully documented `systemd` setup in README.

**Current Status:**
- Poller is fast and stable.
- Dashboard is secured and shows real-time metrics.
- Ready to add **Search & Filter** and **Full-body Analysis**.