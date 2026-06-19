"""
Campaign Bot v3 - Production Ready
Professional marketing campaign assistant with proper error handling
"""

import os
import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from dotenv import load_dotenv
from llm import generate_async as llm_generate_async

from states import CampaignCreation
from campaign_protocol import get_phase_prompt
from database import (
    init_db, get_or_create_user, create_campaign, get_current_campaign,
    save_message, get_campaign_messages, list_user_campaigns
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv(override=False)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN is missing!")
    sys.exit(1)

if ADMIN_TELEGRAM_ID:
    ADMIN_TELEGRAM_ID = ADMIN_TELEGRAM_ID.strip()
    if not ADMIN_TELEGRAM_ID.isdigit():
        logger.error(f"ADMIN_TELEGRAM_ID must be a numeric user ID, got: {ADMIN_TELEGRAM_ID!r}")
        sys.exit(1)

bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

_notified_users = set()

@router.message.outer_middleware
async def admin_only_middleware(handler, event: Message, data):
    if not ADMIN_TELEGRAM_ID:
        return await handler(event, data)
    if not event.from_user:
        return await handler(event, data)
    user_id = str(event.from_user.id)
    if user_id == ADMIN_TELEGRAM_ID:
        return await handler(event, data)
    if user_id not in _notified_users:
        _notified_users.add(user_id)
        await event.answer("🔒 This bot is private. Only the admin can use it.")


# ==================== ERROR HANDLER ====================
@dp.errors()
async def error_handler(event, exception):
    if isinstance(exception, TelegramRetryAfter):
        logger.warning(f"Flood control: retry after {exception.retry_after}s")
        return True  # Let aiogram handle retry

    if isinstance(exception, TelegramAPIError):
        logger.error(f"Telegram API error: {exception}")
        if hasattr(event, 'message'):
            await event.message.answer("⚠️ Telegram is having issues. Please try again in a moment.")
        return True

    logger.exception(f"Unhandled error: {exception}")
    if hasattr(event, 'message'):
        await event.message.answer("❌ Something went wrong. Our team has been notified.")
    return True


# ==================== COMMANDS ====================
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """
    Send a welcome message with available commands and dashboard information.
    """
    await state.clear()
    await get_or_create_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "🧠 <b>CampaignOS</b> — Marketing OS powered by local AI\n\n"
        "Plan campaigns, generate copy, schedule, and broadcast to your Telegram channels. "
        "All self-hosted, all free.\n\n"
        "<b>Commands</b>\n"
        "• /new — Start a new campaign\n"
        "• /campaigns — View your campaigns\n"
        "• /social — Generate social copy for current campaign\n"
        "• /channels — List connected channels\n"
        "• /resume — Resume latest campaign\n"
        "• /help — Full guide\n\n"
        "<b>Dashboard</b> — open http://localhost:8001 in your browser"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Send the help message explaining bot usage, available commands, and dashboard features.
    """
    await message.answer(
        "📋 <b>CampaignOS — How it works</b>\n\n"
        "This bot + dashboard helps you plan, write, schedule, and broadcast "
        "marketing campaigns using a local AI.\n\n"
        "<b>Getting started</b>\n"
        "1. /new — Start a campaign (name a topic)\n"
        "2. Reply <b>yes</b> — Bot researches your topic with AI\n"
        "3. Open the dashboard at http://localhost:8001 — view, continue, schedule\n\n"
        "<b>Commands</b>\n"
        "• /new — Create a new campaign\n"
        "• /campaigns — List your campaigns\n"
        "• /resume — Show latest campaign progress\n"
        "• /social — Generate social copy for current campaign\n"
        "• /channels — List connected Telegram channels\n"
        "• /help — This message\n\n"
        "<b>Dashboard</b>\n"
        "Open http://localhost:8001 in your browser. From there you can:\n"
        "• Start/continue campaigns\n"
        "• Register channels the bot is admin of\n"
        "• Schedule posts (one-off or recurring cron)\n"
        "• View broadcast history\n"
        "• Change password and LLM provider in Settings\n\n"
        "Need more? Open an issue at github.com/hrco/telegram-ollama-campaign"
    )


@router.message(Command("new"))
async def cmd_new_campaign(message: Message, state: FSMContext):
    """
    Initiate a new campaign creation flow and request the campaign topic from the user.
    """
    await state.set_state(CampaignCreation.waiting_for_topic)
    await message.answer("What is the <b>topic</b> of your campaign?\n\nExample: <i>Launch of sustainable coffee brand</i>")


@router.message(CampaignCreation.waiting_for_topic, F.text, ~F.text.startswith("/"))
async def process_topic(message: Message, state: FSMContext):
    """
    Store the campaign topic and request confirmation to start research.
    
    Saves the topic to the FSM context and prompts the user to confirm they want to begin the research phase.
    """
    topic = message.text.strip()
    await state.update_data(topic=topic)
    await state.set_state(CampaignCreation.waiting_for_confirmation)

    await message.answer(
        f"✅ Topic saved: <b>{topic}</b>\n\n"
        "Would you like to start the <b>Research Phase</b> now?\n"
        "Reply with <b>yes</b> or <b>no</b>."
    )


@router.message(CampaignCreation.waiting_for_confirmation, F.text, ~F.text.startswith("/"))
async def process_confirmation(message: Message, state: FSMContext):
    """
    Processes user confirmation to create a marketing campaign and run the initial research phase.
    
    If the user does not confirm with "yes" or "y", campaign creation is cancelled. If confirmed,
    a new campaign is created for the user, the AI-driven research phase is executed, and the generated
    research content is saved and sent to the user. Clears the FSM state upon completion or cancellation.
    """
    if message.text.lower() not in ["yes", "y"]:
        await state.clear()
        await message.answer("Campaign creation cancelled.")
        return

    data = await state.get_data()
    topic = data.get("topic")

    user_id = message.from_user.id
    await get_or_create_user(user_id, message.from_user.username)
    campaign_id = await create_campaign(user_id, topic)

    await message.answer(f"🚀 Starting campaign <b>#{campaign_id}</b>...\nRunning Research Phase...")

    try:
        prompt = get_phase_prompt("research", topic=topic, platform="multi")
        content = await llm_generate_async(prompt)

        await save_message(campaign_id, "assistant", content, "research")
        await message.answer(content[:3800])
        await message.answer("✅ Research phase completed. Use /campaigns to continue.")

    except Exception as e:
        logger.error(f"Error during research phase: {e}")
        await message.answer("❌ Failed to run research phase. Please try again later.")

    await state.clear()


@router.message(Command("campaigns"))
async def cmd_list_campaigns(message: Message):
    campaigns = await list_user_campaigns(message.from_user.id)
    if not campaigns:
        await message.answer("You have no campaigns yet. Use /new to create one.")
        return

    text = "<b>Your Campaigns:</b>\n\n"
    for c in campaigns[:10]:
        text += f"• #{c['id']} — {c['topic'][:60]}\n"
    await message.answer(text)


@router.message(Command("resume"))
async def cmd_resume(message: Message):
    campaign = await get_current_campaign(message.from_user.id)
    if not campaign:
        await message.answer("No active campaign found.")
        return

    messages = await get_campaign_messages(campaign['id'], limit=3)
    await message.answer(
        f"📌 <b>Campaign #{campaign['id']}</b>\n"
        f"Topic: {campaign['topic']}\n\n"
        f"Last activity: {messages[-1]['phase'] if messages else 'None'}"
    )


@router.message(Command("social"))
async def cmd_social(message: Message):
    """
    Generates social media copy for the user's active campaign.
    
    Notifies the user if no active campaign is found.
    """
    campaign = await get_current_campaign(message.from_user.id)
    if not campaign:
        await message.answer("No active campaign. Use /new to start one.")
        return

    await message.answer(f"🎨 Generating social copy for campaign <b>#{campaign['id']}</b>...")

    try:
        prompt = get_phase_prompt("social_copy", topic=campaign["topic"], tone="engaging and direct")
        content = await llm_generate_async(prompt)
        await save_message(campaign["id"], "assistant", content, "social_copy")

        if len(content) > 3800:
            await message.answer(content[:3800])
            await message.answer(content[3800:7600])
        else:
            await message.answer(content)
        await message.answer("✅ Social copy ready. Open the dashboard to schedule it.")
    except Exception as e:
        logger.error(f"Error generating social copy: {e}")
        await message.answer("❌ Failed to generate social copy. Check your configured LLM provider and connectivity.")


@router.message(Command("channels"))
async def cmd_channels(message: Message):
    from database import list_channels
    channels = await list_channels()
    if not channels:
        await message.answer(
            "No channels connected yet.\n"
            "Add the bot as admin to a channel, then register it in the dashboard under Channels."
        )
        return
    text = "<b>Connected Channels:</b>\n\n"
    for ch in channels:
        text += f"• {ch['name']} (<code>{ch['chat_id']}</code>)\n"
    await message.answer(text)


async def main():
    await init_db()
    logger.info("Campaign Bot v3 starting...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")