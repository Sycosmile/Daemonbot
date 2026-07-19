"""
services/leaderboard.py — Track token calls per user in groups.
A "call" is logged when someone uses /scan or /p with a CA in a group.
Persisted to Upstash Redis (survives Render redeploys) with automatic
fallback to a local JSON file when Upstash isn't configured.
"""

import json
import os
import asyncio
import statistics
from datetime import datetime, timedelta
from config import LEADERBOARD_FILE, MAX_LEADERBOARD_ENTRIES
from services.kv_store import kv_get, kv_set

_lock = asyncio.Lock()
_cache: dict = {}   # in-memory copy — avoids a network/disk read on every scan/paste
LEADERBOARD_KEY = "daemonbot:leaderboard"


def _load() -> dict:
    global _cache
    if _cache:
        return _cache

    remote = kv_get(LEADERBOARD_KEY)
    if remote is not None:
        _cache = remote
        return _cache

    # Fallback: local file (Upstash not configured, or the request failed)
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
    _cache = data   # keep memory copy in sync regardless of where it lands

    if kv_set(LEADERBOARD_KEY, data):
        return  # persisted to Upstash — done

    # Fallback: local file (data still survives this process's lifetime,
    # just not across a redeploy, if Upstash isn't configured/reachable)
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


# ── Calls-ranked leaderboard (Group Stats + Top Calls) ──────────────

PERIOD_DAYS = {"1d": 1, "7d": 7, "all": None}
PERIOD_LABELS = {"1d": "1D", "7d": "7D", "all": "All-time"}
HIT_MULTIPLIER = 2.0  # a call counts as a "hit" once its peak reaches 2x
_RANK_ICONS = ["🥇", "🥈", "🥉"] + ["🔸"] * 20


def _within_period(call_time_iso: str, days: int | None) -> bool:
    if days is None:
        return True
    try:
        call_dt = datetime.fromisoformat(call_time_iso)
    except (ValueError, TypeError):
        # Can't parse the timestamp — don't silently exclude it from
        # a period filter we can't actually evaluate.
        return True
    return datetime.utcnow() - call_dt <= timedelta(days=days)


async def get_calls_leaderboard(chat_id: int, period: str = "7d", top_n: int = 10) -> dict:
    """
    Ranks individual calls (not users) by peak multiplier reached since the
    call was made, within the given period. Reuses record_pnl_peak's lazy
    pattern: each call's current price is fetched live and peak_price is
    bumped if higher, so ranking accuracy improves the more this (or /pnl)
    gets run — no background price poller required.

    Returns {"group_stats": {...} | None, "top_calls": [...]}
    """
    from services.crypto import fetch_token_by_address, fetch_token_by_name

    days = PERIOD_DAYS.get(period, 7)

    async with _lock:
        data = _load()
        gkey = str(chat_id)
        group = data.get(gkey, {})

        candidates = []
        for ukey, info in group.items():
            username = info.get("username", "anon")
            # Dedupe: keep only this user's EARLIEST call per token. Every
            # /scan, /p, or CA paste logs a fresh call entry (so first-caller
            # attribution updates live), but that means re-checking the same
            # coin repeatedly would otherwise show up as multiple "calls" on
            # the leaderboard — this collapses those back down to one entry
            # per (user, token), using their real first call as the basis.
            earliest_by_ca = {}
            for call in info.get("calls", []):
                if not _within_period(call.get("time", ""), days):
                    continue
                if not call.get("price"):
                    continue
                ca_key = call.get("ca", "").lower() or call.get("symbol", "").lower()
                if not ca_key:
                    continue
                existing = earliest_by_ca.get(ca_key)
                if existing is None or call.get("time", "") < existing.get("time", ""):
                    earliest_by_ca[ca_key] = call

            for call in earliest_by_ca.values():
                candidates.append((username, call))

        if not candidates:
            return {"group_stats": None, "top_calls": []}

        async def _fetch_current(call):
            ca = call.get("ca", "")
            try:
                pair = await fetch_token_by_address(ca) if ca \
                    else await fetch_token_by_name(call.get("symbol", ""))
                if not pair and ca:
                    # Not yet migrated off pump.fun's bonding curve —
                    # DexScreener has nothing, pump.fun's own API still does.
                    from services.pumpfun import fetch_pumpfun_coin
                    pf = await fetch_pumpfun_coin(ca)
                    mcap = (pf or {}).get("usd_market_cap", (pf or {}).get("market_cap", 0)) or 0
                    if mcap:
                        pair = {"priceUsd": str(mcap / 1_000_000_000), "marketCap": mcap, "chainId": "solana"}
                return pair
            except (TypeError, ValueError):
                return None

        current_pairs = await asyncio.gather(
            *[_fetch_current(call) for (_, call) in candidates]
        )

        from services.ath_tracker import get_real_ath_mc

        results = []
        for (username, call), pair in zip(candidates, current_pairs):
            entry_price = call.get("price", 0) or 0
            if entry_price <= 0:
                continue

            current_price = float((pair or {}).get("priceUsd") or 0)
            current_mc = float((pair or {}).get("marketCap") or (pair or {}).get("fdv") or 0)
            chain = ((pair or {}).get("chainId") or "").lower()
            ca = call.get("ca", "")

            # Same real-ATH source /pnl uses — a call's ranking shouldn't
            # collapse just because the token has since cooled off from
            # its peak. Falls back to the old current-price/peak_price
            # approach only if we can't get real mcap data for this token.
            if current_price > 0 and current_mc > 0:
                call_mc = entry_price * (current_mc / current_price)
                ath_mc = await get_real_ath_mc(ca, current_mc, is_solana=(chain == "solana")) if ca else current_mc
                multiplier = max(ath_mc, call_mc) / call_mc if call_mc > 0 else 1.0
            else:
                stored_peak = call.get("peak_price", entry_price) or entry_price
                peak_price = max(stored_peak, current_price) if current_price else stored_peak
                if peak_price != call.get("peak_price"):
                    call["peak_price"] = peak_price  # bump in place, persisted below
                multiplier = peak_price / entry_price

            results.append({
                "username":   username,
                "symbol":     call.get("symbol", "?"),
                "multiplier": multiplier,
                "ca":         call.get("ca", ""),
                "call_time":  call.get("time", ""),
            })

        _save(data)  # persist any peak_price bumps made during this render

        if not results:
            return {"group_stats": None, "top_calls": []}

        multipliers = [r["multiplier"] for r in results]
        returns_pct = [(m - 1) * 100 for m in multipliers]
        hit_count = sum(1 for m in multipliers if m >= HIT_MULTIPLIER)

        group_stats = {
            "period":         period,
            "calls":          len(results),
            "hit_rate":       round(100 * hit_count / len(results)),
            "median_return":  round(statistics.median(returns_pct)),
            "avg_multiplier": round(statistics.mean(multipliers), 1),
        }

        results.sort(key=lambda r: r["multiplier"], reverse=True)
        return {"group_stats": group_stats, "top_calls": results[:top_n]}


def format_calls_leaderboard(result: dict, group_name: str = "this group") -> str:
    group_stats = result.get("group_stats")
    top_calls = result.get("top_calls", [])

    if not group_stats or not top_calls:
        return "📋 No calls in this period ser. Start calling tokens with /scan or /p."

    period_label = PERIOD_LABELS.get(group_stats["period"], group_stats["period"])

    lines = [
        f"📊 *Group Stats — {group_name}*",
        f"├ Period: `{period_label}`",
        f"├ Calls: `{group_stats['calls']}`",
        f"├ Hit Rate (2x+): `{group_stats['hit_rate']}%`",
        f"├ Median Return: `{group_stats['median_return']}%`",
        f"└ Avg Multiplier: `{group_stats['avg_multiplier']}x`",
        "",
        "🏆 *Top Calls*",
    ]

    for i, entry in enumerate(top_calls):
        icon = _RANK_ICONS[i] if i < len(_RANK_ICONS) else "▫️"
        uname = f"@{entry['username']}" if entry["username"] != "anon" else "anon"
        lines.append(f"{icon} {i + 1}. *${entry['symbol']}* » _{uname}_ [{entry['multiplier']:.1f}x]")

    lines.append("\n_Call tokens with /scan <CA> to get on the board._")
    return "\n".join(lines)

