"""
services/firstcaller.py — Track and display who called a token first (/fc)
"""

import json
import os
import asyncio
from datetime import datetime
from config import LEADERBOARD_FILE
from services.leaderboard import _load


async def get_first_caller_line(chat_id: int, ca: str, current_pair: dict) -> str | None:
    """Compact one-liner for embedding in /p, /scan, and autodetect replies —
    e.g. '🐳 KINGSYCO9 @ $30.7M [+12%] (17m)'. Returns None if nobody in this
    group has called this token yet (stays silent, doesn't clutter replies
    for tokens with no call history).

    Market cap shown is the *entry* market cap (back-calculated from the
    logged entry price vs current price and current market cap — assumes
    supply hasn't changed, which holds for the vast majority of tokens),
    so the % reflects how the call has actually performed.
    """
    from datetime import datetime, timezone
    from services.scan_data import _format_age

    data = _load()
    group = data.get(str(chat_id), {})
    if not group:
        return None

    ca_lower = ca.lower().strip()
    matches = []
    for uid, info in group.items():
        for call in info.get("calls", []):
            if call.get("ca", "").lower() == ca_lower:
                matches.append({
                    "username": info.get("username", "anon"),
                    "time": call.get("time", ""),
                    "price": call.get("price", 0),
                })

    if not matches:
        return None

    matches.sort(key=lambda x: x["time"])
    first = matches[0]
    entry_price = first["price"] or 0
    if entry_price <= 0:
        return None

    current_price = float(current_pair.get("priceUsd") or 0)
    current_mc = float(current_pair.get("marketCap", 0) or current_pair.get("fdv", 0) or 0)
    if current_price <= 0 or current_mc <= 0:
        return None

    pct_change = (current_price - entry_price) / entry_price * 100
    entry_mc = current_mc * (entry_price / current_price)

    try:
        called_at = datetime.fromisoformat(first["time"])
        if called_at.tzinfo is None:
            called_at = called_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - called_at).total_seconds()
        time_ago = _format_age(elapsed)
    except (ValueError, TypeError):
        time_ago = "?"

    from services.crypto import format_number
    mc_str = format_number(entry_mc)
    emoji = "🐳" if len(matches) == 1 else "🐳"
    return f"{emoji} *{first['username']}* @ {mc_str} `[{pct_change:+.0f}%]` ({time_ago})"


async def get_first_caller(chat_id: int, ca_or_symbol: str) -> str:
    """Find who first called a token in this group."""
    data  = _load()
    gkey  = str(chat_id)
    group = data.get(gkey, {})

    if not group:
        return "❌ No calls logged in this group yet."

    query = ca_or_symbol.lower().strip()
    matches = []

    for uid, info in group.items():
        for call in info.get("calls", []):
            if (
                query in call.get("symbol", "").lower() or
                query in call.get("token", "").lower() or
                query == call.get("ca", "").lower()
            ):
                matches.append({
                    "username": info.get("username", "anon"),
                    "time":     call.get("time", ""),
                    "price":    call.get("price", 0),
                    "symbol":   call.get("symbol", "?"),
                    "token":    call.get("token", "?"),
                    "ca":       call.get("ca", ""),
                })

    if not matches:
        return (
            f"❌ No recorded calls for `{ca_or_symbol}` in this group.\n"
            f"_Token might not have been called here yet._"
        )

    # Sort by time ascending — first caller is earliest
    matches.sort(key=lambda x: x["time"])
    first   = matches[0]
    rest    = matches[1:]

    symbol   = first["symbol"]
    token    = first["token"]
    fc_time  = first["time"][:16].replace("T", " ")
    fc_price = first["price"]
    fc_user  = first["username"]
    ca       = first["ca"]

    lines = [
        f"🏆 *First Caller — ${symbol}*\n",
        f"👑 *@{fc_user}*",
        f"⏱ Called at: `{fc_time} UTC`",
        f"💰 Entry price: `${fc_price:.8f}`\n",
    ]

    if rest:
        lines.append(f"📋 *Also called by ({len(rest)}):*")
        for r in rest[:5]:
            t = r["time"][:10]
            lines.append(f"  • @{r['username']} — {t}")
        if len(rest) > 5:
            lines.append(f"  _...and {len(rest)-5} more_")

    if ca:
        lines.append(f"\n`{ca}`")

    return "\n".join(lines)
