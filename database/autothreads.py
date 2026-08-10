# database/autothreads.py
import asyncpg
from database.database import db

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS autothreads (
    id SERIAL PRIMARY KEY,
    thread_id BIGINT NOT NULL,
    parent_channel_id BIGINT NOT NULL,
    parent_message_id BIGINT,
    thread_type BIGINT NOT NULL,
    owner_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_autothreads_table():
    """
    Ensure the autothreads table exists. Call this once during startup
    after db.connect() and before any restore calls.
    """
    async with db.pool.acquire() as conn:
        await conn.execute(CREATE_TABLE_SQL)

async def add_autothread(thread_id, parent_channel_id, parent_message_id, thread_type, owner_id=None):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO autothreads (thread_id, parent_channel_id, parent_message_id, thread_type, owner_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            thread_id,
            parent_channel_id,
            parent_message_id,
            thread_type,
            owner_id
        )

async def get_all_autothreads():
    """
    Return all autothreads rows. If the table doesn't exist yet,
    return an empty list instead of raising.
    """
    async with db.pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT thread_id, parent_channel_id, parent_message_id, thread_type, owner_id
                FROM autothreads
                """
            )
            return rows
        except asyncpg.exceptions.UndefinedTableError:
            # Table not created yet — treat as empty
            return []

async def remove_autothread(thread_id):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM autothreads
            WHERE thread_id = $1
            """,
            thread_id
        )
