import asyncio
import os

from dotenv import load_dotenv

from services.graph_client import (
    get_delta_messages,
    move_message,
    get_all_mail_users,
)
from services.db import init_db, log_quarantine_event
from services.folders import ensure_quarantine_folder
from services.llama_classifier import classify_with_llama
from services.logging_utils import get_logger

load_dotenv()

# Configurable knobs
RISK_THRESHOLD = int(os.getenv("RISK_THRESHOLD", "60"))
# If set, we'll treat messages from *@ORG_DOMAIN as internal (not auto-quarantined)
ORG_DOMAIN = os.getenv("ORG_DOMAIN")  # e.g. "yourcompany.com"

logger = get_logger(__name__)

async def process_user(user_id_or_email: str):
    """
    Process new/changed messages for a single mailbox.

    user_id_or_email is used both as:
      - the identifier for Graph (/users/{user_id_or_email}/...)
      - the user_email stored in the DB
    """
    user_email = user_id_or_email

    messages = await get_delta_messages(user_id_or_email)
    logger.info(
        "delta returned %d messages",
        len(messages),
        extra={"user_email": user_email},
    )

    # Ensure / cache quarantine folder for this mailbox
    quarantine_folder_id = await ensure_quarantine_folder(user_id_or_email)

    for m in messages:
        subject = m.get("subject")
        logger.info(
            "processing message",
            extra={
                "user_email": user_email,
                "message_id": m.get("id"),
                "subject": subject,
            },
        )

        # Classify with local Llama
        score = await classify_with_llama(m)
        risk = score.get("risk_score", 0) or 0
        classification = (score.get("classification") or "unknown").lower()

        # Normalize classification
        if classification not in {"safe", "spam", "phishing", "malicious"}:
            classification = "spam"  # fail-closed-ish but not too harsh

        # Determine if sender is external
        from_addr = (
            (m.get("from", {}) or {})
            .get("emailAddress", {})
            .get("address", "")
        )
        if ORG_DOMAIN:
            is_external = not from_addr.lower().endswith(ORG_DOMAIN.lower())
        else:
            # If ORG_DOMAIN not set, treat everything as external for now
            is_external = True

        # NEW: decision logic
        moved = False
        quarantine_reason = None

        # We never quarantine "safe" emails, regardless of risk_score
        if classification == "safe":
            quarantine = False
            quarantine_reason = "classification=safe"
        else:
            # For spam: use threshold
            if classification == "spam":
                quarantine = is_external and risk >= RISK_THRESHOLD
                quarantine_reason = f"spam & risk>={RISK_THRESHOLD}"
            # For phishing/malicious: more aggressive
            elif classification in {"phishing", "malicious"}:
                # Even if risk is low, treat as dangerous
                quarantine = is_external and (risk >= (RISK_THRESHOLD - 10))
                quarantine_reason = f"{classification} & risk>={RISK_THRESHOLD - 10}"
            else:
                quarantine = False
                quarantine_reason = "unknown classification"

        if quarantine:
            await move_message(user_id_or_email, m["id"], quarantine_folder_id)
            moved = True
            logger.warning(
                "moved message to AI-Quarantine",
                extra={
                    "user_email": user_email,
                    "message_id": m.get("id"),
                    "risk_score": risk,
                    "classification": classification,
                    "is_external": is_external,
                    "rule": quarantine_reason,
                },
            )
        else:
            logger.info(
                "left message in inbox",
                extra={
                    "user_email": user_email,
                    "message_id": m.get("id"),
                    "risk_score": risk,
                    "classification": classification,
                    "is_external": is_external,
                    "rule": quarantine_reason,
                },
            )

        # Log decision in SQLite, tagged with this mailbox
        log_quarantine_event(user_email, m, score, moved)

async def main():
    # Ensure DB schema exists
    init_db()
    logger.info("AI Email Poller started - using delta-based polling")

    while True:
        try:
            # Discover all mail-enabled users each cycle.
            # For larger tenants, you can cache this and refresh periodically.
            all_users = await get_all_mail_users()
            user_emails = [u["mail"] for u in all_users if u.get("mail")]

            logger.info("discovered %d mail-enabled users", len(user_emails))

            for user_email in user_emails:
                await process_user(user_email)

        except Exception:
            logger.exception("poller loop error")

        # Sleep between polling cycles
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())