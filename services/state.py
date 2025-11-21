import json
import os
from threading import Lock

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "state.json")
_state_lock = Lock()

def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with _state_lock:
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

def save_state(state: dict):
    with _state_lock:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)