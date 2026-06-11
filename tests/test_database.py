import asyncio
import os
import tempfile
import pytest
import pytest_asyncio

# Use a temp file instead of :memory: to avoid connection scoping issues
_temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DB_PATH"] = _temp_db.name

from database import (
    init_db,
    add_channel, get_channel, list_channels, remove_channel,
    create_scheduled_post, get_scheduled_post, list_scheduled_posts, update_post_status,
    record_send_analytics, get_dashboard_stats,
    create_campaign, get_or_create_user,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    await init_db()
    yield
    # cleanup not strictly needed for temp file


@pytest.mark.asyncio
async def test_add_and_get_channel():
    channel_id = await add_channel(chat_id="-100123456", name="My Channel")
    assert channel_id > 0
    ch = await get_channel(channel_id)
    assert ch["chat_id"] == "-100123456"
    assert ch["name"] == "My Channel"


@pytest.mark.asyncio
async def test_list_channels():
    await add_channel(chat_id="-100111", name="Chan A")
    await add_channel(chat_id="-100222", name="Chan B")
    channels = await list_channels()
    assert len(channels) >= 2


@pytest.mark.asyncio
async def test_remove_channel():
    channel_id = await add_channel(chat_id="-100999", name="ToDelete")
    await remove_channel(channel_id)
    ch = await get_channel(channel_id)
    assert ch is None


@pytest.mark.asyncio
async def test_create_and_get_scheduled_post():
    await get_or_create_user(1, "testuser")
    campaign_id = await create_campaign(1, "Test Campaign")
    channel_id = await add_channel(chat_id="-100123", name="Chan")
    post_id = await create_scheduled_post(
        campaign_id=campaign_id,
        channel_id=channel_id,
        content="Hello world",
        scheduled_at="2030-01-01T09:00:00",
        recurring_cron=None,
    )
    assert post_id > 0
    post = await get_scheduled_post(post_id)
    assert post["content"] == "Hello world"
    assert post["status"] == "pending"


@pytest.mark.asyncio
async def test_update_post_status():
    await get_or_create_user(2, "user2")
    campaign_id = await create_campaign(2, "Camp")
    channel_id = await add_channel(chat_id="-100777", name="X")
    post_id = await create_scheduled_post(
        campaign_id=campaign_id,
        channel_id=channel_id,
        content="msg",
        scheduled_at="2030-06-01T12:00:00",
    )
    await update_post_status(post_id, "sent", sent_at="2030-06-01T12:00:05")
    post = await get_scheduled_post(post_id)
    assert post["status"] == "sent"


@pytest.mark.asyncio
async def test_record_analytics():
    await get_or_create_user(3, "user3")
    campaign_id = await create_campaign(3, "Analytic Camp")
    channel_id = await add_channel(chat_id="-100888", name="Y")
    post_id = await create_scheduled_post(
        campaign_id=campaign_id,
        channel_id=channel_id,
        content="track me",
        scheduled_at="2030-07-01T10:00:00",
    )
    await record_send_analytics(post_id=post_id, telegram_message_id=42, status="sent")
    # No assertion — just must not throw
