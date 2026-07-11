"""
handlers/autodetect.py — Passive $ticker / contract-address detection.

Mirrors Rick/Phanes: paste a CA or $TICKER with no command and Daemonbot replies
automatically. Syntax (checked on the whole message, not the matched token):
  - leading "."  → ignore this message entirely
  - trailing "." → compact one-line reply
  - trailing ","  → detailed reply (full /scan-style)
  - anything else → standard price reply (like /p)

To keep this from being noisy, a bare $TICKER that doesn't resolve to a real
token stays silent (someone typing "$50" or a made-up word shouldn't get a
reply). A real-looking contract address always gets a reply, even a "not
found" one, since pasting a CA is a much stronger signal of intent.
"""

import re
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.crypto import (
    fetch_token_by_address, fetch_token_by_name,
    build_price_message, build_scan_message,
)
from services.settings import get_autodetect
from services.leaderboard import log_call

EVM_CA_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
SOL_CA_RE = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")
CASHTAG_RE = re.compile(r"\$([A-Za-z]{2,10})\b")


def _classify_detail(text: str) -> str:
    t = text.strip()
    if t.endswith(","):
        return "detailed"
    if t.endswith("."):
        return "compact"
    return "default"


def _extract_candidate(text: str):
    """Returns (kind, value) for the first CA or cashtag found, or (None, None)."""
    m = EVM_CA_RE.search(text)
    if m:
        return "ca", m.group(0)
    m = SOL_CA_RE.search(text)
    if m:
        return "ca", m.group(0)
    m = CASHTAG_RE.search(text)
    if m:
        return "ticker", m.group(1)
    return None, None


async def _get_token_image(pair: dict, ca: str) -> str | None:
    """Best-effort token image URL — DexScreener's icon first (it's the
    actual token logo, not just a chain badge), falling back to pump.fun's
    own image for Solana tokens DexScreener hasn't fully indexed yet."""
    info = pair.get("info", {}) or {}
    img = info.get("imageUrl") or info.get("header")
    if img:
        return img
    if pair.get("chainId", "").lower() == "solana":
        from services.pumpfun import fetch_pumpfun_coin
        pf = await fetch_pumpfun_coin(ca)
        if pf:
            return pf.get("image_uri")
    return None


async def handle_autodetect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return
    text = message.text.strip()

    if text.startswith("."):
        return  # explicit opt-out for this message

    chat = update.effective_chat
    if not await get_autodetect(chat.id):
        return  # group has this turned off

    kind, value = _extract_candidate(text)
    if not kind:
        return

    detail = _classify_detail(text)

    if kind == "ca":
        pair = await fetch_token_by_address(value)
        if not pair:
            from services.pumpfun import get_pumpfun_fallback, fetch_pumpfun_coin
            fallback = await get_pumpfun_fallback(value)
            if fallback:
                pf = await fetch_pumpfun_coin(value)
                img_url = (pf or {}).get("image_uri")
                if img_url:
                    try:
                        await message.reply_photo(img_url, caption=fallback, parse_mode=ParseMode.MARKDOWN)
                        return
                    except Exception:
                        pass
                await message.reply_text(fallback, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
                return
            await message.reply_text(
                f"❌ `{value[:10]}...` not found on DexScreener — too new, "
                f"unlisted, or not a real token.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
    else:
        pair = await fetch_token_by_name(value)
        if not pair:
            return  # stay silent on a $word that isn't a real token — avoid noise

    if detail == "detailed":
        # Full /scan-style reply — this means the actual image card, not
        # just a longer text block. Delegate to the same pipeline /scan
        # uses so both paths stay in sync and only need fixing in one place.
        from handlers.commands import _send_scan_card
        placeholder = await message.reply_text("🧪 Scanning contract...")
        await _send_scan_card(update, ctx, placeholder, value)
        return

    if detail == "compact":
        base = pair.get("baseToken", {})
        price = float(pair.get("priceUsd") or 0)
        change = pair.get("priceChange", {}).get("h24", 0)
        reply = f"💊 *${base.get('symbol', '?')}* `${price:.8f}` ({change:+.1f}% 24h)"
    else:
        reply = build_price_message(pair)

    ca = value if kind == "ca" else pair.get("baseToken", {}).get("address", value)
    img_url = await _get_token_image(pair, ca)
    if img_url:
        try:
            await message.reply_photo(img_url, caption=reply, parse_mode=ParseMode.MARKDOWN)
            return
        except Exception:
            pass  # bad/unfetchable image URL — fall through to text-only

    await message.reply_text(reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

    # Log call to leaderboard (same as /p and /scan)
    if chat.type in ("group", "supergroup") and update.effective_user:
        user = update.effective_user
        base = pair.get("baseToken", {})
        await log_call(
            chat_id=chat.id,
            user_id=user.id,
            username=user.username or user.first_name,
            token_name=base.get("name", "?"),
            token_symbol=base.get("symbol", "?"),
            price_usd=float(pair.get("priceUsd") or 0),
            ca=base.get("address", value if kind == "ca" else ""),
        )
