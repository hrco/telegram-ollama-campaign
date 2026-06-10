import asyncio
import logging
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError

logger = logging.getLogger(__name__)

MAX_MESSAGE_LEN = 4096
SEND_DELAY_SECONDS = 3


def _split_message(text: str) -> list[str]:
    if len(text) <= MAX_MESSAGE_LEN:
        return [text]
    parts = []
    while text:
        parts.append(text[:MAX_MESSAGE_LEN])
        text = text[MAX_MESSAGE_LEN:]
    return parts


async def send_to_channel(bot: Bot, chat_id: str, content: str) -> Optional[int]:
    parts = _split_message(content)
    last_message_id = None
    for part in parts:
        result = await bot.send_message(chat_id=chat_id, text=part, parse_mode="HTML")
        last_message_id = result.message_id
        if len(parts) > 1:
            await asyncio.sleep(1)
    return last_message_id


async def send_with_retry(bot: Bot, chat_id: str, content: str, retries: int = 3) -> Optional[int]:
    for attempt in range(retries):
        try:
            return await send_to_channel(bot, chat_id, content)
        except TelegramRetryAfter as e:
            wait = e.retry_after
            logger.warning(f"Flood control on {chat_id}: waiting {wait}s (attempt {attempt+1}/{retries})")
            await asyncio.sleep(wait)
        except TelegramAPIError as e:
            logger.error(f"TelegramAPIError sending to {chat_id}: {e}")
            if attempt == retries - 1:
                raise
            await asyncio.sleep(2)
    return None


async def broadcast_campaign(bot: Bot, campaign_id: int, channel_ids: list, content: str) -> list:
    results = []
    for channel_id in channel_ids:
        try:
            msg_id = await send_with_retry(bot, str(channel_id), content)
            results.append({"channel_id": channel_id, "message_id": msg_id, "status": "sent"})
        except Exception as e:
            results.append({"channel_id": channel_id, "message_id": None, "status": "failed", "error": str(e)})
        await asyncio.sleep(SEND_DELAY_SECONDS)
    return results