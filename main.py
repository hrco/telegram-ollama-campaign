"""
CampaignOS v2 - Unified entrypoint
Runs the Telegram bot + FastAPI dashboard + APScheduler in one process.

Single startup path (no wrapper app, no duplicate init): bring up the DB, start
the scheduler bound to the live bot, re-register any posts that were pending
before a restart, then run the bot and dashboard concurrently.
"""

import asyncio
import logging
import os

import uvicorn

from bot import bot, main as bot_main
from dashboard import app as dashboard_app
from scheduler import init_scheduler, start_scheduler, stop_scheduler, reconcile_pending_posts
from database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_bot():
    await bot_main()


async def run_dashboard():
    port = int(os.getenv("DASHBOARD_PORT", "8000"))
    config = uvicorn.Config(dashboard_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await init_db()
    init_scheduler(bot)
    await start_scheduler()
    reconciled = await reconcile_pending_posts()
    logger.info(f"CampaignOS v2 started (bot + dashboard + scheduler); {reconciled} post(s) reconciled")

    try:
        await asyncio.gather(run_bot(), run_dashboard())
    finally:
        await stop_scheduler()
        logger.info("CampaignOS v2 shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
