import os
import httpx
from dotenv import load_dotenv

from services.url_analysis import extract_urls

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
    body_preview = email.get("bodyPreview", "") or ""

    urls = extract_urls(body_preview)

    payload = {
        "sender": sender,
        "subject": subject,
        "body": body_preview,
        "urls": urls,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(LLM_API, json=payload)
        resp.raise_for_status()
        return resp.json()