"""
services/quicklinks.py — Static deep-link templates for the scan card's
quick-link row (analytics sites) and quick-buy row (trading bots).

IMPORTANT — verify before relying on these in production:
Trading-bot deep-link formats are NOT a stable public API. Several of these
bots gate their `?start=` param behind a referral code (and you'd actually
WANT your own ref code in there for revenue), and formats change without
notice. Confidence noted per-entry below. Anything marked (verify) should be
manually clicked-through once before you trust it in front of users.

Analytics links (DexScreener, GeckoTerminal, Defined, Solscan, X search) are
stable, documented URL schemes — low risk.
"""

# ── Analytics / research row (DEF · DS · GT · EXP · 𝕏) ──────────────────────

def analytics_links(ca: str, pair_address: str, symbol: str, dexscreener_url: str = "") -> dict:
    return {
        "DEF": f"https://www.defined.fi/sol/{pair_address}" if pair_address else "",
        "DS":  dexscreener_url or f"https://dexscreener.com/solana/{ca}",
        "GT":  f"https://www.geckoterminal.com/solana/pools/{pair_address}" if pair_address else "",
        "EXP": f"https://solscan.io/token/{ca}",
        "𝕏":   f"https://twitter.com/search?q=%24{symbol}&src=typed_query&f=live",
    }


# ── Quick-buy row (GMGN · BonkBot · Trojan · Photon · Maestro) ──────────────
# Format: (label, url_template). {ca} / {pair} get substituted at call time.

QUICKBUY_TEMPLATES = {
    # Web terminal, not a TG bot deep-link — most reliable of the bunch.
    "GMGN":    ("https://gmgn.ai/sol/token/{ca}", "high-confidence (web)"),

    # Confirmed bot handle (@bonkbot_bot). Raw-CA start param is the commonly
    # documented pattern for this bot. (verify)
    "BonkBot": ("https://t.me/bonkbot_bot?start={ca}", "verify"),

    # Confirmed bot handle (@TrojanOnSolana). Trojan's start param is often
    # referral-prefixed (e.g. r-<ref>-<ca>) rather than a bare CA — left
    # without a CA param to avoid shipping a link that silently fails.
    # Add your own ref prefix here once you've got one. (verify)
    "Trojan":  ("https://t.me/TrojanOnSolana", "verify — no CA param, ref-gated"),

    # Photon has no Telegram bot at all — it's web-terminal only. Pair
    # (LP) address, not the token CA, is what its URLs key off.
    "Photon":  ("https://photon-sol.tinyastro.io/en/lp/{pair}", "verify (web, needs pair addr)"),

    # Confirmed bot handle (@maestro). Raw-CA start param is widely
    # documented for this one. (verify)
    "Maestro": ("https://t.me/maestro?start={ca}", "verify"),
}


def quickbuy_links(ca: str, pair_address: str = "") -> dict:
    """Returns {label: url}. Entries needing a {pair} we don't have are
    simply omitted rather than shipped broken."""
    out = {}
    for label, (template, _confidence) in QUICKBUY_TEMPLATES.items():
        if "{pair}" in template and not pair_address:
            continue
        out[label] = template.format(ca=ca, pair=pair_address)
    return out


def build_keyboard_rows(analytics: dict, quickbuy: dict, row_size: int = 4) -> list[list[tuple[str, str]]]:
    """Plain (label, url) tuples grouped into rows — kept free of any
    telegram-library import so this module stays usable outside a bot
    context too. handlers/commands.py wraps these into actual
    InlineKeyboardButton/InlineKeyboardMarkup objects."""
    def _chunk(items, size):
        items = [(k, v) for k, v in items.items() if v]
        return [items[i:i + size] for i in range(0, len(items), size)] if items else []

    rows = _chunk(analytics, row_size)
    rows += _chunk(quickbuy, row_size)
    return rows
