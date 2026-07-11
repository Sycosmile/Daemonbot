"""
handlers/chat.py — Handle free-text messages for AI conversation.

Bot responds when:
  - Any message in a private chat
  - Mentioned by @username anywhere in a group message
  - The message OPENS by addressing the bot by name (e.g. "Daemon, ...",
    "Daemonbot what's the price of...") — matched as a whole word, so
    something like "Daemonology" does NOT accidentally trigger a reply
  - Someone replies directly to the bot's message
"""

import re
import string

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.ai import chat
import config

# Hardcoded alias in addition to config.BOT_NAME / the live @username —
# "Daemon" on its own (without the "bot" suffix) should trigger a reply too.
EXTRA_TRIGGER_NAMES = {"daemon"}

_FIRST_WORD_RE = re.compile(r"^(\S+)")


def _resolve_trigger(
    text: str,
    chat_type: str,
    bot_user: str | None,
    is_reply_to_bot: bool,
) -> tuple[bool, str]:
    """Decide whether to respond, and return (should_respond, cleaned_text).

    Pure function — no Telegram objects — so it's unit-testable on its own
    (see tests/test_chat.py).
    """
    if chat_type == "private":
        return True, text

    if chat_type not in ("group", "supergroup"):
        return False, text  # e.g. "channel" — never auto-respond there

    bot_user_lower = bot_user.lower() if bot_user else ""
    trigger_names = {n for n in {config.BOT_NAME.lower(), bot_user_lower} | EXTRA_TRIGGER_NAMES if n}

    # 1) @mentioned anywhere in the message
    if bot_user:
        mention_re = re.compile(rf"@{re.escape(bot_user)}", re.IGNORECASE)
        if mention_re.search(text):
            return True, mention_re.sub("", text).strip()

    # 2) Message opens by addressing the bot by name (whole first word only,
    #    so "syco" can't match inside "sycophant")
    first_word_match = _FIRST_WORD_RE.match(text)
    if first_word_match:
        raw_first_word = first_word_match.group(1)
        if raw_first_word.strip(string.punctuation).lower() in trigger_names:
            cleaned = text[first_word_match.end():].lstrip(string.punctuation + " ")
            return True, cleaned.strip()

    # 3) Direct reply to the bot's own message
    if is_reply_to_bot:
        return True, text

    return False, text


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return

    bot_user = ctx.bot.username  # e.g. "Daemonbot"
    is_reply_to_bot = bool(
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.username == bot_user
    )

    should_respond, text = _resolve_trigger(
        text=message.text.strip(),
        chat_type=update.effective_chat.type,
        bot_user=bot_user,
        is_reply_to_bot=is_reply_to_bot,
    )

    if not should_respond or not text:
        return

    # Show typing indicator
    await ctx.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    reply = await chat(
        chat_id=update.effective_chat.id,
        user_message=text,
    )

    # LLM output can contain stray/unbalanced Markdown (e.g. a lone "_" or
    # "*") that Telegram's legacy Markdown parser rejects outright. Fall back
    # to plain text rather than silently dropping the reply.
    try:
        await message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        await message.reply_text(reply)
