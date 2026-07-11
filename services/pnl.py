"""
services/pnl.py — PNL Card generator (/pnl, /gpnl)

Generates a visual PNL summary as a formatted Telegram message.
For full image-based PNL cards (like Phanes), you'd use Pillow to
render an image — this version does rich text cards that look clean
in Telegram. Image version scaffolded at the bottom.
"""

import asyncio
from datetime import datetime
from services.crypto import fetch_token_by_address, fetch_token_by_name
from services.leaderboard import _load
from config import LEADERBOARD_FILE


def pnl_emoji(pct: float) -> str:
    if pct >= 100:   return "🚀"
    elif pct >= 50:  return "🔥"
    elif pct >= 10:  return "📈"
    elif pct >= 0:   return "✅"
    elif pct >= -20: return "📉"
    else:            return "💀"


def format_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


async def get_user_pnl(chat_id: int, user_id: int, username: str, query: str) -> str:
    """
    Show a user's PNL for a specific token they called.
    Finds their earliest call price and compares to current price.
    """
    data = _load()
    gkey = str(chat_id)
    ukey = str(user_id)

    user_data = data.get(gkey, {}).get(ukey)
    if not user_data:
        return f"❌ No calls found for @{username} in this group ser. Start calling with /scan or /p."

    calls = user_data.get("calls", [])

    # Find the call matching the query (by symbol or CA)
    matched_call = None
    for call in calls:
        if (
            query.lower() in call.get("symbol", "").lower() or
            query.lower() in call.get("token", "").lower() or
            query.lower() == call.get("ca", "").lower()
        ):
            matched_call = call
            break

    if not matched_call:
        # No specific match — show overall stats
        return await get_user_stats(chat_id, user_id, username)

    # Fetch current price
    ca = matched_call.get("ca", "")
    if ca:
        pair = await fetch_token_by_address(ca)
    else:
        pair = await fetch_token_by_name(matched_call.get("symbol", query))

    entry_price = matched_call.get("price", 0)
    symbol      = matched_call.get("symbol", "?")
    token_name  = matched_call.get("token", symbol)
    call_time   = matched_call.get("time", "?")[:10]

    if pair:
        current_price = float(pair.get("priceUsd") or 0)
    else:
        return f"❌ Couldn't fetch current price for ${symbol}."

    if entry_price <= 0:
        return f"❌ Entry price not recorded for this call."

    pct_change = ((current_price - entry_price) / entry_price) * 100
    emoji = pnl_emoji(pct_change)

    msg = (
        f"💳 *PNL Card — @{username}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 *{token_name}* `${symbol}`\n\n"
        f"📥 Entry:   `${entry_price:.8f}`\n"
        f"📤 Current: `${current_price:.8f}`\n\n"
        f"{emoji} *PNL: {format_pct(pct_change)}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 Called: `{call_time}`\n"
        f"🏷 Total Calls: `{user_data.get('total_calls', 0)}`\n\n"
        f"_NFA. Past performance ≠ future results. DYOR ser._"
    )
    return msg


async def get_user_stats(chat_id: int, user_id: int, username: str) -> str:
    """Show overall call stats for a user in a group."""
    data = _load()
    gkey = str(chat_id)
    ukey = str(user_id)

    user_data = data.get(gkey, {}).get(ukey)
    if not user_data:
        return f"❌ No calls found for @{username} in this group."

    calls       = user_data.get("calls", [])
    total_calls = user_data.get("total_calls", 0)

    # Recent calls list
    recent = calls[-5:][::-1]
    recent_lines = []
    for c in recent:
        sym  = c.get("symbol", "?")
        time = c.get("time", "")[:10]
        recent_lines.append(f"  • ${sym} — {time}")

    recent_text = "\n".join(recent_lines) if recent_lines else "  None yet"

    msg = (
        f"📊 *Stats — @{username}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📣 Total Calls: `{total_calls}`\n\n"
        f"🕐 *Recent Calls:*\n{recent_text}\n\n"
        f"_Use /pnl <token> to see PNL on a specific call._"
    )
    return msg


async def get_group_pnl(chat_id: int, period: str = "7d") -> str:
    """
    Group PNL summary — shows top callers' best performing calls.
    Period: 1d, 7d, 30d, all
    """
    data  = _load()
    gkey  = str(chat_id)
    group = data.get(gkey, {})

    if not group:
        return "❌ No calls logged in this group yet ser."

    # Determine cutoff date
    now = datetime.utcnow()
    cutoff = None
    if period == "1d":
        from datetime import timedelta
        cutoff = now - timedelta(days=1)
    elif period == "7d":
        from datetime import timedelta
        cutoff = now - timedelta(days=7)
    elif period == "30d":
        from datetime import timedelta
        cutoff = now - timedelta(days=30)

    lines = [f"📊 *Group PNL Card — {period}*\n━━━━━━━━━━━━━━━\n"]
    medals = ["🥇", "🥈", "🥉"] + ["🔸"] * 20

    # Collect all callers and their call counts in period
    entries = []
    for uid, info in group.items():
        calls_in_period = info.get("calls", [])
        if cutoff:
            calls_in_period = [
                c for c in calls_in_period
                if c.get("time", "") >= cutoff.isoformat()
            ]
        if calls_in_period:
            entries.append({
                "username": info.get("username", "anon"),
                "count": len(calls_in_period),
                "last": calls_in_period[-1] if calls_in_period else None,
            })

    entries.sort(key=lambda x: x["count"], reverse=True)

    if not entries:
        return f"❌ No calls found in the last {period}."

    for i, e in enumerate(entries[:8]):
        uname = f"@{e['username']}"
        count = e["count"]
        last  = e["last"]
        last_str = f"| Last: ${last['symbol']}" if last else ""
        lines.append(f"{medals[i]} {uname} — *{count} calls* {last_str}")

    lines.append(f"\n_Use /pnl <token> for individual PNL. Period: {period}_")
    return "\n".join(lines)
