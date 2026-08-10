from database.database import db

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
    async with db.pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT thread_id, parent_channel_id, parent_message_id, thread_type, owner_id
            FROM autothreads
            """
        )

async def remove_autothread(thread_id):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM autothreads
            WHERE thread_id = $1
            """,
            thread_id
        )
