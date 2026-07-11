"""
handlers/fixlinks.py — Intercept social media links in group messages.
Runs on every group text message before the AI chat handler.
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from services.fixlinks import process_message_for_links


async def handle_fix_links(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return

    text = message.text.strip()

    # Only process if message contains a URL
    if "http" not in text.lower():
        return

    result = await process_message_for_links(text)
    if result:
        await message.reply_text(
            result,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=False,
        )
