# 🚀 **AI Email Filter – Project Notes (Complete Summary)**

### _(Up to the point where we left off — ready for continuation in a new chat)_

---

## 🏗️ **Architecture Overview**

We deployed a **self-hosted AI-powered email filtering system** integrated with Microsoft 365 using:

- **Proxmox container (CT100)** – Poller + API + Dashboard
    
- **Separate LLM container** – Local Llama 3.1 8B running via Ollama
    
- **Microsoft Graph API** – For polling messages and moving emails
    
- **SQLite** – Local logging of AI decisions
    
- **FastAPI + Jinja2** – Web dashboard
    
- **Systemd services** – For poller and dashboard
    

The system works by:

1. Polling the mailbox with **Graph delta queries**
    
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
    

### ✔ Delta-based polling using a `state.json`

Ensures:

- Only new/changed emails are processed
    
- No re-processing of old mails
    

### ✔ Working poller loop (asyncio + systemd)

The poller:

- Runs every 60 seconds
    
- Gets new mail
    
- Classifies each with Llama
    
- Moves risky ones to quarantine
    
- Logs each event to SQLite
    
- Runs permanently under systemd
    

Poller entrypoint:

`python -m services.poller`

And uses:

`Environment=PYTHONUNBUFFERED=1`

so logs show up in `journalctl`.

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

Prompt includes:

- URL list
    
- Sender
    
- Subject
    
- Body preview
    
- Threat reasoning guidelines
    

If model returns bad JSON → fail-closed as high-risk phishing.

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
    
- Classification
    
- URLs (as reasons)
    
- Release button
    
- Refresh button
    
- Released emails display in green
    

### ✔ Systemd-managed API service

`ai-email-api.service`  
Runs uvicorn:

`uvicorn api.main:app --host 0.0.0.0 --port 8000`

### ✔ Clean HTML template (`quarantine.html`)

Styled, clickable, reliable.

---

## **7. Full End-to-End Flow (Now Working)**

**Inbound email → Graph delta → local classification → quarantine → dashboard → release**

Everything from raw email ingestion through human review is functioning.

---

# 📌 **Where We Stopped (exact handoff point)**

We ended after:

- Confirming the dashboard fully works
    
- Confirming the Release button works
    
- Confirming the poller is stable
    
- Integrating URL reasoning
    
- Llama prompt + API improvements
    
- Systemd services for both poller + API
    
- Dashboard rendered and functioning
    

We are **ready to continue** with:

## ⭐ Proposed Next Steps (Pick any when restarting)

### **1. Full-body email analysis (not just bodyPreview)**

Fetch full email HTML/text with another Graph call and feed that to the model.

### **2. URL reputation heuristics layer**

Add:

- Suspicious TLD detection
    
- IP-based URL detection
    
- Punycode domains
    
- Domain age checks
    
- "Match sender vs domain" checks
    

### **3. Attachment awareness**

Detect:

- File types
    
- Dangerous extensions
    
- Suspicious names
    
- Feed metadata into model
    

### **4. Dashboard authentication**

Add:

- Simple Basic Auth
    
- or Azure AD login (real security)
    

### **5. Variable thresholds + policy engine**

Per-user or global:

- RISK_THRESHOLD
    
- Quarantine or allow rules
    
- URL-only risk bumping
    

### **6. Multi-user or multi-tenant support**

Scaling beyond one mailbox.

---

# 📘 **Summary For Use in New Conversation**

If you paste the following block into a new conversation, I will automatically understand exactly where to continue:

---

## 📌 **Paste This in a New Chat to Resume**

**We built a fully working AI-powered email filter system consisting of:**

- A poller container (CT100) using Microsoft Graph delta queries
    
- A local Llama 3.1 8B inference container via Ollama
    
- A FastAPI LLM wrapper (`/classify`)
    
- A SQLite logging layer (`quarantine_events`)
    
- A delta-based poller that:
    
    - fetches new messages
        
    - extracts URLs from bodies
        
    - sends them to the LLM
        
    - moves high-risk email to an AI-Quarantine folder
        
    - logs everything
        
- A FastAPI admin dashboard (`/admin/quarantine`)
    
- A working release flow that moves emails back to Inbox
    
- Both poller and API run under systemd
    

We stopped right after confirming the dashboard works and release works.  
We are ready for next steps like full-body analysis, URL heuristics, attachment analysis, auth for the dashboard, etc.