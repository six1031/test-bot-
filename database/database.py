import os
import asyncpg


class Database:
    def __init__(self):
        self.pool = None

    # --------------------------------------------------
    # CONNECTION
    # --------------------------------------------------

    async def connect(self):
        if self.pool:
            return

        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise RuntimeError("DATABASE_URL was not found.")

        self.pool = await asyncpg.create_pool(database_url)

        print("✅ Connected to PostgreSQL")

        await self.create_tables()

    async def close(self):
        if self.pool:
            await self.pool.close()
            print("🔒 Database disconnected.")

    # --------------------------------------------------
    # TABLES
    # --------------------------------------------------

    async def create_tables(self):

        async with self.pool.acquire() as conn:

            await conn.execute("""

            CREATE TABLE IF NOT EXISTS ticket_panels (

                id SERIAL PRIMARY KEY,

                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,

                panel_type TEXT NOT NULL

            );

            """)

            await conn.execute("""

            CREATE TABLE IF NOT EXISTS tickets (

                id SERIAL PRIMARY KEY,

                channel_id BIGINT NOT NULL,
                owner_id BIGINT NOT NULL,

                ticket_type TEXT NOT NULL,

                status TEXT DEFAULT 'open',

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            );

            """)
            await conn.execute("""

            CREATE TABLE IF NOT EXISTS game_state (

                guild_id BIGINT PRIMARY KEY,

                counting_channel BIGINT,
                counting_enabled BOOLEAN DEFAULT TRUE,
                current_count INTEGER DEFAULT 0,
                last_counter BIGINT,

                wordchain_channel BIGINT,
                wordchain_enabled BOOLEAN DEFAULT TRUE,
                last_word TEXT DEFAULT '',
                used_words TEXT[] DEFAULT '{}',
                word_last_counter BIGINT

            );

            """)

            await conn.execute("""

            CREATE TABLE IF NOT EXISTS relationships (

                id SERIAL PRIMARY KEY,

                user_id BIGINT NOT NULL,
                partner_id BIGINT NOT NULL,

                relationship_type TEXT NOT NULL

            );

            """)

            await conn.execute("""

            CREATE TABLE IF NOT EXISTS marriages (

                id SERIAL PRIMARY KEY,

                user1_id BIGINT NOT NULL,
                user2_id BIGINT NOT NULL,

                married_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            );

            """)

        print("✅ Database tables ready.")

    # ==================================================
    # TICKET PANEL FUNCTIONS
    # ==================================================

    async def add_ticket_panel(
        self,
        guild_id,
        channel_id,
        message_id,
        panel_type
    ):

        async with self.pool.acquire() as conn:

            await conn.execute("""

                INSERT INTO ticket_panels
                (guild_id, channel_id, message_id, panel_type)

                VALUES ($1,$2,$3,$4)

            """,
            guild_id,
            channel_id,
            message_id,
            panel_type
            )

    async def get_ticket_panels(self):

        async with self.pool.acquire() as conn:

            rows = await conn.fetch("""

                SELECT *

                FROM ticket_panels

            """)

            return rows

    async def remove_ticket_panel(
        self,
        message_id
    ):

        async with self.pool.acquire() as conn:

            await conn.execute("""

                DELETE FROM ticket_panels

                WHERE message_id=$1

            """,
            message_id
            )

    # ==================================================
    # TICKET FUNCTIONS
    # ==================================================

    async def create_ticket(
        self,
        channel_id,
        owner_id,
        ticket_type
    ):

        async with self.pool.acquire() as conn:

            await conn.execute("""

                INSERT INTO tickets
                (channel_id, owner_id, ticket_type)

                VALUES ($1,$2,$3)

            """,
            channel_id,
            owner_id,
            ticket_type
            )

    async def close_ticket(
        self,
        channel_id
    ):

        async with self.pool.acquire() as conn:

            await conn.execute("""

                UPDATE tickets

                SET status='closed'

                WHERE channel_id=$1

            """,
            channel_id
            )

    async def get_open_ticket(
        self,
        owner_id,
        ticket_type
    ):

        async with self.pool.acquire() as conn:

            return await conn.fetchrow("""

                SELECT *

                FROM tickets

                WHERE owner_id=$1

                AND ticket_type=$2

                AND status='open'

            """,
            owner_id,
            ticket_type
            )


db = Database()
