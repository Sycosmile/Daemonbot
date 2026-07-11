"""
services/leaderboard.py — Track token calls per user in groups.
A "call" is logged when someone uses /scan or /p with a CA in a group.
Persisted to JSON file so it survives restarts.
"""

import json
import os
import asyncio
from datetime import datetime
from config import LEADERBOARD_FILE, MAX_LEADERBOARD_ENTRIES

_lock = asyncio.Lock()
_cache: dict = {}   # in-memory copy — avoids disk read on every scan/paste


def _load() -> dict:
    global _cache
    if _cache:
        return _cache
    if not os.path.exists(LEADERBOARD_FILE):
        os.makedirs(os.path.dirname(LEADERBOARD_FILE), exist_ok=True)
        return {}
    with open(LEADERBOARD_FILE) as f:
        try:
            _cache = json.load(f)
            return _cache
        except json.JSONDecodeError:
            return {}


def _save(data: dict):
    global _cache
    _cache = data   # keep memory copy in sync
    os.makedirs(os.path.dirname(LEADERBOARD_FILE), exist_ok=True)
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def log_call(
    chat_id: int,
    user_id: int,
    username: str,
    token_name: str,
    token_symbol: str,
    price_usd: float,
    ca: str,
):
    """Log a token call for a user in a group."""
    async with _lock:
        data = _load()
        gkey = str(chat_id)
        ukey = str(user_id)

        if gkey not in data:
            data[gkey] = {}
        if ukey not in data[gkey]:
            data[gkey][ukey] = {
                "username": username,
                "calls": [],
                "total_calls": 0,
            }

        data[gkey][ukey]["username"] = username  # always update
        data[gkey][ukey]["total_calls"] += 1
        data[gkey][ukey]["calls"].append({
            "token":  token_name,
            "symbol": token_symbol,
            "price":  price_usd,
            "ca":     ca,
            "time":   datetime.utcnow().isoformat(),
        })
        # Keep only last 50 calls per user
        data[gkey][ukey]["calls"] = data[gkey][ukey]["calls"][-50:]
        _save(data)


async def get_leaderboard(chat_id: int) -> list[dict]:
    """Return sorted leaderboard for a group."""
    async with _lock:
        data = _load()
        gkey = str(chat_id)
        group = data.get(gkey, {})

        board = []
        for uid, info in group.items():
            board.append({
                "user_id":    uid,
                "username":   info.get("username", "anon"),
                "total_calls": info.get("total_calls", 0),
                "last_call":  info["calls"][-1] if info.get("calls") else None,
            })

        board.sort(key=lambda x: x["total_calls"], reverse=True)
        return board[:MAX_LEADERBOARD_ENTRIES]


def format_leaderboard(board: list[dict], group_name: str = "this group") -> str:
    if not board:
        return "📋 No calls logged yet ser. Start calling tokens with /scan or /p."

    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 10
    lines  = [f"📊 *Leaderboard — {group_name}*\n"]

    for i, entry in enumerate(board):
        uname = f"@{entry['username']}" if entry["username"] != "anon" else "anon"
        calls = entry["total_calls"]
        last  = entry.get("last_call")
        last_str = f"Last: ${last['symbol']}" if last else ""
        lines.append(f"{medals[i]} {uname} — *{calls} calls* {last_str}")

    lines.append("\n_Call tokens with /scan <CA> to get on the board._")
    return "\n".join(lines)


async def record_pnl_peak(chat_id: int, user_id: int, call_time: str, price_usd: float) -> float:
    """Updates (if higher) and returns the peak price seen for a specific
    call since it was made — powers the PNL card's 'Reached $X' line.

    This is lazily updated, not continuously monitored: the peak is only as
    fresh as the last time someone ran /pnl for that call. Matched by
    call_time (unique per call within a user's history) rather than ca,
    since ca can be blank for symbol-only calls.
    """
    async with _lock:
        data = _load()
        gkey, ukey = str(chat_id), str(user_id)
        calls = data.get(gkey, {}).get(ukey, {}).get("calls", [])
        for call in calls:
            if call.get("time") == call_time:
                peak = max(call.get("peak_price", call.get("price", 0)) or 0, price_usd)
                call["peak_price"] = peak
                _save(data)
                return peak
    return price_usd
