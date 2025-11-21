def simple_rule_based_score(email: dict) -> dict:
    """
    Extremely basic starter scoring.
    We'll plug in real AI later.
    """
    subject = (email.get("subject") or "").lower()
    body = (email.get("bodyPreview") or "").lower()

    score = 0
    reasons = []

    suspicious_words = [
        "password",
        "wire transfer",
        "urgent",
        "verify your account",
        "click here",
        "payment",
        "invoice attached",
    ]

    for word in suspicious_words:
        if word in subject or word in body:
            score += 20
            reasons.append(f"Found suspicious term: {word}")

    from_addr = email.get("from", {}).get("emailAddress", {}).get("address", "")
    if from_addr.endswith("@yourdomain.com"):
        score -= 15
        reasons.append("Internal sender (reduced risk)")

    score = max(0, min(100, score))
    return {
        "risk_score": score,
        "reasons": reasons,
        "is_suspicious": score >= 60,
    }