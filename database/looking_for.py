# database/looking_for.py

from database.database import db


# ==================================================
# TABLE SETUP
# ==================================================

async def init_looking_for_tables():

    # --------------------------------------------------
    # GENERAL SETTINGS
    # --------------------------------------------------

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS looking_for_settings (

            guild_id BIGINT PRIMARY KEY,

            panel_channel_id BIGINT,

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
    # CATEGORY CHANNELS
    #
    # Each Looking For category can have its own channel.
    # --------------------------------------------------

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS looking_for_category_channels (

            guild_id BIGINT NOT NULL,

            category TEXT NOT NULL,

            channel_id BIGINT NOT NULL,

            PRIMARY KEY (
                guild_id,
                category
            )
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

            looking_for_role TEXT NOT NULL,

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
                DEFAULT 'draft',

            created_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            published_at TIMESTAMP,

            closed_at TIMESTAMP
        )
        """
    )

    # --------------------------------------------------
    # MIGRATE OLDER LOOKING FOR TABLE
    # --------------------------------------------------

    await db.execute(
        """
        ALTER TABLE looking_for_posts
        ADD COLUMN IF NOT EXISTS looking_for_role TEXT
        """
    )

    await db.execute(
        """
        ALTER TABLE looking_for_posts
        ADD COLUMN IF NOT EXISTS published_at TIMESTAMP
        """
    )

    # Remove the old rule that only allowed
    # one active post total.
    await db.execute(
        """
        DROP INDEX IF EXISTS
        looking_for_one_active_post_per_user
        """
    )

    # --------------------------------------------------
    # ONE ACTIVE POST PER CATEGORY
    # --------------------------------------------------

    await db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        looking_for_one_active_post_per_category

        ON looking_for_posts (
            guild_id,
            user_id,
            looking_for_role
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
# GENERAL SETTINGS
# ==================================================

async def save_looking_for_settings(
    guild_id: int,
    panel_channel_id: int | None = None,
    selfies_channel_id: int | None = None,
    panel_message_id: int | None = None,
    enabled: bool | None = None,
):

    await db.execute(
        """
        INSERT INTO looking_for_settings (
            guild_id,
            panel_channel_id,
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
            COALESCE($5, TRUE),
            CURRENT_TIMESTAMP
        )

        ON CONFLICT (guild_id)

        DO UPDATE SET

            panel_channel_id =
                COALESCE(
                    EXCLUDED.panel_channel_id,
                    looking_for_settings.panel_channel_id
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
                    $5,
                    looking_for_settings.enabled
                ),

            updated_at =
                CURRENT_TIMESTAMP
        """,
        guild_id,
        panel_channel_id,
        selfies_channel_id,
        panel_message_id,
        enabled,
    )


async def get_looking_for_settings(
    guild_id: int,
) -> dict | None:

    row = await db.fetchrow(
        """
        SELECT *

        FROM looking_for_settings

        WHERE guild_id = $1
        """,
        guild_id,
    )

    if not row:
        return None

    return dict(row)


# ==================================================
# CATEGORY CHANNELS
# ==================================================

async def set_looking_for_category_channel(
    guild_id: int,
    category: str,
    channel_id: int,
):

    await db.execute(
        """
        INSERT INTO looking_for_category_channels (
            guild_id,
            category,
            channel_id
        )

        VALUES (
            $1,
            $2,
            $3
        )

        ON CONFLICT (
            guild_id,
            category
        )

        DO UPDATE SET
            channel_id = EXCLUDED.channel_id
        """,
        guild_id,
        category.lower(),
        channel_id,
    )


async def get_looking_for_category_channel(
    guild_id: int,
    category: str,
) -> int | None:

    row = await db.fetchrow(
        """
        SELECT channel_id

        FROM looking_for_category_channels

        WHERE guild_id = $1
          AND category = $2
        """,
        guild_id,
        category.lower(),
    )

    if not row:
        return None

    return row["channel_id"]


async def get_all_looking_for_category_channels(
    guild_id: int,
) -> dict[str, int]:

    rows = await db.fetch(
        """
        SELECT
            category,
            channel_id

        FROM looking_for_category_channels

        WHERE guild_id = $1
        """,
        guild_id,
    )

    return {
        row["category"]: row["channel_id"]
        for row in rows
    }


async def remove_looking_for_category_channel(
    guild_id: int,
    category: str,
):

    await db.execute(
        """
        DELETE FROM looking_for_category_channels

        WHERE guild_id = $1
          AND category = $2
        """,
        guild_id,
        category.lower(),
    )


# ==================================================
# POSTS
# ==================================================

async def create_looking_for_post(
    guild_id: int,
    user_id: int,
    looking_for_role: str,
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
    status: str = "draft",
) -> dict:

    row = await db.fetchrow(
        """
        INSERT INTO looking_for_posts (
            guild_id,
            user_id,
            looking_for_role,
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
            status
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
            $12,
            $13,
            $14
        )

        RETURNING *
        """,
        guild_id,
        user_id,
        looking_for_role.lower(),
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
        status,
    )

    return dict(row)


# ==================================================
# COPY A POST INTO ANOTHER CATEGORY
# ==================================================

async def copy_looking_for_post(
    post_id: int,
    new_category: str,
) -> dict | None:

    row = await db.fetchrow(
        """
        INSERT INTO looking_for_posts (
            guild_id,
            user_id,
            looking_for_role,
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
            status
        )

        SELECT
            guild_id,
            user_id,
            $2,
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
            'draft'

        FROM looking_for_posts

        WHERE id = $1

        RETURNING *
        """,
        post_id,
        new_category.lower(),
    )

    if not row:
        return None

    return dict(row)


# ==================================================
# GET ONE POST
# ==================================================

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


# ==================================================
# GET ACTIVE POST FOR CATEGORY
# ==================================================

async def get_active_looking_for_post(
    guild_id: int,
    user_id: int,
    looking_for_role: str,
) -> dict | None:

    row = await db.fetchrow(
        """
        SELECT *

        FROM looking_for_posts

        WHERE guild_id = $1
          AND user_id = $2
          AND looking_for_role = $3
          AND status = 'active'

        LIMIT 1
        """,
        guild_id,
        user_id,
        looking_for_role.lower(),
    )

    if not row:
        return None

    return dict(row)


# ==================================================
# GET ALL MEMBER POSTS
# ==================================================

async def get_user_looking_for_posts(
    guild_id: int,
    user_id: int,
) -> list[dict]:

    rows = await db.fetch(
        """
        SELECT *

        FROM looking_for_posts

        WHERE guild_id = $1
          AND user_id = $2
          AND status IN (
              'draft',
              'active'
          )

        ORDER BY created_at ASC
        """,
        guild_id,
        user_id,
    )

    return [
        dict(row)
        for row in rows
    ]


# ==================================================
# PUBLISH POST
# ==================================================

async def publish_looking_for_post(
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
            status = 'active',
            published_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP

        WHERE id = $3
        """,
        channel_id,
        message_id,
        post_id,
    )


# ==================================================
# UPDATE POST FIELD
# ==================================================

async def update_looking_for_post_field(
    post_id: int,
    field: str,
    value,
):

    allowed_fields = {
        "looking_for_role",
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

    if field == "looking_for_role" and value:
        value = value.lower()

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
# CLOSE POST
# ==================================================

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


# ==================================================
# DELETE DRAFT
# ==================================================

async def delete_looking_for_draft(
    post_id: int,
    user_id: int,
):

    await db.execute(
        """
        DELETE FROM looking_for_posts

        WHERE id = $1
          AND user_id = $2
          AND status = 'draft'
        """,
        post_id,
        user_id,
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
