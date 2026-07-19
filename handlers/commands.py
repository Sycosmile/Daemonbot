"""
handlers/commands.py — All slash command handlers
"""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.crypto import (
    fetch_token_by_address, fetch_token_by_name,
    build_price_message, build_scan_message,
    get_trending_tokens, format_trending, format_number
)
from services.leaderboard import log_call, get_leaderboard, format_leaderboard, \
    get_calls_leaderboard, format_calls_leaderboard
from config import CHAIN_EXPLORERS, AUTHOR_NAME, AUTHOR_HANDLE, AUTHOR_GITHUB, AUTHOR_X, BOT_NAME


# ── /start ────────────────────────────────────────────
def _start_text() -> str:
    return (
        "⚡ *Daemonbot online.*\n\n"
        "Multi-chain crypto assistant. AI-powered. Built different.\n\n"
        "*Commands:*\n"
        "/p `<token>` — Price lookup\n"
        "/scan `<CA>` — Contract scan\n"
        "/lb `[1d|7d|all]` — Group leaderboard\n"
        "/th `<CA>` — Top holders\n"
        "/chart `<token>` — Price chart link\n"
        "/trending — Trending tokens\n\n"
        "_Talk to me anytime. I don't bite. Much._"
    )


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ℹ️ About", callback_data="about_daemonbot")],
    ])


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        _start_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=_start_keyboard()
    )


# ── About button (callback) ───────────────────────────
def _about_text() -> str:
    return (
        f"🤖 *{BOT_NAME}*\n\n"
        "A multi-chain AI crypto assistant for Telegram — price lookups, "
        "contract scans, rug/security checks, conviction call leaderboards, "
        "PNL cards, and passive $ticker/CA detection.\n\n"
        "*Chains:* Solana, Ethereum, Base, BSC, Arbitrum, Polygon\n"
        "*Built with:* python-telegram-bot, Pillow, Groq (Llama 3.3)\n\n"
        f"Built by *{AUTHOR_NAME}* ({AUTHOR_HANDLE}) — 3MTT Cybersecurity "
        "fellow, bug bounty hunter 🔐\n\n"
        "_NFA DYOR ser._"
    )


def _about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("GitHub", url=AUTHOR_GITHUB),
            InlineKeyboardButton("X", url=AUTHOR_X),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
    ])


async def about_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        _about_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=_about_keyboard()
    )


async def back_to_start_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        _start_text(), parse_mode=ParseMode.MARKDOWN, reply_markup=_start_keyboard()
    )


# ── /help ─────────────────────────────────────────────
async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛠 *Daemonbot Commands*\n\n"
        "*/p* `<symbol or CA>` — Token price (with image)\n"
        "  Example: `/p SOL` or `/p 0xCA...`\n\n"
        "*/scan* `<CA>` — Deep token scan (full image card)\n"
        "  Example: `/scan So11111...`\n\n"
        "*/soc* `<CA>` — Socials, compact one-liner\n\n"
        "*/lb* `[1d|7d|all]` — Top calls by multiplier + group stats "
        "(hit rate, median return). Defaults to 7d, tap the buttons to switch.\n\n"
        "*/th* `<CA>` — Top holders (via DexScreener)\n\n"
        "*/chart* `<token>` — Get chart link\n\n"
        "*/trending* — Trending tokens on CoinGecko\n\n"
        "*/gh* `owner/repo` — GitHub repo health check\n\n"
        "*/do* `<domain>` — WHOIS lookup\n\n"
        "*/pf* `<mint>` — Pump.fun coin + deployer stats\n\n"
        "*/stats* _(reply optional)_ — Hit rate + median return\n\n"
        "*/alert* `<token> <price>` — Get pinged on a price target\n\n"
        "*/cal* — Economic calendar (needs Finnhub key)\n\n"
        "*/eli5* `/explain` `/fact` `/translate` — reply to any message with these\n\n"
        "*/antiscam on|off* — auto-delete + warn on likely drainer links\n\n"
        "*Paste a CA or $ticker with no command — I'll auto-reply:*\n"
        "  • plain → quick price + image\n"
        "  • ending in `.` → compact one-liner + image\n"
        "  • ending in `,` → full scan card (same as /scan)\n"
        "  • leading `.` → I stay silent on that message\n"
        "  `/autodetect off` to disable this entirely.\n\n"
        "_Mention me or reply to chat with me. NFA DYOR ser._\n\n"
        "Tap *ℹ️ About* on /start for links + tech info.\n\n"
        f"_{AUTHOR_NAME} ({AUTHOR_HANDLE})_"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ── /p <token> ────────────────────────────────────────
async def price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/p <symbol or CA>`", parse_mode=ParseMode.MARKDOWN)
        return

    query = ctx.args[0].strip()
    msg   = await update.message.reply_text("🔍 Fetching price...")

    # Try as CA first (longer strings), else by symbol
    if len(query) > 20:
        pair = await fetch_token_by_address(query)
    else:
        pair = await fetch_token_by_name(query)

    if not pair:
        from services.pumpfun import get_pumpfun_fallback, fetch_pumpfun_coin
        fallback = await get_pumpfun_fallback(query) if len(query) > 20 else None
        if fallback:
            pf = await fetch_pumpfun_coin(query) if len(query) > 20 else None
            img_url = (pf or {}).get("image_uri")

            mcap = (pf or {}).get("usd_market_cap", (pf or {}).get("market_cap", 0)) or 0
            synthetic_price = mcap / 1_000_000_000 if mcap else 0
            synthetic_pair = {"priceUsd": str(synthetic_price), "marketCap": mcap}

            if update.effective_chat.type in ("group", "supergroup") and synthetic_price > 0:
                user = update.effective_user
                await log_call(
                    chat_id=update.effective_chat.id,
                    user_id=user.id,
                    username=user.username or user.first_name,
                    token_name=(pf or {}).get("name", "?"),
                    token_symbol=(pf or {}).get("symbol", "?"),
                    price_usd=synthetic_price,
                    ca=query,
                )
                from services.firstcaller import get_first_caller_line
                fc_line = await get_first_caller_line(update.effective_chat.id, query, synthetic_pair)
                if fc_line:
                    fallback += f"\n\n{fc_line}"

            if img_url:
                try:
                    await msg.delete()
                    await update.message.reply_photo(img_url, caption=fallback, parse_mode=ParseMode.MARKDOWN)
                    return
                except Exception:
                    pass
            await msg.edit_text(fallback, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            return
        await msg.edit_text("❌ Token not found ser. Check the symbol/CA and try again.")
        return

    text = build_price_message(pair)
    ca = pair.get("baseToken", {}).get("address", query)

    # Log the call FIRST — see comment in autodetect.py for why.
    if update.effective_chat.type in ("group", "supergroup"):
        user = update.effective_user
        base = pair.get("baseToken", {})
        await log_call(
            chat_id=update.effective_chat.id,
            user_id=user.id,
            username=user.username or user.first_name,
            token_name=base.get("name", "?"),
            token_symbol=base.get("symbol", "?"),
            price_usd=float(pair.get("priceUsd") or 0),
            ca=ca,
        )

    if update.effective_chat.type in ("group", "supergroup"):
        from services.firstcaller import get_first_caller_line
        fc_line = await get_first_caller_line(update.effective_chat.id, ca, pair)
        if fc_line:
            text += f"\n\n{fc_line}"

    from services.token_image import resolve_token_image
    img_url = await resolve_token_image(pair, ca)

    if img_url:
        try:
            await msg.delete()
            await update.message.reply_photo(img_url, caption=text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /scan <CA> ────────────────────────────────────────
async def scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/scan <contract address>`", parse_mode=ParseMode.MARKDOWN)
        return

    ca  = ctx.args[0].strip()
    msg = await update.message.reply_text("🧪 Scanning contract...")

    await _send_scan_card(update, ctx, msg, ca)


async def _send_scan_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE, msg, query: str):
    """Shared by /scan and /z — builds the data, renders the image card,
    sends it with the quick-link/quick-buy keyboard, and falls back to the
    old plain-text scan message if anything in that pipeline blows up
    (3rd-party API down, Pillow error, whatever)."""
    import asyncio, io
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from services.scan_data import build_scan_data
    from services.scan_card import generate_scan_card
    from services.quicklinks import build_keyboard_rows

    async def _log_this_call(pair: dict):
        if update.effective_chat.type in ("group", "supergroup") and pair and update.effective_user:
            user = update.effective_user
            base = pair.get("baseToken", {})
            await log_call(
                chat_id=update.effective_chat.id,
                user_id=user.id,
                username=user.username or user.first_name,
                token_name=base.get("name", "?"),
                token_symbol=base.get("symbol", "?"),
                price_usd=float(pair.get("priceUsd") or 0),
                ca=base.get("address", query),
            )

    try:
        data = await build_scan_data(query)
        if not data:
            from services.pumpfun import get_pumpfun_fallback, fetch_pumpfun_coin
            fallback = await get_pumpfun_fallback(query)
            if fallback:
                pf = await fetch_pumpfun_coin(query)
                img_url = (pf or {}).get("image_uri")

                mcap = (pf or {}).get("usd_market_cap", (pf or {}).get("market_cap", 0)) or 0
                synthetic_price = mcap / 1_000_000_000 if mcap else 0
                synthetic_pair = {"priceUsd": str(synthetic_price), "marketCap": mcap}

                if update.effective_chat.type in ("group", "supergroup") and synthetic_price > 0:
                    user = update.effective_user
                    await log_call(
                        chat_id=update.effective_chat.id,
                        user_id=user.id,
                        username=user.username or user.first_name,
                        token_name=(pf or {}).get("name", "?"),
                        token_symbol=(pf or {}).get("symbol", "?"),
                        price_usd=synthetic_price,
                        ca=query,
                    )
                    from services.firstcaller import get_first_caller_line
                    fc_line = await get_first_caller_line(update.effective_chat.id, query, synthetic_pair)
                    if fc_line:
                        fallback += f"\n\n{fc_line}"

                if img_url:
                    try:
                        await msg.delete()
                        await update.message.reply_photo(img_url, caption=fallback, parse_mode=ParseMode.MARKDOWN)
                        return
                    except Exception:
                        pass
                await msg.edit_text(fallback, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                return
            await msg.edit_text(
                "❌ Contract not found on DexScreener ser.\n"
                "Either it's too new, not on a supported DEX, or that CA is cooked."
            )
            return
        pair = data["_pair"]
        await _log_this_call(pair)

        loop = asyncio.get_event_loop()
        img_bytes = await loop.run_in_executor(None, generate_scan_card, data)

        kb_rows = build_keyboard_rows(data.get("analytics_links", {}), data.get("quickbuy_links", {}))
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(label, url=url) for label, url in row] for row in kb_rows
        ]) if kb_rows else None

        caption = f"🧪 `${data['symbol']}` scan — {data['chain'].upper()}"
        if update.effective_chat.type in ("group", "supergroup"):
            from services.firstcaller import get_first_caller_line
            fc_line = await get_first_caller_line(update.effective_chat.id, data.get("ca", query), pair)
            if fc_line:
                caption += f"\n\n{fc_line}"

        await msg.delete()
        await update.message.reply_photo(
            photo=io.BytesIO(img_bytes),
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    except Exception:
        # Card pipeline failed somewhere (RugCheck down, Pillow error, etc.)
        # — fall back to the plain-text scan rather than leaving the user
        # with nothing.
        pair = await (fetch_token_by_address(query) if len(query) > 20 else fetch_token_by_name(query))
        if not pair:
            await msg.edit_text("❌ Contract not found ser.")
            return
        await _log_this_call(pair)
        text = build_scan_message(pair)
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


def _leaderboard_keyboard(active_period: str) -> InlineKeyboardMarkup:
    labels = {"1d": "1D", "7d": "7D", "all": "All-time"}
    row = []
    for period, label in labels.items():
        text = f"• {label} •" if period == active_period else label
        row.append(InlineKeyboardButton(text, callback_data=f"lb_period:{period}"))
    return InlineKeyboardMarkup([row])


# ── /lb ───────────────────────────────────────────────
async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Leaderboard only works in group chats ser.")
        return

    period = ctx.args[0].lower() if ctx.args and ctx.args[0].lower() in ("1d", "7d", "all") else "7d"

    msg = await update.message.reply_text("📊 Building leaderboard...")
    result = await get_calls_leaderboard(chat.id, period=period)
    text = format_calls_leaderboard(result, group_name=chat.title or "this group")
    await msg.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_leaderboard_keyboard(period),
    )


async def leaderboard_period_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    period = query.data.split(":", 1)[1]
    chat = update.effective_chat

    result = await get_calls_leaderboard(chat.id, period=period)
    text = format_calls_leaderboard(result, group_name=chat.title or "this group")
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_leaderboard_keyboard(period),
    )


# ── /th <CA> ─────────────────────────────────────────
async def top_holders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/th <CA>`", parse_mode=ParseMode.MARKDOWN)
        return

    ca   = ctx.args[0].strip()
    msg  = await update.message.reply_text("💎 Fetching top holders...")
    pair = await fetch_token_by_address(ca)

    if not pair:
        await msg.edit_text("❌ Token not found ser.")
        return

    base   = pair.get("baseToken", {})
    chain  = pair.get("chainId", "")
    symbol = base.get("symbol", "?")

    # DexScreener doesn't expose holder list directly.
    # We redirect to the right explorer for now.
    explorer = CHAIN_EXPLORERS.get(chain, "")
    link = f"{explorer}{ca}" if explorer else f"https://dexscreener.com/{chain}/{ca}"

    text = (
        f"💎 *Top Holders — ${symbol}*\n\n"
        f"DexScreener doesn't expose holder lists via API ser.\n"
        f"Check directly:\n"
        f"[View on Explorer]({link})\n\n"
        f"_For SOL tokens, Birdeye or Solscan have the full holder breakdown._"
    )
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False)


# ── /chart <token> ────────────────────────────────────
async def chart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/chart <symbol or CA>`", parse_mode=ParseMode.MARKDOWN)
        return

    query = " ".join(ctx.args).strip()
    msg   = await update.message.reply_text("📊 Finding chart...")

    if len(query) > 20:
        pair = await fetch_token_by_address(query)
    else:
        pair = await fetch_token_by_name(query)

    if not pair:
        await msg.edit_text("❌ Token not found ser.")
        return

    base   = pair.get("baseToken", {})
    symbol = base.get("symbol", "?")
    url    = pair.get("url", "")

    text = (
        f"📊 *Chart — ${symbol}*\n\n"
        f"[Open on DexScreener]({url})\n\n"
        f"_Price: {pair.get('priceUsd', '?')} | "
        f"24h: {pair.get('priceChange', {}).get('h24', '?')}%_"
    )
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)


# ── /trending ─────────────────────────────────────────
async def trending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg    = await update.message.reply_text("🔥 Fetching trending...")
    coins  = await get_trending_tokens()
    text   = format_trending(coins)
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)


# ── /nar <token or CA> ────────────────────────────────
async def narrative(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/nar <symbol or CA>`", parse_mode=ParseMode.MARKDOWN)
        return

    query = ctx.args[0].strip()
    msg   = await update.message.reply_text("🧬 Generating narrative...")

    if len(query) > 20:
        pair = await fetch_token_by_address(query)
    else:
        pair = await fetch_token_by_name(query)

    if not pair:
        await msg.edit_text("❌ Token not found ser.")
        return

    base = pair.get("baseToken", {})
    from services.narrative import generate_narrative
    from services.crypto import format_number, format_price

    text = await generate_narrative(
        name=base.get("name", "Unknown"),
        symbol=base.get("symbol", "?"),
        chain=pair.get("chainId", "?").upper(),
        price_usd=format_price(pair.get("priceUsd")),
        market_cap=format_number(pair.get("marketCap") or pair.get("fdv", 0)),
        volume_24h=format_number(pair.get("volume", {}).get("h24", 0)),
        price_change_24h=str(pair.get("priceChange", {}).get("h24", "0")),
        liquidity=format_number(pair.get("liquidity", {}).get("usd", 0)),
        dex=pair.get("dexId", "?").title(),
        ca=base.get("address", ""),
    )

    header = (
        f"🪙 *{base.get('name')}* `${base.get('symbol')}`\n"
        f"⛓ {pair.get('chainId','').upper()} • {pair.get('dexId','').title()}\n\n"
    )
    await msg.edit_text(header + text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /x @username ─────────────────────────────────────
async def x_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/x @username`", parse_mode=ParseMode.MARKDOWN)
        return

    username = ctx.args[0].strip()
    msg      = await update.message.reply_text(f"🔍 Checking `{username}`...")

    from services.xchecker import check_x_account
    result = await check_x_account(username)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /gpnl <period> ───────────────────────────────────
async def gpnl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat   = update.effective_chat
    period = ctx.args[0] if ctx.args else "7d"

    if period not in ("1d", "7d", "30d", "all"):
        await update.message.reply_text(
            "Usage: `/gpnl <1d|7d|30d|all>`", parse_mode=ParseMode.MARKDOWN
        )
        return

    msg = await update.message.reply_text("📊 Building group PNL...")
    from services.pnl import get_group_pnl
    result = await get_group_pnl(chat.id, period)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /fc <token> ──────────────────────────────────────
async def first_caller(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/fc <symbol or CA>`", parse_mode=ParseMode.MARKDOWN)
        return

    chat  = update.effective_chat
    query = ctx.args[0].strip()
    msg   = await update.message.reply_text("🏆 Finding first caller...")

    from services.firstcaller import get_first_caller
    result = await get_first_caller(chat.id, query)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ══════════════════════════════════════════════════════
#  RICK-STYLE RESEARCH COMMANDS
# ══════════════════════════════════════════════════════

# ── /lore <token> ─────────────────────────────────────
async def lore(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/lore <token>`", parse_mode=ParseMode.MARKDOWN)
        return
    query = ctx.args[0].strip()
    msg   = await update.message.reply_text("📖 Researching lore...")
    pair  = await (fetch_token_by_address(query) if len(query) > 20 else fetch_token_by_name(query))
    if not pair:
        # Still try lore with just the query as name/symbol
        from services.research import get_lore
        result = await get_lore(query, query)
    else:
        base = pair.get("baseToken", {})
        from services.research import get_lore
        result = await get_lore(base.get("name", query), base.get("symbol", query))
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /dev <CA> ─────────────────────────────────────────
async def dev(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/dev <contract address>`", parse_mode=ParseMode.MARKDOWN)
        return
    ca  = ctx.args[0].strip()
    msg = await update.message.reply_text("🔎 Fetching deployer history...")
    from services.research import get_deployer_history
    pair = await fetch_token_by_address(ca)
    chain = pair.get("chainId", "ethereum") if pair else "ethereum"
    result = await get_deployer_history(ca, chain)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /soc <CA> ─────────────────────────────────────────
async def soc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/soc <contract address>`", parse_mode=ParseMode.MARKDOWN)
        return
    ca  = ctx.args[0].strip()
    msg = await update.message.reply_text("🔗 Finding socials...")
    from services.research import find_socials
    result = await find_socials(ca)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /gas ──────────────────────────────────────────────
async def gas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⛽ Fetching gas...")
    from services.research import get_gas
    result = await get_gas()
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /groupburp ────────────────────────────────────────
async def groupburp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("GroupBurp only works in group chats ser.")
        return
    msg = await update.message.reply_text("🔥 Calculating active plays...")
    from services.research import get_groupburp
    result = await get_groupburp(chat.id)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /ga ───────────────────────────────────────────────
async def group_ath(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg  = await update.message.reply_text("🏆 Building ATH leaderboard...")
    from services.research import get_ath_leaderboard
    result = await get_ath_leaderboard(chat.id)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /best /worst ──────────────────────────────────────
async def best(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    period = ctx.args[0] if ctx.args else "24h"
    msg    = await update.message.reply_text("🚀 Fetching top gainers...")
    from services.research import get_gainers_losers
    result = await get_gainers_losers("gainers", period)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


async def worst(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    period = ctx.args[0] if ctx.args else "24h"
    msg    = await update.message.reply_text("💀 Fetching top losers...")
    from services.research import get_gainers_losers
    result = await get_gainers_losers("losers", period)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /meta ─────────────────────────────────────────────
async def meta(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📊 Fetching trending metas...")
    from services.research import get_dex_metas
    result = await get_dex_metas()
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /bm <CA> ──────────────────────────────────────────
async def bubblemap(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/bm <CA>`", parse_mode=ParseMode.MARKDOWN)
        return
    ca   = ctx.args[0].strip()
    pair = await fetch_token_by_address(ca)
    chain = pair.get("chainId", "eth") if pair else "eth"
    from services.research import get_bubblemap
    result = get_bubblemap(ca, chain)
    await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /z <token> — compact scan ─────────────────────────
async def compact_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/z <symbol or CA>`", parse_mode=ParseMode.MARKDOWN)
        return
    query = ctx.args[0].strip()
    msg   = await update.message.reply_text("⚡ Quick scan...")
    await _send_scan_card(update, ctx, msg, query)


# ── /pnl — image card version ─────────────────────────
async def pnl_image(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not ctx.args:
        # No token — show text stats
        from services.pnl import get_user_stats
        msg = await update.message.reply_text("📊 Loading stats...")
        result = await get_user_stats(chat.id, user.id, user.username or user.first_name)
        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
        return

    query = ctx.args[0].strip()
    msg   = await update.message.reply_text("🎨 Generating PNL card...")

    from services.pnl import get_user_pnl
    from services.crypto import fetch_token_by_address, fetch_token_by_name
    from services.leaderboard import _load
    from services.pnl_card import generate_pnl_image

    # Get call data
    data  = _load()
    gkey  = str(chat.id)
    ukey  = str(user.id)
    uname = user.username or user.first_name

    user_data = data.get(gkey, {}).get(ukey)
    if not user_data:
        await msg.edit_text("❌ No calls found for you in this group ser.")
        return

    # Find matching call — search newest first so /pnl shows the latest entry
    matched = None
    for call in reversed(user_data.get("calls", [])):
        if (
            query.lower() in call.get("symbol", "").lower() or
            query.lower() in call.get("token", "").lower() or
            query.lower() == call.get("ca", "").lower()
        ):
            matched = call
            break

    if not matched:
        await msg.edit_text(f"❌ No call for `{query}` found in your history.", parse_mode=ParseMode.MARKDOWN)
        return

    ca = matched.get("ca", "")
    if ca:
        pair = await fetch_token_by_address(ca)
    else:
        pair = await fetch_token_by_name(matched.get("symbol", query))

    if not pair and ca:
        # Not yet migrated off pump.fun's bonding curve — DexScreener has
        # nothing for it, but pump.fun's own API still does. Build a
        # synthetic pair dict so everything below (which just reads
        # priceUsd/marketCap/chainId) works unchanged.
        from services.pumpfun import fetch_pumpfun_coin
        pf = await fetch_pumpfun_coin(ca)
        mcap = (pf or {}).get("usd_market_cap", (pf or {}).get("market_cap", 0)) or 0
        if mcap:
            pair = {"priceUsd": str(mcap / 1_000_000_000), "marketCap": mcap, "chainId": "solana"}

    if not pair:
        await msg.edit_text("❌ Couldn't fetch current price — not on DexScreener or pump.fun.")
        return

    current_price = float(pair.get("priceUsd") or 0)
    entry_price   = matched.get("price", 0)
    chain         = pair.get("chainId", "MULTI").upper()

    from services.leaderboard import record_pnl_peak
    peak_price = await record_pnl_peak(
        chat_id=chat.id, user_id=user.id,
        call_time=matched.get("time", ""), price_usd=current_price,
    )

    from services.ath_tracker import get_real_ath_mc
    current_mc = float(pair.get("marketCap") or pair.get("fdv") or 0)
    ath_mc = await get_real_ath_mc(ca, current_mc, is_solana=(chain.lower() == "solana"))

    try:
        import asyncio, io
        loop = asyncio.get_event_loop()
        # run_in_executor offloads the heavy Pillow drawing + sync HTTP image
        # fetch to a thread — the bot stays responsive for other users
        img_bytes = await loop.run_in_executor(None, lambda: generate_pnl_image(
            username=uname,
            token_name=matched.get("token", matched.get("symbol", "?")),
            symbol=matched.get("symbol", "?"),
            entry_price=entry_price,
            current_price=current_price,
            call_time=matched.get("time", ""),
            total_calls=user_data.get("total_calls", 0),
            chain=chain,
            pair=pair,
            peak_price=peak_price,
            ath_mc=ath_mc,
        ))

        from telegram import InputFile
        await msg.delete()
        await update.message.reply_photo(
            photo=io.BytesIO(img_bytes),
            caption=f"PNL Card for @{uname} — ${matched.get('symbol', '?')} | MR SYCO (@Sycosmile)",
        )
    except Exception as e:
        # Fallback to text if Pillow fails
        result = await get_user_pnl(chat.id, user.id, uname, query)
        await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ══════════════════════════════════════════════════════
#  UNIQUE DAEMONBOT FEATURES
# ══════════════════════════════════════════════════════

# ── /rug <CA> — AI Rug Score ──────────────────────────
async def rug_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/rug <contract address>`\n_AI-powered rug probability score._",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    ca  = ctx.args[0].strip()
    msg = await update.message.reply_text("🛡 Running AI rug analysis...")
    from services.rugscore import get_rug_score
    result = await get_rug_score(ca)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /sec <CA> — Full Security Scan ───────────────────
async def security_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/sec <contract address>`\n_GoPlus + Honeypot.is contract analysis._",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    ca  = ctx.args[0].strip()
    msg = await update.message.reply_text("🔐 Running security scan...")
    from services.security_scan import run_security_scan
    result = await run_security_scan(ca)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /call <1-5> — Conviction call ────────────────────
async def conviction_call(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user    = update.effective_user
    chat    = update.effective_chat

    if not ctx.args:
        await message.reply_text(
            "Usage: `/call <1-5>` — reply to a token scan\n"
            "1 = watching | 5 = MAX conviction",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    try:
        level = int(ctx.args[0])
        if level not in range(1, 6):
            raise ValueError
    except ValueError:
        await message.reply_text("❌ Conviction must be 1-5. Example: `/call 4`", parse_mode=ParseMode.MARKDOWN)
        return

    # Try to extract token info from replied-to message
    token_name = "Unknown"
    symbol     = "?"
    ca         = ""
    price      = 0.0

    replied = message.reply_to_message
    if replied and replied.text:
        import re
        # Extract symbol like $SOL or $PEPE from bot message
        sym_match = re.search(r'\$([A-Z]{2,10})', replied.text)
        if sym_match:
            symbol = sym_match.group(1)
            token_name = symbol

        # Extract CA
        ca_match = re.search(
            r'\b(0x[a-fA-F0-9]{40}|[1-9A-HJ-NP-Za-km-z]{32,44})\b',
            replied.text
        )
        if ca_match:
            ca = ca_match.group(1)

        # Extract price
        price_match = re.search(r'Price[:\s`]+\$?([\d.]+)', replied.text, re.IGNORECASE)
        if price_match:
            try:
                price = float(price_match.group(1))
            except ValueError:
                pass

    # If we have a CA, fetch fresh price
    if ca and price == 0:
        try:
            pair = await fetch_token_by_address(ca)
            if pair:
                price      = float(pair.get("priceUsd") or 0)
                base       = pair.get("baseToken", {})
                symbol     = base.get("symbol", symbol)
                token_name = base.get("name", token_name)
        except Exception:
            pass

    from services.conviction import record_call
    result = await record_call(
        chat_id=chat.id,
        user_id=user.id,
        username=user.username or user.first_name,
        token_name=token_name,
        symbol=symbol,
        ca=ca,
        price=price,
        conviction=level,
    )
    await message.reply_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /calls — View my conviction calls ────────────────
async def my_calls(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    msg  = await update.message.reply_text("📋 Loading your calls...")
    from services.conviction import get_user_calls
    result = await get_user_calls(chat.id, user.id, user.username or user.first_name)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /clb — Conviction leaderboard ────────────────────
async def conviction_lb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg  = await update.message.reply_text("📣 Loading conviction board...")
    from services.conviction import get_conviction_leaderboard
    result = await get_conviction_leaderboard(chat.id)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /summary — Summarize group chat ──────────────────
async def summary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Summary only works in group chats ser.")
        return
    limit = 50
    if ctx.args:
        try:
            limit = min(int(ctx.args[0]), 100)
        except ValueError:
            pass
    msg = await update.message.reply_text(f"📋 Summarizing last {limit} messages...")
    from services.summary import summarize_chat
    result = await summarize_chat(chat.id, limit)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /gh — GitHub repo health check ───────────────────
async def github_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/gh owner/repo` (e.g. `/gh Sycosmile/Daemonbot`)", parse_mode=ParseMode.MARKDOWN)
        return
    msg = await update.message.reply_text("🔍 Checking repo...")
    from services.github import get_repo_health
    result = await get_repo_health(" ".join(ctx.args))
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /do — Domain WHOIS lookup ─────────────────────────
async def domain_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/do example.com`", parse_mode=ParseMode.MARKDOWN)
        return
    msg = await update.message.reply_text("🌐 Running WHOIS lookup...")
    from services.domain import lookup_domain
    result = await lookup_domain(ctx.args[0])
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /pf — Pump.fun coin + deployer stats ─────────────
async def pumpfun_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/pf <mint address>`", parse_mode=ParseMode.MARKDOWN)
        return
    msg = await update.message.reply_text("🚀 Checking pump.fun...")
    from services.pumpfun import get_pumpfun_data
    result = await get_pumpfun_data(ctx.args[0])
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /stats — Hit rate + median return for a user ─────
async def user_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    target = update.effective_user
    if update.message.reply_to_message:
        # Reply to someone's message with /stats to see THEIR stats instead of your own
        target = update.message.reply_to_message.from_user
    msg = await update.message.reply_text("📊 Crunching stats...")
    from services.research import get_user_stats
    result = await get_user_stats(chat.id, target.id, target.username or target.first_name)
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)


# ── /autodetect — Toggle passive $ticker/CA detection ─
async def autodetect_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Autodetect only applies to group chats ser.")
        return
    from services.settings import set_autodetect, get_autodetect
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        current = await get_autodetect(chat.id)
        await update.message.reply_text(
            f"Passive $ticker/CA detection is currently *{'ON' if current else 'OFF'}*.\n"
            f"Use `/autodetect on` or `/autodetect off` to change it.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    enabled = ctx.args[0].lower() == "on"
    await set_autodetect(chat.id, enabled)
    await update.message.reply_text(f"✅ Passive detection turned **{'ON' if enabled else 'OFF'}** for this group.", parse_mode=ParseMode.MARKDOWN)


# ── /antiscam — Toggle scam message detection ────────
async def antiscam_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Antiscam only applies to group chats ser.")
        return
    from services.settings import set_antiscam, get_antiscam
    if not ctx.args or ctx.args[0].lower() not in ("on", "off"):
        current = await get_antiscam(chat.id)
        await update.message.reply_text(
            f"Scam message detection is currently *{'ON' if current else 'OFF'}*.\n"
            f"Use `/antiscam on` or `/antiscam off`.\n"
            f"⚠️ Needs admin rights (Delete Messages) to actually remove flagged messages — "
            f"it will only post a warning otherwise. It never auto-bans.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    enabled = ctx.args[0].lower() == "on"
    await set_antiscam(chat.id, enabled)
    await update.message.reply_text(
        f"✅ Scam detection turned **{'ON' if enabled else 'OFF'}** for this group.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── /eli5 /explain /fact /translate — AI reply tools ─
async def _run_reply_tool(update: Update, action: str, label: str):
    if not update.message.reply_to_message or not update.message.reply_to_message.text:
        await update.message.reply_text(f"Reply to a message with /{action} to use this.")
        return
    target_text = update.message.reply_to_message.text
    msg = await update.message.reply_text(f"{label}...")
    from services.ai import reply_tool
    result = await reply_tool(action, target_text)
    await msg.edit_text(result)


async def eli5(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _run_reply_tool(update, "eli5", "🧒 Simplifying")


async def explain(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _run_reply_tool(update, "explain", "🔍 Explaining")


async def fact_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _run_reply_tool(update, "fact", "🕵️ Fact-checking")


async def translate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _run_reply_tool(update, "translate", "🌐 Translating")


# ── /alert <token> <price> — Set a price alert ───────
async def set_alert(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text(
            "Usage: `/alert <symbol or CA> <target price>`\nExample: `/alert SOL 200`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    query = ctx.args[0].strip()
    try:
        target = float(ctx.args[1].replace("$", "").replace(",", ""))
    except ValueError:
        await update.message.reply_text("❌ That doesn't look like a valid price.")
        return

    msg = await update.message.reply_text("🔍 Setting alert...")

    pair = await fetch_token_by_address(query) if len(query) > 20 else await fetch_token_by_name(query)
    if not pair:
        await msg.edit_text("❌ Token not found ser. Check the symbol/CA and try again.")
        return

    base = pair.get("baseToken", {})
    current = float(pair.get("priceUsd") or 0)
    direction = "above" if target > current else "below"

    from services.alerts import add_alert
    chat = update.effective_chat
    user = update.effective_user
    alert_id = await add_alert(
        chat_id=chat.id, user_id=user.id, username=user.username or user.first_name,
        query=query, ca=base.get("address", query), symbol=base.get("symbol", "?"),
        target_price=target, direction=direction,
    )
    await msg.edit_text(
        f"🔔 Alert set: *${base.get('symbol', '?')}* {direction} `${target:,.8f}`\n"
        f"Current: `${current:,.8f}` | ID: `{alert_id}`\n"
        f"_I'll DM you here when it hits. `/unalert {alert_id}` to cancel._",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── /alerts — List your active alerts ────────────────
async def list_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from services.alerts import list_user_alerts
    chat = update.effective_chat
    user = update.effective_user
    alerts = await list_user_alerts(chat.id, user.id)
    if not alerts:
        await update.message.reply_text("📭 No active alerts. Set one with `/alert <token> <price>`.", parse_mode=ParseMode.MARKDOWN)
        return
    lines = ["🔔 *Your Active Alerts*\n"]
    for a in alerts:
        lines.append(f"`{a['id']}` — *${a['symbol']}* {a['direction']} `${a['target']:,.8f}`")
    lines.append("\n_Cancel with `/unalert <id>`._")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ── /unalert <id> — Cancel an alert ──────────────────
async def cancel_alert(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/unalert <id>` — get the id from `/alerts`", parse_mode=ParseMode.MARKDOWN)
        return
    from services.alerts import remove_alert
    chat = update.effective_chat
    user = update.effective_user
    ok = await remove_alert(chat.id, user.id, ctx.args[0].strip())
    if ok:
        await update.message.reply_text("✅ Alert cancelled.")
    else:
        await update.message.reply_text("❌ Couldn't find that alert id. Check `/alerts`.")


# ── /cal — Economic calendar ─────────────────────────
async def economic_calendar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📅 Loading calendar...")
    from services.calendar import get_economic_calendar
    result = await get_economic_calendar()
    await msg.edit_text(result, parse_mode=ParseMode.MARKDOWN)
