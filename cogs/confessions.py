"""Pillow Palace anonymous confessions cog (discord.py 2.x, asyncpg-style db).

Install as cogs/confessions.py. Requires bot.db.execute/fetchrow/fetch methods.
Confessions are anonymous publicly; a private moderation channel logs the author.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)
COOLDOWN_SECONDS = 300
MAX_LENGTH = 1500


class ConfessionModal(discord.ui.Modal, title="Anonymous Confession"):
    confession = discord.ui.TextInput(
        label="Your confession",
        placeholder="Write your anonymous confession here...",
        style=discord.TextStyle.paragraph,
        min_length=1,
        max_length=MAX_LENGTH,
        required=True,
    )

    def __init__(self, cog: "Confessions"):
        super().__init__(timeout=300)
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.submit_confession(interaction, str(self.confession.value))


class ConfessionButtons(discord.ui.View):
    """Persistent buttons; custom IDs remain valid after bot restarts."""

    def __init__(self, cog: "Confessions"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Open Support Thread", style=discord.ButtonStyle.secondary,
        emoji="💬", custom_id="pillow_confessions:support_thread",
    )
    async def support_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.open_support_thread(interaction)

    @discord.ui.button(
        label="Submit a Confession", style=discord.ButtonStyle.primary,
        emoji="💌", custom_id="pillow_confessions:submit",
    )
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.open_confession_modal(interaction)


class Confessions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ready = asyncio.Event()
        self._locks: dict[int, asyncio.Lock] = {}
        self._thread_locks: dict[int, asyncio.Lock] = {}
        # In-memory cooldowns only: never persist member IDs alongside confessions.
        self._cooldowns: dict[tuple[int, int], datetime] = {}

    async def cog_load(self):
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS confession_settings (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                log_channel_id BIGINT
            )
        """)
        await self.bot.db.execute("""
            CREATE TABLE IF NOT EXISTS confession_counters (
                guild_id BIGINT PRIMARY KEY,
                last_number BIGINT NOT NULL DEFAULT 0
            )
        """)
        # Safe migration for installations running the previous version.
        await self.bot.db.execute("""
            ALTER TABLE confession_settings
            ADD COLUMN IF NOT EXISTS log_channel_id BIGINT
        """)
        self.bot.add_view(ConfessionButtons(self))
        self._ready.set()

    async def _setting(self, guild_id: int):
        await self._ready.wait()
        return await self.bot.db.fetchrow(
            "SELECT channel_id, log_channel_id, enabled FROM confession_settings WHERE guild_id=$1",
            guild_id,
        )

    @staticmethod
    def _safe_text(text: str) -> str:
        # Prevent mass mentions, role pings, and user pings. No Markdown escaping:
        # allowed_mentions=None prevents actual notification delivery.
        return text.strip().replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")

    async def open_confession_modal(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        try:
            setting = await self._setting(interaction.guild_id)
        except Exception:
            log.exception("Confession configuration lookup failed")
            return await interaction.response.send_message("Confessions are temporarily unavailable.", ephemeral=True)
        if not setting or not setting["enabled"]:
            return await interaction.response.send_message("Anonymous confessions are not enabled here yet.", ephemeral=True)
        if not setting["log_channel_id"]:
            return await interaction.response.send_message(
                "The private moderation log is not configured yet. Please contact an administrator.", ephemeral=True
            )
        await interaction.response.send_modal(ConfessionModal(self))

    @app_commands.command(name="confess", description="Submit an anonymous confession privately.")
    @app_commands.guild_only()
    async def confess(self, interaction: discord.Interaction):
        await self.open_confession_modal(interaction)

    async def open_support_thread(self, interaction: discord.Interaction):
        """Create a public discussion thread for this confession, or reuse it."""
        message = interaction.message
        if not interaction.guild or not message or not isinstance(message.channel, discord.TextChannel):
            return await interaction.response.send_message("This button works only on a confession post.", ephemeral=True)
        if message.author.id != self.bot.user.id or not message.embeds or not message.embeds[0].title or not message.embeds[0].title.startswith("💌 Anonymous Confession #"):
            return await interaction.response.send_message("This isn't a confession post.", ephemeral=True)
        try:
            setting = await self._setting(interaction.guild.id)
            if not setting or message.channel.id != setting["channel_id"]:
                return await interaction.response.send_message("This isn't the configured confession channel.", ephemeral=True)
        except Exception:
            log.exception("Failed to check confession channel")
            return await interaction.response.send_message("Could not check confession settings.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        lock = self._thread_locks.setdefault(message.id, asyncio.Lock())
        async with lock:
            try:
                # A public thread created from a message normally shares its ID.
                thread = message.thread or interaction.guild.get_thread(message.id)
                if thread is None:
                    try:
                        existing = await self.bot.fetch_channel(message.id)
                        if isinstance(existing, discord.Thread):
                            thread = existing
                    except (discord.NotFound, discord.Forbidden):
                        pass
                if thread is None:
                    number = message.embeds[0].title.rsplit("#", 1)[-1]
                    thread = await message.create_thread(
                        name=f"💜 Support for confession #{number}",
                        auto_archive_duration=1440,
                        reason="Support discussion for an anonymous confession",
                    )
                    await thread.send(
                        "💜 This is a supportive space to discuss the confession. "
                        "Please be kind, respect privacy, and follow the server rules. "
                        "The original author remains anonymous.",
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                if thread.archived or thread.locked:
                    # Archived threads may be reopened by users with appropriate permissions.
                    try:
                        if not thread.locked:
                            await thread.edit(archived=False)
                    except discord.HTTPException:
                        pass
                await interaction.followup.send(
                    f"💬 Support discussion: {thread.mention}", ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "I need **Create Public Threads**, **Send Messages in Threads**, and **Manage Threads** "
                    "(if reopening locked threads) in the confession channel.", ephemeral=True,
                )
            except discord.HTTPException:
                log.exception("Could not open confession thread for message %s", message.id)
                await interaction.followup.send(
                    "I couldn't open the support thread. Please ask a moderator to check thread permissions.",
                    ephemeral=True,
                )

    async def submit_confession(self, interaction: discord.Interaction, text: str):
        if interaction.guild_id is None:
            return await interaction.response.send_message("Use this command in a server.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild_id = interaction.guild_id
        key = (guild_id, interaction.user.id)
        lock = self._locks.setdefault(guild_id, asyncio.Lock())
        async with lock:
            now = datetime.now(timezone.utc)
            # Drop expired cooldown entries to keep memory usage bounded.
            if len(self._cooldowns) > 5000:
                self._cooldowns = {k: t for k, t in self._cooldowns.items() if t > now}
            expiry = self._cooldowns.get(key)
            if expiry and expiry > now:
                wait = int((expiry - now).total_seconds()) + 1
                return await interaction.followup.send(
                    f"Please wait {wait} seconds before sending another confession.", ephemeral=True
                )
            try:
                setting = await self._setting(guild_id)
                if not setting or not setting["enabled"]:
                    return await interaction.followup.send("Confessions are currently disabled.", ephemeral=True)
                channel = interaction.guild.get_channel(setting["channel_id"]) if interaction.guild else None
                if channel is None and interaction.guild:
                    try:
                        channel = await interaction.guild.fetch_channel(setting["channel_id"])
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
                if not isinstance(channel, discord.TextChannel):
                    return await interaction.followup.send(
                        "The confession channel is unavailable. Please contact an administrator.", ephemeral=True
                    )
                log_channel_id = setting["log_channel_id"]
                if not log_channel_id:
                    return await interaction.followup.send(
                        "The private moderation log is not configured. Ask an administrator to run `/confessionsetup`.",
                        ephemeral=True,
                    )
                log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel is None:
                    try:
                        log_channel = await interaction.guild.fetch_channel(log_channel_id)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
                if not isinstance(log_channel, discord.TextChannel):
                    return await interaction.followup.send(
                        "The private confession log channel is unavailable. Contact an administrator.", ephemeral=True
                    )
                # Fail closed if the bot cannot access the moderation log.
                me = interaction.guild.me
                if me:
                    perms = log_channel.permissions_for(me)
                    if not (perms.view_channel and perms.send_messages and perms.embed_links):
                        return await interaction.followup.send(
                            "The bot cannot post to the private confession log. Contact an administrator.",
                            ephemeral=True,
                        )
                # Allocate the next number atomically. Failed sends may leave gaps,
                # which is safer than accidentally publishing duplicate numbers.
                row = await self.bot.db.fetchrow("""
                    INSERT INTO confession_counters (guild_id, last_number)
                    VALUES ($1, 1)
                    ON CONFLICT (guild_id) DO UPDATE
                        SET last_number = confession_counters.last_number + 1
                    RETURNING last_number
                """, guild_id)
                number = row["last_number"]
                embed = discord.Embed(
                    title=f"💌 Anonymous Confession #{number:04d}",
                    description=self._safe_text(text),
                    color=discord.Color.from_rgb(183, 142, 211),
                    timestamp=now,
                )
                embed.set_footer(text="Pillow Palace • Submitted anonymously")
                # Log the author BEFORE publishing. Never post publicly if logging fails.
                # The moderation log intentionally contains identifiable information.
                author = interaction.user
                audit = discord.Embed(
                    title=f"🔒 Confession #{number:04d} • Moderation Log",
                    description=(
                        f"**Submitted by:** {discord.utils.escape_markdown(str(author))} "
                        f"(`{author.id}`)\n"
                        f"**Member:** {author.mention}\n"
                        f"**Status:** Pending publication"
                    ),
                    color=discord.Color.orange(),
                    timestamp=now,
                )
                audit_message = await log_channel.send(
                    embed=audit, allowed_mentions=discord.AllowedMentions.none()
                )
                try:
                    public_message = await channel.send(
                        embed=embed, view=ConfessionButtons(self), allowed_mentions=discord.AllowedMentions.none()
                    )
                except Exception:
                    audit.color = discord.Color.red()
                    audit.add_field(name="Publication", value="Failed to post publicly", inline=False)
                    try:
                        await audit_message.edit(embed=audit)
                    except discord.HTTPException:
                        log.exception("Could not update failed confession audit %s", number)
                    raise
                self._cooldowns[key] = now + timedelta(seconds=COOLDOWN_SECONDS)
                audit.color = discord.Color.green()
                audit.add_field(name="Published", value=public_message.jump_url, inline=False)
                try:
                    await audit_message.edit(embed=audit)
                except discord.HTTPException:
                    log.warning("Confession %s published but audit link update failed", number)
            except discord.Forbidden:
                log.warning("No permission to post confession in guild %s", guild_id)
                return await interaction.followup.send(
                    "I don't have permission to post in the confession channel.", ephemeral=True
                )
            except Exception:
                log.exception("Failed to publish confession in guild %s", guild_id)
                return await interaction.followup.send(
                    "Sorry, I couldn't publish your confession. Please try again later.", ephemeral=True
                )
        await interaction.followup.send(
            f"Your confession **#{number:04d}** was posted anonymously. 💜", ephemeral=True
        )

    @app_commands.command(name="confessionsetup", description="Set public confessions and private author-log channels.")
    @app_commands.describe(
        channel="Public channel where anonymous confessions appear",
        log_channel="Private staff-only channel recording confession numbers and authors",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def confessionsetup(
        self, interaction: discord.Interaction,
        channel: discord.TextChannel,
        log_channel: discord.TextChannel,
    ):
        await interaction.response.defer(ephemeral=True)
        if channel.id == log_channel.id:
            return await interaction.followup.send(
                "The public confession channel and private staff log must be different channels.", ephemeral=True
            )
        me = interaction.guild.me if interaction.guild else None
        if me:
            for target in (channel, log_channel):
                perms = target.permissions_for(me)
                if not (perms.view_channel and perms.send_messages and perms.embed_links):
                    return await interaction.followup.send(
                        f"I need View Channel, Send Messages and Embed Links in {target.mention}.",
                        ephemeral=True,
                    )
        # Administrators must make this channel staff-only using Discord permissions.
        everyone = interaction.guild.default_role
        if log_channel.permissions_for(everyone).view_channel:
            return await interaction.followup.send(
                "The moderation log must be private. Deny **View Channel** to @everyone "
                "in the log channel permissions, then try again.", ephemeral=True
            )
        try:
            await self.bot.db.execute("""
                INSERT INTO confession_settings (guild_id, channel_id, log_channel_id, enabled)
                VALUES ($1, $2, $3, TRUE)
                ON CONFLICT (guild_id) DO UPDATE SET
                    channel_id=EXCLUDED.channel_id,
                    log_channel_id=EXCLUDED.log_channel_id,
                    enabled=TRUE
            """, interaction.guild_id, channel.id, log_channel.id)
        except Exception:
            log.exception("Failed to configure confessions")
            return await interaction.followup.send("Couldn't save the configuration.", ephemeral=True)
        await interaction.followup.send(
            f"💜 Public confessions: {channel.mention}\n"
            f"🔒 Private author log: {log_channel.mention}\n"
            "Members can use `/confess`. Staff with access to the log can identify submitters.",
            ephemeral=True,
        )

    @app_commands.command(name="confessiontoggle", description="Enable or disable anonymous confessions.")
    @app_commands.describe(enabled="Whether new confessions are accepted")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def confessiontoggle(self, interaction: discord.Interaction, enabled: bool):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.bot.db.fetchrow(
                "UPDATE confession_settings SET enabled=$2 WHERE guild_id=$1 RETURNING channel_id",
                interaction.guild_id, enabled,
            )
        except Exception:
            log.exception("Failed to toggle confessions")
            return await interaction.followup.send("Couldn't update the setting.", ephemeral=True)
        if not result:
            return await interaction.followup.send("Run `/confessionsetup` first.", ephemeral=True)
        await interaction.followup.send(
            f"Confessions are now **{'enabled' if enabled else 'disabled'}**.", ephemeral=True
        )

    @app_commands.command(name="confessionstatus", description="Show anonymous confession configuration.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def confessionstatus(self, interaction: discord.Interaction):
        try:
            setting = await self._setting(interaction.guild_id)
        except Exception:
            log.exception("Failed to read confession settings")
            return await interaction.response.send_message("Couldn't load settings.", ephemeral=True)
        if not setting:
            return await interaction.response.send_message("Not configured. Use `/confessionsetup`.", ephemeral=True)
        await interaction.response.send_message(
            f"Public channel: <#{setting['channel_id']}>\n"
            f"Private author log: <#{setting['log_channel_id']}>\n"
            f"Status: **{'Enabled' if setting['enabled'] else 'Disabled'}**\n"
            f"Cooldown: **{COOLDOWN_SECONDS // 60} minutes**",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Confessions(bot))
