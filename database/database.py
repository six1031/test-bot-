# database/database.py

import os
import asyncpg
from typing import Optional


class Database:

    def __init__(self):

        self.pool: asyncpg.pool.Pool | None = None

        self._dsn = os.getenv(
            "DATABASE_URL"
        )

    # ==================================================
    # CONNECTION
    # ==================================================

    async def connect(
        self,
        min_size: int = 1,
        max_size: int = 10,
    ):

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

    async def close(
        self,
    ):

        if self.pool:

            await self.pool.close()

            self.pool = None

    # ==================================================
    # BASIC DATABASE HELPERS
    # ==================================================

    async def execute(
        self,
        query: str,
        *args,
    ):

        if not self.pool:

            raise RuntimeError(
                (
                    "Database pool is not initialized. "
                    "Call db.connect() first."
                )
            )

        async with self.pool.acquire() as conn:

            return await conn.execute(
                query,
                *args,
            )

    async def fetch(
        self,
        query: str,
        *args,
    ):

        if not self.pool:

            raise RuntimeError(
                (
                    "Database pool is not initialized. "
                    "Call db.connect() first."
                )
            )

        async with self.pool.acquire() as conn:

            return await conn.fetch(
                query,
                *args,
            )

    async def fetchrow(
        self,
        query: str,
        *args,
    ):

        if not self.pool:

            raise RuntimeError(
                (
                    "Database pool is not initialized. "
                    "Call db.connect() first."
                )
            )

        async with self.pool.acquire() as conn:

            return await conn.fetchrow(
                query,
                *args,
            )

    # ==================================================
    # DATABASE MIGRATIONS
    # ==================================================

    async def run_migrations(
        self,
    ):

        # ==================================================
        # TICKET PANEL STORAGE
        # ==================================================

        await self.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_panels (
                message_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                panel_type TEXT NOT NULL
            )
            """
        )

        # --------------------------------------------------
        # REMOVE OLD DUPLICATE PANEL RECORDS
        # --------------------------------------------------

        await self.execute(
            """
            DELETE FROM ticket_panels a
            USING ticket_panels b
            WHERE a.ctid < b.ctid
              AND a.message_id = b.message_id
            """
        )

        # --------------------------------------------------
        # MAKE MESSAGE ID UNIQUE
        # --------------------------------------------------

        await self.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            ticket_panels_message_id_unique
            ON ticket_panels (message_id)
            """
        )

        # ==================================================
        # TICKET STORAGE
        # ==================================================

        await self.execute(
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
        # ADD CLOSED COLUMN TO OLD TABLES
        # --------------------------------------------------

        await self.execute(
            """
            ALTER TABLE tickets
            ADD COLUMN IF NOT EXISTS closed
            BOOLEAN NOT NULL DEFAULT FALSE
            """
        )

        # --------------------------------------------------
        # ADD GUILD ID TO OLD TABLES
        # --------------------------------------------------

        await self.execute(
            """
            ALTER TABLE tickets
            ADD COLUMN IF NOT EXISTS guild_id BIGINT
            """
        )

        # ==================================================
        # PROFILE SYSTEM SETTINGS
        #
        # These are stored in guild_settings so every
        # server can have its own:
        #
        # - Verified role
        # - Intro/profile channel
        # ==================================================

        await self.execute(
            """
            ALTER TABLE guild_settings
            ADD COLUMN IF NOT EXISTS verified_role BIGINT
            """
        )

        await self.execute(
            """
            ALTER TABLE guild_settings
            ADD COLUMN IF NOT EXISTS intro_channel BIGINT
            """
        )

        # ==================================================
        # COMMAND ACCESS ROLES
        #
        # mod_role replaces the old staff_role name.
        # staff_role is kept for backwards compatibility
        # with older cogs while they are migrated.
        # ==================================================

        await self.execute(
            """
            ALTER TABLE guild_settings
            ADD COLUMN IF NOT EXISTS mod_role BIGINT
            """
        )

        await self.execute(
            """
            ALTER TABLE guild_settings
            ADD COLUMN IF NOT EXISTS member_role BIGINT
            """
        )

        # Copy the old staff role into mod_role once so
        # existing server setup is not lost.
        await self.execute(
            """
            UPDATE guild_settings
            SET mod_role = staff_role
            WHERE mod_role IS NULL
              AND staff_role IS NOT NULL
            """
        )

        # ==================================================
        # SETUP PERSISTENCE
        #
        # Keep every /setup option saved between restarts.
        # ==================================================

        await self.execute(
            """
            ALTER TABLE guild_settings
            ADD COLUMN IF NOT EXISTS enforce_only_post
            BOOLEAN NOT NULL DEFAULT FALSE
            """
        )

        await self.execute(
            """
            ALTER TABLE guild_settings
            ADD COLUMN IF NOT EXISTS verification_channel BIGINT
            """
        )

        await self.execute(
            """
            ALTER TABLE guild_settings
            ADD COLUMN IF NOT EXISTS verification_message TEXT
            """
        )

        await self.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_auto_role_entries (
                guild_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                PRIMARY KEY (
                    guild_id,
                    role_id
                )
            )
            """
        )

        # Import the older three-slot auto-role table once, if it exists.
        # The old table is intentionally left in place for compatibility.
        await self.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'guild_auto_roles'
                      AND column_name = 'auto_role_1'
                ) THEN
                    INSERT INTO guild_auto_role_entries (
                        guild_id,
                        role_id
                    )
                    SELECT
                        guild_id,
                        roles.role_id
                    FROM guild_auto_roles
                    CROSS JOIN LATERAL UNNEST(
                        ARRAY[
                            auto_role_1,
                            auto_role_2,
                            auto_role_3
                        ]
                    ) AS roles(role_id)
                    WHERE roles.role_id IS NOT NULL
                    ON CONFLICT (
                        guild_id,
                        role_id
                    )
                    DO NOTHING;
                END IF;
            END
            $$;
            """
        )

        # ==================================================
        # MEMBER PROFILE STORAGE
        # ==================================================

        await self.execute(
            """
            CREATE TABLE IF NOT EXISTS member_profiles (

                guild_id BIGINT NOT NULL,

                user_id BIGINT NOT NULL,

                nickname TEXT NOT NULL,

                age TEXT,

                gender TEXT,

                pronouns TEXT,

                sexuality TEXT,

                languages TEXT,

                relationship_status TEXT,

                likes TEXT,

                dislikes TEXT,

                dni TEXT,

                dm_status TEXT,

                extra TEXT,

                intro_message_id BIGINT,

                profile_complete BOOLEAN
                    NOT NULL
                    DEFAULT FALSE,

                created_at TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (
                    guild_id,
                    user_id
                )
            )
            """
        )

    # ==================================================
    # TICKET PANELS
    # ==================================================

    async def add_ticket_panel(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        panel_type: str,
    ):

        await self.execute(
            """
            INSERT INTO ticket_panels (
                guild_id,
                channel_id,
                message_id,
                panel_type
            )

            VALUES (
                $1,
                $2,
                $3,
                $4
            )

            ON CONFLICT (message_id)
            DO NOTHING
            """,
            guild_id,
            channel_id,
            message_id,
            panel_type,
        )

    async def get_ticket_panels(
        self,
    ):

        return await self.fetch(
            """
            SELECT
                guild_id,
                channel_id,
                message_id,
                panel_type
            FROM ticket_panels
            """
        )

    async def remove_ticket_panel(
        self,
        message_id: int,
    ):

        await self.execute(
            """
            DELETE FROM ticket_panels
            WHERE message_id = $1
            """,
            message_id,
        )

    # ==================================================
    # TICKETS
    # ==================================================

    async def create_ticket(
        self,
        guild_id: int,
        channel_id: int,
        owner_id: int,
        ticket_type: str,
    ):

        await self.execute(
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

    async def close_ticket(
        self,
        channel_id: int,
    ):

        await self.execute(
            """
            UPDATE tickets

            SET closed = TRUE

            WHERE channel_id = $1
            """,
            channel_id,
        )

    async def get_open_ticket(
        self,
        guild_id: int,
        owner_id: int,
        ticket_type: str,
    ):

        return await self.fetchrow(
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

            LIMIT 1
            """,
            guild_id,
            owner_id,
            ticket_type,
        )

    # ==================================================
    # MEMBER PROFILES
    # ==================================================

    async def save_member_profile(
        self,
        guild_id: int,
        user_id: int,
        nickname: str,
        age: str | None = None,
        gender: str | None = None,
        pronouns: str | None = None,
        sexuality: str | None = None,
        languages: str | None = None,
        relationship_status: str | None = None,
        likes: str | None = None,
        dislikes: str | None = None,
        dni: str | None = None,
        dm_status: str | None = None,
        extra: str | None = None,
        intro_message_id: int | None = None,
        profile_complete: bool = True,
    ):

        await self.execute(
            """
            INSERT INTO member_profiles (

                guild_id,

                user_id,

                nickname,

                age,

                gender,

                pronouns,

                sexuality,

                languages,

                relationship_status,

                likes,

                dislikes,

                dni,

                dm_status,

                extra,

                intro_message_id,

                profile_complete,

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
                $14,
                $15,
                $16,
                CURRENT_TIMESTAMP
            )

            ON CONFLICT (
                guild_id,
                user_id
            )

            DO UPDATE SET

                nickname = EXCLUDED.nickname,

                age = EXCLUDED.age,

                gender = EXCLUDED.gender,

                pronouns = EXCLUDED.pronouns,

                sexuality = EXCLUDED.sexuality,

                languages = EXCLUDED.languages,

                relationship_status =
                    EXCLUDED.relationship_status,

                likes = EXCLUDED.likes,

                dislikes = EXCLUDED.dislikes,

                dni = EXCLUDED.dni,

                dm_status = EXCLUDED.dm_status,

                extra = EXCLUDED.extra,

                intro_message_id =
                    COALESCE(
                        EXCLUDED.intro_message_id,
                        member_profiles.intro_message_id
                    ),

                profile_complete =
                    EXCLUDED.profile_complete,

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            guild_id,
            user_id,
            nickname,
            age,
            gender,
            pronouns,
            sexuality,
            languages,
            relationship_status,
            likes,
            dislikes,
            dni,
            dm_status,
            extra,
            intro_message_id,
            profile_complete,
        )

    # --------------------------------------------------
    # GET FULL PROFILE
    # --------------------------------------------------

    async def get_member_profile(
        self,
        guild_id: int,
        user_id: int,
    ) -> Optional[dict]:

        row = await self.fetchrow(
            """
            SELECT

                guild_id,

                user_id,

                nickname,

                age,

                gender,

                pronouns,

                sexuality,

                languages,

                relationship_status,

                likes,

                dislikes,

                dni,

                dm_status,

                extra,

                intro_message_id,

                profile_complete,

                created_at,

                updated_at

            FROM member_profiles

            WHERE guild_id = $1
              AND user_id = $2
            """,
            guild_id,
            user_id,
        )

        if not row:
            return None

        return dict(
            row
        )

    # --------------------------------------------------
    # GET SAVED NICKNAME
    #
    # Later /tree will use this.
    # --------------------------------------------------

    async def get_profile_name(
        self,
        guild_id: int,
        user_id: int,
    ) -> str | None:

        row = await self.fetchrow(
            """
            SELECT nickname

            FROM member_profiles

            WHERE guild_id = $1
              AND user_id = $2
              AND profile_complete = TRUE
            """,
            guild_id,
            user_id,
        )

        if not row:
            return None

        return row[
            "nickname"
        ]

    # --------------------------------------------------
    # UPDATE ONE PROFILE FIELD
    #
    # This will be useful for /profile edit.
    # --------------------------------------------------

    async def update_member_profile_field(
        self,
        guild_id: int,
        user_id: int,
        field: str,
        value,
    ):

        allowed_fields = {

            "nickname",

            "age",

            "gender",

            "pronouns",

            "sexuality",

            "languages",

            "relationship_status",

            "likes",

            "dislikes",

            "dni",

            "dm_status",

            "extra",

            "intro_message_id",

            "profile_complete",
        }

        if field not in allowed_fields:

            raise ValueError(
                "Invalid profile field."
            )

        query = f"""
            UPDATE member_profiles

            SET
                {field} = $1,
                updated_at = CURRENT_TIMESTAMP

            WHERE guild_id = $2
              AND user_id = $3
        """

        return await self.execute(
            query,
            value,
            guild_id,
            user_id,
        )

    # --------------------------------------------------
    # SAVE INTRO MESSAGE ID
    # --------------------------------------------------

    async def set_profile_intro_message(
        self,
        guild_id: int,
        user_id: int,
        message_id: int,
    ):

        await self.update_member_profile_field(
            guild_id,
            user_id,
            "intro_message_id",
            message_id,
        )

    # --------------------------------------------------
    # DELETE PROFILE
    # --------------------------------------------------

    async def delete_member_profile(
        self,
        guild_id: int,
        user_id: int,
    ):

        return await self.execute(
            """
            DELETE FROM member_profiles

            WHERE guild_id = $1
              AND user_id = $2
            """,
            guild_id,
            user_id,
        )

    # ==================================================
    # GUILD SETTINGS
    # ==================================================

    async def get_guild_settings(
        self,
        guild_id: int,
    ) -> Optional[dict]:

        if not self.pool:

            raise RuntimeError(
                (
                    "Database pool is not initialized. "
                    "Call db.connect() first."
                )
            )

        async with self.pool.acquire() as conn:

            row = await conn.fetchrow(
                """
                SELECT

                    guild_id,

                    log_channel,

                    admin_role,

                    staff_role,

                    mod_role,

                    member_role,

                    marriage_channel,

                    relationship_channel,

                    ticket_category,

                    verified_role,

                    intro_channel,

                    enforce_only_post,

                    verification_channel,

                    verification_message

                FROM guild_settings

                WHERE guild_id = $1
                """,
                guild_id,
            )

            if not row:
                return None

            auto_role_rows = await conn.fetch(
                """
                SELECT role_id
                FROM guild_auto_role_entries
                WHERE guild_id = $1
                ORDER BY role_id
                """,
                guild_id,
            )

            auto_role_ids = [
                item["role_id"]
                for item in auto_role_rows
            ]

            # Prefer the new mod_role column. Fall back to the
            # old staff_role value for servers not migrated yet.
            mod_role = (
                row["mod_role"]
                if row["mod_role"] is not None
                else row["staff_role"]
            )

            return {

                "guild_id":
                    row["guild_id"],

                "log_channel":
                    row["log_channel"],

                "admin_role":
                    row["admin_role"],

                "mod_role":
                    mod_role,

                "member_role":
                    row["member_role"],

                # Legacy alias so older ticket/mod cogs that still
                # ask for staff_role keep working for now.
                "staff_role":
                    mod_role,

                "marriage_channel":
                    row["marriage_channel"],

                "relationship_channel":
                    row["relationship_channel"],

                "ticket_category":
                    row["ticket_category"],

                "verified_role":
                    row["verified_role"],

                "intro_channel":
                    row["intro_channel"],

                "enforce_only_post":
                    bool(
                        row["enforce_only_post"]
                    ),

                "verification_channel":
                    row["verification_channel"],

                "verification_message":
                    row["verification_message"],

                "auto_roles":
                    auto_role_ids,

                # Legacy aliases for any older code that still expects
                # the original three auto-role fields.
                "auto_role_1":
                    (
                        auto_role_ids[0]
                        if len(auto_role_ids) > 0
                        else None
                    ),

                "auto_role_2":
                    (
                        auto_role_ids[1]
                        if len(auto_role_ids) > 1
                        else None
                    ),

                "auto_role_3":
                    (
                        auto_role_ids[2]
                        if len(auto_role_ids) > 2
                        else None
                    ),
            }

    async def upsert_guild_settings(
        self,
        guild_id: int,
        log_channel_id: int | None = None,
        admin_role_id: int | None = None,
        mod_role_id: int | None = None,
        member_role_id: int | None = None,

        # --------------------------------------------------
        # LEGACY STAFF NAME
        # --------------------------------------------------

        staff_role_id: int | None = None,

        ticket_category_id: int | None = None,
        marriage_channel_id: int | None = None,
        relationship_channel_id: int | None = None,
        enforce_only_post: bool | None = None,

        # --------------------------------------------------
        # PROFILE SYSTEM
        # --------------------------------------------------

        verified_role_id: int | None = None,

        intro_channel_id: int | None = None,
    ):

        if not self.pool:

            raise RuntimeError(
                (
                    "Database pool is not initialized. "
                    "Call db.connect() first."
                )
            )

        # New code should use mod_role_id. If an older cog still
        # passes staff_role_id, accept that too.
        effective_mod_role_id = (
            mod_role_id
            if mod_role_id is not None
            else staff_role_id
        )

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO guild_settings (

                    guild_id,

                    log_channel,

                    admin_role,

                    staff_role,

                    mod_role,

                    member_role,

                    ticket_category,

                    marriage_channel,

                    relationship_channel,

                    verified_role,

                    intro_channel,

                    enforce_only_post
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
                    COALESCE($12, FALSE)
                )

                ON CONFLICT (
                    guild_id
                )

                DO UPDATE SET

                    log_channel =
                        COALESCE(
                            EXCLUDED.log_channel,
                            guild_settings.log_channel
                        ),

                    admin_role =
                        COALESCE(
                            EXCLUDED.admin_role,
                            guild_settings.admin_role
                        ),

                    staff_role =
                        COALESCE(
                            EXCLUDED.staff_role,
                            guild_settings.staff_role
                        ),

                    mod_role =
                        COALESCE(
                            EXCLUDED.mod_role,
                            guild_settings.mod_role
                        ),

                    member_role =
                        COALESCE(
                            EXCLUDED.member_role,
                            guild_settings.member_role
                        ),

                    ticket_category =
                        COALESCE(
                            EXCLUDED.ticket_category,
                            guild_settings.ticket_category
                        ),

                    marriage_channel =
                        COALESCE(
                            EXCLUDED.marriage_channel,
                            guild_settings.marriage_channel
                        ),

                    relationship_channel =
                        COALESCE(
                            EXCLUDED.relationship_channel,
                            guild_settings.relationship_channel
                        ),

                    verified_role =
                        COALESCE(
                            EXCLUDED.verified_role,
                            guild_settings.verified_role
                        ),

                    intro_channel =
                        COALESCE(
                            EXCLUDED.intro_channel,
                            guild_settings.intro_channel
                        ),

                    enforce_only_post =
                        COALESCE(
                            $12,
                            guild_settings.enforce_only_post
                        )
                """,
                guild_id,
                log_channel_id,
                admin_role_id,
                effective_mod_role_id,
                effective_mod_role_id,
                member_role_id,
                ticket_category_id,
                marriage_channel_id,
                relationship_channel_id,
                verified_role_id,
                intro_channel_id,
                enforce_only_post,
            )


    # ==================================================
    # VERIFICATION SETTINGS
    # ==================================================

    async def set_verified_role(
        self,
        guild_id: int,
        role_id: int,
    ):
        await self.upsert_guild_settings(
            guild_id=guild_id,
            verified_role_id=role_id,
        )

    async def set_verification_channel(
        self,
        guild_id: int,
        channel_id: int | None,
    ):
        await self.execute(
            """
            INSERT INTO guild_settings (
                guild_id,
                verification_channel
            )
            VALUES ($1, $2)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                verification_channel = EXCLUDED.verification_channel
            """,
            guild_id,
            channel_id,
        )

    async def set_verification_message(
        self,
        guild_id: int,
        message: str | None,
    ):
        await self.execute(
            """
            INSERT INTO guild_settings (
                guild_id,
                verification_message
            )
            VALUES ($1, $2)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                verification_message = EXCLUDED.verification_message
            """,
            guild_id,
            message,
        )

    # ==================================================
    # GUILD AUTO ROLES
    # ==================================================

    async def get_guild_auto_roles(
        self,
        guild_id: int,
    ) -> list[int]:

        rows = await self.fetch(
            """
            SELECT role_id
            FROM guild_auto_role_entries
            WHERE guild_id = $1
            ORDER BY role_id
            """,
            guild_id,
        )

        return [
            row["role_id"]
            for row in rows
        ]

    async def add_guild_auto_roles(
        self,
        guild_id: int,
        role_ids: list[int],
    ):

        cleaned_role_ids = list(
            dict.fromkeys(
                int(role_id)
                for role_id in role_ids
                if role_id
            )
        )

        if not cleaned_role_ids:
            return

        await self.execute(
            """
            INSERT INTO guild_auto_role_entries (
                guild_id,
                role_id
            )
            SELECT
                $1,
                roles.role_id
            FROM UNNEST(
                $2::BIGINT[]
            ) AS roles(role_id)
            ON CONFLICT (
                guild_id,
                role_id
            )
            DO NOTHING
            """,
            guild_id,
            cleaned_role_ids,
        )

    async def remove_guild_auto_roles(
        self,
        guild_id: int,
        role_ids: list[int],
    ):

        cleaned_role_ids = list(
            dict.fromkeys(
                int(role_id)
                for role_id in role_ids
                if role_id
            )
        )

        if not cleaned_role_ids:
            return

        await self.execute(
            """
            DELETE FROM guild_auto_role_entries
            WHERE guild_id = $1
              AND role_id = ANY(
                  $2::BIGINT[]
              )
            """,
            guild_id,
            cleaned_role_ids,
        )

    async def clear_guild_auto_roles(
        self,
        guild_id: int,
    ):

        await self.execute(
            """
            DELETE FROM guild_auto_role_entries
            WHERE guild_id = $1
            """,
            guild_id,
        )

    async def save_guild_auto_roles(
        self,
        guild_id: int,
        role_ids: list[int],
    ):
        """
        Replace all saved join auto roles for a guild.

        This helper is kept for convenience while the panel itself
        normally uses add/remove/clear operations.
        """

        cleaned_role_ids = list(
            dict.fromkeys(
                int(role_id)
                for role_id in role_ids
                if role_id
            )
        )

        if not self.pool:
            raise RuntimeError(
                (
                    "Database pool is not initialized. "
                    "Call db.connect() first."
                )
            )

        async with self.pool.acquire() as conn:

            async with conn.transaction():

                await conn.execute(
                    """
                    DELETE FROM guild_auto_role_entries
                    WHERE guild_id = $1
                    """,
                    guild_id,
                )

                if cleaned_role_ids:

                    await conn.execute(
                        """
                        INSERT INTO guild_auto_role_entries (
                            guild_id,
                            role_id
                        )
                        SELECT
                            $1,
                            roles.role_id
                        FROM UNNEST(
                            $2::BIGINT[]
                        ) AS roles(role_id)
                        ON CONFLICT (
                            guild_id,
                            role_id
                        )
                        DO NOTHING
                        """,
                        guild_id,
                        cleaned_role_ids,
                    )


# ==================================================
# SHARED DATABASE INSTANCE
# ==================================================

db = Database()
