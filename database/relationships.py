from database.database import db


# ==================================================
# RELATIONSHIPS TABLE FUNCTIONS
# ==================================================

async def add_relationship(user_id: int, partner_id: int, rtype: str):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO relationships (user_id, partner_id, relationship_type)
            VALUES ($1, $2, $3)
            """,
            user_id,
            partner_id,
            rtype
        )


async def remove_relationship(user_id: int, partner_id: int):
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM relationships
            WHERE user_id = $1 AND partner_id = $2
            """,
            user_id,
            partner_id
        )
    return result  # "DELETE 0" or "DELETE 1"


async def get_relationships(user_id: int):
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT partner_id, relationship_type
            FROM relationships
            WHERE user_id = $1
            """,
            user_id
        )
    return rows


# ==================================================
# MARRIAGE TABLE FUNCTIONS
# ==================================================

async def get_marriage(user_id: int):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT *
            FROM marriages
            WHERE user1_id = $1 OR user2_id = $1
            """,
            user_id
        )


async def is_married(user_id: int):
    return await get_marriage(user_id) is not None


async def create_marriage(user1_id: int, user2_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO marriages (user1_id, user2_id)
            VALUES ($1, $2)
            """,
            user1_id,
            user2_id
        )


async def delete_marriage(marriage_id: int):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM marriages
            WHERE id = $1
            """,
            marriage_id
        )


async def get_spouse(user_id: int):
    marriage = await get_marriage(user_id)
    if not marriage:
        return None

    if marriage["user1_id"] == user_id:
        return marriage["user2_id"]
    return marriage["user1_id"]
