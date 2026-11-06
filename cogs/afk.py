"""Pillow Palace AFK, Discord presence and chat-activity dashboard (discord.py 2.x).

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
REFRESH_SECONDS = 15
EVENT_DEBOUNCE_SECONDS = 3
MAX_LINES = 18  # keep dashboard safely below Discord's embed limits
MENTION_NOTICE_DELETE_SECONDS = 10
MENTION_NOTICE_COOLDOWN_SECONDS = 30


class AFK(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ready = asyncio.Event()
        self._update_lock = asyncio.Lock()
        self._pending_updates = {}
        self._initialise_task = None
        self._mention_notice_times = {}

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
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS afk_initialized (
                guild_id BIGINT PRIMARY KEY,
                initialised_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        self._ready.set()
        self._initialise_task = asyncio.create_task(self._initialise_members())
        if not self.refresh_dashboards.is_running():
            self.refresh_dashboards.start()

    def cog_unload(self):
        self.refresh_dashboards.cancel()
        if self._initialise_task:
            self._initialise_task.cancel()
        for task in self._pending_updates.values():
            task.cancel()
        self._pending_updates.clear()

    async def _server_members(self, guild: discord.Guild):
        """Retrieve members; full server enumeration requires Members intent."""
        if self.bot.intents.members:
            try:
                return [m async for m in guild.fetch_members(limit=None) if not m.bot], True
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Could not fetch full member list for %s", guild.id)
        return [m for m in guild.members if not m.bot], False

    async def _seed_members(self, guild: discord.Guild, reset: bool = False):
        members, complete = await self._server_members(guild)
        if not members:
            return 0, complete
        now = datetime.now(timezone.utc)
        for member in members:
            if reset:
                await self.bot.db.execute("""
                    INSERT INTO afk_members (guild_id, user_id, last_message, afk_since, reason, manual)
                    VALUES ($1, $2, $3, NULL, NULL, FALSE)
                    ON CONFLICT (guild_id, user_id) DO UPDATE SET
                        last_message=$3, afk_since=NULL, reason=NULL, manual=FALSE
                """, guild.id, member.id, now)
            else:
                await self.bot.db.execute("""
                    INSERT INTO afk_members (guild_id, user_id, last_message)
                    VALUES ($1, $2, $3) ON CONFLICT (guild_id, user_id) DO NOTHING
                """, guild.id, member.id, now)
        self.schedule_dashboard_update(guild.id)
        return len(members), complete

    async def _initialise_members(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                existing = await self.bot.db.fetchrow(
                    "SELECT guild_id FROM afk_initialized WHERE guild_id=$1", guild.id
                )
                count, complete = await self._seed_members(guild, reset=not bool(existing))
                # Only mark initialisation complete if all members were retrieved.
                if complete and not existing:
                    await self.bot.db.execute("""
                        INSERT INTO afk_initialized (guild_id) VALUES ($1)
                        ON CONFLICT (guild_id) DO NOTHING
                    """, guild.id)
                log.info("AFK seeded %s members for %s (complete=%s)", count, guild.id, complete)
            except Exception:
                log.exception("AFK member initialisation failed for %s", guild.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot and self._ready.is_set():
            await self.bot.db.execute("""
                INSERT INTO afk_members (guild_id, user_id, last_message)
                VALUES ($1, $2, $3) ON CONFLICT (guild_id, user_id) DO NOTHING
            """, member.guild.id, member.id, datetime.now(timezone.utc))
            self.schedule_dashboard_update(member.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.bot.db.execute(
            "DELETE FROM afk_members WHERE guild_id=$1 AND user_id=$2",
            member.guild.id, member.id,
        )
        self.schedule_dashboard_update(member.guild.id)

    @app_commands.command(name="afkreset", description="Mark all server members active now (admin only).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def afkreset(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            count, complete = await self._seed_members(interaction.guild, reset=True)
            await interaction.followup.send(
                f"🟢 Marked **{count}** members active now. "
                + ("They will become AFK after 30 minutes without a message."
                   if complete else "⚠️ This is only the cached member list. Enable Server Members Intent in Discord Developer Portal and in your bot's intents for everyone."),
                ephemeral=True,
            )
        except Exception:
            log.exception("AFK reset failed")
            await interaction.followup.send("Could not reset member activity; check bot logs.", ephemeral=True)

    def schedule_dashboard_update(self, guild_id: int):
        """Coalesce bursts of activity into one Discord message edit."""
        pending = self._pending_updates.get(guild_id)
        if pending and not pending.done():
            return
        self._pending_updates[guild_id] = asyncio.create_task(
            self._delayed_dashboard_update(guild_id)
        )

    async def _delayed_dashboard_update(self, guild_id: int):
        try:
            await asyncio.sleep(EVENT_DEBOUNCE_SECONDS)
            await self.update_dashboard(guild_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("AFK immediate dashboard update failed for %s", guild_id)
        finally:
            self._pending_updates.pop(guild_id, None)

    @staticmethod
    def _utc(value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Refresh when Discord presence changes; no database write needed."""
        if not self._ready.is_set() or after.bot:
            return
        if before.status != after.status:
            self.schedule_dashboard_update(after.guild.id)

    @staticmethod
    def _presence(member: discord.Member | None, enabled: bool):
        if not enabled or member is None:
            return "⚪ Unknown", "unknown"
        status = member.status
        if status == discord.Status.online:
            return "🟢 Online", "online"
        if status == discord.Status.idle:
            return "🌙 Idle", "idle"
        if status == discord.Status.dnd:
            return "⛔ DND", "dnd"
        return "⚫ Offline", "offline"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self._ready.is_set() or message.guild is None or message.author.bot:
            return
        now = datetime.now(timezone.utc)
        try:
            await self._notify_afk_mentions(message, now)
            await self.bot.db.execute("""
                INSERT INTO afk_members (guild_id, user_id, last_message, afk_since, reason, manual)
                VALUES ($1, $2, $3, NULL, NULL, FALSE)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET
                    last_message = EXCLUDED.last_message,
                    afk_since = NULL,
                    reason = NULL,
                    manual = FALSE
            """, message.guild.id, message.author.id, now)
            self.schedule_dashboard_update(message.guild.id)
        except Exception:
            log.exception("Could not update AFK activity")

    async def _notify_afk_mentions(self, message: discord.Message, now: datetime):
        """Post a short-lived public reply when a mentioned member is chat-AFK.

        Discord cannot send ephemeral replies to ordinary messages. We therefore
        delete the notice after a few seconds and suppress all mention pings.
        """
        mentioned = [m for m in message.mentions if not m.bot and m.id != message.author.id]
        if not mentioned:
            return
        unique = list({m.id: m for m in mentioned}.values())[:5]
        ids = [m.id for m in unique]
        try:
            rows = await self.bot.db.fetch(
                "SELECT user_id, last_message, afk_since, reason FROM afk_members "
                "WHERE guild_id=$1 AND user_id = ANY($2::BIGINT[])",
                message.guild.id, ids,
            )
        except Exception:
            log.exception("Could not check mentioned members' AFK statuses")
            return
        by_id = {row["user_id"]: row for row in rows}
        notices = []
        for member in unique:
            row = by_id.get(member.id)
            if row is None:
                continue
            last = self._utc(row["last_message"])
            since = self._utc(row["afk_since"])
            if since is None and (last is None or now - last < AFK_AFTER):
                continue
            key = (message.guild.id, message.channel.id, member.id)
            previous = self._mention_notice_times.get(key)
            if previous is not None and (now - previous).total_seconds() < MENTION_NOTICE_COOLDOWN_SECONDS:
                continue
            self._mention_notice_times[key] = now
            afk_start = since or last + AFK_AFTER
            reason = (row["reason"] or "").replace("\n", " ").replace("\r", " ")
            reason = discord.utils.escape_mentions(discord.utils.escape_markdown(reason[:120]))
            line = f"🌙 **{discord.utils.escape_markdown(member.display_name)}** is AFK (since <t:{int(afk_start.timestamp())}:R>)"
            if reason:
                line += f" — {reason}"
            notices.append(line)
        if not notices:
            return
        try:
            await message.reply(
                "\n".join(notices[:5]),
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
                delete_after=MENTION_NOTICE_DELETE_SECONDS,
            )
        except (discord.Forbidden, discord.HTTPException):
            log.debug("Unable to send AFK mention notice in channel %s", message.channel.id)

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
            self.schedule_dashboard_update(interaction.guild.id)
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
            self.schedule_dashboard_update(interaction.guild.id)
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
        presence, _ = self._presence(member, self.bot.intents.presences)
        await interaction.followup.send(
            f"**{member.display_name}**\nDiscord: {presence}\nChat: {msg}",
            ephemeral=True,
        )

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
            "Chat activity is separate from Discord online presence.", ephemeral=True,
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
            presence_counts = {"online": 0, "idle": 0, "dnd": 0, "offline": 0, "unknown": 0}
            presence_enabled = self.bot.intents.presences
            for r in rows:
                member = guild.get_member(r["user_id"])
                # With members intent, a cache miss is not proof someone left.
                # Show them with unknown presence rather than hiding them.
                label, presence_key = self._presence(member, presence_enabled)
                presence_counts[presence_key] += 1
                last = self._utc(r["last_message"])
                since = self._utc(r["afk_since"])
                if since or now - last >= AFK_AFTER:
                    start = since or last + AFK_AFTER
                    reason = (r["reason"] or "")[:60]
                    extra = f" — {discord.utils.escape_markdown(reason)}" if reason else ""
                    afk.append(f"<@{r['user_id']}> — {label} — AFK <t:{int(start.timestamp())}:R>{extra}")
                else:
                    active.append(f"<@{r['user_id']}> — {label} — last chat <t:{int(last.timestamp())}:R>")
            embed = discord.Embed(
                title="🌙 Pillow Palace | Member Activity",
                description=(
                    "**Discord presence** and **server chat activity** are separate. "
                    "Online members can still be AFK in chat.\n"
                    + (
                        f"🟢 Online: **{presence_counts['online']}**  |  "
                        f"🌙 Idle: **{presence_counts['idle']}**  |  "
                        f"⛔ DND: **{presence_counts['dnd']}**  |  "
                        f"⚫ Offline: **{presence_counts['offline']}**  |  "
                        f"⚪ Unknown: **{presence_counts['unknown']}**"
                        if presence_enabled else
                        "⚠️ Presence Intent is disabled: Discord statuses unavailable."
                    )
                ),
                colour=discord.Colour.blurple(),
            )
            embed.add_field(name=f"💬 Chat Active ({len(active)})", value=("\n".join(active[:MAX_LINES])[:1000] or "None"), inline=False)
            embed.add_field(name=f"🌙 Chat AFK ({len(afk)})", value=("\n".join(afk[:MAX_LINES])[:1000] or "None"), inline=False)
            if len(active) > MAX_LINES or len(afk) > MAX_LINES:
                embed.add_field(name="More members", value="Only the first 18 of each chat group are shown. Use `/activity` for totals or `/afkstatus` for an individual.", inline=False)
            embed.set_footer(text="Presence changes and chat activity: ~3s • automatic AFK checks: 15s • chat AFK after 30m")
            msg = None
            if config["message_id"]:
                try:
                    msg = await channel.fetch_message(config["message_id"])
                except discord.NotFound:
                    pass
            if msg:
                if msg.embeds and msg.embeds[0].to_dict() == embed.to_dict():
                    return
                await msg.edit(embed=embed)
            else:
                msg = await channel.send(embed=embed)
                await self.bot.db.execute(
                    "UPDATE afk_dashboards SET message_id=$2 WHERE guild_id=$1",
                    guild_id, msg.id,
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(AFK(bot))
