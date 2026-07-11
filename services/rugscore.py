"""
services/rugscore.py — AI-powered rug probability score (0-100)
Uses GoPlus Security API (free) + DexScreener data + Claude AI reasoning.
Unique to Daemonbot — not just flags, actual AI judgment with explanation.
"""

import httpx
from openai import AsyncOpenAI
from config import GROQ_API_KEY, AI_MODEL

client = AsyncOpenAI(api_key=GROQ_API_KEY or "unset", base_url="https://api.groq.com/openai/v1")

GOPLUS_BASE = "https://api.gopluslabs.io/api/v1"

CHAIN_IDS = {
    "ethereum": "1",
    "eth":      "1",
    "bsc":      "56",
    "polygon":  "137",
    "matic":    "137",
    "arbitrum": "42161",
    "arb":      "42161",
    "base":     "8453",
    "solana":   "solana",
    "sol":      "solana",
}

RUG_PROMPT = """You are Daemonbot's on-chain security analyst — a based, sharp, no-nonsense judge of crypto tokens.
Given structured token security data, produce:

1. A RUG SCORE from 0-100 (0 = safu, 100 = definite rug)
2. A VERDICT (one of: SAFU ✅ / CAUTION ⚠️ / LIKELY RUG 🚨 / DEFINITE RUG ☠️)
3. A SHORT AI ANALYSIS — 3-4 punchy sentences. Be specific about what's risky or safe.
   Call out the most dangerous flags. Mention if it looks clean.
   Use degen slang but stay factual.

Respond ONLY in this exact JSON format (no markdown, no preamble):
{
  "score": <0-100>,
  "verdict": "<SAFU ✅ / CAUTION ⚠️ / LIKELY RUG 🚨 / DEFINITE RUG ☠️>",
  "analysis": "<3-4 sentence analysis>"
}"""


async def fetch_goplus_evm(ca: str, chain_id: str) -> dict:
    """Fetch token security data from GoPlus for EVM chains."""
    url = f"{GOPLUS_BASE}/token_security/{chain_id}"
    async with httpx.AsyncClient(timeout=12) as c:
        try:
            r = await c.get(url, params={"contract_addresses": ca})
            data = r.json()
            result = data.get("result", {})
            return result.get(ca.lower(), result.get(ca, {}))
        except Exception:
            return {}


async def fetch_goplus_sol(ca: str) -> dict:
    """Fetch Solana token security from GoPlus."""
    url = f"{GOPLUS_BASE}/solana/token_security"
    async with httpx.AsyncClient(timeout=12) as c:
        try:
            r = await c.get(url, params={"contract_addresses": ca})
            data = r.json()
            result = data.get("result", {})
            return result.get(ca, {})
        except Exception:
            return {}


def parse_evm_security(sec: dict, pair: dict) -> dict:
    """Extract key security signals from GoPlus EVM response."""
    liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    mc  = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)

    return {
        "is_honeypot":          sec.get("is_honeypot", "0") == "1",
        "buy_tax":              float(sec.get("buy_tax", 0) or 0),
        "sell_tax":             float(sec.get("sell_tax", 0) or 0),
        "is_mintable":          sec.get("is_mintable", "0") == "1",
        "owner_can_change_balance": sec.get("owner_change_balance", "0") == "1",
        "has_blacklist":        sec.get("is_blacklisted", "0") == "1",
        "has_whitelist":        sec.get("is_whitelisted", "0") == "1",
        "ownership_renounced":  sec.get("owner_address", "0x000") in ("", "0x0000000000000000000000000000000000000000"),
        "proxy_contract":       sec.get("is_proxy", "0") == "1",
        "self_destruct":        sec.get("self_destruct", "0") == "1",
        "external_call":        sec.get("external_call", "0") == "1",
        "top10_holder_pct":     float(sec.get("holder_count", 0) or 0),
        "creator_pct":          float(sec.get("creator_percent", 0) or 0) * 100,
        "lp_locked":            sec.get("lp_holder_analysis", [{}])[0].get("is_locked", False) if sec.get("lp_holder_analysis") else False,
        "lp_locked_pct":        float(sec.get("lp_holder_analysis", [{}])[0].get("percent", 0) or 0) * 100 if sec.get("lp_holder_analysis") else 0,
        "liquidity_usd":        liq,
        "market_cap":           mc,
        "holder_count":         int(sec.get("holder_count", 0) or 0),
        "open_source":          sec.get("is_open_source", "0") == "1",
        "trading_cooldown":     sec.get("trading_cooldown", "0") == "1",
        "can_take_ownership":   sec.get("can_take_back_ownership", "0") == "1",
        "hidden_owner":         sec.get("hidden_owner", "0") == "1",
    }


def parse_sol_security(sec: dict, pair: dict) -> dict:
    liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    mc  = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)
    return {
        "is_honeypot":          False,  # SOL doesn't have traditional honeypots
        "mintable":             sec.get("mintable", False),
        "freezable":            sec.get("freezable", False),
        "ownership_renounced":  sec.get("non_transferable", False),
        "top10_holder_pct":     float(sec.get("top10_holder_percent", 0) or 0) * 100,
        "creator_pct":          float(sec.get("creator_percentage", 0) or 0) * 100,
        "lp_locked":            sec.get("lockInfo", {}).get("isLocked", False) if isinstance(sec.get("lockInfo"), dict) else False,
        "liquidity_usd":        liq,
        "market_cap":           mc,
        "holder_count":         int(sec.get("holder_count", 0) or 0),
        "open_source":          True,  # SOL programs are generally public
        "can_take_ownership":   False,
        "hidden_owner":         False,
    }


async def ai_rug_score(signals: dict, name: str, symbol: str) -> dict:
    """Send security signals to Claude for AI rug scoring."""
    import json

    signals_text = json.dumps(signals, indent=2)
    prompt = f"Token: {name} (${symbol})\nSecurity Data:\n{signals_text}"

    try:
        resp = await client.chat.completions.create(
            model=AI_MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": RUG_PROMPT},
                {"role": "user",   "content": prompt},
            ],
        )
        text = resp.choices[0].message.content.strip()
        # Strip markdown fences if present
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        return {
            "score": 50,
            "verdict": "CAUTION ⚠️",
            "analysis": f"AI scoring failed ({type(e).__name__}). Review signals manually."
        }


def format_rug_report(
    name: str,
    symbol: str,
    chain: str,
    ca: str,
    signals: dict,
    ai: dict,
) -> str:
    score   = ai.get("score", 50)
    verdict = ai.get("verdict", "CAUTION ⚠️")
    analysis = ai.get("analysis", "")

    # Score bar
    filled = int(score / 10)
    bar    = "█" * filled + "░" * (10 - filled)
    score_color = "🟢" if score < 30 else "🟡" if score < 60 else "🔴"

    # Key signals
    flags = []
    s = signals

    if s.get("is_honeypot"):         flags.append("🚨 HONEYPOT detected")
    if s.get("buy_tax", 0) > 10:     flags.append(f"🚩 High buy tax: {s['buy_tax']}%")
    if s.get("sell_tax", 0) > 10:    flags.append(f"🚩 High sell tax: {s['sell_tax']}%")
    if s.get("is_mintable") or s.get("mintable"): flags.append("⚠️ Mintable — dev can print tokens")
    if s.get("has_blacklist"):        flags.append("⚠️ Blacklist function exists")
    if s.get("hidden_owner"):         flags.append("🚩 Hidden owner detected")
    if s.get("can_take_ownership"):   flags.append("🚩 Owner can reclaim contract")
    if s.get("self_destruct"):        flags.append("🚨 Self-destruct function")
    if s.get("proxy_contract"):       flags.append("⚠️ Proxy contract — upgradeable")
    if s.get("freezable"):            flags.append("⚠️ Freezable (SOL) — wallets can be frozen")
    if s.get("creator_pct", 0) > 10: flags.append(f"🚩 Creator holds {s['creator_pct']:.1f}% of supply")
    if s.get("lp_locked"):
        pct = s.get("lp_locked_pct", 0)
        flags.append(f"✅ LP locked ({pct:.0f}%)")
    elif "lp_locked" in s:
        flags.append("🚩 LP NOT locked — instant rug possible")
    if s.get("ownership_renounced"):  flags.append("✅ Ownership renounced")
    if s.get("open_source"):          flags.append("✅ Open source / verified")
    if s.get("liquidity_usd", 0) < 10000: flags.append(f"⚠️ Low liquidity: ${s.get('liquidity_usd', 0):,.0f}")
    if not flags:                     flags.append("✅ No major red flags detected")

    flags_text = "\n".join(f"  {f}" for f in flags)

    msg = (
        f"🛡 *Rug Score — {name} (${symbol})*\n"
        f"⛓ {chain.upper()}\n\n"
        f"{score_color} *Score: {score}/100* `[{bar}]`\n"
        f"🏷 *Verdict: {verdict}*\n\n"
        f"🤖 *AI Analysis:*\n_{analysis}_\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*Security Signals:*\n{flags_text}\n\n"
        f"📋 `{ca[:20]}...`\n"
        f"_Powered by GoPlus + Claude AI. NFA DYOR ser._"
    )
    return msg


async def get_rug_score(ca: str) -> str:
    """Main entry point — fetch data, score, format."""
    from services.crypto import fetch_token_by_address

    pair = await fetch_token_by_address(ca)
    if not pair:
        return "❌ Token not found on DexScreener. Check the CA."

    base   = pair.get("baseToken", {})
    name   = base.get("name", "Unknown")
    symbol = base.get("symbol", "?")
    chain  = pair.get("chainId", "ethereum")

    chain_id = CHAIN_IDS.get(chain.lower(), "1")

    # Fetch security data
    if chain_id == "solana":
        raw_sec = await fetch_goplus_sol(ca)
        signals = parse_sol_security(raw_sec, pair)
    else:
        raw_sec = await fetch_goplus_evm(ca, chain_id)
        signals = parse_evm_security(raw_sec, pair)

    if not raw_sec:
        # GoPlus returned nothing — use DexScreener data only
        signals = {
            "liquidity_usd": float(pair.get("liquidity", {}).get("usd", 0) or 0),
            "market_cap":    float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0),
            "note": "GoPlus returned no data — limited analysis",
        }

    # AI scoring
    ai_result = await ai_rug_score(signals, name, symbol)

    return format_rug_report(name, symbol, chain, ca, signals, ai_result)
