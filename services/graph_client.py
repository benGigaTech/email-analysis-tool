import os
import httpx
from dotenv import load_dotenv

from services.auth import get_token
from services.state import load_state, save_state
from services.logging_utils import get_logger

load_dotenv()

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
# For legacy endpoints in the API that don't specify a user explicitly
DEFAULT_USER = os.getenv("MONITORED_USER")

logger = get_logger(__name__)

async def get_all_mail_users():
    """
    Return a list of mail-enabled users in the tenant.

    Primary mode: call /users (requires directory permissions).
    Fallback: if 403 Forbidden, use MONITORED_USERS from env.
    """
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}

    env_users = [
        u.strip()
        for u in os.getenv("MONITORED_USERS", "").split(",")
        if u.strip()
    ]

    url = f"{GRAPH_BASE}/users?$select=id,userPrincipalName,mail&$top=50"
    users = []

    async with httpx.AsyncClient() as client:
        try:
            while True:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                for u in data.get("value", []):
                    mail = u.get("mail")
                    if mail:
                        users.append(
                            {
                                "id": u["id"],
                                "userPrincipalName": u["userPrincipalName"],
                                "mail": mail,
                            }
                        )

                next_link = data.get("@odata.nextLink")
                if next_link:
                    url = next_link
                    continue

                break

            # If Graph returned some users, use them
            if users:
                return users

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 403:
                logger.warning(
                    "403 Forbidden on /users - falling back to env configured users"
                )
            else:
                logger.error("error calling /users", exc_info=True)
        except Exception:
            logger.exception("unexpected error in get_all_mail_users")

    # Fallback: environment-defined users
    if env_users:
        logger.info("using MONITORED_USERS fallback", extra={"users": env_users})
        return [
            {
                "id": u,
                "userPrincipalName": u,
                "mail": u,
            }
            for u in env_users
        ]

    logger.error("no users discovered and MONITORED_USERS not set")
    return []


async def get_delta_messages(user_id: str):
    """
    Use Microsoft Graph delta query to get new/changed messages for a given user.
    Stores and updates a per-user deltaLink in state.json.
    user_id should be something Graph accepts in /users/{user_id}, e.g. UPN or mail.
    """
    state = load_state()
    users_state = state.get("users", {})
    user_state = users_state.get(user_id, {})

    delta_link = user_state.get("delta_link")

    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}

    if not delta_link:
        url = f"{GRAPH_BASE}/users/{user_id}/mailFolders/inbox/messages/delta"
    else:
        url = delta_link

    messages = []

    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            page_msgs = data.get("value", [])
            for m in page_msgs:
                if "@removed" in m:
                    continue
                messages.append(m)

            next_link = data.get("@odata.nextLink")
            new_delta_link = data.get("@odata.deltaLink")

            if next_link:
                url = next_link
                continue

            if new_delta_link:
                user_state["delta_link"] = new_delta_link
                users_state[user_id] = user_state
                state["users"] = users_state
                save_state(state)

            break

    return messages


async def move_message(user_id: str, message_id: str, destination_folder_id: str):
    """
    Move a message to a different folder for a specific user.
    """
    token = await get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    body = {"destinationId": destination_folder_id}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_BASE}/users/{user_id}/messages/{message_id}/move",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


# ---- Legacy helpers used by the API test endpoints ----

async def list_recent_messages(top: int = 10):
    """
    Legacy helper for /test/emails endpoint.
    Uses DEFAULT_USER from env (MONITORED_USER).
    """
    if not DEFAULT_USER:
        raise RuntimeError("MONITORED_USER is not set in environment")

    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}

    params = {
        "$top": top,
        "$orderby": "receivedDateTime desc",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE}/users/{DEFAULT_USER}/mailFolders/inbox/messages",
            headers=headers,
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("value", [])


async def get_inbox_folder_id(user_id: str | None = None):
    """
    Get Inbox folder ID for a user.
    If user_id is None, uses DEFAULT_USER (for admin 'release' API).
    """
    user = user_id or DEFAULT_USER
    if not user:
        raise RuntimeError("No user_id provided and MONITORED_USER not set")

    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE}/users/{user}/mailFolders/inbox",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["id"]