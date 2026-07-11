"""
services/conviction.py — Conviction call tracking system (/call 1-5)

Users reply to a Daemonbot scan with /call <1-5> to record conviction level.
Tracked separately from regular scans — only explicit calls count here.
Leaderboard shows call accuracy over time.
"""

import json
import os
import asyncio
from datetime import datetime
from typing import Optional

CONVICTION_FILE = "data/conviction.json"
_lock = asyncio.Lock()


def _load() -> dict:
    if not os.path.exists(CONVICTION_FILE):
        os.makedirs(os.path.dirname(CONVICTION_FILE), exist_ok=True)
        return {}
    with open(CONVICTION_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(CONVICTION_FILE), exist_ok=True)
    with open(CONVICTION_FILE, "w") as f:
        json.dump(data, f, indent=2)


CONVICTION_LABELS = {
    1: "👀 Watching",
    2: "🤏 Small interest",
    3: "🤝 Moderate conviction",
    4: "🔥 High conviction",
    5: "💎 MAX CONVICTION — diamond hands",
}


async def record_call(
    chat_id: int,
    user_id: int,
    username: str,
    token_name: str,
    symbol: str,
    ca: str,
    price: float,
    conviction: int,
) -> str:
    """Record a conviction call. Returns confirmation message."""
    if conviction not in range(1, 6):
        return "❌ Conviction must be 1-5 ser. Example: `/call 4`"

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
                "stats": {"total": 0, "wins": 0, "losses": 0}
            }

        data[gkey][ukey]["username"] = username
        data[gkey][ukey]["stats"]["total"] += 1

        call_entry = {
            "token":      token_name,
            "symbol":     symbol,
            "ca":         ca,
            "price":      price,
            "conviction": conviction,
            "time":       datetime.utcnow().isoformat(),
            "status":     "open",     # open / win / loss
            "peak_price": price,
            "peak_mult":  1.0,
        }
        data[gkey][ukey]["calls"].append(call_entry)
        _save(data)

    label = CONVICTION_LABELS[conviction]
    stars = "⭐" * conviction + "☆" * (5 - conviction)
    return (
        f"📣 *Call Recorded!*\n\n"
        f"🪙 *{token_name}* `${symbol}`\n"
        f"💰 Entry: `${price:.8f}`\n"
        f"🎯 Conviction: {stars} ({conviction}/5)\n"
        f"🏷 Level: _{label}_\n\n"
        f"_Use /calls to see your call history. Use /clb to see group leaderboard._"
    )


async def get_user_calls(chat_id: int, user_id: int, username: str) -> str:
    """Show a user's conviction calls with current performance."""
    from services.crypto import fetch_token_by_address, fetch_token_by_name

    async with _lock:
        data  = _load()
        gkey  = str(chat_id)
        ukey  = str(user_id)
        udata = data.get(gkey, {}).get(ukey)

    if not udata or not udata.get("calls"):
        return f"📋 No conviction calls from @{username} yet.\nUse `/call <1-5>` while replying to a token scan."

    calls = udata["calls"][-10:][::-1]  # last 10, newest first
    stats = udata.get("stats", {})

    lines = [f"📣 *Conviction Calls — @{username}*\n"]

    for call in calls:
        sym   = call.get("symbol", "?")
        conv  = call.get("conviction", 1)
        stars = "⭐" * conv
        entry = call.get("price", 0)
        time  = call.get("time", "")[:10]
        ca    = call.get("ca", "")

        # Try to get current price
        current = None
        try:
            if ca:
                pair = await fetch_token_by_address(ca)
            else:
                pair = await fetch_token_by_name(sym)
            if pair:
                current = float(pair.get("priceUsd") or 0)
        except Exception:
            pass

        if current and entry > 0:
            pct  = ((current - entry) / entry) * 100
            sign = "+" if pct >= 0 else ""
            arr  = "🟢" if pct >= 0 else "🔴"
            perf = f"{arr} {sign}{pct:.1f}%"
        else:
            perf = "—"

        lines.append(f"{stars} *${sym}* | {perf} | Called {time}")

    lines.append(f"\n📊 Total calls: *{stats.get('total', 0)}*")
    lines.append("_Use /clb for group conviction leaderboard._")
    return "\n".join(lines)


async def get_conviction_leaderboard(chat_id: int) -> str:
    """Group conviction call leaderboard — sorted by total calls."""
    from services.crypto import fetch_token_by_address, fetch_token_by_name

    async with _lock:
        data  = _load()
        gkey  = str(chat_id)
        group = data.get(gkey, {})

    if not group:
        return "❌ No conviction calls in this group yet.\nReply to a scan with `/call <1-5>` to start."

    entries = []
    for uid, info in group.items():
        calls = info.get("calls", [])
        if not calls:
            continue

        # Quick current price check for best call
        best_pct = None
        best_sym = "?"
        for call in calls[-5:]:  # check recent 5
            try:
                ca = call.get("ca", "")
                if ca:
                    pair = await fetch_token_by_address(ca)
                else:
                    pair = await fetch_token_by_name(call.get("symbol", ""))
                if pair:
                    current = float(pair.get("priceUsd") or 0)
                    entry   = call.get("price", 0)
                    if current > 0 and entry > 0:
                        pct = ((current - entry) / entry) * 100
                        if best_pct is None or pct > best_pct:
                            best_pct = pct
                            best_sym = call.get("symbol", "?")
            except Exception:
                pass

        entries.append({
            "username":    info.get("username", "anon"),
            "total":       info.get("stats", {}).get("total", 0),
            "best_pct":    best_pct,
            "best_sym":    best_sym,
        })

    entries.sort(key=lambda x: x["total"], reverse=True)
    medals = ["🥇", "🥈", "🥉"] + ["🔸"] * 20

    lines = ["📣 *Conviction Call Leaderboard*\n"]
    for i, e in enumerate(entries[:8]):
        uname = f"@{e['username']}"
        total = e["total"]
        best  = f"| Best: ${e['best_sym']} +{e['best_pct']:.0f}%" if e["best_pct"] and e["best_pct"] > 0 else ""
        lines.append(f"{medals[i]} {uname} — *{total} calls* {best}")

    lines.append("\n_Reply to any scan with /call <1-5> to log a conviction call._")
    return "\n".join(lines)
