import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def make_bot(message_id=101, raise_flood=False):
    bot = MagicMock()
    if raise_flood:
        from aiogram.exceptions import TelegramRetryAfter
        bot.send_message = AsyncMock(side_effect=TelegramRetryAfter(method=MagicMock(), message="Flood", retry_after=1))
    else:
        result = MagicMock()
        result.message_id = message_id
        bot.send_message = AsyncMock(return_value=result)
    return bot


@pytest.mark.asyncio
async def test_send_to_channel_success():
    from broadcaster import send_to_channel
    bot = make_bot(message_id=42)
    msg_id = await send_to_channel(bot, "-100123456", "Hello channel!")
    assert msg_id == 42
    bot.send_message.assert_called_once_with(
        chat_id="-100123456", text="Hello channel!", parse_mode="HTML"
    )


@pytest.mark.asyncio
async def test_send_long_message_splits():
    from broadcaster import send_to_channel
    bot = make_bot(message_id=1)
    long_text = "x" * 5000
    await send_to_channel(bot, "-100123", long_text)
    assert bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_send_with_retry_success_after_flood():
    from broadcaster import send_with_retry
    from aiogram.exceptions import TelegramRetryAfter
    bot = MagicMock()
    result = MagicMock()
    result.message_id = 99
    bot.send_message = AsyncMock(
        side_effect=[
            TelegramRetryAfter(method=MagicMock(), message="Flood control", retry_after=0),
            result
        ]
    )
    msg_id = await send_with_retry(bot, "-100x", "msg", retries=3)
    assert msg_id == 99
