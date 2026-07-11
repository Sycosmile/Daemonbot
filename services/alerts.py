"""
services/alerts.py — Price alerts / watchlist.
Checked periodically by a JobQueue job registered in main.py.
"""

import json
import os
import asyncio
import uuid
from config import LEADERBOARD_FILE

ALERTS_FILE = os.path.join(os.path.dirname(LEADERBOARD_FILE), "alerts.json")
_lock = asyncio.Lock()


def _load() -> dict:
    if not os.path.exists(ALERTS_FILE):
        os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
        return {}
    with open(ALERTS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
    with open(ALERTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def add_alert(
    chat_id: int, user_id: int, username: str,
    query: str, ca: str, symbol: str,
    target_price: float, direction: str,
) -> str:
    """direction: 'above' or 'below'. Returns the new alert's short id."""
    async with _lock:
        data = _load()
        gkey, ukey = str(chat_id), str(user_id)
        data.setdefault(gkey, {}).setdefault(ukey, {"username": username, "alerts": []})
        data[gkey][ukey]["username"] = username

        alert_id = uuid.uuid4().hex[:6]
        data[gkey][ukey]["alerts"].append({
            "id": alert_id,
            "query": query,
            "ca": ca,
            "symbol": symbol,
            "target": target_price,
            "direction": direction,
            "active": True,
        })
        _save(data)
        return alert_id


async def list_user_alerts(chat_id: int, user_id: int) -> list[dict]:
    async with _lock:
        data = _load()
        info = data.get(str(chat_id), {}).get(str(user_id), {})
        return [a for a in info.get("alerts", []) if a.get("active")]


async def remove_alert(chat_id: int, user_id: int, alert_id: str) -> bool:
    async with _lock:
        data = _load()
        info = data.get(str(chat_id), {}).get(str(user_id))
        if not info:
            return False
        for a in info["alerts"]:
            if a["id"] == alert_id:
                a["active"] = False
                _save(data)
                return True
        return False


async def get_all_active_alerts() -> list[dict]:
    """Flattened list across all chats/users — used by the periodic checker job."""
    async with _lock:
        data = _load()
    out = []
    for chat_id, users in data.items():
        for user_id, info in users.items():
            for a in info.get("alerts", []):
                if a.get("active"):
                    out.append({
                        **a,
                        "chat_id": int(chat_id),
                        "user_id": int(user_id),
                        "username": info.get("username", "anon"),
                    })
    return out


async def deactivate_alert(chat_id: int, user_id: int, alert_id: str):
    await remove_alert(chat_id, user_id, alert_id)


async def check_due_alerts(bot):
    """Called periodically by main.py's JobQueue. Checks every active alert's
    current price and DMs/messages the triggering chat when it hits."""
    from services.crypto import fetch_token_by_address, fetch_token_by_name
    import logging
    logger = logging.getLogger(__name__)

    alerts = await get_all_active_alerts()
    for a in alerts:
        try:
            pair = await fetch_token_by_address(a["ca"]) if a.get("ca") else None
            if not pair:
                pair = await fetch_token_by_name(a["query"])
            if not pair:
                continue
            price = float(pair.get("priceUsd") or 0)
            if price <= 0:
                continue

            hit = (
                (a["direction"] == "above" and price >= a["target"]) or
                (a["direction"] == "below" and price <= a["target"])
            )
            if hit:
                await _send_alert_card(bot, a, price, logger)
                await deactivate_alert(a["chat_id"], a["user_id"], a["id"])
        except Exception as e:
            logger.warning(f"Alert check failed for {a.get('id')}: {e}")


async def _send_alert_card(bot, a: dict, price: float, logger):
    """Same image card as /scan, sent into the chat that set the alert.
    Falls back to the old plain-text ping if the card pipeline fails for
    any reason — an alert firing should never end up silent."""
    caption = (
        f"🔔 *Alert triggered!*\n"
        f"@{a['username']}'s *${a['symbol']}* hit "
        f"`${price:,.8f}` ({a['direction']} target `${a['target']:,.8f}`)"
    )
    try:
        import asyncio, io
        from services.scan_data import build_scan_data
        from services.scan_card import generate_scan_card

        data = await build_scan_data(a.get("ca") or a["query"])
        if not data:
            raise ValueError("no scan data")

        loop = asyncio.get_event_loop()
        img_bytes = await loop.run_in_executor(None, generate_scan_card, data)

        await bot.send_photo(chat_id=a["chat_id"], photo=io.BytesIO(img_bytes),
                              caption=caption, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Alert card render failed for {a.get('id')}, falling back to text: {e}")
        try:
            await bot.send_message(chat_id=a["chat_id"], text=caption, parse_mode="Markdown")
        except Exception as e2:
            logger.warning(f"Couldn't send alert notification to {a['chat_id']}: {e2}")
