"""
services/rugcheck.py — RugCheck.xyz integration (Solana holder/security data)

Free, no API key needed for the base report endpoint — only RugCheck's
"force refresh" query param is gated behind a paid key, and we don't use it.

NOTE ON SCHEMA: RugCheck's response shape has shifted slightly across
versions in the wild (community wrappers disagree on a couple of field
names). This parser checks the known alternates with .get() fallbacks and
degrades to "—" for anything missing rather than raising, matching the rest
of this codebase's "never crash the command over a 3rd-party API" philosophy
(see services/pumpfun.py). Worth a spot-check against a few live tokens
before you lean on this for anything more than the scan card.
"""

import httpx
from config import RUGCHECK_BASE

_http = httpx.AsyncClient(timeout=12, headers={"User-Agent": "Daemonbot/2.0"})


async def fetch_report(mint: str) -> dict | None:
    """Raw GET /tokens/{mint}/report. None if the token isn't found / API is down."""
    try:
        r = await _http.get(f"{RUGCHECK_BASE}/tokens/{mint}/report")
        if r.status_code != 200:
            return None
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _pct(holder: dict) -> float:
    """Holder rows have used both 'pct' and a raw 0-1 'percent' across schema
    versions — normalise to a 0-100 percentage either way."""
    if "pct" in holder:
        return float(holder.get("pct") or 0)
    p = float(holder.get("percent") or holder.get("percentage") or 0)
    return p * 100 if p <= 1 else p


def parse_security(report: dict) -> dict:
    """Pull the fields the scan card actually needs out of a raw report."""
    if not report:
        return {"available": False}

    holders = report.get("topHolders") or report.get("top_holders") or []
    holders = sorted(holders, key=_pct, reverse=True)

    top10_pct = round(sum(_pct(h) for h in holders[:10]), 1)
    top5_breakdown = [round(_pct(h), 1) for h in holders[:5]]

    creator = report.get("creator") or report.get("creatorAddress") or ""

    mint_auth = report.get("mintAuthority")
    freeze_auth = report.get("freezeAuthority")

    meta = report.get("tokenMeta") or report.get("token") or {}
    file_meta = report.get("fileMeta") or {}
    lore = (
        file_meta.get("description")
        or meta.get("description")
        or report.get("description")
        or ""
    ).strip()

    risks = report.get("risks") or []
    risk_names = [r.get("name", r.get("description", "?")) for r in risks if isinstance(r, dict)]

    score = report.get("score_normalised", report.get("score"))

    return {
        "available": True,
        "creator": creator,
        "top10_pct": top10_pct,
        "top_breakdown": top5_breakdown,        # e.g. [4.5, 3.8, 3.5, 2.6, 2.5]
        "total_holders": report.get("totalHolders") or report.get("total_holders") or len(holders),
        "holders_raw": holders,                 # kept for the dev-sold cross-check
        "mint_renounced": mint_auth in (None, "", "11111111111111111111111111111111"),
        "freeze_renounced": freeze_auth in (None, "", "11111111111111111111111111111111"),
        "rugged": bool(report.get("rugged")),
        "lp_locked_pct": report.get("totalLPProviders") and None,  # see lockers below
        "lockers": report.get("lockers") or {},
        "lore": lore,
        "risk_flags": risk_names,
        "risk_score": score,
    }


async def get_security_data(mint: str) -> dict:
    """Main entry point — fetch + parse in one call. Always returns a dict;
    check ['available'] before relying on the rest."""
    report = await fetch_report(mint)
    return parse_security(report)


def fresh_wallet_pct_estimate(creation_dates: list, window_days: int) -> float | None:
    """Given a list of holder-wallet 'first seen' unix timestamps (from
    services/fluxrpc.py), return the % that are younger than window_days.
    Returns None if we have no dates to work with (caller should show '—')."""
    if not creation_dates:
        return None
    import time
    now = time.time()
    cutoff = now - window_days * 86400
    fresh = sum(1 for ts in creation_dates if ts and ts >= cutoff)
    return round(fresh / len(creation_dates) * 100, 1)
