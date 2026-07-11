"""
services/security_scan.py — Full security scan for Daemonbot (/sec)
Combines: GoPlus API, DexScreener, honeypot check, contract analysis.
Cybersecurity-first approach — leverages @Sycosmile's background.
"""

import httpx
import asyncio
from typing import Optional

GOPLUS_BASE  = "https://api.gopluslabs.io/api/v1"
HONEYPOT_URL = "https://api.honeypot.is/v2/IsHoneypot"

CHAIN_IDS = {
    "ethereum": "1", "eth": "1",
    "bsc": "56",
    "polygon": "137", "matic": "137",
    "arbitrum": "42161", "arb": "42161",
    "base": "8453",
    "solana": "solana", "sol": "solana",
}

RISK_WEIGHTS = {
    "is_honeypot":          40,
    "has_self_destruct":    35,
    "hidden_owner":         30,
    "can_take_ownership":   25,
    "is_mintable":          20,
    "has_blacklist":        15,
    "has_whitelist":        10,
    "proxy_contract":       10,
    "trading_cooldown":     10,
    "high_buy_tax":         15,
    "high_sell_tax":        20,
    "low_liquidity":        20,
    "lp_not_locked":        25,
    "creator_holds_much":   20,
    "external_call":        10,
    "not_open_source":      10,
}


async def fetch_honeypot_check(ca: str, chain: str = "eth") -> dict:
    """Check honeypot.is for EVM tokens."""
    chain_map = {
        "ethereum": "eth", "eth": "eth",
        "bsc": "bsc", "base": "base",
        "polygon": "polygon", "arbitrum": "arbitrum",
    }
    c = chain_map.get(chain.lower(), "eth")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(HONEYPOT_URL, params={"address": ca, "chainID": c})
            return r.json()
        except Exception:
            return {}


async def fetch_goplus(ca: str, chain_id: str) -> dict:
    if chain_id == "solana":
        url = f"{GOPLUS_BASE}/solana/token_security"
    else:
        url = f"{GOPLUS_BASE}/token_security/{chain_id}"
    async with httpx.AsyncClient(timeout=12) as client:
        try:
            r = await client.get(url, params={"contract_addresses": ca})
            result = r.json().get("result", {})
            return result.get(ca.lower(), result.get(ca, {}))
        except Exception:
            return {}


def calculate_risk_score(signals: dict) -> int:
    """Calculate numeric risk score 0-100 from signals."""
    score = 0
    for key, weight in RISK_WEIGHTS.items():
        if signals.get(key):
            score += weight
    return min(score, 100)


def risk_level(score: int) -> tuple[str, str]:
    if score <= 15:   return "SAFU", "🟢"
    elif score <= 35: return "LOW RISK", "🟡"
    elif score <= 55: return "MEDIUM RISK", "🟠"
    elif score <= 75: return "HIGH RISK", "🔴"
    else:             return "DANGER ZONE", "☠️"


def format_security_report(
    name: str,
    symbol: str,
    chain: str,
    ca: str,
    signals: dict,
    hp_data: dict,
    pair: dict,
) -> str:
    score        = calculate_risk_score(signals)
    level, emoji = risk_level(score)

    # Risk bar
    filled = int(score / 10)
    bar    = "█" * filled + "░" * (10 - filled)

    # Honeypot data
    hp_result = hp_data.get("honeypotResult", {})
    is_hp     = hp_result.get("isHoneypot", False)
    hp_reason = hp_result.get("honeypotReason", "")
    sim       = hp_data.get("simulationResult", {})
    buy_tax   = sim.get("buyTax", signals.get("buy_tax", 0))
    sell_tax  = sim.get("sellTax", signals.get("sell_tax", 0))

    # Liquidity
    liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    mc  = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)

    # Build flag list
    lines_pass = []
    lines_warn = []
    lines_fail = []

    def flag(condition, pass_msg, fail_msg, severity="warn"):
        if condition:
            if severity == "fail":
                lines_fail.append(f"🚨 {fail_msg}")
            else:
                lines_warn.append(f"⚠️ {fail_msg}")
        else:
            lines_pass.append(f"✅ {pass_msg}")

    flag(is_hp,                           "Not a honeypot",         f"HONEYPOT — {hp_reason}", "fail")
    flag(signals.get("is_mintable"),      "Not mintable",           "Mintable — dev can print tokens")
    flag(signals.get("hidden_owner"),     "No hidden owner",        "Hidden owner detected", "fail")
    flag(signals.get("can_take_ownership"), "Ownership safe",       "Dev can reclaim ownership", "fail")
    flag(signals.get("has_self_destruct"),"No self-destruct",       "Self-destruct function exists", "fail")
    flag(signals.get("has_blacklist"),    "No blacklist",           "Blacklist function — wallets can be blocked")
    flag(signals.get("proxy_contract"),   "No proxy",               "Proxy/upgradeable contract")
    flag(signals.get("external_call"),    "No external calls",      "External calls in contract")
    flag(signals.get("trading_cooldown"), "No trading cooldown",    "Trading cooldown function")

    if not signals.get("ownership_renounced"):
        lines_warn.append("⚠️ Ownership NOT renounced")
    else:
        lines_pass.append("✅ Ownership renounced")

    if signals.get("open_source"):
        lines_pass.append("✅ Contract verified/open source")
    else:
        lines_warn.append("⚠️ Contract NOT verified")

    # Tax check
    bt = float(buy_tax or 0)
    st = float(sell_tax or 0)
    if bt > 10:
        lines_fail.append(f"🚨 Buy tax: {bt:.1f}%")
    elif bt > 0:
        lines_warn.append(f"⚠️ Buy tax: {bt:.1f}%")
    else:
        lines_pass.append("✅ Buy tax: 0%")

    if st > 10:
        lines_fail.append(f"🚨 Sell tax: {st:.1f}%")
    elif st > 0:
        lines_warn.append(f"⚠️ Sell tax: {st:.1f}%")
    else:
        lines_pass.append("✅ Sell tax: 0%")

    # Liquidity
    if liq < 5000:
        lines_fail.append(f"🚨 Liquidity: ${liq:,.0f} — extremely low")
    elif liq < 25000:
        lines_warn.append(f"⚠️ Liquidity: ${liq:,.0f} — low")
    else:
        lines_pass.append(f"✅ Liquidity: ${liq:,.0f}")

    # LP Lock
    if signals.get("lp_locked"):
        pct = signals.get("lp_locked_pct", 0)
        lines_pass.append(f"✅ LP locked ({pct:.0f}%)")
    else:
        lines_warn.append("⚠️ LP not locked — rug possible")

    # Creator %
    cr_pct = signals.get("creator_pct", 0)
    if cr_pct > 20:
        lines_fail.append(f"🚨 Creator holds {cr_pct:.1f}% of supply")
    elif cr_pct > 5:
        lines_warn.append(f"⚠️ Creator holds {cr_pct:.1f}%")

    # Combine sections
    all_flags = lines_fail + lines_warn + lines_pass
    flags_text = "\n".join(f"  {f}" for f in all_flags[:14])

    dexlink = pair.get("url", "")

    msg = (
        f"🔐 *Security Scan — {name} (${symbol})*\n"
        f"⛓ {chain.upper()}\n\n"
        f"{emoji} *Risk: {score}/100 — {level}*\n"
        f"`[{bar}]`\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*Contract Checks:*\n{flags_text}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📊 MC: `${mc:,.0f}` | LIQ: `${liq:,.0f}`\n"
        f"📋 `{ca[:20]}{'...' if len(ca) > 20 else ''}`\n\n"
        f"_GoPlus + Honeypot.is data. Always DYOR ser._\n"
    )
    if dexlink:
        msg += f"[DexScreener]({dexlink})"
    return msg


async def run_security_scan(ca: str) -> str:
    """Full security scan pipeline."""
    from services.crypto import fetch_token_by_address

    pair = await fetch_token_by_address(ca)
    if not pair:
        return "❌ Token not found. Check the contract address."

    base   = pair.get("baseToken", {})
    name   = base.get("name", "Unknown")
    symbol = base.get("symbol", "?")
    chain  = pair.get("chainId", "ethereum")
    chain_id = CHAIN_IDS.get(chain.lower(), "1")

    # Parallel fetch — GoPlus + Honeypot check
    if chain_id != "solana":
        gp_task = fetch_goplus(ca, chain_id)
        hp_task = fetch_honeypot_check(ca, chain)
        gp_data, hp_data = await asyncio.gather(gp_task, hp_task)
    else:
        gp_data = await fetch_goplus(ca, "solana")
        hp_data = {}

    # Parse signals
    liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    mc  = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)
    hp_result = hp_data.get("honeypotResult", {})
    sim       = hp_data.get("simulationResult", {})

    signals = {
        "is_honeypot":          hp_result.get("isHoneypot", gp_data.get("is_honeypot", "0") == "1"),
        "is_mintable":          gp_data.get("is_mintable", "0") == "1",
        "hidden_owner":         gp_data.get("hidden_owner", "0") == "1",
        "can_take_ownership":   gp_data.get("can_take_back_ownership", "0") == "1",
        "has_self_destruct":    gp_data.get("self_destruct", "0") == "1",
        "has_blacklist":        gp_data.get("is_blacklisted", "0") == "1",
        "has_whitelist":        gp_data.get("is_whitelisted", "0") == "1",
        "proxy_contract":       gp_data.get("is_proxy", "0") == "1",
        "trading_cooldown":     gp_data.get("trading_cooldown", "0") == "1",
        "external_call":        gp_data.get("external_call", "0") == "1",
        "ownership_renounced":  gp_data.get("owner_address", "x") in ("", "0x0000000000000000000000000000000000000000"),
        "open_source":          gp_data.get("is_open_source", "0") == "1",
        "lp_locked":            False,
        "lp_locked_pct":        0,
        "creator_pct":          float(gp_data.get("creator_percent", 0) or 0) * 100,
        "buy_tax":              float(sim.get("buyTax", gp_data.get("buy_tax", 0)) or 0),
        "sell_tax":             float(sim.get("sellTax", gp_data.get("sell_tax", 0)) or 0),
        "low_liquidity":        liq < 10000,
        "lp_not_locked":        True,
    }

    # LP lock check
    lp_holders = gp_data.get("lp_holder_analysis") or gp_data.get("lp_holders", [])
    if lp_holders and isinstance(lp_holders, list) and lp_holders:
        top_lp = lp_holders[0]
        if isinstance(top_lp, dict) and top_lp.get("is_locked"):
            signals["lp_locked"]     = True
            signals["lp_not_locked"] = False
            signals["lp_locked_pct"] = float(top_lp.get("percent", 0) or 0) * 100

    # Solana-specific overrides
    if chain_id == "solana":
        signals["is_mintable"]  = gp_data.get("mintable", False)
        signals["has_blacklist"] = gp_data.get("freezable", False)
        signals["open_source"]  = True

    return format_security_report(name, symbol, chain, ca, signals, hp_data, pair)
