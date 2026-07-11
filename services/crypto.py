"""
services/crypto.py — Token price, scan, top holders, trending
Uses DexScreener (free, no key needed) + CoinGecko for fallback.
"""

import httpx
import asyncio
from typing import Optional
from config import DEXSCREENER_BASE, COINGECKO_BASE, CHAIN_EXPLORERS
from services.cache import TTLCache

# Shared persistent client — reuses TCP connections instead of making a new
# handshake on every request. Saves ~200-400ms per call.
_http = httpx.AsyncClient(
    timeout=10,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    headers={"User-Agent": "Daemonbot/2.0"},
)

_price_cache = TTLCache(ttl=20)


async def fetch_token_by_address(ca: str) -> Optional[dict]:
    """Search DexScreener by contract address. Returns best pair data.
    Cached for 20s — repeated pastes of the same CA in a busy group
    shouldn't each cost a fresh API call."""
    return await _price_cache.get_or_set(f"ca:{ca}", lambda: _fetch_token_by_address(ca))


async def _fetch_token_by_address(ca: str) -> Optional[dict]:
    url = f"{DEXSCREENER_BASE}/tokens/{ca}"
    try:
        r = await _http.get(url)
        data = r.json()
        pairs = data.get("pairs")
        if not pairs:
            return None
        pairs.sort(key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
        return pairs[0]
    except Exception:
        return None


async def fetch_token_by_name(symbol: str) -> Optional[dict]:
    """Search DexScreener by token name/symbol. Cached for 20s — see
    fetch_token_by_address for why."""
    return await _price_cache.get_or_set(f"sym:{symbol.lower()}", lambda: _fetch_token_by_name(symbol))


async def _fetch_token_by_name(symbol: str) -> Optional[dict]:
    url = f"{DEXSCREENER_BASE}/search?q={symbol}"
    try:
        r = await _http.get(url)
        data = r.json()
        pairs = data.get("pairs")
        if not pairs:
            return None
        pairs.sort(key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
        return pairs[0]
    except Exception:
        return None


def format_number(n) -> str:
    """Format large numbers to K/M/B."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "N/A"
    if n >= 1_000_000_000:
        return f"${n/1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"${n/1_000_000:.2f}M"
    elif n >= 1_000:
        return f"${n/1_000:.1f}K"
    else:
        return f"${n:.4f}"


def format_price(p) -> str:
    try:
        p = float(p)
        if p < 0.000001:
            return f"${p:.10f}"
        elif p < 0.001:
            return f"${p:.8f}"
        elif p < 1:
            return f"${p:.6f}"
        else:
            return f"${p:.4f}"
    except (TypeError, ValueError):
        return "N/A"


def pct(val) -> str:
    try:
        v = float(val)
        arrow = "🟢" if v >= 0 else "🔴"
        return f"{arrow} {v:+.2f}%"
    except (TypeError, ValueError):
        return "—"


def build_price_message(pair: dict) -> str:
    """Format a DexScreener pair into a clean price message."""
    base  = pair.get("baseToken", {})
    quote = pair.get("quoteToken", {})
    chain = pair.get("chainId", "?").upper()
    dex   = pair.get("dexId", "?").title()
    ca    = base.get("address", "")

    name   = base.get("name", "Unknown")
    symbol = base.get("symbol", "?")
    price  = format_price(pair.get("priceUsd"))

    txns   = pair.get("txns", {})
    h1     = txns.get("h1", {})
    h24    = txns.get("h24", {})

    vol24  = format_number(pair.get("volume", {}).get("h24", 0))
    liq    = format_number(pair.get("liquidity", {}).get("usd", 0))
    mc     = format_number(pair.get("marketCap", 0) or pair.get("fdv", 0))

    pc1h   = pct(pair.get("priceChange", {}).get("h1"))
    pc6h   = pct(pair.get("priceChange", {}).get("h6"))
    pc24h  = pct(pair.get("priceChange", {}).get("h24"))

    buys24  = h24.get("buys", 0)
    sells24 = h24.get("sells", 0)

    explorer = CHAIN_EXPLORERS.get(pair.get("chainId", ""), "")
    ca_link  = f"{explorer}{ca}" if explorer else ca

    msg = (
        f"🔎 *{name}* `${symbol}`\n"
        f"⛓ {chain} • {dex}\n\n"
        f"💰 *Price:* `{price}`\n"
        f"📊 *Market Cap:* `{mc}`\n"
        f"💧 *Liquidity:* `{liq}`\n"
        f"📈 *Volume 24h:* `{vol24}`\n\n"
        f"*Price Change*\n"
        f"  1H: {pc1h}\n"
        f"  6H: {pc6h}\n"
        f" 24H: {pc24h}\n\n"
        f"*Txns 24H* — 🟢 {buys24} buys / 🔴 {sells24} sells\n\n"
        f"`{ca}`\n"
        f"[View Chart]({pair.get('url', '')})"
    )
    return msg


def build_scan_message(pair: dict) -> str:
    """Build a detailed scan/contract analysis message."""
    base   = pair.get("baseToken", {})
    chain  = pair.get("chainId", "?").upper()
    ca     = base.get("address", "")
    name   = base.get("name", "Unknown")
    symbol = base.get("symbol", "?")
    liq    = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    mc     = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)
    age_h  = pair.get("pairAge") or "?"

    # Simple heuristic risk flags
    flags = []
    if liq < 10_000:
        flags.append("⚠️ Low liquidity (<$10K) — high rug risk")
    if liq < 50_000:
        flags.append("⚠️ Thin liquidity — trade carefully")
    if mc > 0 and liq > 0:
        liq_mc_ratio = liq / mc
        if liq_mc_ratio < 0.01:
            flags.append("⚠️ Liquidity/MC ratio very low")
    if not flags:
        flags.append("✅ Basic checks passed — always DYOR ser")

    explorer = CHAIN_EXPLORERS.get(pair.get("chainId", ""), "")
    ca_link  = f"{explorer}{ca}" if explorer else ca

    flag_text = "\n".join(flags)

    msg = (
        f"🧪 *SCAN: {name}* `${symbol}`\n"
        f"⛓ *Chain:* {chain}\n\n"
        f"📋 *Contract:*\n`{ca}`\n\n"
        f"💧 *Liquidity:* `{format_number(liq)}`\n"
        f"📊 *Market Cap:* `{format_number(mc)}`\n"
        f"⏳ *Pair Age:* {age_h}\n\n"
        f"🚦 *Risk Flags:*\n{flag_text}\n\n"
        f"_NFA DYOR ser. I'm a bot, not your financial advisor._\n"
        f"[DexScreener]({pair.get('url', '')})"
    )
    return msg


async def get_trending_tokens() -> list[dict]:
    """Fetch trending tokens from CoinGecko."""
    url = f"{COINGECKO_BASE}/search/trending"
    try:
        r = await _http.get(url)
        data = r.json()
        return data.get("coins", [])[:7]
    except Exception:
        return []


def format_trending(coins: list) -> str:
    if not coins:
        return "❌ Can't fetch trending rn ser. CoinGecko probably napping."
    lines = ["🔥 *Trending on CoinGecko*\n"]
    for i, item in enumerate(coins, 1):
        c = item.get("item", {})
        name   = c.get("name", "?")
        symbol = c.get("symbol", "?")
        rank   = c.get("market_cap_rank", "?")
        score  = c.get("score", 0)
        lines.append(f"{i}. *{name}* `${symbol}` — MC Rank #{rank}")
    lines.append("\n_Use /p <symbol> to get price. NFA._")
    return "\n".join(lines)
