from fastapi import FastAPI
import httpx
import json

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

EMAIL_CLASSIFIER_PROMPT = """
You are an AI email threat classifier.

You MUST respond ONLY in valid JSON with this exact structure:

{{
  "risk_score": 0-100,
  "classification": "safe" | "spam" | "phishing" | "malicious",
  "reasons": ["reason1", "reason2", "..."]
}}

Guidelines:
- "phishing": attempts to steal credentials, payments, or impersonate trusted parties.
- "malicious": malware delivery, clearly harmful payloads or exploit attempts.
- "spam": unsolicited marketing/junk that is not clearly dangerous.
- "safe": legitimate, expected messages with no obvious malicious intent.

Consider:
- Sender address patterns and domain.
- Subject urgency and pressure language.
- Requests for credentials, payments, wire transfers, gift cards, etc.
- ANY links or URLs (domains, paths, suspicious TLDs, IP-based URLs).
- Consistency between sender and content.

Email Metadata:
From: {sender}
Subject: {subject}

System Detected Warnings (heuristic analysis):
{warnings_section}

Body Preview:
{body}

Links found in the email body:
{urls_section}

Task:
1. Evaluate overall threat level (safe/spam/phishing/malicious).
2. Assign a numeric risk_score (0-100) where:
   - 0-20 = very low risk
   - 21-49 = low/medium risk
   - 50-79 = elevated risk
   - 80-100 = high/critical risk
3. Provide 1-5 short, concrete reasons.

Return ONLY the JSON object. No markdown, no comments, no extra text.
"""


app = FastAPI()


@app.post("/classify")
async def classify_email(email: dict):
    sender = email.get("sender", "")
    subject = email.get("subject", "")
    body = email.get("body", "")
    urls = email.get("urls", []) or []
    warnings = email.get("url_warnings", []) or []

    if urls:
        urls_section = "\n".join(f"- {u}" for u in urls)
    else:
        urls_section = "No links detected."

    if warnings:
        warnings_section = "\n".join(f"CRITICAL: {w}" for w in warnings)
    else:
        warnings_section = "None."

    prompt = EMAIL_CLASSIFIER_PROMPT.format(
        sender=sender,
        subject=subject,
        body=body,
        urls_section=urls_section,
        warnings_section=warnings_section,
    )

    payload = {
        "model": "llama3.1:8b",
        "prompt": prompt,
        "temperature": 0.0,
        "num_predict": 220,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(OLLAMA_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        content = data.get("response", "")

    # Try to parse JSON from the response
    try:
        result = json.loads(content)

        # Basic sanity normalization
        classification = (result.get("classification") or "spam").lower()
        risk_score = result.get("risk_score")

        if risk_score is None:
            # Default by classification if missing
            if classification == "safe":
                risk_score = 10
            elif classification == "spam":
                risk_score = 40
            elif classification in {"phishing", "malicious"}:
                risk_score = 80
            else:
                risk_score = 50

        # Clamp range 0-100
        risk_score = max(0, min(int(risk_score), 100))

        # Calibrate risk to match classification
        if classification == "safe" and risk_score > 30:
            risk_score = 20  # safe should be low
        elif classification == "spam" and risk_score < 20:
            risk_score = 35
        elif classification in {"phishing", "malicious"} and risk_score < 60:
            risk_score = 75

        result["classification"] = classification
        result["risk_score"] = risk_score

        if "reasons" not in result:
            result["reasons"] = ["Model did not provide reasons"]

        return result

    except Exception:
        # Fallback: treat as high risk if we can't parse JSON
        return {
            "risk_score": 90,
            "classification": "phishing",
            "reasons": [
                "Model returned invalid JSON. Failing closed as phishing."
            ],
        }