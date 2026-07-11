"""
services/scan_data.py — Assembles the dict that services/scan_card.py
renders. This is the only place that should know about all the different
data sources at once; everything else (commands.py, scan_card.py) stays
decoupled from "where the data came from."

Solana-only features (RugCheck, FluxRPC dev-sold/fresh-wallet, pump.fun
banner/lore/ATH) are skipped gracefully on other chains — the card already
renders fine with those fields missing (see scan_card.py's sparse-data test).
"""

import time
import httpx

from services.crypto import fetch_token_by_address, fetch_token_by_name
from services.pumpfun import fetch_pumpfun_coin
from services.rugcheck import get_security_data
from services.fluxrpc import check_dev_sold, fresh_wallet_pct
from services.ath_tracker import record_and_get_ath
from services.quicklinks import analytics_links, quickbuy_links

_img_http = httpx.AsyncClient(timeout=8, follow_redirects=True, headers={"User-Agent": "Daemonbot/2.0"})


def _format_age(seconds: float) -> str:
    if seconds < 0:
        return "—"
    m = seconds / 60
    if m < 60:
        return f"{int(m)}m"
    h = m / 60
    if h < 48:
        return f"{int(h)}h"
    d = h / 24
    return f"{int(d)}d"


async def _fetch_image_bytes(url: str) -> bytes | None:
    if not url:
        return None
    try:
        r = await _img_http.get(url)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


async def build_scan_data(query: str) -> dict | None:
    """query is a CA or a symbol/name. Returns None only if the token
    couldn't be found at all — everything else degrades field-by-field."""
    pair = await (fetch_token_by_address(query) if len(query) > 20 else fetch_token_by_name(query))
    if not pair:
        return None

    base = pair.get("baseToken", {})
    ca = base.get("address", query)
    name = base.get("name", "Unknown")
    symbol = base.get("symbol", "?")
    chain = pair.get("chainId", "?").lower()
    is_solana = chain == "solana"

    liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    mc = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)
    price = float(pair.get("priceUsd") or 0)
    vol_1h = float(pair.get("volume", {}).get("h1", 0) or 0)
    chg_1h = pair.get("priceChange", {}).get("h1")
    txns_1h = pair.get("txns", {}).get("h1", {})
    pair_address = pair.get("pairAddress", "")

    created_ms = pair.get("pairCreatedAt")
    age_label = _format_age((time.time() * 1000 - created_ms) / 1000) if created_ms else "—"

    info = pair.get("info", {}) or {}
    socials = info.get("socials", [])
    twitter_url = next((s.get("url") for s in socials if s.get("type") == "twitter"), None)
    # "DEX Paid" signal: DexScreener only populates the `info` block (socials,
    # description, header image) for tokens that paid for Enhanced Token
    # Info — that's a more direct signal than the unrelated `boosts` (trending
    # visibility) field. Empty/missing info block -> hasn't paid (or too new
    # for DexScreener to have indexed it yet either way).
    dex_paid = bool(info) if pair.get("pairCreatedAt") else None

    # ── pump.fun (Solana only — silently empty on other chains/non-pumpfun) ──
    pf_coin = await fetch_pumpfun_coin(ca) if is_solana else None
    banner_url = (pf_coin or {}).get("image_uri") or info.get("header") or info.get("imageUrl")
    banner_bytes = await _fetch_image_bytes(banner_url)
    lore = (pf_coin or {}).get("description", "")
    pf_ath = (pf_coin or {}).get("ath_market_cap")

    # ── RugCheck security data (Solana only) ─────────────────────────────
    sec = await get_security_data(ca) if is_solana else {"available": False}

    # ── Dev sold + fresh wallets (Solana only, needs RugCheck's holder list) ──
    dev_sold = "unknown"
    fresh_1d = fresh_7d = None
    if is_solana and sec.get("available"):
        dev_sold = await check_dev_sold(sec.get("creator", ""), ca, sec.get("holders_raw", []))
        holder_addrs = [h.get("address") or h.get("owner") for h in sec.get("holders_raw", [])]
        holder_addrs = [a for a in holder_addrs if a]
        fresh_1d = await fresh_wallet_pct(holder_addrs, window_days=1)
        fresh_7d = await fresh_wallet_pct(holder_addrs, window_days=7)

    # ── ATH ────────────────────────────────────────────────────────────────
    if pf_ath:
        ath_mc, ath_pct_off, ath_time_label = pf_ath, (mc - pf_ath) / pf_ath * 100 if pf_ath else 0, ""
    else:
        ath_info = await record_and_get_ath(ca, mc)
        ath_mc = ath_info["ath_mc"]
        ath_pct_off = ath_info["pct_off_ath"]
        ath_time_label = "since tracked"

    data = {
        "name": name, "symbol": symbol, "chain": chain, "ca": ca,
        "price_usd": price, "price_change_pct": float(chg_1h) if chg_1h is not None else None,
        "mc": mc, "vol_1h": vol_1h, "liq": liq,
        "supply_circ": None, "supply_total": None,  # DexScreener doesn't expose this — left for a future source
        "age_label": age_label,
        "buys_1h": txns_1h.get("buys"), "sells_1h": txns_1h.get("sells"),
        "ath_mc": ath_mc, "ath_pct_off": round(ath_pct_off, 1) if ath_mc else None, "ath_time_label": ath_time_label,
        "socials_age_label": age_label, "twitter_url": twitter_url, "lore": lore,
        "banner_image_bytes": banner_bytes,
        "security_available": sec.get("available", False),
        "fresh_1d": fresh_1d, "fresh_7d": fresh_7d,
        "top10_pct": sec.get("top10_pct"), "total_holders": sec.get("total_holders"),
        "top_breakdown": sec.get("top_breakdown", []),
        "dev_sold": dev_sold, "dex_paid": dex_paid,
        "mint_renounced": sec.get("mint_renounced"), "freeze_renounced": sec.get("freeze_renounced"),
        "risk_score": sec.get("risk_score"),
        "_pair": pair,  # kept for callers that still want the raw DexScreener pair (leaderboard logging etc.)
    }

    if is_solana:
        data["analytics_links"] = analytics_links(ca, pair_address, symbol, pair.get("url", ""))
        data["quickbuy_links"] = quickbuy_links(ca, pair_address)
    else:
        data["analytics_links"] = {"DS": pair.get("url", "")}
        data["quickbuy_links"] = {}

    return data
