import asyncpg
from . import db  # adjust if your Database instance lives elsewhere


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

async def get_game_state(guild_id: int) -> dict:
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM game_state
            WHERE guild_id = $1
            """,
            guild_id,
        )

        if row is None:
            # Create default row
            await conn.execute(
                """
                INSERT INTO game_state (
                    guild_id,
                    counting_channel,
                    counting_enabled,
                    current_count,
                    last_counter,
                    wordchain_channel,
                    wordchain_enabled,
                    last_word,
                    used_words,
                    word_last_counter
                )
                VALUES ($1, NULL, TRUE, 0, NULL, NULL, TRUE, '', '{}', NULL)
                """,
                guild_id,
            )

            row = await conn.fetchrow(
                """
                SELECT *
                FROM game_state
                WHERE guild_id = $1
                """,
                guild_id,
            )

        return dict(row)


async def save_settings(
    guild_id: int,
    counting_channel: int | None,
    counting_enabled: bool,
    wordchain_channel: int | None,
    wordchain_enabled: bool,
):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE game_state
            SET
                counting_channel = $2,
                counting_enabled = $3,
                wordchain_channel = $4,
                wordchain_enabled = $5
            WHERE guild_id = $1
            """,
            guild_id,
            counting_channel,
            counting_enabled,
            wordchain_channel,
            wordchain_enabled,
        )


async def save_game_state(
    guild_id: int,
    current_count: int,
    last_counter: int | None,
    last_word: str,
    used_words: list[str],
    word_last_counter: int | None,
):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE game_state
            SET
                current_count = $2,
                last_counter = $3,
                last_word = $4,
                used_words = $5,
                word_last_counter = $6
            WHERE guild_id = $1
            """,
            guild_id,
            current_count,
            last_counter,
            last_word,
            used_words,
            word_last_counter,
        )


# Optional wrappers if you still want these names:

async def save_counting(guild_id: int, current_count: int, last_counter: int | None):
    state = await get_game_state(guild_id)
    await save_game_state(
        guild_id,
        current_count,
        last_counter,
        state["last_word"],
        state["used_words"],
        state["word_last_counter"],
    )


async def save_wordchain(
    guild_id: int,
    last_word: str,
    used_words: list[str],
    word_last_counter: int | None,
):
    state = await get_game_state(guild_id)
    await save_game_state(
        guild_id,
        state["current_count"],
        state["last_counter"],
        last_word,
        used_words,
        word_last_counter,
    )
