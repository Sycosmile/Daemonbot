"""
services/settings.py — Per-group toggles (currently just /autodetect)
Daemonbot — MR SYCO (@Sycosmile)
"""

import json
import os
import asyncio

SETTINGS_FILE = os.path.join("data", "group_settings.json")
_lock = asyncio.Lock()


def _load() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        return {}
    with open(SETTINGS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def get_autodetect(chat_id: int) -> bool:
    """Passive $ticker/CA detection — defaults ON, matching Rick/Phanes behavior."""
    async with _lock:
        data = _load()
        return data.get(str(chat_id), {}).get("autodetect", True)


async def set_autodetect(chat_id: int, enabled: bool):
    async with _lock:
        data = _load()
        gkey = str(chat_id)
        if gkey not in data:
            data[gkey] = {}
        data[gkey]["autodetect"] = enabled
        _save(data)


async def get_antiscam(chat_id: int) -> bool:
    """Scammer detection (deletes flagged messages) — defaults OFF.
    This takes a destructive action on a false positive, so it must be an
    explicit opt-in, unlike the read-only autodetect feature above."""
    async with _lock:
        data = _load()
        return data.get(str(chat_id), {}).get("antiscam", False)


async def set_antiscam(chat_id: int, enabled: bool):
    async with _lock:
        data = _load()
        gkey = str(chat_id)
        if gkey not in data:
            data[gkey] = {}
        data[gkey]["antiscam"] = enabled
        _save(data)
