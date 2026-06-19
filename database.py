"""
SQLite Persistence Layer for CampaignOS v2
"""

import aiosqlite
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.commit()


# ==================== EXISTING FUNCTIONS (kept for compatibility) ====================

async def get_or_create_user(user_id: int, username: Optional[str] = None) -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await db.commit()
            return {"user_id": user_id, "username": username, "current_campaign_id": None}
        return {"user_id": user[0], "username": user[1], "current_campaign_id": user[2]}


async def create_campaign(user_id: int, topic: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await db.execute(
            "INSERT INTO campaigns (user_id, topic, created_at) VALUES (?, ?, ?)",
            (user_id, topic, now)
        )
        campaign_id = cursor.lastrowid
        await db.execute(
            "UPDATE users SET current_campaign_id = ? WHERE user_id = ?",
            (campaign_id, user_id)
        )
        await db.commit()
        return campaign_id


async def get_current_campaign(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT c.* FROM campaigns c
            JOIN users u ON u.current_campaign_id = c.id
            WHERE u.user_id = ?
        """, (user_id,))
        row = await cursor.fetchone()
        if row:
            return {"id": row[0], "user_id": row[1], "topic": row[2], "status": row[3], "created_at": row[4]}
        return None


async def save_message(campaign_id: int, role: str, content: str, phase: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO messages (campaign_id, role, content, phase, timestamp) VALUES (?, ?, ?, ?, ?)",
            (campaign_id, role, content, phase, now)
        )
        await db.commit()


async def get_campaign_messages(campaign_id: int, limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT role, content, phase FROM messages WHERE campaign_id = ? ORDER BY id DESC LIMIT ?",
            (campaign_id, limit)
        )
        rows = await cursor.fetchall()
        return [{"role": r[0], "content": r[1], "phase": r[2]} for r in reversed(rows)]


async def list_user_campaigns(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, topic, status, created_at FROM campaigns WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "topic": r[1], "status": r[2], "created_at": r[3]} for r in rows]


# ==================== CHANNEL CRUD ====================

async def add_channel(chat_id: str, name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now(timezone.utc).isoformat()
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
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """INSERT INTO send_analytics (scheduled_post_id, telegram_message_id, sent_at, status)
               VALUES (?, ?, ?, ?)""",
            (post_id, telegram_message_id, now, status)
        )
        await db.commit()


async def list_pending_scheduled_posts() -> List[Dict]:
    """Pending posts with the fields the scheduler needs to (re)register jobs."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, scheduled_at, recurring_cron
               FROM scheduled_posts WHERE status = 'pending'
               ORDER BY scheduled_at ASC"""
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "scheduled_at": r[1], "recurring_cron": r[2]} for r in rows]


# ==================== USER SETTINGS ====================

async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT value FROM user_settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


async def get_all_settings() -> Dict[str, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT key, value FROM user_settings")
        rows = await cursor.fetchall()
        return {r[0]: r[1] for r in rows}


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
