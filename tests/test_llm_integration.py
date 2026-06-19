"""
Tests that exercise the LLM generate path end-to-end with a monkeypatched provider.
Covers the blind spot that let the return-type contract change silently.
"""
import asyncio
import os
import tempfile
from unittest.mock import patch, AsyncMock

import pytest

_temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DB_PATH"] = _temp_db.name
os.environ.setdefault("SECRET_KEY", "testsecret")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "testpass")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-token-not-real")

from fastapi.testclient import TestClient
from database import init_db, get_or_create_user, create_campaign, save_message


MOCK_LLM_RESPONSE = "This is a mocked LLM response for testing."


# ---------- Dashboard generate path ----------

@pytest.fixture
def client():
    from dashboard import app
    from auth import require_auth
    app.dependency_overrides[require_auth] = lambda: "admin"
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@patch("dashboard.llm_generate_async", new_callable=AsyncMock)
def test_dashboard_create_campaign_calls_llm(mock_generate, client):
    mock_generate.return_value = MOCK_LLM_RESPONSE
    async def seed():
        await init_db()
        await get_or_create_user(1, "testuser")

    asyncio.run(seed())

    r = client.post(
        "/campaign/new",
        data={"topic": "Sustainable coffee brand launch"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"].startswith("/campaign/")
    mock_generate.assert_called_once()

    campaign_id = int(r.headers["location"].split("/")[-1])
    r2 = client.get(f"/campaign/{campaign_id}")
    assert r2.status_code == 200
    assert MOCK_LLM_RESPONSE in r2.text


@patch("dashboard.llm_generate_async", new_callable=AsyncMock)
def test_dashboard_continue_campaign_calls_llm(mock_generate, client):
    mock_generate.return_value = MOCK_LLM_RESPONSE
    async def seed():
        await init_db()
        await get_or_create_user(1, "testuser")
        cid = await create_campaign(1, "Continue test")
        return cid

    cid = asyncio.run(seed())

    r = client.post(
        f"/campaign/{cid}/continue",
        data={"phase": "social_copy"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    mock_generate.assert_called_once()
    assert MOCK_LLM_RESPONSE in client.get(f"/campaign/{cid}").text


# ---------- Bot generate path ----------

@pytest.mark.asyncio
@patch("bot.llm_generate_async", new_callable=AsyncMock)
@patch("bot.get_current_campaign")
@patch("bot.save_message")
async def test_bot_social_path_uses_llm(mock_save_message, mock_get_campaign, mock_generate):
    mock_generate.return_value = MOCK_LLM_RESPONSE
    await init_db()
    mock_get_campaign.return_value = {"id": 42, "topic": "Bot test campaign"}

    from unittest.mock import MagicMock
    fake_message = MagicMock()
    fake_message.from_user.id = 901
    fake_message.answer = AsyncMock()

    from bot import cmd_social
    await cmd_social(fake_message)

    mock_generate.assert_called_once()
    mock_save_message.assert_called_once_with(42, "assistant", MOCK_LLM_RESPONSE, "social_copy")
    fake_message.answer.assert_any_await("✅ Social copy ready. Open the dashboard to schedule it.")
