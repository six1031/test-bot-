# database/database.py

import os
import asyncpg
from typing import Optional


class Database:
    def __init__(self):
        self.pool: asyncpg.pool.Pool | None = None
        self._dsn = os.getenv("DATABASE_URL")

    # --------------------------------------------------
    # CONNECTION
    # --------------------------------------------------

    async def connect(self, min_size: int = 1, max_size: int = 10):
        if not self._dsn:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set."
            )

        if self.pool:
            return

        self.pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=min_size,
            max_size=max_size,
        )

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    # --------------------------------------------------
    # BASIC DATABASE HELPERS
    # --------------------------------------------------

    async def execute(self, query: str, *args):
        if not self.pool:
            raise RuntimeError(
                "Database pool is not initialized. Call db.connect() first."
            )

        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        if not self.pool:
            raise RuntimeError(
                "Database pool is not initialized. Call db.connect() first."
            )

        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        if not self.pool:
            raise RuntimeError(
                "Database pool is not initialized. Call db.connect() first."
            )

        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    # --------------------------------------------------
    # DATABASE MIGRATIONS
    # --------------------------------------------------

    async def run_migrations(self):

        # Ticket panel storage
        await self.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_panels (
                message_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                panel_type TEXT NOT NULL
            )
            """
        )

        # Remove any old duplicate panel records
        await self.execute(
            """
            DELETE FROM ticket_panels a
            USING ticket_panels b
            WHERE a.ctid < b.ctid
              AND a.message_id = b.message_id
            """
        )

        # Older versions of the table may not have had
        # message_id marked as unique.
        await self.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            ticket_panels_message_id_unique
            ON ticket_panels (message_id)
            """
        )

        # Ticket storage
        await self.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                channel_id BIGINT PRIMARY KEY,
                owner_id BIGINT NOT NULL,
                ticket_type TEXT NOT NULL,
                closed BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )      
        await self.execute(
            """
            ALTER TABLE tickets
            ADD COLUMN IF NOT EXISTS closed BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
                await self.execute(
            """
            ALTER TABLE tickets
            ADD COLUMN IF NOT EXISTS guild_id BIGINT
            """
        )

    # --------------------------------------------------
    # TICKET PANELS
    # --------------------------------------------------

    async def add_ticket_panel(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        panel_type: str,
    ):
        await self.execute(
            """
            INSERT INTO ticket_panels (
                guild_id,
                channel_id,
                message_id,
                panel_type
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (message_id) DO NOTHING
            """,
            guild_id,
            channel_id,
            message_id,
            panel_type,
        )

    async def get_ticket_panels(self):
        return await self.fetch(
            """
            SELECT
                guild_id,
                channel_id,
                message_id,
                panel_type
            FROM ticket_panels
            """
        )

    async def remove_ticket_panel(self, message_id: int):
        await self.execute(
            """
            DELETE FROM ticket_panels
            WHERE message_id = $1
            """,
            message_id,
        )

    # --------------------------------------------------
    # TICKETS
    # --------------------------------------------------

    async def create_ticket(
        self,
        channel_id: int,
        owner_id: int,
        ticket_type: str,
    ):
        await self.execute(
            """
            INSERT INTO tickets (
                channel_id,
                owner_id,
                ticket_type,
                closed
            )
            VALUES ($1, $2, $3, FALSE)
            ON CONFLICT (channel_id)
            DO UPDATE SET
                owner_id = EXCLUDED.owner_id,
                ticket_type = EXCLUDED.ticket_type,
                closed = FALSE
            """,
            channel_id,
            owner_id,
            ticket_type,
        )

    async def close_ticket(self, channel_id: int):
        await self.execute(
            """
            UPDATE tickets
            SET closed = TRUE
            WHERE channel_id = $1
            """,
            channel_id,
        )

    async def get_open_ticket(
        self,
        owner_id: int,
        ticket_type: str,
    ):
        return await self.fetchrow(
            """
            SELECT
                channel_id,
                owner_id,
                ticket_type,
                closed
            FROM tickets
            WHERE owner_id = $1
              AND ticket_type = $2
              AND closed = FALSE
            LIMIT 1
            """,
            owner_id,
            ticket_type,
        )

    # --------------------------------------------------
    # GUILD SETTINGS
    # --------------------------------------------------

    async def get_guild_settings(
        self,
        guild_id: int,
    ) -> Optional[dict]:

        if not self.pool:
            raise RuntimeError(
                "Database pool is not initialized. Call db.connect() first."
            )

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    guild_id,
                    log_channel,
                    admin_role,
                    staff_role,
                    marriage_channel,
                    relationship_channel,
                    ticket_category
                FROM guild_settings
                WHERE guild_id = $1
                """,
                guild_id,
            )

            if not row:
                return None

            return {
                "guild_id": row["guild_id"],
                "log_channel": row["log_channel"],
                "admin_role": row["admin_role"],
                "staff_role": row["staff_role"],
                "marriage_channel": row["marriage_channel"],
                "relationship_channel": row["relationship_channel"],
                "ticket_category": row["ticket_category"],
                "enforce_only_post": False,
            }

    async def upsert_guild_settings(
        self,
        guild_id: int,
        log_channel_id: int | None = None,
        admin_role_id: int | None = None,
        staff_role_id: int | None = None,
        ticket_category_id: int | None = None,
        marriage_channel_id: int | None = None,
        relationship_channel_id: int | None = None,
        enforce_only_post: bool = False,
    ):

        if not self.pool:
            raise RuntimeError(
                "Database pool is not initialized. Call db.connect() first."
            )

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO guild_settings (
                    guild_id,
                    log_channel,
                    admin_role,
                    staff_role,
                    ticket_category,
                    marriage_channel,
                    relationship_channel
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)

                ON CONFLICT (guild_id)
                DO UPDATE SET

                    log_channel = COALESCE(
                        EXCLUDED.log_channel,
                        guild_settings.log_channel
                    ),

                    admin_role = COALESCE(
                        EXCLUDED.admin_role,
                        guild_settings.admin_role
                    ),

                    staff_role = COALESCE(
                        EXCLUDED.staff_role,
                        guild_settings.staff_role
                    ),

                    ticket_category = COALESCE(
                        EXCLUDED.ticket_category,
                        guild_settings.ticket_category
                    ),

                    marriage_channel = COALESCE(
                        EXCLUDED.marriage_channel,
                        guild_settings.marriage_channel
                    ),

                    relationship_channel = COALESCE(
                        EXCLUDED.relationship_channel,
                        guild_settings.relationship_channel
                    )
                """,
                guild_id,
                log_channel_id,
                admin_role_id,
                staff_role_id,
                ticket_category_id,
                marriage_channel_id,
                relationship_channel_id,
            )


# --------------------------------------------------
# SHARED DATABASE INSTANCE
# --------------------------------------------------

db = Database()
