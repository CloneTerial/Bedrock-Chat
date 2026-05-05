import os
import json
from config import MODELS, DEFAULT_SYSTEM_PROMPT

CHATS_DIR = "chats"
SETTINGS_FILE = "settings.json"

os.makedirs(CHATS_DIR, exist_ok=True)

def get_settings() -> dict:
    """Retrieve application settings from file or return defaults."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "default_model": list(MODELS.keys())[0],
        "temperature": 0.7,
        "max_tokens": 4096,
        "tools_enabled": True,
    }

def put_settings(s: dict):
    """Save application settings to a JSON file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)

def get_conv(cid: str):
    """Load a specific conversation by its ID."""
    p = os.path.join(CHATS_DIR, f"{cid}.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)

def put_conv(c: dict):
    """Save or update a conversation object in the chats directory."""
    with open(os.path.join(CHATS_DIR, f"{c['id']}.json"), "w") as f:
        json.dump(c, f, indent=2, default=str)

def del_conv(cid: str):
    """Delete a specific conversation file."""
    p = os.path.join(CHATS_DIR, f"{cid}.json")
    if os.path.exists(p):
        os.remove(p)

def list_convs() -> list:
    """List all saved conversations with their metadata, sorted by last update."""
    out = []
    if not os.path.exists(CHATS_DIR):
        return []
    for fn in os.listdir(CHATS_DIR):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(CHATS_DIR, fn)) as f:
                d = json.load(f)
            out.append({
                "id": d["id"],
                "title": d["title"],
                "model": d.get("model", ""),
                "updated_at": d.get("updated_at", ""),
                "total_cost": d.get("total_cost", 0),
            })
        except Exception:
            pass
    out.sort(key=lambda x: x["updated_at"], reverse=True)
    return out
