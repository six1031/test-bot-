from database.database import db


# ==================================================
# DATABASE SETUP / MIGRATION
# ==================================================

async def init_relationship_tables():
    """
    Makes sure relationships can contain multiple relationship
    types between the same two people.

    Example:
        User A -> User B -> spouse
        User A -> User B -> little

    Both rows are allowed.
    """

    if not db.pool:
        raise RuntimeError(
            "Database pool is not initialized."
        )

    async with db.pool.acquire() as conn:

        # --------------------------------------------------
        # RELATIONSHIPS TABLE
        # --------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationships (
                user_id BIGINT NOT NULL,
                partner_id BIGINT NOT NULL,
                relationship_type TEXT NOT NULL
            )
            """
        )

        # --------------------------------------------------
        # MARRIAGES TABLE
        # --------------------------------------------------

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS marriages (
                id SERIAL PRIMARY KEY,
                user1_id BIGINT NOT NULL,
                user2_id BIGINT NOT NULL
            )
            """
        )

        # --------------------------------------------------
        # REMOVE OLD UNIQUE CONSTRAINT
        #
        # Older versions may only allow one relationship
        # between the same two users.
        # --------------------------------------------------

        constraints = await conn.fetch(
            """
            SELECT
                tc.constraint_name,
                array_agg(
                    kcu.column_name::text
                    ORDER BY kcu.ordinal_position
                ) AS columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'public'
              AND tc.table_name = 'relationships'
              AND tc.constraint_type IN (
                    'PRIMARY KEY',
                    'UNIQUE'
              )
            GROUP BY
                tc.constraint_name
            """
        )

        for row in constraints:

            columns = list(
                row["columns"]
            )

            if (
                len(columns) == 2
                and set(columns)
                == {
                    "user_id",
                    "partner_id",
                }
            ):
                constraint_name = (
                    row["constraint_name"]
                    .replace('"', '""')
                )

                await conn.execute(
                    f"""
                    ALTER TABLE relationships
                    DROP CONSTRAINT IF EXISTS
                    "{constraint_name}"
                    """
                )

        # --------------------------------------------------
        # REMOVE OLD UNIQUE INDEX
        # --------------------------------------------------

        indexes = await conn.fetch(
            """
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'relationships'
            """
        )

        for row in indexes:

            indexdef = (
                row["indexdef"]
                .lower()
                .replace('"', "")
                .replace(" ", "")
            )

            if (
                "createuniqueindex" in indexdef
                and "(user_id,partner_id)" in indexdef
                and "relationship_type" not in indexdef
            ):
                index_name = (
                    row["indexname"]
                    .replace('"', '""')
                )

                await conn.execute(
                    f"""
                    DROP INDEX IF EXISTS
                    "{index_name}"
                    """
                )

        # --------------------------------------------------
        # REMOVE EXACT DUPLICATES
        # --------------------------------------------------

        await conn.execute(
            """
            DELETE FROM relationships a
            USING relationships b
            WHERE a.ctid < b.ctid
              AND a.user_id = b.user_id
              AND a.partner_id = b.partner_id
              AND a.relationship_type
                  = b.relationship_type
            """
        )

        # --------------------------------------------------
        # NEW UNIQUE INDEX
        #
        # The same two people can now have multiple
        # relationship types, but not duplicate the exact
        # same type.
        # --------------------------------------------------

        await conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            relationships_user_partner_type_unique
            ON relationships (
                user_id,
                partner_id,
                relationship_type
            )
            """
        )


# ==================================================
# RELATIONSHIP FUNCTIONS
# ==================================================

async def add_relationship(
    user_id: int,
    partner_id: int,
    rtype: str,
):
    """
    Adds one specific relationship type.

    The same two users may have multiple different types,
    for example spouse + little.
    """

    async with db.pool.acquire() as conn:

        await conn.execute(
            """
            INSERT INTO relationships (
                user_id,
                partner_id,
                relationship_type
            )
            VALUES ($1, $2, $3)

            ON CONFLICT (
                user_id,
                partner_id,
                relationship_type
            )
            DO NOTHING
            """,
            user_id,
            partner_id,
            rtype,
        )


async def remove_relationship(
    user_id: int,
    partner_id: int,
    rtype: str | None = None,
):
    """
    Removes a relationship.

    If rtype is supplied, ONLY that relationship type
    is removed.

    Example:
        remove_relationship(a, b, "spouse")

    will leave Little/Pet/etc relationships untouched.
    """

    async with db.pool.acquire() as conn:

        if rtype is None:

            return await conn.execute(
                """
                DELETE FROM relationships
                WHERE user_id = $1
                  AND partner_id = $2
                """,
                user_id,
                partner_id,
            )

        return await conn.execute(
            """
            DELETE FROM relationships
            WHERE user_id = $1
              AND partner_id = $2
              AND relationship_type = $3
            """,
            user_id,
            partner_id,
            rtype,
        )


async def relationship_exists(
    user_id: int,
    partner_id: int,
    rtype: str,
):
    async with db.pool.acquire() as conn:

        row = await conn.fetchrow(
            """
            SELECT 1
            FROM relationships
            WHERE user_id = $1
              AND partner_id = $2
              AND relationship_type = $3
            LIMIT 1
            """,
            user_id,
            partner_id,
            rtype,
        )

    return row is not None


async def get_relationships(
    user_id: int,
):
    async with db.pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                partner_id,
                relationship_type
            FROM relationships
            WHERE user_id = $1
            ORDER BY
                relationship_type,
                partner_id
            """,
            user_id,
        )

    return rows


async def get_relationships_between(
    user_id: int,
    partner_id: int,
):
    async with db.pool.acquire() as conn:

        rows = await conn.fetch(
            """
            SELECT
                partner_id,
                relationship_type
            FROM relationships
            WHERE user_id = $1
              AND partner_id = $2
            ORDER BY relationship_type
            """,
            user_id,
            partner_id,
        )

    return rows


# ==================================================
# MARRIAGE FUNCTIONS
# ==================================================

async def get_marriage(
    user_id: int,
):
    async with db.pool.acquire() as conn:

        return await conn.fetchrow(
            """
            SELECT *
            FROM marriages
            WHERE user1_id = $1
               OR user2_id = $1
            LIMIT 1
            """,
            user_id,
        )


async def is_married(
    user_id: int,
):
    return (
        await get_marriage(
            user_id
        )
    ) is not None


async def create_marriage(
    user1_id: int,
    user2_id: int,
):
    async with db.pool.acquire() as conn:

        await conn.execute(
            """
            INSERT INTO marriages (
                user1_id,
                user2_id
            )
            VALUES ($1, $2)
            """,
            user1_id,
            user2_id,
        )


async def delete_marriage(
    marriage_id: int,
):
    async with db.pool.acquire() as conn:

        await conn.execute(
            """
            DELETE FROM marriages
            WHERE id = $1
            """,
            marriage_id,
        )


async def get_spouse(
    user_id: int,
):
    marriage = await get_marriage(
        user_id
    )

    if not marriage:
        return None

    if marriage["user1_id"] == user_id:
        return marriage[
            "user2_id"
        ]

    return marriage[
        "user1_id"
    ]
