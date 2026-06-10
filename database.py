"""
SQLite Persistence Layer for Campaign Bot
"""

import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = "campaigns.db"

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
        await db.commit()

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
        now = datetime.utcnow().isoformat()
        cursor = await db.execute(
            "INSERT INTO campaigns (user_id, topic, created_at) VALUES (?, ?, ?)",
            (user_id, topic, now)
        )
        campaign_id = cursor.lastrowid
        
        # Update user's current campaign
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
        now = datetime.utcnow().isoformat()
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