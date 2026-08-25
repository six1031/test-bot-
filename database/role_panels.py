from database.database import db


# ==================================================
# TABLE SETUP
# ==================================================

async def init_role_panel_tables():

    # --------------------------------------------------
    # ROLE PANELS
    # --------------------------------------------------

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS role_panels (

            id SERIAL PRIMARY KEY,

            guild_id BIGINT NOT NULL,

            channel_id BIGINT,

            message_id BIGINT UNIQUE,

            title TEXT NOT NULL,

            description TEXT,

            created_by BIGINT,

            created_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # --------------------------------------------------
    # ROLES INSIDE EACH PANEL
    # --------------------------------------------------

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS role_panel_items (

            id SERIAL PRIMARY KEY,

            panel_id INTEGER NOT NULL
                REFERENCES role_panels(id)
                ON DELETE CASCADE,

            role_id BIGINT NOT NULL,

            emoji TEXT,

            position INTEGER
                NOT NULL
                DEFAULT 0,

            UNIQUE (
                panel_id,
                role_id
            )
        )
        """
    )


# ==================================================
# CREATE PANEL
# ==================================================

async def create_role_panel(
    guild_id: int,
    title: str,
    description: str | None,
    created_by: int,
):

    row = await db.fetchrow(
        """
        INSERT INTO role_panels (
            guild_id,
            title,
            description,
            created_by
        )

        VALUES (
            $1,
            $2,
            $3,
            $4
        )

        RETURNING id
        """,
        guild_id,
        title,
        description,
        created_by,
    )

    return row["id"]


# ==================================================
# SET PUBLISHED MESSAGE
# ==================================================

async def set_role_panel_message(
    panel_id: int,
    channel_id: int,
    message_id: int,
):

    await db.execute(
        """
        UPDATE role_panels

        SET
            channel_id = $1,
            message_id = $2

        WHERE id = $3
        """,
        channel_id,
        message_id,
        panel_id,
    )


# ==================================================
# ADD ROLE TO PANEL
# ==================================================

async def add_role_panel_item(
    panel_id: int,
    role_id: int,
    emoji: str | None,
    position: int = 0,
):

    await db.execute(
        """
        INSERT INTO role_panel_items (
            panel_id,
            role_id,
            emoji,
            position
        )

        VALUES (
            $1,
            $2,
            $3,
            $4
        )

        ON CONFLICT (
            panel_id,
            role_id
        )

        DO UPDATE SET

            emoji = EXCLUDED.emoji,

            position = EXCLUDED.position
        """,
        panel_id,
        role_id,
        emoji,
        position,
    )


# ==================================================
# REMOVE ROLE FROM PANEL
# ==================================================

async def remove_role_panel_item(
    panel_id: int,
    role_id: int,
):

    return await db.execute(
        """
        DELETE FROM role_panel_items

        WHERE panel_id = $1
          AND role_id = $2
        """,
        panel_id,
        role_id,
    )


# ==================================================
# GET ONE PANEL
# ==================================================

async def get_role_panel(
    panel_id: int,
):

    row = await db.fetchrow(
        """
        SELECT
            id,
            guild_id,
            channel_id,
            message_id,
            title,
            description,
            created_by,
            created_at

        FROM role_panels

        WHERE id = $1
        """,
        panel_id,
    )

    if not row:
        return None

    return dict(row)


# ==================================================
# GET PANEL ROLES
# ==================================================

async def get_role_panel_items(
    panel_id: int,
):

    rows = await db.fetch(
        """
        SELECT
            id,
            panel_id,
            role_id,
            emoji,
            position

        FROM role_panel_items

        WHERE panel_id = $1

        ORDER BY
            position ASC,
            id ASC
        """,
        panel_id,
    )

    return [
        dict(row)
        for row in rows
    ]


# ==================================================
# GET ALL PANELS FOR A SERVER
# ==================================================

async def get_guild_role_panels(
    guild_id: int,
):

    rows = await db.fetch(
        """
        SELECT
            id,
            guild_id,
            channel_id,
            message_id,
            title,
            description,
            created_by,
            created_at

        FROM role_panels

        WHERE guild_id = $1

        ORDER BY id ASC
        """,
        guild_id,
    )

    return [
        dict(row)
        for row in rows
    ]


# ==================================================
# GET ALL PUBLISHED PANELS
#
# Used when the bot starts after a Railway redeploy.
# ==================================================

async def get_all_published_role_panels():

    rows = await db.fetch(
        """
        SELECT
            id,
            guild_id,
            channel_id,
            message_id,
            title,
            description,
            created_by,
            created_at

        FROM role_panels

        WHERE channel_id IS NOT NULL
          AND message_id IS NOT NULL

        ORDER BY id ASC
        """
    )

    return [
        dict(row)
        for row in rows
    ]


# ==================================================
# UPDATE PANEL TEXT
# ==================================================

async def update_role_panel_text(
    panel_id: int,
    title: str,
    description: str | None,
):

    await db.execute(
        """
        UPDATE role_panels

        SET
            title = $1,
            description = $2

        WHERE id = $3
        """,
        title,
        description,
        panel_id,
    )


# ==================================================
# DELETE PANEL
#
# role_panel_items are automatically deleted because
# of ON DELETE CASCADE.
# ==================================================

async def delete_role_panel(
    panel_id: int,
):

    return await db.execute(
        """
        DELETE FROM role_panels

        WHERE id = $1
        """,
        panel_id,
    )
