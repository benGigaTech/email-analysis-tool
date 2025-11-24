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
    
    # Extract URLs from the FULL content before truncation
    # This ensures links at the bottom of long emails are caught
    full_text_for_urls = body_content if body_content else (email.get("bodyPreview", "") or "")
    urls = extract_urls(full_text_for_urls)
    url_warnings = analyze_url_reputation(urls)

    # Prepare body text for LLM (truncated)
    if body_content:
        # Truncate to ~2k chars to improve CPU inference speed
        if len(body_content) > 2000:
            body_text = body_content[:2000] + "\n...[TRUNCATED]..."
        else:
            body_text = body_content
    else:
        body_text = full_text_for_urls

    payload = {
        "sender": sender,
        "subject": subject,
        "body": body_text,
        "urls": urls,
        "url_warnings": url_warnings,
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(LLM_API, json=payload)
        resp.raise_for_status()
        return resp.json()