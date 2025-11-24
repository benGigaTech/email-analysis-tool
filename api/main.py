from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
import os
import secrets
from dotenv import load_dotenv

from services.graph_client import (
    list_recent_messages,
    move_message,
    get_inbox_folder_id,
)
from services.db import (
    list_quarantine_events,
    get_event_by_id,
    mark_released,
    get_dashboard_stats,
)
from services.logging_utils import get_logger

app = FastAPI()
templates = Jinja2Templates(directory="templates")
logger = get_logger(__name__)
load_dotenv()

security = HTTPBasic()

ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin")


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verify Basic Auth credentials.
    Using secrets.compare_digest to prevent timing attacks.
    """
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASS)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/test/emails")
async def test_emails():
    """
    Simple test endpoint to verify Graph connectivity.
    """
    messages = await list_recent_messages(5)
    simplified = [
        {
            "id": m["id"],
            "subject": m.get("subject"),
            "from": m.get("from", {}).get("emailAddress", {}),
            "receivedDateTime": m.get("receivedDateTime"),
        }
        for m in messages
    ]
    return {"emails": simplified}


@app.get("/quarantine")
async def quarantine_json(limit: int = 50):
    """
    JSON API: list recent quarantine events (for debugging / integration).
    """
    events = list_quarantine_events(limit)
    return {"events": events}


# ---------- Admin HTML Dashboard ----------

@app.get("/admin/quarantine", response_class=HTMLResponse)
async def admin_quarantine(
    request: Request, 
    limit: int = 50,
    username: str = Depends(get_current_username)
):
    """
    HTML dashboard: show quarantine events in a table.
    Protected by Basic Auth.
    """
    events = list_quarantine_events(limit)
    stats = get_dashboard_stats()
    return templates.TemplateResponse(
        "quarantine.html",
        {"request": request, "events": events, "stats": stats, "user": username},
    )


@app.get("/admin/quarantine/{event_id}/release")
async def admin_release(
    event_id: int, 
    request: Request,
    username: str = Depends(get_current_username)
):
    """
    Release an email from AI-Quarantine back to Inbox.
    Protected by Basic Auth.
    """
    logger.info("release requested", extra={"event_id": event_id, "admin": username})

    # Find event in DB
    event = get_event_by_id(event_id)
    if not event:
        logger.warning("event not found", extra={"event_id": event_id})
        return RedirectResponse(url="/admin/quarantine", status_code=303)

    message_id = event["message_id"]
    logger.info(
        "loaded event",
        extra={"event_id": event_id, "message_id": message_id},
    )

    # Get Inbox folder ID from Graph
    inbox_folder_id = await get_inbox_folder_id()
    logger.info("resolved inbox folder", extra={"folder_id": inbox_folder_id})

    # Move message back to Inbox
    await move_message(message_id, inbox_folder_id)
    logger.info(
        "released message",
        extra={"event_id": event_id, "message_id": message_id},
    )

    # Mark as released in DB
    mark_released(event_id)
    logger.info("marked event as released", extra={"event_id": event_id})

    # Redirect back to dashboard
    return RedirectResponse(url="/admin/quarantine", status_code=303)