# database/looking_for.py

from database.database import db


# ==================================================
# TABLE SETUP
# ==================================================

async def init_looking_for_tables():

    # --------------------------------------------------
    # LOOKING FOR SETTINGS
    # --------------------------------------------------

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS looking_for_settings (

            guild_id BIGINT PRIMARY KEY,

            panel_channel_id BIGINT,

            posts_channel_id BIGINT,

            selfies_channel_id BIGINT,

            panel_message_id BIGINT,

            enabled BOOLEAN
                NOT NULL
                DEFAULT TRUE,

            created_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # --------------------------------------------------
    # LOOKING FOR POSTS
    # --------------------------------------------------

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS looking_for_posts (

            id BIGSERIAL PRIMARY KEY,

            guild_id BIGINT NOT NULL,

            user_id BIGINT NOT NULL,

            channel_id BIGINT,

            message_id BIGINT,

            roles TEXT,

            connection_type TEXT,

            dynamic_type TEXT,

            preferred_vibe TEXT,

            looking_for TEXT,

            questions TEXT,

            dni TEXT,

            dm_status TEXT,

            extra TEXT,

            selfie_url TEXT,

            status TEXT
                NOT NULL
                DEFAULT 'active',

            created_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            closed_at TIMESTAMP
        )
        """
    )

    # Only allow one active post per member
    await db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        looking_for_one_active_post_per_user
        ON looking_for_posts (
            guild_id,
            user_id
        )
        WHERE status = 'active'
        """
    )

    # --------------------------------------------------
    # CONTACT REQUESTS
    # --------------------------------------------------

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS looking_for_messages (

            id BIGSERIAL PRIMARY KEY,

            post_id BIGINT NOT NULL
                REFERENCES looking_for_posts(id)
                ON DELETE CASCADE,

            guild_id BIGINT NOT NULL,

            sender_id BIGINT NOT NULL,

            recipient_id BIGINT NOT NULL,

            message TEXT NOT NULL,

            status TEXT
                NOT NULL
                DEFAULT 'pending',

            created_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            responded_at TIMESTAMP
        )
        """
    )

    # --------------------------------------------------
    # REPORTS
    # --------------------------------------------------

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS looking_for_reports (

            id BIGSERIAL PRIMARY KEY,

            post_id BIGINT NOT NULL
                REFERENCES looking_for_posts(id)
                ON DELETE CASCADE,

            guild_id BIGINT NOT NULL,

            reporter_id BIGINT NOT NULL,

            reported_user_id BIGINT NOT NULL,

            reason TEXT NOT NULL,

            status TEXT
                NOT NULL
                DEFAULT 'open',

            created_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            resolved_at TIMESTAMP,

            resolved_by BIGINT
        )
        """
    )


# ==================================================
# SETTINGS
# ==================================================

async def save_looking_for_settings(
    guild_id: int,
    panel_channel_id: int | None = None,
    posts_channel_id: int | None = None,
    selfies_channel_id: int | None = None,
    panel_message_id: int | None = None,
    enabled: bool | None = None,
):

    await db.execute(
        """
        INSERT INTO looking_for_settings (
            guild_id,
            panel_channel_id,
            posts_channel_id,
            selfies_channel_id,
            panel_message_id,
            enabled,
            updated_at
        )

        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            COALESCE($6, TRUE),
            CURRENT_TIMESTAMP
        )

        ON CONFLICT (guild_id)

        DO UPDATE SET

            panel_channel_id =
                COALESCE(
                    EXCLUDED.panel_channel_id,
                    looking_for_settings.panel_channel_id
                ),

            posts_channel_id =
                COALESCE(
                    EXCLUDED.posts_channel_id,
                    looking_for_settings.posts_channel_id
                ),

            selfies_channel_id =
                COALESCE(
                    EXCLUDED.selfies_channel_id,
                    looking_for_settings.selfies_channel_id
                ),

            panel_message_id =
                COALESCE(
                    EXCLUDED.panel_message_id,
                    looking_for_settings.panel_message_id
                ),

            enabled =
                COALESCE(
                    $6,
                    looking_for_settings.enabled
                ),

            updated_at =
                CURRENT_TIMESTAMP
        """,
        guild_id,
        panel_channel_id,
        posts_channel_id,
        selfies_channel_id,
        panel_message_id,
        enabled,
    )


async def get_looking_for_settings(
    guild_id: int,
) -> dict | None:

    row = await db.fetchrow(
        """
        SELECT
            guild_id,
            panel_channel_id,
            posts_channel_id,
            selfies_channel_id,
            panel_message_id,
            enabled,
            created_at,
            updated_at

        FROM looking_for_settings

        WHERE guild_id = $1
        """,
        guild_id,
    )

    if not row:
        return None

    return dict(row)


# ==================================================
# POSTS
# ==================================================

async def create_looking_for_post(
    guild_id: int,
    user_id: int,
    roles: str | None = None,
    connection_type: str | None = None,
    dynamic_type: str | None = None,
    preferred_vibe: str | None = None,
    looking_for: str | None = None,
    questions: str | None = None,
    dni: str | None = None,
    dm_status: str | None = None,
    extra: str | None = None,
    selfie_url: str | None = None,
) -> dict:

    row = await db.fetchrow(
        """
        INSERT INTO looking_for_posts (
            guild_id,
            user_id,
            roles,
            connection_type,
            dynamic_type,
            preferred_vibe,
            looking_for,
            questions,
            dni,
            dm_status,
            extra,
            selfie_url
        )

        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5,
            $6,
            $7,
            $8,
            $9,
            $10,
            $11,
            $12
        )

        RETURNING *
        """,
        guild_id,
        user_id,
        roles,
        connection_type,
        dynamic_type,
        preferred_vibe,
        looking_for,
        questions,
        dni,
        dm_status,
        extra,
        selfie_url,
    )

    return dict(row)


async def get_active_looking_for_post(
    guild_id: int,
    user_id: int,
) -> dict | None:

    row = await db.fetchrow(
        """
        SELECT *

        FROM looking_for_posts

        WHERE guild_id = $1
          AND user_id = $2
          AND status = 'active'

        LIMIT 1
        """,
        guild_id,
        user_id,
    )

    if not row:
        return None

    return dict(row)


async def get_looking_for_post(
    post_id: int,
) -> dict | None:

    row = await db.fetchrow(
        """
        SELECT *

        FROM looking_for_posts

        WHERE id = $1
        """,
        post_id,
    )

    if not row:
        return None

    return dict(row)


async def set_looking_for_message(
    post_id: int,
    channel_id: int,
    message_id: int,
):

    await db.execute(
        """
        UPDATE looking_for_posts

        SET
            channel_id = $1,
            message_id = $2,
            updated_at = CURRENT_TIMESTAMP

        WHERE id = $3
        """,
        channel_id,
        message_id,
        post_id,
    )


async def close_looking_for_post(
    post_id: int,
):

    await db.execute(
        """
        UPDATE looking_for_posts

        SET
            status = 'closed',
            closed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP

        WHERE id = $1
        """,
        post_id,
    )


async def update_looking_for_post_field(
    post_id: int,
    field: str,
    value,
):

    allowed_fields = {
        "roles",
        "connection_type",
        "dynamic_type",
        "preferred_vibe",
        "looking_for",
        "questions",
        "dni",
        "dm_status",
        "extra",
        "selfie_url",
        "status",
        "channel_id",
        "message_id",
    }

    if field not in allowed_fields:
        raise ValueError(
            "Invalid Looking For field."
        )

    query = f"""
        UPDATE looking_for_posts

        SET
            {field} = $1,
            updated_at = CURRENT_TIMESTAMP

        WHERE id = $2
    """

    await db.execute(
        query,
        value,
        post_id,
    )


# ==================================================
# CONTACT REQUESTS
# ==================================================

async def create_looking_for_message(
    post_id: int,
    guild_id: int,
    sender_id: int,
    recipient_id: int,
    message: str,
) -> dict:

    row = await db.fetchrow(
        """
        INSERT INTO looking_for_messages (
            post_id,
            guild_id,
            sender_id,
            recipient_id,
            message
        )

        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5
        )

        RETURNING *
        """,
        post_id,
        guild_id,
        sender_id,
        recipient_id,
        message,
    )

    return dict(row)


async def get_looking_for_message(
    message_request_id: int,
) -> dict | None:

    row = await db.fetchrow(
        """
        SELECT *

        FROM looking_for_messages

        WHERE id = $1
        """,
        message_request_id,
    )

    if not row:
        return None

    return dict(row)


async def update_looking_for_message_status(
    message_request_id: int,
    status: str,
):

    await db.execute(
        """
        UPDATE looking_for_messages

        SET
            status = $1,
            responded_at = CURRENT_TIMESTAMP

        WHERE id = $2
        """,
        status,
        message_request_id,
    )


# ==================================================
# REPORTS
# ==================================================

async def create_looking_for_report(
    post_id: int,
    guild_id: int,
    reporter_id: int,
    reported_user_id: int,
    reason: str,
) -> dict:

    row = await db.fetchrow(
        """
        INSERT INTO looking_for_reports (
            post_id,
            guild_id,
            reporter_id,
            reported_user_id,
            reason
        )

        VALUES (
            $1,
            $2,
            $3,
            $4,
            $5
        )

        RETURNING *
        """,
        post_id,
        guild_id,
        reporter_id,
        reported_user_id,
        reason,
    )

    return dict(row)
