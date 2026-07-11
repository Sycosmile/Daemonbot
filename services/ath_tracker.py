"""
services/ath_tracker.py — Rolling ATH (high-water-mark) cache.

DexScreener doesn't expose true all-time-high market cap, and this isn't a
chain-indexing bot, so we can't back-fill history. What we CAN do: every
time /scan, /z, or an alert check touches a CA, record the market cap we
saw — and report the highest one we've ever seen as "ATH (since tracked)".

For pump.fun-origin tokens, skip this entirely and use pump.fun's own
`ath_market_cap` field instead (services/pumpfun.py) — that's a real lifetime
ATH from their indexer, not an approximation.
"""

import json
import os
import time
import asyncio
from config import ATH_FILE

_lock = asyncio.Lock()


def _load() -> dict:
    if not os.path.exists(ATH_FILE):
        os.makedirs(os.path.dirname(ATH_FILE), exist_ok=True)
        return {}
    try:
        with open(ATH_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(ATH_FILE), exist_ok=True)
    with open(ATH_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def record_and_get_ath(ca: str, current_mc: float) -> dict:
    """Updates the high-water-mark for `ca` if current_mc is a new high,
    and returns {"ath_mc": float, "is_new_high": bool, "pct_off_ath": float}.
    Safe to call on every scan — it's just a dict read/write behind a lock."""
    ca = (ca or "").lower()
    if not ca or current_mc <= 0:
        return {"ath_mc": current_mc, "is_new_high": False, "pct_off_ath": 0.0}

    async with _lock:
        data = _load()
        entry = data.get(ca, {"ath_mc": 0, "first_seen": time.time()})
        is_new_high = current_mc > entry["ath_mc"]
        if is_new_high:
            entry["ath_mc"] = current_mc
            entry["ath_time"] = time.time()
        data[ca] = entry
        _save(data)

    ath_mc = entry["ath_mc"]
    pct_off = ((current_mc - ath_mc) / ath_mc * 100) if ath_mc > 0 else 0.0
    return {"ath_mc": ath_mc, "is_new_high": is_new_high, "pct_off_ath": round(pct_off, 1)}
