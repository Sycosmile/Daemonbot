"""
handlers/scammer_detection.py — Hooks scam detection into group messages.

Off by default per-group (/antiscam on to enable). When it fires: deletes the
message and posts a warning naming the user. Does NOT ban — see the note in
services/scammer_detection.py for why that's a deliberate v1 scope decision.

Requires the bot to have "Delete Messages" admin rights in the group, or the
delete call below will fail silently (caught and logged, not crashed).
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.settings import get_antiscam
from services.scammer_detection import check_message

logger = logging.getLogger(__name__)


async def handle_scam_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    if not message or not message.text or chat.type not in ("group", "supergroup"):
        return

    if not await get_antiscam(chat.id):
        return

    result = await check_message(message.text)
    if not result["is_scam"]:
        return

    user = update.effective_user
    uname = f"@{user.username}" if user.username else user.first_name

    try:
        await message.delete()
        deleted = True
    except Exception as e:
        logger.warning(f"Could not delete flagged message in {chat.id}: {e}")
        deleted = False

    note = "Deleted a" if deleted else "Flagged a (couldn't delete — give me admin rights)"
    await ctx.bot.send_message(
        chat_id=chat.id,
        text=(
            f"🚨 *{note} likely scam message from {uname}*\n"
            f"Confidence: `{result['confidence']}%`\n"
            f"This is a heuristic flag, not a guarantee — admins, please verify "
            f"before taking further action."
        ),
        parse_mode="Markdown",
    )
