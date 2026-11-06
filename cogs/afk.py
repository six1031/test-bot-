"""Pillow Palace AFK and chat-activity dashboard (discord.py 2.x).

Requires bot.db.execute(query, *args), bot.db.fetch(query, *args), and
bot.db.fetchrow(query, *args), backed by PostgreSQL/asyncpg.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

log = logging.getLogger(__name__)
AFK_AFTER = timedelta(minutes=30)
REFRESH_SECONDS = 60
MAX_LINES = 18  # keep dashboard safely below Discord's embed limits


class AFK(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ready = asyncio.Event()
        self._update_lock = asyncio.Lock()
        self.refresh_dashboards.start()

    async def cog_load(self):
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS afk_members (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                last_message TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                afk_since TIMESTAMPTZ,
                reason TEXT,
                manual BOOLEAN NOT NULL DEFAULT FALSE,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS afk_dashboards (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                message_id BIGINT
            )
        """)
        self._ready.set()

    def cog_unload(self):
        self.refresh_dashboards.cancel()

    @staticmethod
    def _utc(value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self._ready.is_set() or message.guild is None or message.author.bot:
            return
        now = datetime.now(timezone.utc)
        try:
            await self.bot.db.execute("""
                INSERT INTO afk_members (guild_id, user_id, last_message, afk_since, reason, manual)
                VALUES ($1, $2, $3, NULL, NULL, FALSE)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET
                    last_message = EXCLUDED.last_message,
                    afk_since = NULL,
                    reason = NULL,
                    manual = FALSE
            """, message.guild.id, message.author.id, now)
        except Exception:
            log.exception("Could not update AFK activity")

    @app_commands.command(name="afk", description="Set yourself as AFK, optionally with a reason.")
    @app_commands.describe(reason="Optional AFK reason")
    async def afk(self, interaction: discord.Interaction, reason: str = "Away"):
        if interaction.guild is None:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        reason = reason.strip()[:200] or "Away"
        now = datetime.now(timezone.utc)
        try:
            await self.bot.db.execute("""
                INSERT INTO afk_members (guild_id, user_id, last_message, afk_since, reason, manual)
                VALUES ($1, $2, $3, $3, $4, TRUE)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET
                    afk_since = EXCLUDED.afk_since,
                    reason = EXCLUDED.reason,
                    manual = TRUE
            """, interaction.guild.id, interaction.user.id, now, reason)
            await interaction.followup.send(f"🌙 You're now AFK. Reason: **{discord.utils.escape_markdown(reason)}**. Send a message or use `/back` to return.", ephemeral=True)
        except Exception:
            log.exception("Failed to set AFK")
            await interaction.followup.send("Couldn't save your AFK status.", ephemeral=True)
            
    async def setup(bot: commands.Bot):
        await bot.add_cog(AFK(bot))
