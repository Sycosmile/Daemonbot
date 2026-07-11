"""
services/pumpfun.py — Pump.fun coin info + deployer history (/pf)
Daemonbot — MR SYCO (@Sycosmile)

NOTE: This uses pump.fun's unofficial frontend API, which is reverse-engineered
and undocumented — it has no SLA and pump.fun can wall it behind auth or change
the schema at any time without notice. Everything here degrades to a clear
"couldn't fetch" message instead of crashing if that happens. If it stops
working entirely, swap in a paid indexer (Bitquery/Helius) for this feature.
"""

import httpx

PUMPFUN_API = "https://frontend-api-v3.pump.fun"


async def fetch_pumpfun_coin(mint: str) -> dict | None:
    """Raw pump.fun coin record (used by /pf's text report AND the scan card
    for banner image / lore / real lifetime ATH). None if not a pump.fun
    token or the API is unreachable — never raises."""
    mint = mint.strip()
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{PUMPFUN_API}/coins/{mint}")
        except httpx.HTTPError:
            return None
        if r.status_code != 200:
            return None
        return r.json()


async def fetch_pumpfun_coin_verbose(mint: str) -> tuple[dict | None, str]:
    """Same as fetch_pumpfun_coin, but keeps the status-code-specific error
    message for /pf's text output instead of collapsing everything to a
    generic 'couldn't fetch'."""
    mint = mint.strip()
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{PUMPFUN_API}/coins/{mint}")
        except httpx.HTTPError as e:
            return None, f"❌ Pump.fun lookup failed: {type(e).__name__}"

        if r.status_code in (401, 403):
            return None, ("❌ Pump.fun blocked this lookup (their API now requires auth "
                           "for this endpoint). Check the token directly: "
                           f"https://pump.fun/coin/{mint}")
        if r.status_code == 404:
            return None, f"❌ `{mint}` isn't a pump.fun token (or has migrated off-curve)."
        if r.status_code != 200:
            return None, f"❌ Pump.fun returned {r.status_code}. Try again shortly."
        return r.json(), ""


async def fetch_deployer_history(creator: str) -> list:
    """Best-effort: other launches by this creator. Empty list if pump.fun
    walls/changes this endpoint — callers should treat that as 'unknown',
    not 'zero launches'."""
    if not creator:
        return []
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            cr = await client.get(
                f"{PUMPFUN_API}/coins",
                params={"creator": creator, "limit": 50, "offset": 0, "sort": "created_timestamp"},
            )
            if cr.status_code == 200:
                data = cr.json()
                return list(data.values()) if isinstance(data, dict) else data
        except Exception:
            pass
    return []


async def get_pumpfun_data(mint: str) -> str:
    mint = mint.strip()
    coin, err = await fetch_pumpfun_coin_verbose(mint)

    if coin is None:
        return err

    creator = coin.get("creator", "")
    dev_tokens = await fetch_deployer_history(creator)

    name = coin.get("name", "Unknown")
    symbol = coin.get("symbol", "?")
    mcap = coin.get("usd_market_cap", coin.get("market_cap", 0)) or 0
    bonded = coin.get("complete", False)
    koth = bool(coin.get("king_of_the_hill_timestamp"))
    ath_mcap = coin.get("ath_market_cap")
    twitter = coin.get("twitter") or "—"
    website = coin.get("website") or "—"
    reply_count = coin.get("reply_count", 0)

    status = "🟢 Bonded → migrated to Raydium" if bonded else "🟡 Still on bonding curve"

    msg = (
        f"🚀 *Pump.fun — {name} (${symbol})*\n\n"
        f"💰 Market cap: `${mcap:,.0f}`\n"
        f"📈 Status: {status}\n"
        f"👑 King of the Hill: {'✅ Yes' if koth else '❌ No'}\n"
    )
    if ath_mcap:
        msg += f"🏔️ ATH market cap: `${ath_mcap:,.0f}`\n"
    msg += f"💬 Replies: `{reply_count}`\n"
    msg += f"🐦 Twitter: {twitter}\n🔗 Website: {website}\n"

    if dev_tokens:
        total = len(dev_tokens)
        bonded_count = sum(1 for t in dev_tokens if t.get("complete"))
        best_mcap = max((t.get("usd_market_cap", t.get("market_cap", 0)) or 0) for t in dev_tokens)
        bond_rate = (bonded_count / total * 100) if total else 0

        dev_flag = ""
        if total >= 10 and bond_rate < 10:
            dev_flag = "\n🚨 *Serial deployer* — many launches, low bond rate. Classic farm pattern."
        elif total >= 5 and bond_rate < 25:
            dev_flag = "\n⚠️ Dev has launched several tokens with a low success rate."

        msg += (
            f"\n👤 *Deployer history* (`{creator[:6]}...{creator[-4:]}`)\n"
            f"  🪙 Total launches: `{total}`\n"
            f"  ✅ Bonded: `{bonded_count}` (`{bond_rate:.0f}%`)\n"
            f"  🏆 Best mcap reached: `${best_mcap:,.0f}`"
            f"{dev_flag}"
        )
    else:
        msg += f"\n👤 Deployer: `{creator[:6]}...{creator[-4:]}` _(history unavailable)_"

    msg += f"\n\n[View on Pump.fun](https://pump.fun/coin/{mint})"
    return msg

