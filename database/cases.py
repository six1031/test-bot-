# database/cases.py

import asyncio

from database.database import db


# ==================================================
# INITIALIZATION
# ==================================================

_tables_ready = False
_tables_lock = asyncio.Lock()


async def init_case_tables():
    """
    Create the moderation case tables.

    This uses the bot's existing PostgreSQL database.
    It does NOT create a second Railway database.
    """

    global _tables_ready

    if _tables_ready:
        return

    async with _tables_lock:
        if _tables_ready:
            return

        # --------------------------------------------------
        # PER-SERVER CASE SETTINGS
        # --------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_settings (
                guild_id BIGINT PRIMARY KEY,
                case_channel_id BIGINT
            )
            """
        )

        # --------------------------------------------------
        # ONE CASE PANEL / THREAD PER MEMBER
        # --------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS member_cases (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                member_id BIGINT NOT NULL,
                thread_id BIGINT,
                panel_message_id BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (
                    guild_id,
                    member_id
                )
            )
            """
        )

        # --------------------------------------------------
        # WARNINGS / NOTES / FUTURE MOD ACTIONS
        #
        # entry_type currently supports:
        # - warning
        # - note
        #
        # It is intentionally TEXT so timeout / kick / ban
        # entries can be added later without another migration.
        # --------------------------------------------------

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_entries (
                id BIGSERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                member_id BIGINT NOT NULL,
                entry_type TEXT NOT NULL,
                content TEXT NOT NULL,
                staff_id BIGINT NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                removed_by BIGINT,
                removed_at TIMESTAMPTZ
            )
            """
        )

        # --------------------------------------------------
        # INDEXES
        # --------------------------------------------------

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            member_cases_guild_member_idx
            ON member_cases (
                guild_id,
                member_id
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            case_entries_guild_member_idx
            ON case_entries (
                guild_id,
                member_id,
                created_at DESC
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            case_entries_active_warning_idx
            ON case_entries (
                guild_id,
                member_id,
                active
            )
            WHERE entry_type = 'warning'
            """
        )

        _tables_ready = True


# ==================================================
# CASE CHANNEL SETTINGS
# ==================================================

async def set_case_channel(
    guild_id: int,
    channel_id: int | None,
):
    await init_case_tables()

    await db.execute(
        """
        INSERT INTO case_settings (
            guild_id,
            case_channel_id
        )
        VALUES ($1, $2)
        ON CONFLICT (guild_id)
        DO UPDATE SET
            case_channel_id = EXCLUDED.case_channel_id
        """,
        guild_id,
        channel_id,
    )


async def get_case_settings(
    guild_id: int,
) -> dict:
    await init_case_tables()

    row = await db.fetchrow(
        """
        SELECT
            guild_id,
            case_channel_id
        FROM case_settings
        WHERE guild_id = $1
        """,
        guild_id,
    )

    if not row:
        return {
            "guild_id": guild_id,
            "case_channel_id": None,
        }

    return {
        "guild_id": row["guild_id"],
        "case_channel_id": row["case_channel_id"],
    }


# ==================================================
# MEMBER CASES
# ==================================================

async def get_member_case(
    guild_id: int,
    member_id: int,
):
    await init_case_tables()

    return await db.fetchrow(
        """
        SELECT
            id,
            guild_id,
            member_id,
            thread_id,
            panel_message_id,
            created_at,
            updated_at
        FROM member_cases
        WHERE guild_id = $1
          AND member_id = $2
        """,
        guild_id,
        member_id,
    )


async def get_member_case_by_panel_message(
    panel_message_id: int,
):
    await init_case_tables()

    return await db.fetchrow(
        """
        SELECT
            id,
            guild_id,
            member_id,
            thread_id,
            panel_message_id,
            created_at,
            updated_at
        FROM member_cases
        WHERE panel_message_id = $1
        """,
        panel_message_id,
    )


async def save_member_case(
    guild_id: int,
    member_id: int,
    thread_id: int | None,
    panel_message_id: int | None,
):
    """
    Create or update the member's case location.

    Each guild/member pair has exactly one case record.
    """

    await init_case_tables()

    return await db.fetchrow(
        """
        INSERT INTO member_cases (
            guild_id,
            member_id,
            thread_id,
            panel_message_id
        )
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (
            guild_id,
            member_id
        )
        DO UPDATE SET
            thread_id = EXCLUDED.thread_id,
            panel_message_id = EXCLUDED.panel_message_id,
            updated_at = NOW()
        RETURNING
            id,
            guild_id,
            member_id,
            thread_id,
            panel_message_id,
            created_at,
            updated_at
        """,
        guild_id,
        member_id,
        thread_id,
        panel_message_id,
    )


async def get_all_member_cases():
    """
    Used on bot startup to restore persistent case-panel buttons.
    """

    await init_case_tables()

    return await db.fetch(
        """
        SELECT
            id,
            guild_id,
            member_id,
            thread_id,
            panel_message_id,
            created_at,
            updated_at
        FROM member_cases
        WHERE panel_message_id IS NOT NULL
        ORDER BY id ASC
        """
    )


async def delete_member_case_location(
    guild_id: int,
    member_id: int,
):
    """
    Remove only the Discord thread/panel location record.

    Warning/note history remains untouched.
    """

    await init_case_tables()

    await db.execute(
        """
        DELETE FROM member_cases
        WHERE guild_id = $1
          AND member_id = $2
        """,
        guild_id,
        member_id,
    )


# ==================================================
# CASE ENTRIES
# ==================================================

async def add_case_entry(
    guild_id: int,
    member_id: int,
    entry_type: str,
    content: str,
    staff_id: int,
):
    await init_case_tables()

    entry_type = entry_type.strip().lower()
    content = content.strip()

    if not entry_type:
        raise ValueError(
            "entry_type cannot be empty"
        )

    if not content:
        raise ValueError(
            "content cannot be empty"
        )

    return await db.fetchrow(
        """
        INSERT INTO case_entries (
            guild_id,
            member_id,
            entry_type,
            content,
            staff_id
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING
            id,
            guild_id,
            member_id,
            entry_type,
            content,
            staff_id,
            active,
            created_at,
            removed_by,
            removed_at
        """,
        guild_id,
        member_id,
        entry_type,
        content,
        staff_id,
    )


async def get_case_entry(
    entry_id: int,
):
    await init_case_tables()

    return await db.fetchrow(
        """
        SELECT
            id,
            guild_id,
            member_id,
            entry_type,
            content,
            staff_id,
            active,
            created_at,
            removed_by,
            removed_at
        FROM case_entries
        WHERE id = $1
        """,
        entry_id,
    )


async def get_case_entries(
    guild_id: int,
    member_id: int,
    entry_type: str | None = None,
    active_only: bool = False,
    limit: int = 50,
):
    await init_case_tables()

    limit = max(
        1,
        min(
            int(limit),
            100,
        ),
    )

    if entry_type is not None:
        entry_type = (
            entry_type
            .strip()
            .lower()
        )

    return await db.fetch(
        """
        SELECT
            id,
            guild_id,
            member_id,
            entry_type,
            content,
            staff_id,
            active,
            created_at,
            removed_by,
            removed_at
        FROM case_entries
        WHERE guild_id = $1
          AND member_id = $2
          AND (
                $3::TEXT IS NULL
                OR entry_type = $3
          )
          AND (
                $4::BOOLEAN = FALSE
                OR active = TRUE
          )
        ORDER BY created_at DESC
        LIMIT $5
        """,
        guild_id,
        member_id,
        entry_type,
        active_only,
        limit,
    )


async def get_latest_case_entry(
    guild_id: int,
    member_id: int,
):
    await init_case_tables()

    return await db.fetchrow(
        """
        SELECT
            id,
            guild_id,
            member_id,
            entry_type,
            content,
            staff_id,
            active,
            created_at,
            removed_by,
            removed_at
        FROM case_entries
        WHERE guild_id = $1
          AND member_id = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        guild_id,
        member_id,
    )


async def count_case_entries(
    guild_id: int,
    member_id: int,
):
    """
    Return counts used by the member case panel.
    """

    await init_case_tables()

    row = await db.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE entry_type = 'warning'
                  AND active = TRUE
            ) AS active_warnings,

            COUNT(*) FILTER (
                WHERE entry_type = 'warning'
            ) AS total_warnings,

            COUNT(*) FILTER (
                WHERE entry_type = 'note'
                  AND active = TRUE
            ) AS notes,

            COUNT(*) AS total_entries

        FROM case_entries
        WHERE guild_id = $1
          AND member_id = $2
        """,
        guild_id,
        member_id,
    )

    return {
        "active_warnings": (
            row["active_warnings"]
            if row
            else 0
        ),
        "total_warnings": (
            row["total_warnings"]
            if row
            else 0
        ),
        "notes": (
            row["notes"]
            if row
            else 0
        ),
        "total_entries": (
            row["total_entries"]
            if row
            else 0
        ),
    }


# ==================================================
# REMOVE / CLEAR ENTRIES
# ==================================================

async def deactivate_case_entry(
    entry_id: int,
    guild_id: int,
    removed_by: int,
):
    """
    Soft-delete a case entry.

    We keep the original record for staff accountability,
    but mark it inactive and record who removed it.
    """

    await init_case_tables()

    return await db.fetchrow(
        """
        UPDATE case_entries
        SET
            active = FALSE,
            removed_by = $3,
            removed_at = NOW()
        WHERE id = $1
          AND guild_id = $2
          AND active = TRUE
        RETURNING
            id,
            guild_id,
            member_id,
            entry_type,
            content,
            staff_id,
            active,
            created_at,
            removed_by,
            removed_at
        """,
        entry_id,
        guild_id,
        removed_by,
    )


async def clear_warning(
    warning_id: int,
    guild_id: int,
    removed_by: int,
):
    """
    Clear only warning entries.

    Notes cannot accidentally be removed with /clearwarning.
    """

    await init_case_tables()

    return await db.fetchrow(
        """
        UPDATE case_entries
        SET
            active = FALSE,
            removed_by = $3,
            removed_at = NOW()
        WHERE id = $1
          AND guild_id = $2
          AND entry_type = 'warning'
          AND active = TRUE
        RETURNING
            id,
            guild_id,
            member_id,
            entry_type,
            content,
            staff_id,
            active,
            created_at,
            removed_by,
            removed_at
        """,
        warning_id,
        guild_id,
        removed_by,
    )
