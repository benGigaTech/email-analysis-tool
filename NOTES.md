# 👁️ Eye of Sauron - Project Status & Roadmap

> **Last Updated:** Nov 24, 2025
> **Status:** 🟢 Production Ready (Stable)

## 📍 Current State
A self-hosted, AI-powered email security gateway that sits alongside Microsoft 365. It uses Graph API delta queries to poll for new messages, analyzes them using a local Llama 3.1 model, and automatically quarantines high-risk emails.

### Core Capabilities
- **Parallel Processing**: Concurrent message handling (semaphore limited) for high throughput.
- **Local Intelligence**: Zero-data-exfiltration classification using Llama 3.1 8B.
- **Threat Detection**:
  - **Contextual Analysis**: LLM evaluates sender, subject, and body text.
  - **URL Forensics**: Static analysis for IP-based URLs and suspicious TLDs (e.g., `.xyz`, `.top`).
  - **Fail-Closed**: Fallback security if LLM JSON parsing fails.
- **Admin Dashboard**:
  - Real-time statistics (Total/Quarantined/Released).
  - Full-text search for subject/sender.
  - One-click release workflow to restore false positives.
  - Protected via HTTP Basic Auth.

---

## 📅 Recent Achievements

### Phase 3: Security & Performance (Completed)
- **Parallel Poller**: Implemented `asyncio.gather` with `MAX_CONCURRENT_MSGS=5` to eliminate bottlenecks.
- **URL Analysis Engine**: Added regex-based extraction and reputation checks in `services/url_analysis.py`.
- **Dashboard Polish**:
  - Differentiated status: **Allowed** (Safe), **Quarantined** (Moved), **Released** (Restored).
  - Added search functionality and robust pagination.
- **Deployment Hardening**:
  - Documented dual-container Proxmox setup (Poller vs. LLM).
  - Systemd integration for auto-restart and logging.

---

## 🚀 Roadmap

### Immediate Priorities (Next Sprint)
- [ ] **Attachment Inspection**:
  - Extract filenames and extensions from Graph API attachments.
  - Flag high-risk types (`.exe`, `.ps1`, `.vbs`, `.macro`).
- [ ] **User Policy Engine**:
  - Allow per-user risk thresholds (e.g., Executives = Strict, Sales = Lenient).
  - Whitelist/Blacklist support by domain.

### Future Enhancements
- **LLM Fine-Tuning**: Train a LoRA adapter specifically on email threat datasets.
- **Graph Webhooks**: Move from polling (Delta) to push notifications for instant processing.
- **Multi-Tenant Dashboard**: centralized view for MSP usage.

---

## 🔧 Technical Dictionary

| Component | Implementation |
|-----------|----------------|
| **Poller** | `services/poller.py` (AsyncIO, Graph Delta) |
| **Classifier** | `llm-api/` (FastAPI + Ollama Llama 3.1) |
| **Database** | SQLite (`data/quarantine.db`) |
| **UI** | Jinja2 Templates + FastAPI (`/admin/quarantine`) |
| **URL Logic** | `services/url_analysis.py` (Regex + TLD Check) |