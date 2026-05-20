"""
core/memory.py
==============
Memória de curto prazo (RAM) + longo prazo (SQLite).

NOVO: o buffer de curto prazo agora é persistido no banco.
Ao iniciar, o bot recarrega as últimas mensagens de cada canal
para não começar "do zero" após reiniciar.
"""

import json
import time
import aiosqlite
from dataclasses import dataclass
from collections import deque
from config import settings

DB_PATH = "data/memory.db"


@dataclass
class Message:
    author_id: int
    author_name: str
    content: str
    timestamp: float


@dataclass
class UserProfile:
    user_id: int
    username: str
    writing_samples: list[str]
    known_interests: list[str]
    interaction_count: int
    last_seen: float


_channel_buffers: dict[int, deque[Message]] = {}


def add_message(channel_id: int, msg: Message):
    if channel_id not in _channel_buffers:
        _channel_buffers[channel_id] = deque(maxlen=settings.CONTEXT_WINDOW_SIZE)
    _channel_buffers[channel_id].append(msg)


def get_recent_messages(channel_id: int, n: int = None) -> list[Message]:
    buf  = _channel_buffers.get(channel_id, deque())
    msgs = list(buf)
    return msgs[-n:] if n else msgs


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id           INTEGER PRIMARY KEY,
                username          TEXT,
                writing_samples   TEXT,
                known_interests   TEXT,
                interaction_count INTEGER DEFAULT 0,
                last_seen         REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS interaction_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                user_id    INTEGER,
                user_msg   TEXT,
                bot_reply  TEXT,
                timestamp  REAL
            )
        """)
        # Tabela nova: persiste o buffer de mensagens por canal
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channel_buffer (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id  INTEGER,
                author_id   INTEGER,
                author_name TEXT,
                content     TEXT,
                timestamp   REAL
            )
        """)
        await db.commit()
    print("[MEMORY] Banco de dados inicializado")


async def save_buffer(channel_id: int):
    """
    Salva o buffer atual do canal no banco.
    Sobrescreve as mensagens antigas desse canal.
    """
    msgs = get_recent_messages(channel_id)
    if not msgs:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        # Remove as mensagens antigas desse canal
        await db.execute(
            "DELETE FROM channel_buffer WHERE channel_id = ?", (channel_id,)
        )
        # Insere as mensagens atuais
        for msg in msgs:
            await db.execute("""
                INSERT INTO channel_buffer (channel_id, author_id, author_name, content, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (channel_id, msg.author_id, msg.author_name, msg.content, msg.timestamp))
        await db.commit()


async def load_buffer(channel_id: int):
    """
    Recarrega o buffer de um canal do banco ao iniciar.
    Assim o bot lembra das conversas anteriores ao reiniciar.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM channel_buffer
            WHERE channel_id = ?
            ORDER BY timestamp ASC
        """, (channel_id,)) as cur:
            rows = await cur.fetchall()

    if not rows:
        return

    for row in rows:
        msg = Message(
            author_id=row["author_id"],
            author_name=row["author_name"],
            content=row["content"],
            timestamp=row["timestamp"],
        )
        add_message(channel_id, msg)

    print(f"[MEMORY] Canal {channel_id}: {len(rows)} mensagens recarregadas do banco")


async def save_all_buffers():
    """Salva todos os buffers ativos. Chamado ao desligar o bot."""
    for channel_id in _channel_buffers:
        await save_buffer(channel_id)
    print(f"[MEMORY] {len(_channel_buffers)} canal(is) salvos no banco")


async def get_user_profile(user_id: int, username: str) -> UserProfile:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()

    if row:
        return UserProfile(
            user_id=row["user_id"],
            username=row["username"],
            writing_samples=json.loads(row["writing_samples"] or "[]"),
            known_interests=json.loads(row["known_interests"] or "[]"),
            interaction_count=row["interaction_count"],
            last_seen=row["last_seen"],
        )
    return UserProfile(user_id=user_id, username=username,
                       writing_samples=[], known_interests=[],
                       interaction_count=0, last_seen=time.time())


async def update_user_profile(profile: UserProfile):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO user_profiles
                (user_id, username, writing_samples, known_interests, interaction_count, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            profile.user_id,
            profile.username,
            json.dumps(profile.writing_samples, ensure_ascii=False),
            json.dumps(profile.known_interests, ensure_ascii=False),
            profile.interaction_count,
            profile.last_seen,
        ))
        await db.commit()


async def learn_from_message(user_id: int, username: str, message_text: str):
    profile = await get_user_profile(user_id, username)
    profile.writing_samples.append(message_text)
    if len(profile.writing_samples) > 50:
        profile.writing_samples = profile.writing_samples[-50:]
    profile.last_seen = time.time()
    await update_user_profile(profile)


async def log_interaction(channel_id: int, user_id: int, user_msg: str, bot_reply: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO interaction_log (channel_id, user_id, user_msg, bot_reply, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (channel_id, user_id, user_msg, bot_reply, time.time()))
        await db.commit()
