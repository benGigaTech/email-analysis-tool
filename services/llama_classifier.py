import os
import httpx
from dotenv import load_dotenv

from services.url_analysis import extract_urls, analyze_url_reputation

load_dotenv()

# URL of your LLM wrapper API (FastAPI on the LLM container)
LLM_API = os.getenv("LLM_API_URL", "http://192.168.2.125:8081/classify")


async def classify_with_llama(email: dict) -> dict:
    """
    Calls the local Llama 3.1 8B inference API to classify an email.
    Expects /classify to return JSON:
    {
      "risk_score": int,
      "classification": "safe" | "spam" | "phishing" | "malicious",
      "reasons": [ ... ]
    }
    """
    sender = (
        (email.get("from", {}) or {})
        .get("emailAddress", {})
        .get("address", "")
    )
    subject = email.get("subject", "")
    
    # Prefer full body content if available (from new delta queries), else fallback to preview
    body_content = email.get("body", {}).get("content", "")
    if body_content:
        # Truncate to ~4k chars to prevent LLM timeouts on CPU-only inference
        if len(body_content) > 4000:
            body_text = body_content[:4000] + "\n...[TRUNCATED]..."
        else:
            body_text = body_content
    else:
        body_text = email.get("bodyPreview", "") or ""

    urls = extract_urls(body_text)
    url_warnings = analyze_url_reputation(urls)

    payload = {
        "sender": sender,
        "subject": subject,
        "body": body_text,
        "urls": urls,
        "url_warnings": url_warnings,
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(LLM_API, json=payload)
        resp.raise_for_status()
        return resp.json()