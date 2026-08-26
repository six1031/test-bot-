# database/tickets.py

import asyncio

from database.database import db


# ==================================================
# INITIALIZATION
# ==================================================

_tables_ready = False
_tables_lock = asyncio.Lock()


async def init_ticket_tables():
    """
    Make the existing tickets table compatible with the ticket cog.

    Fixes older databases where channel_id existed but was not
    UNIQUE / PRIMARY KEY, which causes PostgreSQL to reject:

        ON CONFLICT (channel_id)

    with:
        there is no unique or exclusion constraint matching
        the ON CONFLICT specification
    """

    global _tables_ready

    if _tables_ready:
        return

    async with _tables_lock:
        if _tables_ready:
            return

        # --------------------------------------------------
        # CREATE TABLE IF IT DOESN'T EXIST
        # --------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                channel_id BIGINT PRIMARY KEY,
                guild_id BIGINT,
                owner_id BIGINT NOT NULL,
                ticket_type TEXT NOT NULL,
                closed BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )

        # --------------------------------------------------
        # MIGRATE OLDER TABLE SHAPES
        # --------------------------------------------------

        await db.execute(
            """
            ALTER TABLE tickets
            ADD COLUMN IF NOT EXISTS guild_id BIGINT
            """
        )

        await db.execute(
            """
            ALTER TABLE tickets
            ADD COLUMN IF NOT EXISTS closed
            BOOLEAN NOT NULL DEFAULT FALSE
            """
        )

        # --------------------------------------------------
        # REMOVE ANY ACCIDENTAL DUPLICATE CHANNEL IDS
        #
        # Discord channel IDs are globally unique, so there should
        # only ever be one ticket row for a channel.
        # --------------------------------------------------

        await db.execute(
            """
            DELETE FROM tickets a
            USING tickets b
            WHERE a.ctid < b.ctid
              AND a.channel_id = b.channel_id
            """
        )

        # --------------------------------------------------
        # CRITICAL FIX
        #
        # PostgreSQL requires a UNIQUE / PRIMARY KEY constraint
        # matching the ON CONFLICT target.
        # --------------------------------------------------

        await db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            tickets_channel_id_unique
            ON tickets (channel_id)
            """
        )

        # Useful lookup index for "one open ticket per type".
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            tickets_open_lookup_idx
            ON tickets (
                guild_id,
                owner_id,
                ticket_type,
                closed
            )
            """
        )

        _tables_ready = True


# ==================================================
# CREATE / SAVE TICKET
# ==================================================

async def create_ticket(
    guild_id: int,
    channel_id: int,
    owner_id: int,
    ticket_type: str,
):
    await init_ticket_tables()

    await db.execute(
        """
        INSERT INTO tickets (
            guild_id,
            channel_id,
            owner_id,
            ticket_type,
            closed
        )
        VALUES (
            $1,
            $2,
            $3,
            $4,
            FALSE
        )
        ON CONFLICT (channel_id)
        DO UPDATE SET
            guild_id = EXCLUDED.guild_id,
            owner_id = EXCLUDED.owner_id,
            ticket_type = EXCLUDED.ticket_type,
            closed = FALSE
        """,
        guild_id,
        channel_id,
        owner_id,
        ticket_type,
    )

    return True


# ==================================================
# OPEN TICKET LOOKUP
# ==================================================

async def get_open_ticket(
    guild_id: int,
    owner_id: int,
    ticket_type: str,
):
    await init_ticket_tables()

    return await db.fetchrow(
        """
        SELECT
            guild_id,
            channel_id,
            owner_id,
            ticket_type,
            closed
        FROM tickets
        WHERE guild_id = $1
          AND owner_id = $2
          AND ticket_type = $3
          AND closed = FALSE
        ORDER BY channel_id DESC
        LIMIT 1
        """,
        guild_id,
        owner_id,
        ticket_type,
    )


async def has_open_ticket(
    guild_id: int,
    owner_id: int,
    ticket_type: str,
) -> bool:
    row = await get_open_ticket(
        guild_id,
        owner_id,
        ticket_type,
    )

    return row is not None


# ==================================================
# CLOSE TICKET
# ==================================================

async def close_ticket(
    channel_id: int,
):
    await init_ticket_tables()

    await db.execute(
        """
        UPDATE tickets
        SET closed = TRUE
        WHERE channel_id = $1
        """,
        channel_id,
    )

    return True


# ==================================================
# OPTIONAL CLEANUP
# ==================================================

async def delete_ticket_record(
    channel_id: int,
):
    """
    Permanently remove a ticket row.

    Normal ticket closing should use close_ticket() so history
    remains available.
    """

    await init_ticket_tables()

    await db.execute(
        """
        DELETE FROM tickets
        WHERE channel_id = $1
        """,
        channel_id,
    )


async def get_guild_open_tickets(
    guild_id: int,
):
    await init_ticket_tables()

    return await db.fetch(
        """
        SELECT
            guild_id,
            channel_id,
            owner_id,
            ticket_type,
            closed
        FROM tickets
        WHERE guild_id = $1
          AND closed = FALSE
        ORDER BY channel_id ASC
        """,
        guild_id,
    )
