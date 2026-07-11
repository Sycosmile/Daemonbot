"""
config.py — All env vars + constants for Daemonbot.

Daemonbot — built by MR SYCO (@Sycosmile)
https://github.com/Sycosmile
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Core secrets ──────────────────────────────────────────────────────────────
BOT_TOKEN     = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")

# ── AI model ──────────────────────────────────────────────────────────────────
# llama-3.3-70b-versatile is Groq's best free model — fast and smart.
# Override in .env to use a different Groq model e.g. mixtral-8x7b-32768
AI_MODEL = os.getenv("AI_MODEL") or "llama-3.3-70b-versatile"

# Daemonbot's personality for free-text AI chat (mentions/replies). Keep it short —
# this is injected as the system prompt on every chat turn.
BOT_PERSONA = (
    "You are Daemonbot, a sharp, based, slightly degen AI assistant living in a "
    "crypto Telegram group. You were built by MR SYCO (@Sycosmile), a "
    "cybersecurity student and bug bounty hunter. You know crypto, trading "
    "slang, and on-chain security — you're skeptical of hype, you call out "
    "obvious rug signals, and you never give financial advice as fact, only "
    "as opinion with NFA DYOR energy. Keep replies short (2-4 sentences), "
    "punchy, and useful. No corporate tone, no excessive emoji spam."
)

# ── Chain RPC endpoints (reserved for future on-chain checks) ────────────────
RPC_URLS = {
    "solana": "https://api.mainnet-beta.solana.com",
    "ethereum": "https://eth.llamarpc.com",
    "bsc": "https://bsc-dataseed.binance.org",
    "base": "https://mainnet.base.org",
}

# ── Free APIs — no key needed ─────────────────────────────────────────────────
DEXSCREENER_BASE = "https://api.dexscreener.com/latest/dex"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
BIRDEYE_API = "https://public-api.birdeye.so"
BIRDEYE_KEY = os.getenv("BIRDEYE_API_KEY", "")  # NOTE: Birdeye's data API is NOT
# meaningfully free anymore (paid tiers start ~$39/mo, free tier is eval-only
# with strict limits) — keep this key optional/unused unless you've actually
# paid for it. Holder/security data now comes from RugCheck instead (free).

RUGCHECK_BASE = "https://api.rugcheck.xyz/v1"  # free, no key needed for /report

# FluxRPC — Solana RPC provider, used only for the few things RugCheck doesn't
# give us directly (creator wallet balance for the Dev Sold check, and the
# best-effort "fresh wallet" heuristic). Free tier: 10GB bandwidth/mo.
# Leave FLUXRPC_API_KEY blank to fall back to the public Solana RPC endpoint
# in RPC_URLS["solana"] (much lower rate limit, fine for light use/testing).
FLUXRPC_URL = os.getenv("FLUXRPC_URL", "https://eu.fluxrpc.com")
FLUXRPC_API_KEY = os.getenv("FLUXRPC_API_KEY", "")

# Back-compat aliases (older modules referenced these names) ─ harmless to keep.
DEXSCREENER_API = DEXSCREENER_BASE
COINGECKO_API = COINGECKO_BASE

# ── Optional keys — deployer history (/dev) and ETH gas (/gas) degrade
# gracefully to "add a key" messages if these are left blank ─────────────────
ETHERSCAN_KEY = os.getenv("ETHERSCAN_KEY", "")
BSCSCAN_KEY = os.getenv("BSCSCAN_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # optional — raises GitHub rate limit 60/hr -> 5,000/hr
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")  # optional, free signup — powers /cal

# ── Chain explorer link prefixes (CA gets appended) ──────────────────────────
CHAIN_EXPLORERS = {
    "ethereum": "https://etherscan.io/address/",
    "eth":      "https://etherscan.io/address/",
    "bsc":      "https://bscscan.com/address/",
    "base":     "https://basescan.org/address/",
    "arbitrum": "https://arbiscan.io/address/",
    "polygon":  "https://polygonscan.com/address/",
    "avalanche": "https://snowtrace.io/address/",
    "solana":   "https://solscan.io/token/",
}

# ── Leaderboard persistence ───────────────────────────────────────────────────
LEADERBOARD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "leaderboard.json")
MAX_LEADERBOARD_ENTRIES = 10

# ── ATH high-water-mark cache (non-pump.fun tokens only — see services/ath_tracker.py) ──
ATH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ath_cache.json")

# ── Identity ──────────────────────────────────────────────────────────────────
BOT_NAME = "Daemonbot"
BOT_USERNAME = os.getenv("BOT_USERNAME", "Daemonbot")

# Brand credit — used in footers (/start, /help, PNL cards). Edit freely.
AUTHOR_NAME = "MR SYCO"
AUTHOR_HANDLE = "@Sycosmile"
AUTHOR_GITHUB = "https://github.com/Sycosmile"
