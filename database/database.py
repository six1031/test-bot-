# database/database.py
import os
import asyncpg
import asyncio

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
        # Optional: run migrations or ensure tables here if you want
        # await self.run_migrations()

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def execute(self, query: str, *args):
        """
        Execute a statement (INSERT/UPDATE/DELETE). Returns command status.
        """
        if not self.pool:
            raise RuntimeError("Database pool is not initialized. Call db.connect() first.")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        """
        Fetch multiple rows. Returns a list of Record objects.
        """
        if not self.pool:
            raise RuntimeError("Database pool is not initialized. Call db.connect() first.")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """
        Fetch a single row. Returns a Record or None.
        """
        if not self.pool:
            raise RuntimeError("Database pool is not initialized. Call db.connect() first.")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def run_migrations(self):
        """
        Hook to run DB migrations or ensure tables exist.
        Keep this minimal or call your external migration tool here.
        Example usage: call this after db.connect() in startup.
        """
        # Example: create a minimal autothreads table if you want to ensure it here.
        # Commented out because we already have init_autothreads_table in autothreads.py
        # async with self.pool.acquire() as conn:
        #     await conn.execute("""
        #     CREATE TABLE IF NOT EXISTS autothreads (
        #         id SERIAL PRIMARY KEY,
        #         thread_id BIGINT NOT NULL,
        #         parent_channel_id BIGINT NOT NULL,
        #         parent_message_id BIGINT,
        #         thread_type BIGINT NOT NULL,
        #         owner_id BIGINT,
        #         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        #     );
        #     """)
        return

# single shared instance used across the project
db = Database()
