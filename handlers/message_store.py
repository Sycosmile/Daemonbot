"""
handlers/message_store.py — Silently stores group messages for /summary
"""

from telegram import Update
from telegram.ext import ContextTypes
from services.summary import store_message


async def store_messages(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Silently store every group message. No response."""
    message = update.effective_message
    user    = update.effective_user
    if not message or not message.text or not user:
        return
    username = user.username or user.first_name or "anon"
    store_message(update.effective_chat.id, username, message.text)
