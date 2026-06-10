# CampaignOS v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade CampaignOS from a bare-bones proof-of-concept into a production-ready self-hosted Telegram marketing OS with auth, a scheduler, a broadcaster, and a beautiful mobile-first dashboard.

**Architecture:** Single Python process runs the aiogram Telegram bot and a FastAPI dashboard concurrently via `asyncio.gather`. APScheduler (in-process) fires scheduled broadcasts. SQLite stores everything — 3 new tables added to existing schema.

**Tech Stack:** Python 3.10+, aiogram 3.x, FastAPI, aiosqlite, APScheduler 3.x, PyJWT, bcrypt, Tailwind CSS v3 (CDN), Alpine.js v3 (CDN), Jinja2, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-06-10-campaignos-v2-design.md`

---

## File Map

| Path | Action | Responsibility |
|------|--------|---------------|
| `main.py` | CREATE | Single entrypoint — runs bot + dashboard + scheduler together |
| `auth.py` | CREATE | JWT token creation/verification, password hashing, `require_auth` dependency |
| `broadcaster.py` | CREATE | Send messages to Telegram channels, rate-limit, retry |
| `scheduler.py` | CREATE | APScheduler wrapper — schedule/cancel/list jobs, execute broadcasts |
| `database.py` | MODIFY | Add `channels`, `scheduled_posts`, `send_analytics` tables and CRUD |
| `campaign_protocol.py` | MODIFY | Add `social_copy` phase |
| `bot.py` | MODIFY | Add `/social`, `/channels` commands; wire in scheduler |
| `dashboard.py` | MODIFY | Add auth dependency, `/login`, `/logout`, `/channels`, `/schedule` routes |
| `templates/base.html` | CREATE | Shared layout: Tailwind + Alpine, mobile bottom nav, desktop sidebar |
| `templates/login.html` | CREATE | Login form page |
| `templates/dashboard.html` | REPLACE | Stat cards + upcoming schedule + recent campaigns |
| `templates/campaigns.html` | REPLACE | Filterable campaign cards |
| `templates/campaign_detail.html` | REPLACE | Phase tabs + schedule-post section |
| `templates/channels.html` | CREATE | Channel list + add/remove |
| `templates/schedule.html` | CREATE | Upcoming posts table + cancel |
| `requirements.txt` | MODIFY | Add apscheduler, PyJWT, bcrypt, python-multipart |
| `.env.example` | MODIFY | Add ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY |
| `Makefile` | MODIFY | Add `make all` target |
| `tests/test_auth.py` | CREATE | Auth unit tests |
| `tests/test_broadcaster.py` | CREATE | Broadcaster unit tests |
| `tests/test_scheduler.py` | CREATE | Scheduler unit tests |
| `tests/test_database.py` | CREATE | New DB table CRUD tests |

---

## Task 1: Update Dependencies and DB Schema

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1.1: Update requirements.txt**

Replace the file content entirely:

```
aiogram>=3.4
aiosqlite>=0.20
fastapi>=0.110
uvicorn>=0.27
jinja2>=3.1
python-dotenv>=1.0
ollama>=0.1
pydantic>=2.0
apscheduler>=3.10
PyJWT>=2.8
bcrypt>=4.1
python-multipart>=0.0.9
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 1.2: Update .env.example**

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
OLLAMA_MODEL=llama3.1:8b
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme
SECRET_KEY=generate-with-python-secrets-token-hex-32
```

- [ ] **Step 1.3: Write failing DB tests**

Create `tests/__init__.py` (empty).

Create `tests/test_database.py`:

```python
import asyncio
import os
import pytest
import pytest_asyncio

os.environ["DB_PATH"] = ":memory:"

from database import (
    init_db,
    add_channel, get_channel, list_channels, remove_channel,
    create_scheduled_post, get_scheduled_post, list_scheduled_posts, update_post_status,
    record_send_analytics,
)


@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db():
    await init_db()


@pytest.mark.asyncio
async def test_add_and_get_channel(db):
    channel_id = await add_channel(chat_id="-100123456", name="My Channel")
    assert channel_id > 0
    ch = await get_channel(channel_id)
    assert ch["chat_id"] == "-100123456"
    assert ch["name"] == "My Channel"


@pytest.mark.asyncio
async def test_list_channels(db):
    await add_channel(chat_id="-100111", name="Chan A")
    await add_channel(chat_id="-100222", name="Chan B")
    channels = await list_channels()
    assert len(channels) >= 2


@pytest.mark.asyncio
async def test_remove_channel(db):
    channel_id = await add_channel(chat_id="-100999", name="ToDelete")
    await remove_channel(channel_id)
    ch = await get_channel(channel_id)
    assert ch is None


@pytest.mark.asyncio
async def test_create_and_get_scheduled_post(db):
    from database import init_db, create_campaign, get_or_create_user
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
async def test_update_post_status(db):
    from database import create_campaign, get_or_create_user
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
async def test_record_analytics(db):
    from database import create_campaign, get_or_create_user
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
    # No assertion on return value — just must not throw
```

- [ ] **Step 1.4: Run tests — expect failure**

```bash
cd /home/supremeleader/mylab/telegram-ollama-campaign
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/test_database.py -v
```

Expected: ImportError — new functions don't exist yet.

- [ ] **Step 1.5: Extend database.py with new tables and functions**

Add to the end of `database.py` (do NOT remove existing code):

```python
import os
DB_PATH = os.getenv("DB_PATH", "campaigns.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                current_campaign_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                topic TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                role TEXT,
                content TEXT,
                phase TEXT,
                timestamp TEXT,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                added_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                recurring_cron TEXT,
                status TEXT DEFAULT 'pending',
                sent_at TEXT,
                error TEXT,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY(channel_id) REFERENCES channels(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS send_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scheduled_post_id INTEGER NOT NULL,
                telegram_message_id INTEGER,
                sent_at TEXT,
                status TEXT,
                FOREIGN KEY(scheduled_post_id) REFERENCES scheduled_posts(id)
            )
        """)
        await db.commit()


# ==================== CHANNEL CRUD ====================

async def add_channel(chat_id: str, name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        cursor = await db.execute(
            "INSERT OR IGNORE INTO channels (chat_id, name, added_at) VALUES (?, ?, ?)",
            (chat_id, name, now)
        )
        await db.commit()
        if cursor.lastrowid:
            return cursor.lastrowid
        cursor2 = await db.execute("SELECT id FROM channels WHERE chat_id = ?", (chat_id,))
        row = await cursor2.fetchone()
        return row[0]


async def get_channel(channel_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, chat_id, name, added_at FROM channels WHERE id = ?", (channel_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {"id": row[0], "chat_id": row[1], "name": row[2], "added_at": row[3]}
        return None


async def list_channels() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, chat_id, name, added_at FROM channels ORDER BY added_at DESC")
        rows = await cursor.fetchall()
        return [{"id": r[0], "chat_id": r[1], "name": r[2], "added_at": r[3]} for r in rows]


async def remove_channel(channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        await db.commit()


# ==================== SCHEDULED POSTS CRUD ====================

async def create_scheduled_post(
    campaign_id: int,
    channel_id: int,
    content: str,
    scheduled_at: str,
    recurring_cron: Optional[str] = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO scheduled_posts
               (campaign_id, channel_id, content, scheduled_at, recurring_cron)
               VALUES (?, ?, ?, ?, ?)""",
            (campaign_id, channel_id, content, scheduled_at, recurring_cron)
        )
        await db.commit()
        return cursor.lastrowid


async def get_scheduled_post(post_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, campaign_id, channel_id, content, scheduled_at,
                      recurring_cron, status, sent_at, error
               FROM scheduled_posts WHERE id = ?""",
            (post_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0], "campaign_id": row[1], "channel_id": row[2],
                "content": row[3], "scheduled_at": row[4], "recurring_cron": row[5],
                "status": row[6], "sent_at": row[7], "error": row[8],
            }
        return None


async def list_scheduled_posts(status: Optional[str] = None, limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        if status:
            cursor = await db.execute(
                """SELECT sp.id, sp.campaign_id, c.topic, ch.name, sp.scheduled_at,
                          sp.status, sp.content
                   FROM scheduled_posts sp
                   JOIN campaigns c ON c.id = sp.campaign_id
                   JOIN channels ch ON ch.id = sp.channel_id
                   WHERE sp.status = ?
                   ORDER BY sp.scheduled_at ASC LIMIT ?""",
                (status, limit)
            )
        else:
            cursor = await db.execute(
                """SELECT sp.id, sp.campaign_id, c.topic, ch.name, sp.scheduled_at,
                          sp.status, sp.content
                   FROM scheduled_posts sp
                   JOIN campaigns c ON c.id = sp.campaign_id
                   JOIN channels ch ON ch.id = sp.channel_id
                   ORDER BY sp.scheduled_at ASC LIMIT ?""",
                (limit,)
            )
        rows = await cursor.fetchall()
        return [
            {"id": r[0], "campaign_id": r[1], "topic": r[2], "channel": r[3],
             "scheduled_at": r[4], "status": r[5], "content": r[6]}
            for r in rows
        ]


async def update_post_status(post_id: int, status: str, sent_at: Optional[str] = None, error: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE scheduled_posts SET status = ?, sent_at = ?, error = ? WHERE id = ?",
            (status, sent_at, error, post_id)
        )
        await db.commit()


async def record_send_analytics(post_id: int, telegram_message_id: Optional[int], status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.utcnow().isoformat()
        await db.execute(
            """INSERT INTO send_analytics (scheduled_post_id, telegram_message_id, sent_at, status)
               VALUES (?, ?, ?, ?)""",
            (post_id, telegram_message_id, now, status)
        )
        await db.commit()


async def get_dashboard_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        c1 = await db.execute("SELECT COUNT(*) FROM campaigns")
        c2 = await db.execute("SELECT COUNT(*) FROM scheduled_posts WHERE status = 'pending'")
        c3 = await db.execute("SELECT COUNT(*) FROM scheduled_posts WHERE status = 'sent'")
        c4 = await db.execute("SELECT COUNT(*) FROM channels")
        return {
            "total_campaigns": (await c1.fetchone())[0],
            "posts_scheduled": (await c2.fetchone())[0],
            "posts_sent": (await c3.fetchone())[0],
            "channels_connected": (await c4.fetchone())[0],
        }
```

**Important:** Replace the existing `init_db()` function in `database.py` with the full version above (which adds the 3 new tables). Also add `DB_PATH = os.getenv("DB_PATH", "campaigns.db")` at the top, replacing the hardcoded `DB_PATH = "campaigns.db"`.

- [ ] **Step 1.6: Run tests — expect pass**

```bash
pytest tests/test_database.py -v
```

Expected: All 6 tests pass.

- [ ] **Step 1.7: Commit**

```bash
git add requirements.txt .env.example database.py tests/
git commit -m "feat: extend DB schema — channels, scheduled_posts, analytics tables

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Task 2: Auth Module

**Files:**
- Create: `auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 2.1: Write failing auth tests**

Create `tests/test_auth.py`:

```python
import os
os.environ["SECRET_KEY"] = "testsecret"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "testpass"

import time
import pytest
from auth import (
    get_password_hash, verify_password,
    create_token, verify_token,
)


def test_password_hash_and_verify():
    hashed = get_password_hash("mypassword")
    assert verify_password("mypassword", hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_create_and_verify_token():
    token = create_token("admin")
    username = verify_token(token)
    assert username == "admin"


def test_verify_invalid_token():
    result = verify_token("not.a.real.token")
    assert result is None


def test_verify_expired_token():
    import jwt
    from datetime import datetime, timedelta, timezone
    payload = {"sub": "admin", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}
    expired = jwt.encode(payload, "testsecret", algorithm="HS256")
    assert verify_token(expired) is None
```

- [ ] **Step 2.2: Run tests — expect failure**

```bash
pytest tests/test_auth.py -v
```

Expected: ImportError — `auth` module doesn't exist.

- [ ] **Step 2.3: Create auth.py**

```python
import os
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Request
from fastapi.responses import RedirectResponse

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-use-secrets-token-hex")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
TOKEN_EXPIRE_HOURS = 24
COOKIE_NAME = "campaignos_session"


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def check_credentials(username: str, password: str) -> bool:
    if username != ADMIN_USERNAME:
        return False
    # Compare plain password from env (hash on first run is optional complexity)
    return password == ADMIN_PASSWORD


class NotAuthenticatedException(Exception):
    pass


def require_auth(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise NotAuthenticatedException()
    username = verify_token(token)
    if not username:
        raise NotAuthenticatedException()
    return username
```

- [ ] **Step 2.4: Run tests — expect pass**

```bash
pytest tests/test_auth.py -v
```

Expected: 4 tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add auth.py tests/test_auth.py
git commit -m "feat: auth module — JWT tokens, password verify, require_auth dependency

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Task 3: Broadcaster Module

**Files:**
- Create: `broadcaster.py`
- Create: `tests/test_broadcaster.py`

- [ ] **Step 3.1: Write failing broadcaster tests**

Create `tests/test_broadcaster.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def make_bot(message_id=101, raise_flood=False):
    bot = MagicMock()
    if raise_flood:
        from aiogram.exceptions import TelegramRetryAfter
        bot.send_message = AsyncMock(side_effect=TelegramRetryAfter(retry_after=1))
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
        side_effect=[TelegramRetryAfter(retry_after=0), result]
    )
    msg_id = await send_with_retry(bot, "-100x", "msg", retries=3)
    assert msg_id == 99
```

- [ ] **Step 3.2: Run tests — expect failure**

```bash
pytest tests/test_broadcaster.py -v
```

Expected: ImportError.

- [ ] **Step 3.3: Create broadcaster.py**

```python
import asyncio
import logging
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError

logger = logging.getLogger(__name__)

MAX_MESSAGE_LEN = 4096
SEND_DELAY_SECONDS = 3  # minimum delay between sends to same channel


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
            logger.warning(f"Flood control on {chat_id}: waiting {wait}s (attempt {attempt + 1}/{retries})")
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
```

- [ ] **Step 3.4: Run tests — expect pass**

```bash
pytest tests/test_broadcaster.py -v
```

Expected: 3 tests pass.

- [ ] **Step 3.5: Commit**

```bash
git add broadcaster.py tests/test_broadcaster.py
git commit -m "feat: broadcaster module — send, split, retry, flood-control

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Task 4: Scheduler Module

**Files:**
- Create: `scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 4.1: Write failing scheduler tests**

Create `tests/test_scheduler.py`:

```python
import asyncio
import os
import pytest

os.environ["DB_PATH"] = ":memory:"

@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_scheduler_starts_and_stops():
    from scheduler import CampaignScheduler
    sched = CampaignScheduler(bot=None)
    sched.start()
    assert sched.scheduler.running
    sched.stop()
    assert not sched.scheduler.running


@pytest.mark.asyncio
async def test_schedule_one_shot_returns_job_id():
    from scheduler import CampaignScheduler
    from datetime import datetime, timedelta, timezone
    sched = CampaignScheduler(bot=None)
    sched.start()
    run_at = datetime.now(timezone.utc) + timedelta(hours=1)
    job_id = sched.schedule_post(post_id=1, run_at=run_at)
    assert job_id is not None
    sched.cancel_job(job_id)
    sched.stop()


@pytest.mark.asyncio
async def test_cancel_nonexistent_job_returns_false():
    from scheduler import CampaignScheduler
    sched = CampaignScheduler(bot=None)
    sched.start()
    result = sched.cancel_job("nonexistent-job-id")
    assert result is False
    sched.stop()
```

- [ ] **Step 4.2: Run tests — expect failure**

```bash
pytest tests/test_scheduler.py -v
```

Expected: ImportError.

- [ ] **Step 4.3: Create scheduler.py**

```python
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)


class CampaignScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self):
        self.scheduler.start()
        logger.info("Scheduler started")

    def stop(self):
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    def schedule_post(self, post_id: int, run_at: datetime) -> str:
        job_id = f"post_{post_id}"
        self.scheduler.add_job(
            self._execute_post,
            trigger=DateTrigger(run_date=run_at),
            args=[post_id],
            id=job_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled post {post_id} at {run_at}")
        return job_id

    def schedule_recurring(self, post_id: int, cron_expr: str) -> str:
        job_id = f"recurring_{post_id}"
        minute, hour, dom, month, dow = cron_expr.split()
        self.scheduler.add_job(
            self._execute_post,
            trigger=CronTrigger(minute=minute, hour=hour, day=dom, month=month, day_of_week=dow),
            args=[post_id],
            id=job_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled recurring post {post_id} cron={cron_expr}")
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        job = self.scheduler.get_job(job_id)
        if job:
            job.remove()
            return True
        return False

    def get_upcoming_jobs(self, limit: int = 20) -> list:
        jobs = self.scheduler.get_jobs()
        result = []
        for job in jobs[:limit]:
            result.append({
                "job_id": job.id,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })
        return result

    async def _execute_post(self, post_id: int):
        from database import get_scheduled_post, get_channel, update_post_status, record_send_analytics
        from broadcaster import send_with_retry

        post = await get_scheduled_post(post_id)
        if not post:
            logger.error(f"Post {post_id} not found for execution")
            return

        channel = await get_channel(post["channel_id"])
        if not channel:
            logger.error(f"Channel {post['channel_id']} not found")
            await update_post_status(post_id, "failed", error="Channel not found")
            return

        now = datetime.now(timezone.utc).isoformat()
        try:
            msg_id = await send_with_retry(self.bot, channel["chat_id"], post["content"])
            await update_post_status(post_id, "sent", sent_at=now)
            await record_send_analytics(post_id, msg_id, "sent")
            logger.info(f"Post {post_id} sent to {channel['chat_id']}, message_id={msg_id}")
        except Exception as e:
            await update_post_status(post_id, "failed", error=str(e))
            await record_send_analytics(post_id, None, "failed")
            logger.error(f"Post {post_id} failed: {e}")


# Global instance — initialized in main.py
campaign_scheduler: Optional[CampaignScheduler] = None
```

- [ ] **Step 4.4: Run tests — expect pass**

```bash
pytest tests/test_scheduler.py -v
```

Expected: 3 tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add scheduler.py tests/test_scheduler.py
git commit -m "feat: scheduler module — APScheduler wrapper, one-shot + cron, cancel

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Task 5: Campaign Protocol v2 + /social Bot Command

**Files:**
- Modify: `campaign_protocol.py`
- Modify: `bot.py`
- Modify: `states.py`

- [ ] **Step 5.1: Add `social_copy` phase to campaign_protocol.py**

Add this entry to the `CAMPAIGN_PROTOCOL` dict in `campaign_protocol.py`:

```python
    "social_copy": CampaignPhase(
        name="Social Copy Pack",
        objective="Generate ready-to-post Telegram message variants",
        prompt_template="""Based on campaign research and content, create 5 ready-to-post Telegram messages.

Each message must have:
- A sharp hook (first line, max 10 words)
- Body (2-4 lines, plain language, no corporate speak)
- Clear call to action (last line)

Vary the angle for each. Keep each under 280 words. Format with --- between messages.

Topic: {topic}
Tone: {tone}
""",
    ),
```

Update `get_phase_prompt` to handle optional kwargs gracefully:

```python
def get_phase_prompt(phase: str, **kwargs) -> str:
    if phase not in CAMPAIGN_PROTOCOL:
        raise ValueError(f"Unknown phase: {phase}")
    template = CAMPAIGN_PROTOCOL[phase].prompt_template
    # Fill what we have, leave unfilled slots with placeholder
    import re
    keys = re.findall(r'\{(\w+)\}', template)
    filled = {k: kwargs.get(k, f"[{k}]") for k in keys}
    return template.format(**filled)
```

- [ ] **Step 5.2: Add `/social` command to bot.py**

Add after the existing `/resume` handler:

```python
@router.message(Command("social"))
async def cmd_social(message: Message):
    campaign = await get_current_campaign(message.from_user.id)
    if not campaign:
        await message.answer("No active campaign. Use /new to start one.")
        return

    await message.answer(f"🎨 Generating social copy for campaign <b>#{campaign['id']}</b>...")

    try:
        prompt = get_phase_prompt("social_copy", topic=campaign["topic"], tone="engaging and direct")
        resp = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
        content = resp["message"]["content"]
        await save_message(campaign["id"], "assistant", content, "social_copy")

        # Split into 2 messages if over 3800 chars
        if len(content) > 3800:
            await message.answer(content[:3800])
            await message.answer(content[3800:7600])
        else:
            await message.answer(content)
        await message.answer("✅ Social copy ready. Check your dashboard to schedule.")
    except Exception as e:
        logger.error(f"Error generating social copy: {e}")
        await message.answer("❌ Failed to generate social copy. Is Ollama running?")
```

- [ ] **Step 5.3: Update /start help text in bot.py**

Replace the `/start` handler's `answer` text:

```python
    await message.answer(
        "🧠 <b>CampaignOS Bot</b> — Professional Marketing Assistant\n\n"
        "Commands:\n"
        "/new — Start a new campaign\n"
        "/campaigns — View all campaigns\n"
        "/social — Generate social copy for current campaign\n"
        "/channels — List connected Telegram channels\n"
        "/resume — Resume latest campaign\n"
        "/help — Show help",
        parse_mode="HTML"
    )
```

- [ ] **Step 5.4: Update /help handler similarly**

```python
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📋 <b>CampaignOS Help</b>\n\n"
        "• /new — Create a new marketing campaign\n"
        "• /campaigns — List all your campaigns\n"
        "• /social — Generate social copy pack for current campaign\n"
        "• /channels — List channels the bot can post to\n"
        "• /resume — Resume your latest campaign",
        parse_mode="HTML"
    )
```

- [ ] **Step 5.5: Add /channels command to bot.py**

```python
@router.message(Command("channels"))
async def cmd_channels(message: Message):
    from database import list_channels
    channels = await list_channels()
    if not channels:
        await message.answer(
            "No channels connected yet.\n"
            "Add the bot as admin to a channel, then register it in the dashboard at /channels."
        )
        return
    text = "<b>Connected Channels:</b>\n\n"
    for ch in channels:
        text += f"• {ch['name']} (<code>{ch['chat_id']}</code>)\n"
    await message.answer(text, parse_mode="HTML")
```

- [ ] **Step 5.6: Commit**

```bash
git add campaign_protocol.py bot.py states.py
git commit -m "feat: social_copy campaign phase, /social and /channels bot commands

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Task 6: Dashboard — Auth + Login Routes

**Files:**
- Modify: `dashboard.py`
- Create: `templates/login.html`

- [ ] **Step 6.1: Add auth wiring to dashboard.py**

At the top of `dashboard.py`, add these imports and the exception handler:

```python
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
from auth import (
    require_auth, check_credentials, create_token,
    NotAuthenticatedException, COOKIE_NAME
)
from database import (
    init_db, get_or_create_user, create_campaign, get_current_campaign,
    save_message, get_campaign_messages, list_user_campaigns,
    list_channels, add_channel, remove_channel,
    list_scheduled_posts, create_scheduled_post, update_post_status,
    get_dashboard_stats,
)

app = FastAPI(title="CampaignOS")
templates = Jinja2Templates(directory="templates")
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


@app.exception_handler(NotAuthenticatedException)
async def not_auth_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url="/login", status_code=303)
```

- [ ] **Step 6.2: Add login/logout routes to dashboard.py**

```python
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if not check_credentials(username, password):
        return RedirectResponse(url="/login?error=Invalid+credentials", status_code=303)
    token = create_token(username)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
```

- [ ] **Step 6.3: Add `require_auth` dependency to all existing routes**

Update existing route signatures in `dashboard.py` to add `_user: str = Depends(require_auth)`:

```python
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, _user: str = Depends(require_auth)):
    ...

@app.get("/campaigns", response_class=HTMLResponse)
async def list_campaigns(request: Request, user_id: int = 1, _user: str = Depends(require_auth)):
    ...

@app.get("/campaign/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign_id: int, _user: str = Depends(require_auth)):
    ...

@app.post("/campaign/new")
async def create_new_campaign(topic: str = Form(...), user_id: int = Form(1), _user: str = Depends(require_auth)):
    ...

@app.post("/campaign/{campaign_id}/continue")
async def continue_campaign(campaign_id: int, phase: str = Form(...), _user: str = Depends(require_auth)):
    ...
```

- [ ] **Step 6.4: Create templates/login.html**

```html
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CampaignOS — Login</title>
    <script src="/static/tailwind.min.js"></script>
    <script>tailwind.config = { darkMode: 'class' }</script>
</head>
<body class="bg-[#0f0f0f] min-h-screen flex items-center justify-center px-4">
    <div class="w-full max-w-sm">
        <div class="text-center mb-8">
            <h1 class="text-2xl font-bold text-white">🧠 CampaignOS</h1>
            <p class="text-zinc-400 text-sm mt-1">Sign in to your dashboard</p>
        </div>
        <div class="bg-[#1a1a1a] rounded-2xl p-6 shadow-xl border border-zinc-800">
            {% if error %}
            <div class="mb-4 px-4 py-3 bg-red-900/40 border border-red-700 rounded-lg text-red-300 text-sm">
                {{ error }}
            </div>
            {% endif %}
            <form method="post" action="/login" class="space-y-4">
                <div>
                    <label class="block text-sm text-zinc-400 mb-1">Username</label>
                    <input
                        type="text" name="username" autocomplete="username"
                        class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                        placeholder="admin" required
                    >
                </div>
                <div>
                    <label class="block text-sm text-zinc-400 mb-1">Password</label>
                    <input
                        type="password" name="password" autocomplete="current-password"
                        class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                        placeholder="••••••••" required
                    >
                </div>
                <button
                    type="submit"
                    class="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl py-3 text-sm transition-colors mt-2"
                >
                    Sign In
                </button>
            </form>
        </div>
    </div>
</body>
</html>
```

- [ ] **Step 6.5: Test auth manually**

```bash
source .venv/bin/activate
python -c "from database import init_db; import asyncio; asyncio.run(init_db())"
uvicorn dashboard:app --port 8000
```

Open `http://localhost:8000` — should redirect to `/login`. Sign in with `admin` / `changeme` (or whatever is in `.env`). Should reach dashboard. `Ctrl+C` to stop.

- [ ] **Step 6.6: Commit**

```bash
git add dashboard.py templates/login.html auth.py
git commit -m "feat: dashboard auth — JWT cookie, login/logout, protected routes

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Task 7: Channel & Schedule Routes in Dashboard

**Files:**
- Modify: `dashboard.py`

- [ ] **Step 7.1: Add channels routes**

Append to `dashboard.py`:

```python
@app.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request, _user: str = Depends(require_auth)):
    channels = await list_channels()
    return templates.TemplateResponse("channels.html", {
        "request": request,
        "channels": channels,
        "title": "Channels",
    })


@app.post("/channels/add")
async def add_channel_route(
    request: Request,
    chat_id: str = Form(...),
    name: str = Form(...),
    _user: str = Depends(require_auth),
):
    await add_channel(chat_id=chat_id.strip(), name=name.strip())
    return RedirectResponse(url="/channels", status_code=303)


@app.post("/channels/{channel_id}/remove")
async def remove_channel_route(channel_id: int, _user: str = Depends(require_auth)):
    await remove_channel(channel_id)
    return RedirectResponse(url="/channels", status_code=303)
```

- [ ] **Step 7.2: Add schedule routes**

```python
@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request, _user: str = Depends(require_auth)):
    posts = await list_scheduled_posts(limit=50)
    return templates.TemplateResponse("schedule.html", {
        "request": request,
        "posts": posts,
        "title": "Schedule",
    })


@app.post("/schedule/new")
async def create_schedule_post(
    request: Request,
    campaign_id: int = Form(...),
    channel_id: int = Form(...),
    content: str = Form(...),
    scheduled_at: str = Form(...),  # ISO datetime from datetime-local input
    recurring_cron: str = Form(""),
    _user: str = Depends(require_auth),
):
    cron = recurring_cron.strip() or None
    post_id = await create_scheduled_post(
        campaign_id=campaign_id,
        channel_id=channel_id,
        content=content,
        scheduled_at=scheduled_at,
        recurring_cron=cron,
    )
    # Register with scheduler
    import scheduler as sched_module
    if sched_module.campaign_scheduler:
        from datetime import datetime
        run_at = datetime.fromisoformat(scheduled_at)
        if cron:
            sched_module.campaign_scheduler.schedule_recurring(post_id, cron)
        else:
            sched_module.campaign_scheduler.schedule_post(post_id, run_at)
    return RedirectResponse(url="/schedule", status_code=303)


@app.post("/schedule/{post_id}/cancel")
async def cancel_scheduled_post(post_id: int, _user: str = Depends(require_auth)):
    await update_post_status(post_id, "cancelled")
    import scheduler as sched_module
    if sched_module.campaign_scheduler:
        sched_module.campaign_scheduler.cancel_job(f"post_{post_id}")
        sched_module.campaign_scheduler.cancel_job(f"recurring_{post_id}")
    return RedirectResponse(url="/schedule", status_code=303)
```

- [ ] **Step 7.3: Update dashboard home route to use stats**

Replace the existing `@app.get("/")` handler:

```python
@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, _user: str = Depends(require_auth)):
    stats = await get_dashboard_stats()
    upcoming = await list_scheduled_posts(status="pending", limit=5)
    campaigns = await list_user_campaigns(user_id=1)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Dashboard",
        "stats": stats,
        "upcoming": upcoming[:5],
        "recent_campaigns": campaigns[:5],
    })
```

- [ ] **Step 7.4: Commit**

```bash
git add dashboard.py
git commit -m "feat: channels and schedule routes in dashboard

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Task 8: Mobile-First Dashboard UI

**Files:**
- Create: `templates/base.html`
- Replace: `templates/dashboard.html`
- Replace: `templates/campaigns.html`
- Replace: `templates/campaign_detail.html`
- Create: `templates/channels.html`
- Create: `templates/schedule.html`

- [ ] **Step 8.1: Create templates/base.html**

```html
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} — CampaignOS</title>
    <script src="/static/tailwind.min.js"></script>
    <script>tailwind.config = { darkMode: 'class' }</script>
    <script defer src="/static/alpine.min.js"></script>
    <style>
        [x-cloak] { display: none !important; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    </style>
</head>
<body class="bg-[#0f0f0f] text-white min-h-screen">

<!-- Desktop sidebar -->
<aside class="hidden md:flex fixed left-0 top-0 h-full w-56 bg-[#111] border-r border-zinc-800 flex-col z-10">
    <div class="px-5 py-4 border-b border-zinc-800">
        <span class="text-lg font-bold text-white">🧠 CampaignOS</span>
    </div>
    <nav class="flex-1 px-3 py-4 space-y-1">
        <a href="/" class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors {% if title == 'Dashboard' %}bg-zinc-800 text-white{% endif %}">
            <span>📊</span> Dashboard
        </a>
        <a href="/campaigns" class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors {% if title == 'Campaigns' %}bg-zinc-800 text-white{% endif %}">
            <span>🎯</span> Campaigns
        </a>
        <a href="/schedule" class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors {% if title == 'Schedule' %}bg-zinc-800 text-white{% endif %}">
            <span>📅</span> Schedule
        </a>
        <a href="/channels" class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors {% if title == 'Channels' %}bg-zinc-800 text-white{% endif %}">
            <span>📡</span> Channels
        </a>
    </nav>
    <div class="px-3 py-4 border-t border-zinc-800">
        <a href="/logout" class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-red-400 transition-colors">
            <span>🚪</span> Logout
        </a>
    </div>
</aside>

<!-- Main content -->
<main class="md:ml-56 pb-20 md:pb-0 min-h-screen">
    <div class="max-w-5xl mx-auto px-4 py-6">
        {% block content %}{% endblock %}
    </div>
</main>

<!-- Mobile bottom nav -->
<nav class="md:hidden fixed bottom-0 left-0 right-0 bg-[#111] border-t border-zinc-800 flex z-10">
    <a href="/" class="flex-1 flex flex-col items-center py-3 text-xs {% if title == 'Dashboard' %}text-blue-400{% else %}text-zinc-500{% endif %}">
        <span class="text-lg">📊</span>Home
    </a>
    <a href="/campaigns" class="flex-1 flex flex-col items-center py-3 text-xs {% if title == 'Campaigns' %}text-blue-400{% else %}text-zinc-500{% endif %}">
        <span class="text-lg">🎯</span>Campaigns
    </a>
    <a href="/schedule" class="flex-1 flex flex-col items-center py-3 text-xs {% if title == 'Schedule' %}text-blue-400{% else %}text-zinc-500{% endif %}">
        <span class="text-lg">📅</span>Schedule
    </a>
    <a href="/channels" class="flex-1 flex flex-col items-center py-3 text-xs {% if title == 'Channels' %}text-blue-400{% else %}text-zinc-500{% endif %}">
        <span class="text-lg">📡</span>Channels
    </a>
</nav>

</body>
</html>
```

- [ ] **Step 8.2: Replace templates/dashboard.html**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-xl font-bold mb-6">Dashboard</h1>

<!-- Stat Cards -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
    <div class="bg-[#1a1a1a] rounded-2xl p-4 border border-zinc-800">
        <p class="text-zinc-400 text-xs mb-1">Campaigns</p>
        <p class="text-2xl font-bold text-white">{{ stats.total_campaigns }}</p>
    </div>
    <div class="bg-[#1a1a1a] rounded-2xl p-4 border border-zinc-800">
        <p class="text-zinc-400 text-xs mb-1">Scheduled</p>
        <p class="text-2xl font-bold text-blue-400">{{ stats.posts_scheduled }}</p>
    </div>
    <div class="bg-[#1a1a1a] rounded-2xl p-4 border border-zinc-800">
        <p class="text-zinc-400 text-xs mb-1">Sent</p>
        <p class="text-2xl font-bold text-green-400">{{ stats.posts_sent }}</p>
    </div>
    <div class="bg-[#1a1a1a] rounded-2xl p-4 border border-zinc-800">
        <p class="text-zinc-400 text-xs mb-1">Channels</p>
        <p class="text-2xl font-bold text-purple-400">{{ stats.channels_connected }}</p>
    </div>
</div>

<!-- Upcoming -->
<div class="mb-8">
    <h2 class="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">Upcoming Posts</h2>
    {% if upcoming %}
    <div class="space-y-2">
        {% for post in upcoming %}
        <div class="bg-[#1a1a1a] rounded-xl px-4 py-3 border border-zinc-800 flex items-center justify-between">
            <div>
                <p class="text-sm text-white font-medium">{{ post.topic[:50] }}</p>
                <p class="text-xs text-zinc-500">{{ post.channel }} · {{ post.scheduled_at[:16].replace('T',' ') }}</p>
            </div>
            <span class="text-xs bg-blue-900/50 text-blue-300 px-2 py-1 rounded-full">pending</span>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <p class="text-zinc-600 text-sm">No posts scheduled. <a href="/schedule" class="text-blue-400 hover:underline">Add one →</a></p>
    {% endif %}
</div>

<!-- Recent Campaigns -->
<div>
    <h2 class="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">Recent Campaigns</h2>
    {% if recent_campaigns %}
    <div class="space-y-2">
        {% for c in recent_campaigns %}
        <a href="/campaign/{{ c.id }}" class="block bg-[#1a1a1a] rounded-xl px-4 py-3 border border-zinc-800 hover:border-zinc-600 transition-colors">
            <div class="flex items-center justify-between">
                <p class="text-sm text-white font-medium">{{ c.topic[:60] }}</p>
                <span class="text-xs {% if c.status == 'active' %}text-green-400{% else %}text-zinc-500{% endif %}">{{ c.status }}</span>
            </div>
            <p class="text-xs text-zinc-600 mt-1">{{ c.created_at[:10] }}</p>
        </a>
        {% endfor %}
    </div>
    {% else %}
    <p class="text-zinc-600 text-sm">No campaigns yet. <a href="/campaigns" class="text-blue-400 hover:underline">Create one →</a></p>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 8.3: Replace templates/campaigns.html**

```html
{% extends "base.html" %}
{% block content %}
<div x-data="{ filter: 'all', showNew: false }">

<div class="flex items-center justify-between mb-6">
    <h1 class="text-xl font-bold">Campaigns</h1>
    <button @click="showNew = true" class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors">+ New</button>
</div>

<!-- New Campaign Modal -->
<div x-show="showNew" x-cloak class="fixed inset-0 bg-black/70 flex items-end md:items-center justify-center z-50 p-4" @click.self="showNew = false">
    <div class="bg-[#1a1a1a] rounded-2xl p-6 w-full max-w-md border border-zinc-700">
        <h2 class="text-lg font-bold mb-4">New Campaign</h2>
        <form method="post" action="/campaign/new">
            <input type="hidden" name="user_id" value="1">
            <label class="block text-sm text-zinc-400 mb-1">Campaign Topic</label>
            <input type="text" name="topic" placeholder="e.g. Launch of sustainable coffee brand"
                class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 mb-4"
                required autofocus>
            <div class="flex gap-3">
                <button type="button" @click="showNew = false" class="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm py-2.5 rounded-xl transition-colors">Cancel</button>
                <button type="submit" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium py-2.5 rounded-xl transition-colors">Start Research</button>
            </div>
        </form>
    </div>
</div>

<!-- Filter tabs -->
<div class="flex gap-2 mb-4">
    <button @click="filter = 'all'" :class="filter === 'all' ? 'bg-blue-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-white'" class="px-4 py-1.5 rounded-full text-sm transition-colors">All</button>
    <button @click="filter = 'active'" :class="filter === 'active' ? 'bg-blue-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-white'" class="px-4 py-1.5 rounded-full text-sm transition-colors">Active</button>
    <button @click="filter = 'completed'" :class="filter === 'completed' ? 'bg-blue-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-white'" class="px-4 py-1.5 rounded-full text-sm transition-colors">Completed</button>
</div>

<!-- Campaign list -->
<div class="space-y-3">
    {% for c in campaigns %}
    <a href="/campaign/{{ c.id }}"
       x-show="filter === 'all' || filter === '{{ c.status }}'"
       class="block bg-[#1a1a1a] rounded-2xl p-4 border border-zinc-800 hover:border-zinc-600 transition-colors">
        <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
                <p class="font-medium text-white truncate">{{ c.topic }}</p>
                <p class="text-xs text-zinc-500 mt-1">{{ c.created_at[:10] }}</p>
            </div>
            <span class="shrink-0 text-xs px-2 py-1 rounded-full {% if c.status == 'active' %}bg-green-900/50 text-green-400{% else %}bg-zinc-800 text-zinc-400{% endif %}">
                {{ c.status }}
            </span>
        </div>
    </a>
    {% else %}
    <p class="text-zinc-600 text-sm text-center py-8">No campaigns yet. Hit <span class="text-blue-400">+ New</span> to start.</p>
    {% endfor %}
</div>

</div>
{% endblock %}
```

- [ ] **Step 8.4: Replace templates/campaign_detail.html**

```html
{% extends "base.html" %}
{% block content %}
<div x-data="{ tab: 'research' }">

<div class="flex items-center gap-3 mb-6">
    <a href="/campaigns" class="text-zinc-500 hover:text-white text-sm transition-colors">← Back</a>
    <h1 class="text-xl font-bold">Campaign #{{ campaign_id }}</h1>
</div>

<!-- Phase tabs -->
<div class="flex gap-1 overflow-x-auto mb-6 pb-1">
    {% for phase in ['research', 'content', 'schedule', 'social_copy'] %}
    <button
        @click="tab = '{{ phase }}'"
        :class="tab === '{{ phase }}' ? 'bg-blue-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-white'"
        class="shrink-0 px-4 py-2 rounded-xl text-sm font-medium transition-colors capitalize">
        {{ phase.replace('_', ' ') }}
    </button>
    {% endfor %}
</div>

<!-- Phase content -->
{% for phase in ['research', 'content', 'schedule', 'social_copy'] %}
<div x-show="tab === '{{ phase }}'" x-cloak class="space-y-4">
    {% set phase_msgs = messages | selectattr('phase', 'equalto', phase) | list %}
    {% if phase_msgs %}
        {% for msg in phase_msgs %}
        <div class="bg-[#1a1a1a] rounded-2xl p-4 border border-zinc-800">
            <pre class="text-sm text-zinc-200 whitespace-pre-wrap font-sans">{{ msg.content }}</pre>
        </div>
        {% endfor %}
    {% else %}
    <div class="bg-[#1a1a1a] rounded-2xl p-6 border border-zinc-800 text-center">
        <p class="text-zinc-500 text-sm mb-4">No {{ phase }} content yet.</p>
        <form method="post" action="/campaign/{{ campaign_id }}/continue">
            <input type="hidden" name="phase" value="{{ phase }}">
            <button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white text-sm px-5 py-2.5 rounded-xl transition-colors">
                Run {{ phase.replace('_', ' ').title() }} Phase
            </button>
        </form>
    </div>
    {% endif %}
</div>
{% endfor %}

</div>
{% endblock %}
```

- [ ] **Step 8.5: Create templates/channels.html**

```html
{% extends "base.html" %}
{% block content %}
<div x-data="{ showAdd: false }">

<div class="flex items-center justify-between mb-6">
    <h1 class="text-xl font-bold">Channels</h1>
    <button @click="showAdd = true" class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors">+ Add Channel</button>
</div>

<!-- Add Channel Modal -->
<div x-show="showAdd" x-cloak class="fixed inset-0 bg-black/70 flex items-end md:items-center justify-center z-50 p-4" @click.self="showAdd = false">
    <div class="bg-[#1a1a1a] rounded-2xl p-6 w-full max-w-md border border-zinc-700">
        <h2 class="text-lg font-bold mb-2">Add Channel</h2>
        <p class="text-zinc-500 text-sm mb-4">Add the bot as admin to the channel first, then register it here.</p>
        <form method="post" action="/channels/add">
            <label class="block text-sm text-zinc-400 mb-1">Channel ID</label>
            <input type="text" name="chat_id" placeholder="-100123456789"
                class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 mb-3"
                required>
            <label class="block text-sm text-zinc-400 mb-1">Display Name</label>
            <input type="text" name="name" placeholder="My Marketing Channel"
                class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 mb-4"
                required>
            <div class="flex gap-3">
                <button type="button" @click="showAdd = false" class="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm py-2.5 rounded-xl transition-colors">Cancel</button>
                <button type="submit" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium py-2.5 rounded-xl transition-colors">Add</button>
            </div>
        </form>
    </div>
</div>

<!-- Channel list -->
<div class="space-y-3">
    {% for ch in channels %}
    <div class="bg-[#1a1a1a] rounded-2xl p-4 border border-zinc-800 flex items-center justify-between">
        <div>
            <p class="font-medium text-white">{{ ch.name }}</p>
            <p class="text-xs text-zinc-500 font-mono mt-0.5">{{ ch.chat_id }}</p>
        </div>
        <form method="post" action="/channels/{{ ch.id }}/remove">
            <button type="submit" class="text-xs text-zinc-500 hover:text-red-400 transition-colors px-3 py-1.5 rounded-lg hover:bg-red-900/20">Remove</button>
        </form>
    </div>
    {% else %}
    <div class="text-center py-12">
        <p class="text-zinc-500 text-sm">No channels connected yet.</p>
        <p class="text-zinc-600 text-xs mt-1">Add the bot as admin to a Telegram channel, then click <span class="text-blue-400">+ Add Channel</span>.</p>
    </div>
    {% endfor %}
</div>

</div>
{% endblock %}
```

- [ ] **Step 8.6: Create templates/schedule.html**

```html
{% extends "base.html" %}
{% block content %}
<div x-data="{ showNew: false }">

<div class="flex items-center justify-between mb-6">
    <h1 class="text-xl font-bold">Schedule</h1>
    <button @click="showNew = true" class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors">+ Schedule Post</button>
</div>

<!-- New Scheduled Post Modal -->
<div x-show="showNew" x-cloak class="fixed inset-0 bg-black/70 flex items-end md:items-center justify-center z-50 p-4" @click.self="showNew = false">
    <div class="bg-[#1a1a1a] rounded-2xl p-6 w-full max-w-lg border border-zinc-700 max-h-[90vh] overflow-y-auto">
        <h2 class="text-lg font-bold mb-4">Schedule a Post</h2>
        <form method="post" action="/schedule/new" class="space-y-3">
            <div>
                <label class="block text-sm text-zinc-400 mb-1">Campaign ID</label>
                <input type="number" name="campaign_id" placeholder="1"
                    class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
                    required>
            </div>
            <div>
                <label class="block text-sm text-zinc-400 mb-1">Channel ID</label>
                <input type="number" name="channel_id" placeholder="1"
                    class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
                    required>
            </div>
            <div>
                <label class="block text-sm text-zinc-400 mb-1">Content</label>
                <textarea name="content" rows="4" placeholder="Your message text..."
                    class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 resize-none"
                    required></textarea>
            </div>
            <div>
                <label class="block text-sm text-zinc-400 mb-1">Send At</label>
                <input type="datetime-local" name="scheduled_at"
                    class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500"
                    required>
            </div>
            <div>
                <label class="block text-sm text-zinc-400 mb-1">Recurring Cron (optional)</label>
                <input type="text" name="recurring_cron" placeholder="0 9 * * 1  (every Mon 9am)"
                    class="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500">
            </div>
            <div class="flex gap-3 pt-2">
                <button type="button" @click="showNew = false" class="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm py-2.5 rounded-xl transition-colors">Cancel</button>
                <button type="submit" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium py-2.5 rounded-xl transition-colors">Schedule</button>
            </div>
        </form>
    </div>
</div>

<!-- Posts table -->
{% if posts %}
<div class="space-y-3">
    {% for post in posts %}
    <div class="bg-[#1a1a1a] rounded-2xl p-4 border border-zinc-800">
        <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-white truncate">{{ post.topic }}</p>
                <p class="text-xs text-zinc-500 mt-0.5">📡 {{ post.channel }} · 🕐 {{ post.scheduled_at[:16].replace('T', ' ') }}</p>
                <p class="text-xs text-zinc-600 mt-1 line-clamp-2">{{ post.content[:100] }}{% if post.content|length > 100 %}...{% endif %}</p>
            </div>
            <div class="flex flex-col items-end gap-2">
                <span class="text-xs px-2 py-1 rounded-full
                    {% if post.status == 'pending' %}bg-blue-900/50 text-blue-300
                    {% elif post.status == 'sent' %}bg-green-900/50 text-green-400
                    {% elif post.status == 'failed' %}bg-red-900/50 text-red-400
                    {% else %}bg-zinc-800 text-zinc-400{% endif %}">
                    {{ post.status }}
                </span>
                {% if post.status == 'pending' %}
                <form method="post" action="/schedule/{{ post.id }}/cancel">
                    <button type="submit" class="text-xs text-zinc-500 hover:text-red-400 transition-colors">cancel</button>
                </form>
                {% endif %}
            </div>
        </div>
    </div>
    {% endfor %}
</div>
{% else %}
<div class="text-center py-12">
    <p class="text-zinc-500 text-sm">No posts scheduled yet.</p>
    <p class="text-zinc-600 text-xs mt-1">Click <span class="text-blue-400">+ Schedule Post</span> to queue a broadcast.</p>
</div>
{% endif %}

</div>
{% endblock %}
```

- [ ] **Step 8.7: Commit all templates**

```bash
git add templates/
git commit -m "feat: mobile-first dashboard UI — Tailwind + Alpine, all 6 pages

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Task 9: main.py — Unified Entrypoint

**Files:**
- Create: `main.py`
- Modify: `Makefile`

- [ ] **Step 9.1: Create main.py**

```python
"""
CampaignOS — Single entrypoint.
Runs the Telegram bot + FastAPI dashboard + APScheduler in one asyncio process.
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    import uvicorn
    from bot import dp, bot
    from dashboard import app
    from database import init_db
    from scheduler import CampaignScheduler
    import scheduler as sched_module

    await init_db()
    logger.info("Database initialized")

    sched = CampaignScheduler(bot=bot)
    sched.start()
    sched_module.campaign_scheduler = sched
    logger.info("Scheduler started")

    # Recover pending posts on startup
    from database import list_scheduled_posts
    from datetime import datetime, timezone
    pending = await list_scheduled_posts(status="pending", limit=200)
    recovered = 0
    for post in pending:
        try:
            run_at = datetime.fromisoformat(post["scheduled_at"])
            if run_at.tzinfo is None:
                run_at = run_at.replace(tzinfo=timezone.utc)
            if run_at > datetime.now(timezone.utc):
                sched.schedule_post(post["id"], run_at)
                recovered += 1
        except Exception as e:
            logger.warning(f"Could not recover post {post['id']}: {e}")
    logger.info(f"Recovered {recovered} pending scheduled posts")

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    await asyncio.gather(
        server.serve(),
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("CampaignOS stopped")
```

- [ ] **Step 9.2: Update Makefile**

Replace the entire Makefile:

```makefile
.PHONY: help setup run dashboard all model db clean test

help:
	@echo "CampaignOS v2 Makefile"
	@echo ""
	@echo "  make setup      Install dependencies + init DB + vendor JS/CSS"
	@echo "  make all        Run bot + dashboard + scheduler together (recommended)"
	@echo "  make run        Run Telegram bot only"
	@echo "  make dashboard  Run web dashboard only"
	@echo "  make model      Download llama3.1:8b"
	@echo "  make db         Initialize database"
	@echo "  make test       Run test suite"
	@echo "  make clean      Remove generated files"

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt
	mkdir -p static
	curl -fsSL https://cdn.tailwindcss.com/3.4.16 -o static/tailwind.min.js
	curl -fsSL https://cdn.jsdelivr.net/npm/alpinejs@3.14.9/dist/cdn.min.js -o static/alpine.min.js
	@echo "✓ Dependencies installed and JS/CSS vendored to static/"

all:
	. .venv/bin/activate && python main.py

run:
	. .venv/bin/activate && python bot.py

dashboard:
	. .venv/bin/activate && uvicorn dashboard:app --reload --port 8000

model:
	ollama pull llama3.1:8b
	@echo "✓ Model ready"

db:
	. .venv/bin/activate && python -c "from database import init_db; import asyncio; asyncio.run(init_db())"
	@echo "✓ Database initialized"

test:
	. .venv/bin/activate && pytest tests/ -v

clean:
	rm -f campaigns.db
	rm -rf __pycache__ .pytest_cache tests/__pycache__
	@echo "✓ Cleaned"
```

- [ ] **Step 9.3: Smoke test**

```bash
source .venv/bin/activate
python -c "import main; print('Import OK')"
```

Expected: `Import OK` (no import errors).

- [ ] **Step 9.4: Commit**

```bash
git add main.py Makefile
git commit -m "feat: main.py unified entrypoint — bot + dashboard + scheduler in one process

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Task 10: Full Test Run + Ship-It Checklist Update

**Files:**
- Modify: `ship-it.md`

- [ ] **Step 10.1: Run full test suite**

```bash
source .venv/bin/activate
pytest tests/ -v
```

Expected output (all pass):
```
tests/test_auth.py::test_password_hash_and_verify PASSED
tests/test_auth.py::test_create_and_verify_token PASSED
tests/test_auth.py::test_verify_invalid_token PASSED
tests/test_auth.py::test_verify_expired_token PASSED
tests/test_broadcaster.py::test_send_to_channel_success PASSED
tests/test_broadcaster.py::test_send_long_message_splits PASSED
tests/test_broadcaster.py::test_send_with_retry_success_after_flood PASSED
tests/test_database.py::test_add_and_get_channel PASSED
tests/test_database.py::test_list_channels PASSED
tests/test_database.py::test_remove_channel PASSED
tests/test_database.py::test_create_and_get_scheduled_post PASSED
tests/test_database.py::test_update_post_status PASSED
tests/test_database.py::test_record_analytics PASSED
tests/test_scheduler.py::test_scheduler_starts_and_stops PASSED
tests/test_scheduler.py::test_schedule_one_shot_returns_job_id PASSED
tests/test_scheduler.py::test_cancel_nonexistent_job_returns_false PASSED
```

If any test fails, fix before continuing.

- [ ] **Step 10.2: Manual end-to-end verification**

```bash
# Ensure .env has real TELEGRAM_BOT_TOKEN, set ADMIN_PASSWORD
make all
```

Open `http://localhost:8000` — verify:
- [ ] Redirects to `/login`
- [ ] Login with admin credentials succeeds
- [ ] Dashboard shows 4 stat cards
- [ ] `/campaigns` loads and shows "+ New" button
- [ ] `/channels` loads empty state with "+ Add Channel"
- [ ] `/schedule` loads empty state
- [ ] On mobile viewport (375px) — bottom nav visible, no horizontal scroll

In Telegram:
- [ ] `/start` shows all commands
- [ ] `/new` starts campaign creation flow
- [ ] `/social` responds (needs Ollama running)
- [ ] `/channels` shows empty list or registered channels

- [ ] **Step 10.3: Update ship-it.md**

Replace `ship-it.md` with updated content:

```markdown
# Ship-it Guide — CampaignOS v2

## Prerequisites

- Python 3.10+ and venv
- Ollama installed (`curl -fsSL https://ollama.com/install.sh | sh`)
- Telegram bot token from @BotFather
- Ubuntu/Debian server (16GB+ RAM recommended for Ollama)

## 1. Setup

```bash
git clone <your-repo> /opt/campaignos
cd /opt/campaignos
make setup
make model
cp .env.example .env
nano .env   # Add TELEGRAM_BOT_TOKEN, ADMIN_PASSWORD, SECRET_KEY
make db
```

Generate SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 2. Run

```bash
make all    # Bot + Dashboard + Scheduler together at http://localhost:8000
```

## 3. Systemd Service

Create `/etc/systemd/system/campaignos.service`:

```ini
[Unit]
Description=CampaignOS v2
After=network.target ollama.service

[Service]
Type=simple
User=supremeleader
WorkingDirectory=/opt/campaignos
EnvironmentFile=/opt/campaignos/.env
ExecStart=/opt/campaignos/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable campaignos
sudo systemctl start campaignos
sudo journalctl -u campaignos -f
```

## 4. Quick Checklist

- [ ] `.env` configured (TOKEN, ADMIN_PASSWORD, SECRET_KEY)
- [ ] `make db` ran
- [ ] `make all` starts without errors
- [ ] Dashboard loads at `http://localhost:8000`
- [ ] Login works
- [ ] Telegram bot responds to `/start`
- [ ] Ollama running (`ollama serve`)
```

- [ ] **Step 10.4: Final commit**

```bash
git add ship-it.md tests/
git commit -m "docs: update ship-it guide for v2; all 16 tests passing

— SpectreHawk. Co-Conjured-By: hermes-grok-4 <hermes@spectrehawk.void>"
```

---

## Success Criteria

Before declaring done, verify ALL of these:

- [ ] `pytest tests/ -v` → 16 tests pass, 0 failures
- [ ] `http://localhost:8000` → redirects to `/login` without a cookie
- [ ] Login page submits → sets cookie → reaches dashboard
- [ ] Dashboard shows 4 stat cards
- [ ] Can add a channel in `/channels`
- [ ] Can schedule a post from `/schedule`
- [ ] `make all` runs bot + dashboard together without errors
- [ ] Dashboard renders cleanly at 375px viewport width (no horizontal scroll)
- [ ] Telegram `/start`, `/new`, `/social`, `/channels` all respond
