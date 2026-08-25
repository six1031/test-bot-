# database/autothreads.py

import asyncpg

from database.database import db


# --------------------------------------------------
# TABLE SETUP
# --------------------------------------------------

AUTOTHREADS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS autothreads (
    id SERIAL PRIMARY KEY,
    thread_id BIGINT NOT NULL,
    guild_id BIGINT,
    parent_channel_id BIGINT NOT NULL,
    parent_message_id BIGINT,
    thread_type BIGINT NOT NULL DEFAULT 0,
    owner_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


AUTOTHREAD_CONFIGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS autothread_configs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    auto_archive_duration INTEGER NOT NULL DEFAULT 1440,
    include_bots BOOLEAN NOT NULL DEFAULT TRUE,
    thread_name_format TEXT NOT NULL DEFAULT '{message}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (guild_id, channel_id)
);
"""


async def init_autothreads_table():
    """
    Ensure all autothread tables and columns exist.
    """

    if not db.pool:
        raise RuntimeError(
            "Database pool is not initialized. Call db.connect() first."
        )

    async with db.pool.acquire() as conn:

        # Existing thread records
        await conn.execute(
            AUTOTHREADS_TABLE_SQL
        )

        # Add guild_id to older autothreads tables
        await conn.execute(
            """
            ALTER TABLE autothreads
            ADD COLUMN IF NOT EXISTS guild_id BIGINT
            """
        )

        # Configured auto-thread channels
        await conn.execute(
            AUTOTHREAD_CONFIGS_TABLE_SQL
        )

        # --------------------------------------------------
        # MIGRATE EXISTING CONFIG TABLE
        # --------------------------------------------------

        await conn.execute(
            """
            ALTER TABLE autothread_configs
            ADD COLUMN IF NOT EXISTS include_bots
            BOOLEAN NOT NULL DEFAULT TRUE
            """
        )

        await conn.execute(
            """
            ALTER TABLE autothread_configs
            ADD COLUMN IF NOT EXISTS thread_name_format
            TEXT NOT NULL DEFAULT '{message}'
            """
        )


# --------------------------------------------------
# AUTO-THREAD CONFIGURATION
# --------------------------------------------------

async def add_autothread_config(
    guild_id: int,
    channel_id: int,
    auto_archive_duration: int = 1440,
    include_bots: bool = True,
    thread_name_format: str = "{message}",
):
    """
    Add or update a channel that should automatically
    create threads when messages are posted.
    """

    async with db.pool.acquire() as conn:

        await conn.execute(
            """
            INSERT INTO autothread_configs (
                guild_id,
                channel_id,
                auto_archive_duration,
                include_bots,
                thread_name_format
            )
            VALUES ($1, $2, $3, $4, $5)

            ON CONFLICT (guild_id, channel_id)
            DO UPDATE SET
                auto_archive_duration =
                    EXCLUDED.auto_archive_duration,
                include_bots =
                    EXCLUDED.include_bots,
                thread_name_format =
                    EXCLUDED.thread_name_format
            """,
            guild_id,
            channel_id,
            auto_archive_duration,
            include_bots,
            thread_name_format,
        )


async def update_autothread_config(
    guild_id: int,
    channel_id: int,
    auto_archive_duration: int | None = None,
    include_bots: bool | None = None,
    thread_name_format: str | None = None,
):
    """
    Update an existing autothread channel.

    Only supplied settings are changed.
    """

    async with db.pool.acquire() as conn:

        existing = await conn.fetchrow(
            """
            SELECT
                auto_archive_duration,
                include_bots,
                thread_name_format
            FROM autothread_configs
            WHERE guild_id = $1
              AND channel_id = $2
            """,
            guild_id,
            channel_id,
        )

        if not existing:
            return False

        new_archive_duration = (
            auto_archive_duration
            if auto_archive_duration is not None
            else existing["auto_archive_duration"]
        )

        new_include_bots = (
            include_bots
            if include_bots is not None
            else existing["include_bots"]
        )

        new_thread_name_format = (
            thread_name_format
            if thread_name_format is not None
            else existing["thread_name_format"]
        )

        await conn.execute(
            """
            UPDATE autothread_configs
            SET
                auto_archive_duration = $3,
                include_bots = $4,
                thread_name_format = $5
            WHERE guild_id = $1
              AND channel_id = $2
            """,
            guild_id,
            channel_id,
            new_archive_duration,
            new_include_bots,
            new_thread_name_format,
        )

        return True


async def get_autothread_configs(
    guild_id: int | None = None,
):
    """
    Get configured auto-thread channels.

    If guild_id is supplied, only return that server's
    configurations.
    """

    async with db.pool.acquire() as conn:

        if guild_id is not None:

            return await conn.fetch(
                """
                SELECT
                    id,
                    guild_id,
                    channel_id,
                    auto_archive_duration,
                    include_bots,
                    thread_name_format,
                    created_at
                FROM autothread_configs
                WHERE guild_id = $1
                ORDER BY id
                """,
                guild_id,
            )

        return await conn.fetch(
            """
            SELECT
                id,
                guild_id,
                channel_id,
                auto_archive_duration,
                include_bots,
                thread_name_format,
                created_at
            FROM autothread_configs
            ORDER BY guild_id, id
            """
        )


async def get_autothread_config(
    guild_id: int,
    channel_id: int,
):
    """
    Get one auto-thread channel configuration.
    """

    async with db.pool.acquire() as conn:

        return await conn.fetchrow(
            """
            SELECT
                id,
                guild_id,
                channel_id,
                auto_archive_duration,
                include_bots,
                thread_name_format,
                created_at
            FROM autothread_configs
            WHERE guild_id = $1
              AND channel_id = $2
            """,
            guild_id,
            channel_id,
        )


async def remove_autothread_config(
    guild_id: int,
    channel_id: int,
):
    """
    Stop a channel from automatically creating threads.
    """

    async with db.pool.acquire() as conn:

        return await conn.execute(
            """
            DELETE FROM autothread_configs
            WHERE guild_id = $1
              AND channel_id = $2
            """,
            guild_id,
            channel_id,
        )


# --------------------------------------------------
# CREATED THREAD RECORDS
# --------------------------------------------------

async def add_autothread(
    thread_id: int,
    parent_channel_id: int,
    parent_message_id: int | None,
    thread_type: int = 0,
    owner_id: int | None = None,
    guild_id: int | None = None,
):
    """
    Save an actual Discord thread that has been created.
    """

    async with db.pool.acquire() as conn:

        await conn.execute(
            """
            INSERT INTO autothreads (
                thread_id,
                guild_id,
                parent_channel_id,
                parent_message_id,
                thread_type,
                owner_id
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            thread_id,
            guild_id,
            parent_channel_id,
            parent_message_id,
            thread_type,
            owner_id,
        )


async def get_all_autothreads(
    guild_id: int | None = None,
):
    """
    Return actual created autothread records.

    Existing bot.py code can continue calling this
    without supplying guild_id.
    """

    async with db.pool.acquire() as conn:

        try:

            if guild_id is not None:

                return await conn.fetch(
                    """
                    SELECT
                        thread_id,
                        guild_id,
                        parent_channel_id,
                        parent_message_id,
                        thread_type,
                        owner_id
                    FROM autothreads
                    WHERE guild_id = $1
                    """,
                    guild_id,
                )

            return await conn.fetch(
                """
                SELECT
                    thread_id,
                    guild_id,
                    parent_channel_id,
                    parent_message_id,
                    thread_type,
                    owner_id
                FROM autothreads
                """
            )

        except asyncpg.exceptions.UndefinedTableError:
            return []


async def remove_autothread(
    thread_id: int,
):
    """
    Remove a stored thread record.
    """

    async with db.pool.acquire() as conn:

        await conn.execute(
            """
            DELETE FROM autothreads
            WHERE thread_id = $1
            """,
            thread_id,
        )
