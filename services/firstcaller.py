"""
services/firstcaller.py — Track and display who called a token first (/fc)
"""

import json
import os
import asyncio
from datetime import datetime
from config import LEADERBOARD_FILE
from services.leaderboard import _load


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
