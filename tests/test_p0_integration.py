"""
P0 end-to-end wiring tests: scheduler reconciliation + dashboard schedule/detail
routes. These cover the gaps that left the app non-functional end-to-end, without
requiring Ollama or a live Telegram connection.
"""
import asyncio
import os
import tempfile

import pytest

# Temp file DB, set before importing app modules (they read DB_PATH at import).
_temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DB_PATH"] = _temp_db.name
os.environ.setdefault("SECRET_KEY", "testsecret")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "testpass")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-token-not-real")

from fastapi.testclient import TestClient

import scheduler as sched_module
from scheduler import CampaignScheduler, reconcile_pending_posts
from database import (
    init_db, create_campaign, get_or_create_user, add_channel,
    create_scheduled_post, get_scheduled_post,
)


# ---------- scheduler reconciliation (P0.5) ----------

@pytest.mark.asyncio
async def test_reconcile_registers_pending_posts():
    await init_db()
    await get_or_create_user(900, "reconcile")
    cid = await create_campaign(900, "Reconcile camp")
    ch = await add_channel(chat_id="-100rec", name="Rec")
    # one future one-off, one past-due one-off, one recurring
    pid_future = await create_scheduled_post(cid, ch, "future", "2999-01-01T09:00:00")
    pid_past = await create_scheduled_post(cid, ch, "past", "2000-01-01T09:00:00")
    pid_cron = await create_scheduled_post(cid, ch, "cron", "2999-01-01T09:00:00", recurring_cron="0 9 * * *")

    sched_module.init_scheduler(bot=None)
    sched_module.campaign_scheduler.start()
    try:
        # Other test modules share this DB file (DB_PATH is bound once at import),
        # so assert on our specific jobs rather than a global count.
        count = await reconcile_pending_posts()
        assert count >= 3
        job_ids = {j["job_id"] for j in sched_module.campaign_scheduler.get_upcoming_jobs(limit=200)}
        assert f"post_{pid_future}" in job_ids
        assert f"post_{pid_past}" in job_ids      # past-due nudged to fire shortly
        assert f"recurring_{pid_cron}" in job_ids
    finally:
        sched_module.campaign_scheduler.stop()
        sched_module.campaign_scheduler = None


# ---------- dashboard routes (P0.3 + P0.4) ----------

@pytest.fixture
def client():
    from dashboard import app
    from auth import require_auth
    app.dependency_overrides[require_auth] = lambda: "admin"
    with TestClient(app) as c:  # lifespan runs init_db
        yield c
    app.dependency_overrides.clear()


def test_campaign_detail_route_renders(client):
    async def seed():
        await get_or_create_user(901, "detail")
        cid = await create_campaign(901, "Detail camp")
        from database import save_message
        await save_message(cid, "assistant", "hello <world>", "research")
        return cid
    cid = asyncio.run(seed())

    r = client.get(f"/campaign/{cid}")
    assert r.status_code == 200
    # default escaping protects the angle brackets (no raw <world> tag)
    assert "&lt;world&gt;" in r.text
    assert "<world>" not in r.text


def test_schedule_new_creates_post_then_cancel(client):
    async def seed():
        await get_or_create_user(902, "sched")
        cid = await create_campaign(902, "Sched camp")
        ch = await add_channel(chat_id="-100sched", name="SchedChan")
        return cid, ch
    cid, ch = asyncio.run(seed())

    r = client.post(
        "/schedule/new",
        data={
            "campaign_id": cid, "channel_id": ch,
            "content": "Broadcast me", "scheduled_at": "2999-01-01T09:00:00",
            "recurring_cron": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/schedule"

    # find the post we just made (id may vary across test order) — scan
    async def find():
        from database import list_scheduled_posts
        posts = await list_scheduled_posts(limit=100)
        return [p for p in posts if p["content"] == "Broadcast me"]
    matches = asyncio.run(find())
    assert matches, "scheduled post was not persisted"
    pid = matches[0]["id"]

    r2 = client.post(f"/schedule/{pid}/cancel", follow_redirects=False)
    assert r2.status_code == 302
    cancelled = asyncio.run(get_scheduled_post(pid))
    assert cancelled["status"] == "cancelled"
