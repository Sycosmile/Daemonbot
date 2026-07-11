"""
Daemonbot — Multi-chain AI crypto bot
Inspired by RickBurpBot + Phanes.

Built by MR SYCO (@Sycosmile) — 3MTT Cybersecurity fellow, bug bounty hunter.
GitHub: https://github.com/Sycosmile
"""

import os
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
)
from handlers.commands import (
    # Core
    start, help_command,
    # Price & Scan
    price, scan, compact_scan,
    # Charts & Trending
    chart, trending,
    # Leaderboards
    leaderboard, group_ath,
    # Holders & Maps
    top_holders, bubblemap,
    # Phanes features
    narrative, x_check, pnl_image, gpnl, first_caller,
    # Rick features
    lore, dev, soc, gas, groupburp,
    best, worst, meta,
    # Unique Daemonbot features
    rug_score, security_scan,
    conviction_call, my_calls, conviction_lb,
    summary,
    # New: research tools + stats + passive detection toggle
    github_check, domain_check, pumpfun_check, user_stats, autodetect_toggle,
    # New: scam detection toggle, AI reply tools, alerts, calendar
    antiscam_toggle, eli5, explain, fact_check, translate,
    set_alert, list_alerts, cancel_alert, economic_calendar,
)
from handlers.chat import handle_message
from handlers.fixlinks import handle_fix_links
from handlers.message_store import store_messages
from handlers.autodetect import handle_autodetect
from handlers.scammer_detection import handle_scam_check
from services.alerts import check_due_alerts
from config import BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def _alerts_job(ctx):
    """JobQueue callback wrapper — see services.alerts.check_due_alerts."""
    await check_due_alerts(ctx.bot)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Core ──────────────────────────────────────────
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("help",        help_command))

    # ── Price & Scan ──────────────────────────────────
    app.add_handler(CommandHandler("p",           price))
    app.add_handler(CommandHandler("price",       price))
    app.add_handler(CommandHandler("scan",        scan))
    app.add_handler(CommandHandler("ca",          scan))
    app.add_handler(CommandHandler("z",           compact_scan))

    # ── Charts & Trending ─────────────────────────────
    app.add_handler(CommandHandler("chart",       chart))
    app.add_handler(CommandHandler("c",           chart))
    app.add_handler(CommandHandler("trending",    trending))

    # ── Leaderboards ──────────────────────────────────
    app.add_handler(CommandHandler("lb",          leaderboard))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("ga",          group_ath))
    app.add_handler(CommandHandler("clb",         conviction_lb))

    # ── Holders & Maps ────────────────────────────────
    app.add_handler(CommandHandler("th",          top_holders))
    app.add_handler(CommandHandler("bm",          bubblemap))

    # ── Phanes features ───────────────────────────────
    app.add_handler(CommandHandler("nar",         narrative))
    app.add_handler(CommandHandler("x",           x_check))
    app.add_handler(CommandHandler("pnl",         pnl_image))
    app.add_handler(CommandHandler("gpnl",        gpnl))
    app.add_handler(CommandHandler("fc",          first_caller))

    # ── Rick features ─────────────────────────────────
    app.add_handler(CommandHandler("lore",        lore))
    app.add_handler(CommandHandler("dev",         dev))
    app.add_handler(CommandHandler("soc",         soc))
    app.add_handler(CommandHandler("gas",         gas))
    app.add_handler(CommandHandler("groupburp",   groupburp))
    app.add_handler(CommandHandler("best",        best))
    app.add_handler(CommandHandler("worst",       worst))
    app.add_handler(CommandHandler("meta",        meta))

    # ── Unique Daemonbot features ───────────────────────
    app.add_handler(CommandHandler("rug",         rug_score))
    app.add_handler(CommandHandler("sec",         security_scan))
    app.add_handler(CommandHandler("call",        conviction_call))
    app.add_handler(CommandHandler("calls",       my_calls))
    app.add_handler(CommandHandler("summary",     summary))

    # ── Research tools (new) ──────────────────────────
    app.add_handler(CommandHandler("gh",          github_check))
    app.add_handler(CommandHandler("do",          domain_check))
    app.add_handler(CommandHandler("pf",          pumpfun_check))
    app.add_handler(CommandHandler("stats",       user_stats))
    app.add_handler(CommandHandler("autodetect",  autodetect_toggle))
    app.add_handler(CommandHandler("antiscam",    antiscam_toggle))
    app.add_handler(CommandHandler("cal",         economic_calendar))

    # ── AI reply tools (new) ──────────────────────────
    app.add_handler(CommandHandler("eli5",        eli5))
    app.add_handler(CommandHandler("explain",     explain))
    app.add_handler(CommandHandler("fact",        fact_check))
    app.add_handler(CommandHandler("translate",   translate))

    # ── Price alerts (new) ────────────────────────────
    app.add_handler(CommandHandler("alert",       set_alert))
    app.add_handler(CommandHandler("alerts",      list_alerts))
    app.add_handler(CommandHandler("unalert",     cancel_alert))

    # ── Message handlers ───────────────────────────────
    # IMPORTANT: each of these gets its own `group=`. python-telegram-bot only
    # runs the FIRST matching handler within a given group, then moves on —
    # it does NOT fall through to the next handler in the same group. Without
    # distinct groups here, store_messages (which matches every non-command
    # group text message) would always win, and handle_fix_links / handle_message
    # would silently never fire in groups. Lower group number = runs first.
    # 1. Store messages for /summary (silent)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        store_messages
    ), group=0)
    # 2. Fix social links
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        handle_fix_links
    ), group=1)
    # 3. AI chat (mention / reply / DM)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ), group=2)
    # 4. Passive $ticker/CA auto-detection (own group — independent of AI chat)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_autodetect
    ), group=3)
    # 5. Scammer detection (own group — off by default, see /antiscam)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        handle_scam_check
    ), group=4)

    # ── Background jobs ────────────────────────────────
    # Checks all active price alerts every 60s. Needs the [job-queue] extra
    # (APScheduler) — see requirements.txt.
    app.job_queue.run_repeating(
        _alerts_job,
        interval=60,
        first=15,
        name="check_price_alerts",
    )

    logger.info("⚡ Daemonbot is alive — built by MR SYCO (@Sycosmile)")

    # ── Webhook (Render) vs polling (local/Kali) ───────────────────────
    # Render auto-sets RENDER_EXTERNAL_URL and PORT for every web service —
    # we key off RENDER_EXTERNAL_URL's presence so nothing needs touching
    # for local dev. The webhook path uses the bot token as an unguessable
    # suffix (standard PTB pattern) so randos can't POST fake updates in.
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    port = int(os.getenv("PORT", 8443))

    if render_url:
        webhook_path = BOT_TOKEN
        webhook_url = f"{render_url}/{webhook_path}"
        logger.info(f"Starting in WEBHOOK mode → {webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,
            webhook_url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logger.info("Starting in POLLING mode (local dev)")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
