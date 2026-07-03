"""
memory.py — حافظه SQLite async (فقط برای حالت polling/local در bot.py)

روی Vercel استفاده نمیشه چون فایل‌سیستم موقتیه — اونجا api/webhook.py
از Redis (Upstash/Vercel KV) مستقیماً استفاده می‌کنه.
"""
import logging
import aiosqlite

from config import DB_PATH, MAX_HISTORY, MAX_FACTS
from fact_patterns import extract_facts

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")

            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id    INTEGER PRIMARY KEY,
                    first_name TEXT,
                    username   TEXT,
                    msg_count  INTEGER DEFAULT 0,
                    joined_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id  INTEGER NOT NULL,
                    role     TEXT    NOT NULL CHECK(role IN ('user','assistant')),
                    content  TEXT    NOT NULL,
                    ts       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id  INTEGER NOT NULL,
                    fact     TEXT    NOT NULL,
                    ts       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, fact)
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_msg_user ON messages(user_id, id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_facts_user ON facts(user_id)")
            await db.commit()
        logger.info("🗄️  Database ready.")

    # ── Users ────────────────────────────────────────────────────────────────

    async def ensure_user(self, user_id: int, first_name: str, username: str | None = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?,?,?)",
                (user_id, first_name, username),
            )
            await db.execute(
                "UPDATE users SET first_name=?, username=? WHERE user_id=?",
                (first_name, username, user_id),
            )
            await db.commit()

    async def get_stats(self, user_id: int) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT first_name, msg_count, joined_at FROM users WHERE user_id=?",
                (user_id,),
            ) as cur:
                row = await cur.fetchone()
        return {"name": row[0], "messages": row[1], "since": row[2]} if row else {}

    async def list_all_users(self) -> list[dict]:
        """برای پنل ادمین — همه‌ی کاربرها با آمار پایه، جدیدترین‌ها اول."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, first_name, username, msg_count, joined_at
                FROM users ORDER BY joined_at DESC
            """) as cur:
                rows = await cur.fetchall()
        return [
            {"user_id": r[0], "first_name": r[1], "username": r[2], "messages": r[3], "since": r[4]}
            for r in rows
        ]

    async def total_stats(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*), COALESCE(SUM(msg_count),0) FROM users") as cur:
                row = await cur.fetchone()
        return {"total_users": row[0], "total_messages": row[1]}

    # ── Messages ─────────────────────────────────────────────────────────────

    async def add_message(self, user_id: int, role: str, content: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (user_id, role, content) VALUES (?,?,?)",
                (user_id, role, content),
            )
            await db.execute("UPDATE users SET msg_count = msg_count + 1 WHERE user_id=?", (user_id,))
            keep = MAX_HISTORY * 2
            await db.execute("""
                DELETE FROM messages
                WHERE user_id=? AND id NOT IN (
                    SELECT id FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?
                )
            """, (user_id, user_id, keep))
            await db.commit()

    async def get_history(self, user_id: int) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role, content FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, MAX_HISTORY),
            ) as cur:
                rows = await cur.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    async def clear_history(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
            await db.commit()

    # ── Facts ────────────────────────────────────────────────────────────────

    async def get_facts(self, user_id: int) -> list[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT fact FROM facts WHERE user_id=? ORDER BY ts DESC LIMIT ?",
                (user_id, MAX_FACTS),
            ) as cur:
                rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def save_fact(self, user_id: int, fact: str):
        fact = fact.strip()
        if not fact or len(fact) > 150:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO facts (user_id, fact) VALUES (?,?)", (user_id, fact))
            await db.commit()

    async def clear_facts(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM facts WHERE user_id=?", (user_id,))
            await db.commit()

    async def extract_and_save_facts(self, user_id: int, text: str):
        for fact in extract_facts(text):
            await self.save_fact(user_id, fact)
            logger.debug(f"💡 Learned fact for {user_id}: {fact}")
