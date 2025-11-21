import httpx
from dotenv import load_dotenv

from services.auth import get_token
from services.state import load_state, save_state

load_dotenv()

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


async def ensure_quarantine_folder(user_id: str, folder_name: str = "AI-Quarantine") -> str:
    """
    Ensure the user has an AI-Quarantine folder.
    Returns the folder ID, creating it if necessary.
    Cached in state.json per user.
    """
    state = load_state()
    users_state = state.get("users", {})
    user_state = users_state.get(user_id, {})

    if "quarantine_folder_id" in user_state:
        return user_state["quarantine_folder_id"]

    token = await get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        payload = {"displayName": folder_name}
        resp = await client.post(
            f"{GRAPH_BASE}/users/{user_id}/mailFolders",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        folder = resp.json()
        folder_id = folder["id"]

    user_state["quarantine_folder_id"] = folder_id
    users_state[user_id] = user_state
    state["users"] = users_state
    save_state(state)

    return folder_id