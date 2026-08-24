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

    async def run_migrations(self):
        return

    # --------------------------------------------------
    # GUILD SETTINGS
    # --------------------------------------------------

    async def get_guild_settings(
        self,
        guild_id: int
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
                    staff_role,
                    admin_role,
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
                "marriage_channel": row["marriage_channel"],
                "relationship_channel": row["relationship_channel"],
                "ticket_category": row["ticket_category"],

                # Your current database table does not appear
                # to contain an enforce_only_post column.
                # Keep this key available for other code.
                "enforce_only_post": False,
            }

    async def upsert_guild_settings(
        self,
        guild_id: int,
        log_channel_id: int | None = None,
        admin_role_id: int | None = None,
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
                    marriage_channel,
                    relationship_channel
                )
                VALUES ($1, $2, $3, $4, $5)

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
                marriage_channel_id,
                relationship_channel_id,
            )


# --------------------------------------------------
# SHARED DATABASE INSTANCE
# --------------------------------------------------

db = Database()
