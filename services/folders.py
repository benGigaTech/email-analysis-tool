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
        try:
            resp = await client.post(
                f"{GRAPH_BASE}/users/{user_id}/mailFolders",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            folder = resp.json()
            folder_id = folder["id"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 409:
                raise
            # Folder already exists – look it up
            folder_id = await _lookup_folder_id(client, user_id, headers, folder_name)
            if not folder_id:
                # Surface original error if lookup somehow fails
                raise

    user_state["quarantine_folder_id"] = folder_id
    users_state[user_id] = user_state
    state["users"] = users_state
    save_state(state)

    return folder_id


async def _lookup_folder_id(client: httpx.AsyncClient, user_id: str, headers: dict, folder_name: str) -> str | None:
    params = {"$filter": f"displayName eq '{folder_name}'", "$top": "50"}
    resp = await client.get(
        f"{GRAPH_BASE}/users/{user_id}/mailFolders",
        headers=headers,
        params=params,
    )
    resp.raise_for_status()
    for folder in resp.json().get("value", []):
        if folder.get("displayName") == folder_name:
            return folder.get("id")
    return None