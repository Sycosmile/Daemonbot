"""
services/research.py — Rick-style token research features
/dev  — deployer history
/soc  — find socials from CA
/lore — AI lore explanation
/gas  — ETH gas
/groupburp — best active plays
/ga   — ATH leaderboard
/best /worst — top gainers/losers
/meta — trending DexScreener metas
/bm   — BubbleMap link
/dp   — DEX paid checker
"""

import httpx
from openai import AsyncOpenAI
from datetime import datetime
from typing import Optional
from config import GROQ_API_KEY, AI_MODEL, ETHERSCAN_KEY, BSCSCAN_KEY
from services.leaderboard import _load


client = AsyncOpenAI(api_key=GROQ_API_KEY or "unset", base_url="https://api.groq.com/openai/v1")

# ── LORE ─────────────────────────────────────────────────────────────────────

LORE_PROMPT = """You are a based crypto researcher. Given a token name and symbol,
explain in 3-5 punchy sentences what the "lore" or cultural narrative around this token is.
What meme/community/event spawned it? What does it represent in crypto culture?
If you don't know, say it's either brand new or niche, and speculate based on the name.
Use degen slang. Keep it fun. End with "NFA DYOR ser." """


async def get_lore(name: str, symbol: str) -> str:
    try:
        resp = await client.chat.completions.create(
            model=AI_MODEL,
            max_tokens=200,
            messages=[
                {"role": "system", "content": LORE_PROMPT},
                {"role": "user",   "content": f"What's the lore of {name} (${symbol})?"},
            ],
        )
        return f"📖 *Lore — {name} (${symbol})*\n\n{resp.choices[0].message.content.strip()}"
    except Exception as e:
        return f"❌ Lore fetch failed: {type(e).__name__}"


# ── DEPLOYER HISTORY ──────────────────────────────────────────────────────────

async def get_deployer_history(ca: str, chain: str = "ethereum") -> str:
    """Fetch deployer wallet and its other deployments via Etherscan/BSCScan."""
    api_key = ETHERSCAN_KEY if chain != "bsc" else BSCSCAN_KEY
    base_url = (
        "https://api.etherscan.io/api" if chain != "bsc"
        else "https://api.bscscan.com/api"
    )

    if not api_key:
        return (
            "⚠️ Deployer history requires an Etherscan/BSCScan API key.\n"
            "Add `ETHERSCAN_KEY` to your `.env` file.\n"
            f"[View manually](https://etherscan.io/address/{ca})"
        )

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            # Get contract creation tx to find deployer
            r = await client.get(base_url, params={
                "module": "contract",
                "action": "getcontractcreation",
                "contractaddresses": ca,
                "apikey": api_key,
            })
            data = r.json()
            result = data.get("result", [])
            if not result:
                return "❌ Contract not found or not verified on Etherscan."

            deployer = result[0].get("contractCreator", "unknown")
            tx_hash  = result[0].get("txHash", "")

            # Get all txns from deployer wallet
            r2 = await client.get(base_url, params={
                "module": "account",
                "action": "txlist",
                "address": deployer,
                "sort": "desc",
                "page": 1,
                "offset": 20,
                "apikey": api_key,
            })
            txns = r2.json().get("result", [])

            # Find contract creation txns
            deployments = [t for t in txns if t.get("to") == "" and t.get("contractAddress")]
            dep_lines = []
            for d in deployments[:6]:
                addr  = d.get("contractAddress", "?")[:10] + "..."
                ts    = datetime.fromtimestamp(int(d.get("timeStamp", 0))).strftime("%Y-%m-%d")
                dep_lines.append(f"  • `{addr}` — {ts}")

            deps_text = "\n".join(dep_lines) if dep_lines else "  None found"

            return (
                f"🔎 *Deployer History*\n\n"
                f"👤 Deployer:\n`{deployer}`\n\n"
                f"📦 *Other Deployments ({len(deployments)} found):*\n{deps_text}\n\n"
                f"[View on Etherscan](https://etherscan.io/address/{deployer})"
            )
        except Exception as e:
            return f"❌ Failed to fetch deployer: {type(e).__name__}"


# ── SOCIAL FINDER ─────────────────────────────────────────────────────────────

async def find_socials(ca: str) -> str:
    """Find socials for a token via DexScreener pair info."""
    from services.crypto import fetch_token_by_address
    pair = await fetch_token_by_address(ca)
    if not pair:
        return "❌ Token not found on DexScreener."

    base   = pair.get("baseToken", {})
    name   = base.get("name", "?")
    symbol = base.get("symbol", "?")
    info   = pair.get("info", {}) or {}

    websites  = info.get("websites", []) or []
    socials   = info.get("socials", []) or []

    lines = [f"🔗 *Socials — {name} (${symbol})*\n"]

    if websites:
        lines.append("🌐 *Websites:*")
        for w in websites[:3]:
            url = w.get("url", "")
            lines.append(f"  • {url}")

    if socials:
        lines.append("\n📱 *Socials:*")
        for s in socials[:6]:
            stype = s.get("type", "").title()
            url   = s.get("url", "")
            lines.append(f"  • {stype}: {url}")

    if not websites and not socials:
        lines.append("❌ No socials found on DexScreener for this token.")
        lines.append(f"\n[Check DexScreener]({pair.get('url', '')})")

    return "\n".join(lines)


# ── ETH GAS ───────────────────────────────────────────────────────────────────

async def get_gas() -> str:
    """Fetch current ETH gas prices."""
    # Use etherscan gas oracle (free, no key for basic)
    url = "https://api.etherscan.io/api"
    params = {
        "module": "gastracker",
        "action": "gasoracle",
        "apikey": ETHERSCAN_KEY or "YourApiKeyToken",
    }
    async with httpx.AsyncClient(timeout=8) as client:
        try:
            r = await client.get(url, params=params)
            data = r.json().get("result", {})
            slow   = data.get("SafeGasPrice", "?")
            avg    = data.get("ProposeGasPrice", "?")
            fast   = data.get("FastGasPrice", "?")
            base   = data.get("suggestBaseFee", "?")

            return (
                f"⛽ *ETH Gas Prices*\n\n"
                f"🐢 Slow:  `{slow} gwei`\n"
                f"🚶 Avg:   `{avg} gwei`\n"
                f"🚀 Fast:  `{fast} gwei`\n"
                f"📊 Base:  `{base} gwei`\n\n"
                f"_Updated in real-time via Etherscan._"
            )
        except Exception as e:
            return f"❌ Gas fetch failed: {type(e).__name__}"


# ── GROUPBURP — Active plays ───────────────────────────────────────────────────

async def get_groupburp(chat_id: int, limit: int = 8) -> str:
    """Show most actively scanned tokens in this group recently."""
    data  = _load()
    gkey  = str(chat_id)
    group = data.get(gkey, {})

    if not group:
        return "❌ No calls logged in this group yet ser."

    # Count token frequency
    token_counts: dict[str, dict] = {}
    for uid, info in group.items():
        for call in info.get("calls", []):
            ca = call.get("ca", "") or call.get("symbol", "")
            if not ca:
                continue
            if ca not in token_counts:
                token_counts[ca] = {
                    "symbol": call.get("symbol", "?"),
                    "token":  call.get("token", "?"),
                    "count":  0,
                    "callers": set(),
                    "last": call.get("time", ""),
                }
            token_counts[ca]["count"] += 1
            token_counts[ca]["callers"].add(uid)
            if call.get("time", "") > token_counts[ca]["last"]:
                token_counts[ca]["last"] = call.get("time", "")

    if not token_counts:
        return "❌ No token data found."

    # Sort by call count
    sorted_tokens = sorted(token_counts.values(), key=lambda x: x["count"], reverse=True)[:limit]

    lines = ["🔥 *GroupBurp — Active Plays*\n"]
    medals = ["🥇", "🥈", "🥉"] + ["🔸"] * 20

    for i, t in enumerate(sorted_tokens):
        callers = len(t["callers"])
        last    = t["last"][:10] if t["last"] else "?"
        lines.append(
            f"{medals[i]} *${t['symbol']}* — {t['count']} scans | "
            f"{callers} callers | last: {last}"
        )

    lines.append("\n_Use /scan <CA> to add tokens. Use /ga for ATH leaderboard._")
    return "\n".join(lines)


# ── ATH LEADERBOARD ──────────────────────────────────────────────────────────

async def get_ath_leaderboard(chat_id: int) -> str:
    """
    Show best calls by ATH multiplier in this group.
    Fetches current price for each unique token called.
    """
    data  = _load()
    gkey  = str(chat_id)
    group = data.get(gkey, {})

    if not group:
        return "❌ No calls in this group yet ser."

    from services.crypto import fetch_token_by_address, fetch_token_by_name

    # Collect all calls with entry prices
    all_calls = []
    for uid, info in group.items():
        username = info.get("username", "anon")
        for call in info.get("calls", []):
            entry = call.get("price", 0)
            if entry > 0:
                all_calls.append({
                    "username": username,
                    "symbol":   call.get("symbol", "?"),
                    "token":    call.get("token", "?"),
                    "ca":       call.get("ca", ""),
                    "entry":    entry,
                    "time":     call.get("time", ""),
                })

    if not all_calls:
        return "❌ No calls with price data found."

    # Fetch current prices (limit to avoid rate limits)
    results = []
    seen_cas = set()
    for call in all_calls[:15]:
        ca = call.get("ca", "")
        if ca in seen_cas:
            continue
        seen_cas.add(ca)

        if ca:
            pair = await fetch_token_by_address(ca)
        else:
            pair = await fetch_token_by_name(call["symbol"])

        if pair:
            current = float(pair.get("priceUsd") or 0)
            if current > 0 and call["entry"] > 0:
                mult = current / call["entry"]
                results.append({
                    **call,
                    "current": current,
                    "mult":    mult,
                    "pct":     (mult - 1) * 100,
                })

    if not results:
        return "❌ Couldn't fetch current prices for any called tokens."

    results.sort(key=lambda x: x["mult"], reverse=True)

    lines = ["🏆 *ATH Leaderboard — Best Calls*\n"]
    medals = ["🥇", "🥈", "🥉"] + ["🔸"] * 20

    for i, r in enumerate(results[:8]):
        mult = r["mult"]
        pct  = r["pct"]
        sign = "+" if pct >= 0 else ""
        lines.append(
            f"{medals[i]} *${r['symbol']}* by @{r['username']} — "
            f"`{mult:.2f}x` ({sign}{pct:.0f}%)"
        )

    lines.append("\n_Live prices. Past calls only. NFA._")
    return "\n".join(lines)


def compute_call_stats(returns: list[float], hit_threshold: float = 100.0) -> dict:
    """
    Pure math, no network — easy to unit test. `returns` is a list of % gains
    (e.g. 150.0 means +150%, -30.0 means -30%). hit_threshold default 100.0
    means "≥2x counts as a hit".
    """
    if not returns:
        return {"median": 0.0, "average": 0.0, "hit_rate": 0.0, "n": 0}

    sorted_r = sorted(returns)
    n = len(sorted_r)
    median = sorted_r[n // 2] if n % 2 else (sorted_r[n // 2 - 1] + sorted_r[n // 2]) / 2
    average = sum(sorted_r) / n
    hits = sum(1 for p in sorted_r if p >= hit_threshold)
    hit_rate = (hits / n) * 100

    return {"median": median, "average": average, "hit_rate": hit_rate, "n": n}


async def get_user_stats(chat_id: int, user_id: int, username: str) -> str:
    """
    Phanes-style /stats — hit rate + median return for one user's calls.
    Median matters here because one 50x outlier shouldn't make a 1/20 hit
    rate look like a good track record — median resists that skew.
    """
    data  = _load()
    group = data.get(str(chat_id), {})
    info  = group.get(str(user_id))

    if not info or not info.get("calls"):
        return f"❌ No calls logged for @{username} in this group yet."

    from services.crypto import fetch_token_by_address, fetch_token_by_name

    calls = info["calls"]
    total_calls = len(calls)

    seen_cas = set()
    returns = []
    best = worst = None

    for call in calls[-25:]:  # cap to avoid hammering rate limits
        entry = call.get("price", 0)
        ca = call.get("ca", "")
        if entry <= 0 or ca in seen_cas:
            continue
        seen_cas.add(ca)

        pair = await fetch_token_by_address(ca) if ca else await fetch_token_by_name(call.get("symbol", ""))
        if not pair:
            continue
        current = float(pair.get("priceUsd") or 0)
        if current <= 0:
            continue

        pct = (current / entry - 1) * 100
        returns.append(pct)
        entry_data = {"symbol": call.get("symbol", "?"), "pct": pct}
        if best is None or pct > best["pct"]:
            best = entry_data
        if worst is None or pct < worst["pct"]:
            worst = entry_data

    if not returns:
        return f"❌ Couldn't fetch live prices for @{username}'s calls right now."

    stats = compute_call_stats(returns)
    median_return, avg_return, hit_rate, n = (
        stats["median"], stats["average"], stats["hit_rate"], stats["n"]
    )

    def _sign(v):
        return "+" if v >= 0 else ""

    msg = (
        f"📊 *Stats — @{username}*\n\n"
        f"🪙 Total calls: `{total_calls}` (priced: `{n}`)\n"
        f"🎯 Hit rate (≥2x): `{hit_rate:.0f}%`\n"
        f"📈 Median return: `{_sign(median_return)}{median_return:.0f}%`\n"
        f"📊 Average return: `{_sign(avg_return)}{avg_return:.0f}%`\n"
    )
    if best:
        msg += f"🏆 Best: *${best['symbol']}* `{_sign(best['pct'])}{best['pct']:.0f}%`\n"
    if worst:
        msg += f"💀 Worst: *${worst['symbol']}* `{_sign(worst['pct'])}{worst['pct']:.0f}%`\n"
    msg += "\n_Median > average here — one moonshot shouldn't hide a bad hit rate._"
    return msg


# ── TOP GAINERS / LOSERS ──────────────────────────────────────────────────────

async def get_gainers_losers(mode: str = "gainers", period: str = "24h") -> str:
    """Fetch top gainers or losers from CoinGecko."""
    valid_periods = {"1h", "24h", "7d", "14d", "30d"}
    if period not in valid_periods:
        period = "24h"

    # CoinGecko top gainers endpoint (free)
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "percent_change_24h_desc" if mode == "gainers" else "percent_change_24h_asc",
        "per_page": 10,
        "page": 1,
        "price_change_percentage": "24h",
        "sparkline": False,
    }
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            r = await c.get(url, params=params)
            coins = r.json()
            if isinstance(coins, dict) and coins.get("error"):
                return "❌ CoinGecko rate limit hit — try again in a moment."

            emoji = "🚀" if mode == "gainers" else "💀"
            title = "Top Gainers" if mode == "gainers" else "Top Losers"
            lines = [f"{emoji} *{title} — {period}*\n"]

            for i, coin in enumerate(coins[:8], 1):
                name   = coin.get("name", "?")
                sym    = coin.get("symbol", "?").upper()
                chg    = coin.get("price_change_percentage_24h", 0) or 0
                price  = coin.get("current_price", 0)
                sign   = "+" if chg >= 0 else ""
                arr    = "🟢" if chg >= 0 else "🔴"
                lines.append(f"{i}. *{name}* `${sym}` — {arr} {sign}{chg:.1f}% | ${price:,.4f}")

            lines.append(f"\n_Via CoinGecko. NFA DYOR._")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Failed: {type(e).__name__}"


# ── DEXSCREENER TRENDING METAS ────────────────────────────────────────────────

async def get_dex_metas() -> str:
    """Fetch trending token categories from DexScreener."""
    url = "https://api.dexscreener.com/token-boosts/top/v1"
    async with httpx.AsyncClient(timeout=10) as c:
        try:
            r = await c.get(url)
            tokens = r.json()
            if not tokens:
                return "❌ No trending data from DexScreener."

            lines = ["📊 *Trending on DexScreener*\n"]
            for i, t in enumerate(tokens[:8], 1):
                name   = t.get("description", "?")[:30]
                chain  = t.get("chainId", "?").upper()
                ca     = t.get("tokenAddress", "")[:10] + "..."
                amount = t.get("totalAmount", 0)
                lines.append(f"{i}. *{name}* ({chain}) — {amount} boosts")

            lines.append("\n_Use /scan <CA> for full token data._")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ DexScreener meta fetch failed: {type(e).__name__}"


# ── BUBBLEMAP ────────────────────────────────────────────────────────────────

def get_bubblemap(ca: str, chain: str = "eth") -> str:
    chain_map = {
        "ethereum": "eth", "eth": "eth",
        "solana": "sol",   "sol": "sol",
        "bsc": "bnb",      "base": "base",
        "arbitrum": "arb", "polygon": "matic",
    }
    bm_chain = chain_map.get(chain.lower(), "eth")
    url = f"https://app.bubblemaps.io/{bm_chain}/token/{ca}"
    return (
        f"🫧 *BubbleMap*\n\n"
        f"Chain: `{bm_chain.upper()}`\n"
        f"CA: `{ca}`\n\n"
        f"[Open BubbleMap]({url})\n\n"
        f"_Shows wallet concentration and holder distribution visually._"
    )
