from database.database import db


# ==================================================
# DATABASE SETUP
# ==================================================

async def init_system_profile_tables():

    # ==================================================
    # SYSTEM PROFILE SETTINGS
    #
    # Completely separate from the normal
    # member-profile configuration.
    # ==================================================

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS system_profile_settings (

            guild_id BIGINT PRIMARY KEY,

            profile_channel_id BIGINT
        )
        """
    )

    # ==================================================
    # MAIN SYSTEM PROFILE
    #
    # One system profile per Discord member,
    # per server.
    # ==================================================

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS system_profiles (

            id SERIAL PRIMARY KEY,

            guild_id BIGINT NOT NULL,

            user_id BIGINT NOT NULL,

            system_name TEXT NOT NULL,

            collective_name TEXT,

            collective_pronouns TEXT,

            system_size TEXT,

            system_type TEXT,

            frequent_fronters TEXT,

            shared_interests TEXT,

            communication_preferences TEXT,

            boundaries TEXT,

            dm_status TEXT,

            extra TEXT,

            profile_message_id BIGINT,

            created_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            UNIQUE (
                guild_id,
                user_id
            )
        )
        """
    )

    # ==================================================
    # ALTER PROFILES
    #
    # One system can have unlimited alter profiles.
    # ==================================================

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS alter_profiles (

            id SERIAL PRIMARY KEY,

            system_profile_id INTEGER NOT NULL
                REFERENCES system_profiles(id)
                ON DELETE CASCADE,

            name TEXT NOT NULL,

            nicknames TEXT,

            pronouns TEXT,

            gender TEXT,

            age TEXT,

            birthday TEXT,

            system_role TEXT,

            species_identity TEXT,

            source_info TEXT,

            proxy_emoji TEXT,

            favourite_colour TEXT,

            likes TEXT,

            dislikes TEXT,

            hobbies TEXT,

            communication_style TEXT,

            address_preferences TEXT,

            dm_status TEXT,

            interaction_status TEXT,

            relationship_status TEXT,

            boundaries TEXT,

            dni TEXT,

            comforts TEXT,

            frequent_fronter BOOLEAN
                NOT NULL
                DEFAULT FALSE,

            fronting_frequency TEXT,

            about_me TEXT,

            position INTEGER
                NOT NULL
                DEFAULT 0,

            created_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


# ==================================================
# SYSTEM PROFILE CHANNEL
# ==================================================

async def set_system_profile_channel(
    guild_id: int,
    channel_id: int,
):

    await db.execute(
        """
        INSERT INTO system_profile_settings (
            guild_id,
            profile_channel_id
        )

        VALUES (
            $1,
            $2
        )

        ON CONFLICT (
            guild_id
        )

        DO UPDATE SET

            profile_channel_id =
                EXCLUDED.profile_channel_id
        """,
        guild_id,
        channel_id,
    )


async def get_system_profile_settings(
    guild_id: int,
):

    row = await db.fetchrow(
        """
        SELECT
            guild_id,
            profile_channel_id

        FROM system_profile_settings

        WHERE guild_id = $1
        """,
        guild_id,
    )

    if not row:
        return None

    return dict(row)


# ==================================================
# CREATE / UPDATE SYSTEM PROFILE
# ==================================================

async def save_system_profile(
    guild_id: int,
    user_id: int,
    system_name: str,
    collective_name: str | None = None,
    collective_pronouns: str | None = None,
    system_size: str | None = None,
    system_type: str | None = None,
    frequent_fronters: str | None = None,
    shared_interests: str | None = None,
    communication_preferences: str | None = None,
    boundaries: str | None = None,
    dm_status: str | None = None,
    extra: str | None = None,
):

    row = await db.fetchrow(
        """
        INSERT INTO system_profiles (

            guild_id,

            user_id,

            system_name,

            collective_name,

            collective_pronouns,

            system_size,

            system_type,

            frequent_fronters,

            shared_interests,

            communication_preferences,

            boundaries,

            dm_status,

            extra,

            updated_at
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
            CURRENT_TIMESTAMP
        )

        ON CONFLICT (
            guild_id,
            user_id
        )

        DO UPDATE SET

            system_name =
                EXCLUDED.system_name,

            collective_name =
                EXCLUDED.collective_name,

            collective_pronouns =
                EXCLUDED.collective_pronouns,

            system_size =
                EXCLUDED.system_size,

            system_type =
                EXCLUDED.system_type,

            frequent_fronters =
                EXCLUDED.frequent_fronters,

            shared_interests =
                EXCLUDED.shared_interests,

            communication_preferences =
                EXCLUDED.communication_preferences,

            boundaries =
                EXCLUDED.boundaries,

            dm_status =
                EXCLUDED.dm_status,

            extra =
                EXCLUDED.extra,

            updated_at =
                CURRENT_TIMESTAMP

        RETURNING id
        """,
        guild_id,
        user_id,
        system_name,
        collective_name,
        collective_pronouns,
        system_size,
        system_type,
        frequent_fronters,
        shared_interests,
        communication_preferences,
        boundaries,
        dm_status,
        extra,
    )

    return row["id"]


# ==================================================
# GET SYSTEM PROFILE
# ==================================================

async def get_system_profile(
    guild_id: int,
    user_id: int,
):

    row = await db.fetchrow(
        """
        SELECT *

        FROM system_profiles

        WHERE guild_id = $1
          AND user_id = $2
        """,
        guild_id,
        user_id,
    )

    if not row:
        return None

    return dict(row)


async def get_system_profile_by_id(
    system_profile_id: int,
):

    row = await db.fetchrow(
        """
        SELECT *

        FROM system_profiles

        WHERE id = $1
        """,
        system_profile_id,
    )

    if not row:
        return None

    return dict(row)


# ==================================================
# PROFILE MESSAGE
# ==================================================

async def set_system_profile_message(
    system_profile_id: int,
    message_id: int,
):

    await db.execute(
        """
        UPDATE system_profiles

        SET
            profile_message_id = $1,
            updated_at = CURRENT_TIMESTAMP

        WHERE id = $2
        """,
        message_id,
        system_profile_id,
    )


# ==================================================
# DELETE SYSTEM PROFILE
#
# Alter profiles will also be deleted because
# alter_profiles uses ON DELETE CASCADE.
# ==================================================

async def delete_system_profile(
    guild_id: int,
    user_id: int,
):

    return await db.execute(
        """
        DELETE FROM system_profiles

        WHERE guild_id = $1
          AND user_id = $2
        """,
        guild_id,
        user_id,
    )


# ==================================================
# ADD ALTER
# ==================================================

async def add_alter_profile(
    system_profile_id: int,
    name: str,
    nicknames: str | None = None,
    pronouns: str | None = None,
    gender: str | None = None,
    age: str | None = None,
    birthday: str | None = None,
    system_role: str | None = None,
    species_identity: str | None = None,
    source_info: str | None = None,
    proxy_emoji: str | None = None,
    favourite_colour: str | None = None,
    likes: str | None = None,
    dislikes: str | None = None,
    hobbies: str | None = None,
    communication_style: str | None = None,
    address_preferences: str | None = None,
    dm_status: str | None = None,
    interaction_status: str | None = None,
    relationship_status: str | None = None,
    boundaries: str | None = None,
    dni: str | None = None,
    comforts: str | None = None,
    frequent_fronter: bool = False,
    fronting_frequency: str | None = None,
    about_me: str | None = None,
):

    row = await db.fetchrow(
        """
        SELECT
            COALESCE(
                MAX(position),
                -1
            ) + 1 AS next_position

        FROM alter_profiles

        WHERE system_profile_id = $1
        """,
        system_profile_id,
    )

    position = (
        row["next_position"]
        if row
        else 0
    )

    row = await db.fetchrow(
        """
        INSERT INTO alter_profiles (

            system_profile_id,

            name,

            nicknames,

            pronouns,

            gender,

            age,

            birthday,

            system_role,

            species_identity,

            source_info,

            proxy_emoji,

            favourite_colour,

            likes,

            dislikes,

            hobbies,

            communication_style,

            address_preferences,

            dm_status,

            interaction_status,

            relationship_status,

            boundaries,

            dni,

            comforts,

            frequent_fronter,

            fronting_frequency,

            about_me,

            position
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
            $14,
            $15,
            $16,
            $17,
            $18,
            $19,
            $20,
            $21,
            $22,
            $23,
            $24,
            $25,
            $26,
            $27
        )

        RETURNING id
        """,
        system_profile_id,
        name,
        nicknames,
        pronouns,
        gender,
        age,
        birthday,
        system_role,
        species_identity,
        source_info,
        proxy_emoji,
        favourite_colour,
        likes,
        dislikes,
        hobbies,
        communication_style,
        address_preferences,
        dm_status,
        interaction_status,
        relationship_status,
        boundaries,
        dni,
        comforts,
        frequent_fronter,
        fronting_frequency,
        about_me,
        position,
    )

    return row["id"]


# ==================================================
# GET ALTER
# ==================================================

async def get_alter_profile(
    alter_id: int,
):

    row = await db.fetchrow(
        """
        SELECT *

        FROM alter_profiles

        WHERE id = $1
        """,
        alter_id,
    )

    if not row:
        return None

    return dict(row)


# ==================================================
# GET ALL ALTERS FOR SYSTEM
# ==================================================

async def get_alter_profiles(
    system_profile_id: int,
):

    rows = await db.fetch(
        """
        SELECT *

        FROM alter_profiles

        WHERE system_profile_id = $1

        ORDER BY
            position ASC,
            id ASC
        """,
        system_profile_id,
    )

    return [
        dict(row)
        for row in rows
    ]


# ==================================================
# UPDATE ALTER FIELD
# ==================================================

async def update_alter_field(
    alter_id: int,
    field: str,
    value,
):

    allowed_fields = {

        "name",

        "nicknames",

        "pronouns",

        "gender",

        "age",

        "birthday",

        "system_role",

        "species_identity",

        "source_info",

        "proxy_emoji",

        "favourite_colour",

        "likes",

        "dislikes",

        "hobbies",

        "communication_style",

        "address_preferences",

        "dm_status",

        "interaction_status",

        "relationship_status",

        "boundaries",

        "dni",

        "comforts",

        "frequent_fronter",

        "fronting_frequency",

        "about_me",

        "position",
    }

    if field not in allowed_fields:

        raise ValueError(
            "Invalid alter profile field."
        )

    query = f"""
        UPDATE alter_profiles

        SET
            {field} = $1,
            updated_at = CURRENT_TIMESTAMP

        WHERE id = $2
    """

    return await db.execute(
        query,
        value,
        alter_id,
    )


# ==================================================
# DELETE ALTER
# ==================================================

async def delete_alter_profile(
    alter_id: int,
):

    return await db.execute(
        """
        DELETE FROM alter_profiles

        WHERE id = $1
        """,
        alter_id,
    )


# ==================================================
# COUNT ALTERS
# ==================================================

async def count_alter_profiles(
    system_profile_id: int,
):

    row = await db.fetchrow(
        """
        SELECT COUNT(*) AS total

        FROM alter_profiles

        WHERE system_profile_id = $1
        """,
        system_profile_id,
    )

    return (
        row["total"]
        if row
        else 0
    )
