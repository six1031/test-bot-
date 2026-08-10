# database/database.py
import os
import asyncpg
import asyncio
from typing import Optional

class Database:
    def __init__(self):
        self.pool: asyncpg.pool.Pool | None = None
        self._dsn = os.getenv("DATABASE_URL")  # e.g. postgres://user:pass@host:5432/dbname

    async def connect(self, min_size: int = 1, max_size: int = 10):
        if not self._dsn:
            raise RuntimeError("DATABASE_URL environment variable is not set.")
        if self.pool:
            return
        self.pool = await asyncpg.create_pool(dsn=self._dsn, min_size=min_size, max_size=max_size)

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def execute(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database pool is not initialized. Call db.connect() first.")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database pool is not initialized. Call db.connect() first.")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        if not self.pool:
            raise RuntimeError("Database pool is not initialized. Call db.connect() first.")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def run_migrations(self):
        return

    # -------------------------
    # Guild settings helpers
    # -------------------------
    async def get_guild_settings(self, guild_id: int) -> Optional[dict]:
        """
        Return a dict of settings for the guild, or None if not found.
        Keys returned: guild_id, log_channel, admin_role, marriage_channel, relationship_channel, enforce_only_post
        """
        if not self.pool:
            raise RuntimeError("Database pool is not initialized. Call db.connect() first.")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT guild_id, log_channel_id, admin_role_id, marriage_channel_id, relationship_channel_id, enforce_only_post
                FROM guild_settings
                WHERE guild_id = $1
                """,
                guild_id
            )
            if not row:
                return None
            return {
                "guild_id": row["guild_id"],
                "log_channel": row["log_channel_id"],
                "admin_role": row["admin_role_id"],
                "marriage_channel": row["marriage_channel_id"],
                "relationship_channel": row["relationship_channel_id"],
                "enforce_only_post": row["enforce_only_post"],
            }

    async def upsert_guild_settings(
        self,
        guild_id: int,
        log_channel_id: int | None = None,
        admin_role_id: int | None = None,
        marriage_channel_id: int | None = None,
        relationship_channel_id: int | None = None,
        enforce_only_post: bool = False
    ):
        """
        Insert or update guild settings.
        """
        if not self.pool:
            raise RuntimeError("Database pool is not initialized. Call db.connect() first.")
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO guild_settings (guild_id, log_channel_id, admin_role_id, marriage_channel_id, relationship_channel_id, enforce_only_post)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (guild_id) DO UPDATE
                SET log_channel_id = COALESCE(EXCLUDED.log_channel_id, guild_settings.log_channel_id),
                    admin_role_id = COALESCE(EXCLUDED.admin_role_id, guild_settings.admin_role_id),
                    marriage_channel_id = COALESCE(EXCLUDED.marriage_channel_id, guild_settings.marriage_channel_id),
                    relationship_channel_id = COALESCE(EXCLUDED.relationship_channel_id, guild_settings.relationship_channel_id),
                    enforce_only_post = EXCLUDED.enforce_only_post,
                    updated_at = now()
                """,
                guild_id, log_channel_id, admin_role_id, marriage_channel_id, relationship_channel_id, enforce_only_post
            )

# single shared instance used across the project
db = Database()
