"""
services/fluxrpc.py — Minimal Solana JSON-RPC client (via FluxRPC, falls back
to the public Solana RPC if no FluxRPC key is set).

Only used for the two things RugCheck's report doesn't give us directly:
  1. Dev Sold check     — does the creator wallet still hold the token?
  2. Fresh wallet %      — best-effort heuristic, see is_wallet_fresh() below.

Kept to raw JSON-RPC over httpx (no solana-py dependency) to match the rest
of this codebase's "no heavy SDKs" style.
"""

import time
import httpx
from config import FLUXRPC_URL, FLUXRPC_API_KEY, RPC_URLS

_http = httpx.AsyncClient(timeout=10, headers={"User-Agent": "Daemonbot/2.0"})


def _endpoint() -> str:
    if FLUXRPC_API_KEY:
        return f"{FLUXRPC_URL}?key={FLUXRPC_API_KEY}"
    return RPC_URLS["solana"]  # public fallback — slower, rate-limited, but free


async def _rpc(method: str, params: list) -> dict | None:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        r = await _http.post(_endpoint(), json=payload)
        data = r.json()
        if "error" in data:
            return None
        return data.get("result")
    except Exception:
        return None


async def get_wallet_token_balance(owner: str, mint: str) -> float | None:
    """Sum of `owner`'s balance of `mint` across all their token accounts.
    None on RPC failure (caller should show 'unknown', not assume 0)."""
    if not owner or not mint:
        return None
    result = await _rpc(
        "getTokenAccountsByOwner",
        [owner, {"mint": mint}, {"encoding": "jsonParsed"}],
    )
    if result is None:
        return None
    total = 0.0
    for acc in result.get("value", []):
        try:
            info = acc["account"]["data"]["parsed"]["info"]
            total += float(info["tokenAmount"]["uiAmount"] or 0)
        except (KeyError, TypeError, ValueError):
            continue
    return total


async def check_dev_sold(creator: str, mint: str, holders_raw: list) -> str:
    """Returns 'sold', 'holding', or 'unknown'.

    Cheapest first: if RugCheck's own holder list already shows the creator
    wallet with a real balance, we don't need an RPC call at all. Only fall
    back to a live balance check when the creator isn't in that list (could
    mean they sold everything, or RugCheck just didn't surface them)."""
    if not creator:
        return "unknown"

    for h in holders_raw or []:
        addr = h.get("address") or h.get("owner") or ""
        if addr == creator:
            pct = h.get("pct", h.get("percent", 0))
            return "holding" if float(pct or 0) > 0.05 else "sold"

    # Creator not in top holders — confirm with a direct balance check
    bal = await get_wallet_token_balance(creator, mint)
    if bal is None:
        return "unknown"
    return "holding" if bal > 0 else "sold"


async def is_wallet_fresh(address: str, window_days: int) -> bool | None:
    """Heuristic: a wallet counts as 'fresh' if its ENTIRE on-chain history
    (capped at 50 signatures — one RPC call, no pagination) fits inside the
    window. If it already has 50+ signatures we know it's not fresh without
    needing the exact age. Returns None if we couldn't determine it either
    way (RPC failure, or an empty/never-used wallet) — show '—', not a guess.
    """
    if not address:
        return None
    sigs = await _rpc("getSignaturesForAddress", [address, {"limit": 50}])
    if sigs is None:
        return None
    if len(sigs) >= 50:
        return False  # more history than we fetched — definitely not fresh
    if not sigs:
        return None
    block_times = [s.get("blockTime") for s in sigs if s.get("blockTime")]
    if not block_times:
        return None
    oldest = min(block_times)
    cutoff = time.time() - window_days * 86400
    return oldest >= cutoff


async def fresh_wallet_pct(addresses: list, window_days: int) -> float | None:
    """% of the given wallets that look 'fresh' (see is_wallet_fresh).
    Capped to the first 10 addresses to keep /scan and /z responsive —
    RugCheck already sorts topHolders by size, so this checks the top 10."""
    import asyncio
    sample = addresses[:10]
    if not sample:
        return None
    results = await asyncio.gather(*[is_wallet_fresh(a, window_days) for a in sample])
    known = [r for r in results if r is not None]
    if not known:
        return None
    return round(sum(known) / len(known) * 100, 1)
