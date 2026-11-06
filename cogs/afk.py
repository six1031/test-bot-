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
        if not self.refresh_dashboards.is_running():
            self.refresh_dashboards.start()

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

    @app_commands.command(name="back", description="Mark yourself active again.")
    async def back(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            now = datetime.now(timezone.utc)
            await self.bot.db.execute("""
                INSERT INTO afk_members (guild_id, user_id, last_message)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET
                    last_message = EXCLUDED.last_message,
                    afk_since = NULL,
                    reason = NULL,
                    manual = FALSE
            """, interaction.guild.id, interaction.user.id, now)
            await interaction.followup.send("🟢 You're marked active again.", ephemeral=True)
        except Exception:
            log.exception("Failed to clear AFK")
            await interaction.followup.send("Couldn't update your status.", ephemeral=True)

    @app_commands.command(name="afkstatus", description="Check a member's chat activity status.")
    async def afkstatus(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.guild is None:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        row = await self.bot.db.fetchrow(
            "SELECT last_message, afk_since, reason FROM afk_members WHERE guild_id=$1 AND user_id=$2",
            interaction.guild.id, member.id,
        )
        if not row:
            msg = "No recorded message activity yet."
        else:
            now = datetime.now(timezone.utc)
            last = self._utc(row["last_message"])
            since = self._utc(row["afk_since"])
            if since or now - last >= AFK_AFTER:
                start = since or last + AFK_AFTER
                msg = f"🌙 AFK since <t:{int(start.timestamp())}:R>."
                if row["reason"]:
                    msg += f" Reason: {discord.utils.escape_markdown(row['reason'])}"
            else:
                msg = f"🟢 Active in chat; last message <t:{int(last.timestamp())}:R>."
        await interaction.followup.send(f"**{member.display_name}**: {msg}", ephemeral=True)

    @app_commands.command(name="afksetup", description="Set the AFK dashboard's text channel (admin only).")
    @app_commands.describe(channel="Channel to host the automatically updated AFK dashboard")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def afksetup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        me = interaction.guild.me
        perms = channel.permissions_for(me)
        if not (perms.view_channel and perms.send_messages and perms.embed_links and perms.read_message_history):
            return await interaction.response.send_message(
                "I need View Channel, Send Messages, Embed Links and Read Message History there.", ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.db.execute("""
                INSERT INTO afk_dashboards (guild_id, channel_id, message_id)
                VALUES ($1, $2, NULL)
                ON CONFLICT (guild_id) DO UPDATE SET
                    channel_id = EXCLUDED.channel_id,
                    message_id = CASE WHEN afk_dashboards.channel_id = EXCLUDED.channel_id
                        THEN afk_dashboards.message_id ELSE NULL END
            """, interaction.guild.id, channel.id)
            await self.update_dashboard(interaction.guild.id)
            await interaction.followup.send(f"✅ Dashboard configured in {channel.mention}.", ephemeral=True)
        except Exception:
            log.exception("Failed to configure AFK dashboard")
            await interaction.followup.send("Couldn't configure the dashboard. Check database and bot logs.", ephemeral=True)

    @app_commands.command(name="activity", description="Show the server's current chat activity totals.")
    async def activity(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        rows = await self.bot.db.fetch(
            "SELECT last_message, afk_since FROM afk_members WHERE guild_id=$1",
            interaction.guild.id,
        )
        now = datetime.now(timezone.utc)
        active = sum(1 for r in rows if r["afk_since"] is None and now - self._utc(r["last_message"]) < AFK_AFTER)
        await interaction.response.send_message(
            f"🟢 Active: **{active}** | 🌙 AFK: **{len(rows)-active}** | Tracked: **{len(rows)}**\n"
            "Based on messages sent in this server, not Discord presence.", ephemeral=True,
        )

    @tasks.loop(seconds=REFRESH_SECONDS)
    async def refresh_dashboards(self):
        await self._ready.wait()
        try:
            dashboards = await self.bot.db.fetch("SELECT guild_id FROM afk_dashboards")
            for entry in dashboards:
                try:
                    await self.update_dashboard(entry["guild_id"])
                except Exception:
                    log.exception("Failed to refresh AFK dashboard for %s", entry["guild_id"])
        except Exception:
            log.exception("AFK dashboard refresh failed")

    @refresh_dashboards.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()

    async def update_dashboard(self, guild_id: int):
        async with self._update_lock:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return
            config = await self.bot.db.fetchrow(
                "SELECT channel_id, message_id FROM afk_dashboards WHERE guild_id=$1", guild_id,
            )
            if not config:
                return
            channel = guild.get_channel(config["channel_id"])
            if not isinstance(channel, discord.TextChannel):
                log.warning("AFK dashboard channel missing in guild %s", guild_id)
                return
            rows = await self.bot.db.fetch("""
                SELECT user_id, last_message, afk_since, reason FROM afk_members
                WHERE guild_id=$1 ORDER BY last_message DESC
            """, guild_id)
            now = datetime.now(timezone.utc)
            active, afk = [], []
            for r in rows:
                member = guild.get_member(r["user_id"])
                if member is None:
                    continue  # do not show users who are no longer cached in the server
                last = self._utc(r["last_message"])
                since = self._utc(r["afk_since"])
                if since or now - last >= AFK_AFTER:
                    start = since or last + AFK_AFTER
                    reason = (r["reason"] or "")[:60]
                    extra = f" — {discord.utils.escape_markdown(reason)}" if reason else ""
                    afk.append(f"{member.mention} — <t:{int(start.timestamp())}:R>{extra}")
                else:
                    active.append(f"{member.mention} — <t:{int(last.timestamp())}:R>")
            embed = discord.Embed(
                title="🌙 Pillow Palace | Member Activity",
                description="Based on messages sent in this server, not Discord online status. Members appear after their first tracked message.",
                colour=discord.Colour.blurple(), timestamp=now,
            )
            embed.add_field(name=f"🟢 Active ({len(active)})", value=("\n".join(active[:MAX_LINES])[:1000] or "None"), inline=False)
            embed.add_field(name=f"🌙 AFK ({len(afk)})", value=("\n".join(afk[:MAX_LINES])[:1000] or "None"), inline=False)
            if len(active) > MAX_LINES or len(afk) > MAX_LINES:
                embed.add_field(name="More members", value="Use `/activity` for totals or `/afkstatus` for a member's status.", inline=False)
            embed.set_footer(text="Refreshes every 60 seconds • AFK after 30 minutes")
            msg = None
            if config["message_id"]:
                try:
                    msg = await channel.fetch_message(config["message_id"])
                except discord.NotFound:
                    pass
            if msg:
                await msg.edit(embed=embed)
            else:
                msg = await channel.send(embed=embed)
                await self.bot.db.execute(
                    "UPDATE afk_dashboards SET message_id=$2 WHERE guild_id=$1",
                    guild_id, msg.id,
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(AFK(bot))
